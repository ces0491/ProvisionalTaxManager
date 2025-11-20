from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from functools import wraps
import os
from werkzeug.utils import secure_filename
from datetime import datetime
from decimal import Decimal

from src.config import Config
from src.database.models import db, Account, Statement, Category, Transaction, ExpenseRule
from src.services.pdf_parser import BankStatementParser, detect_duplicates
from src.services.categorizer import categorize_transaction, is_inter_account_transfer, init_categories_in_db, get_category_by_name
from src.services.excel_export import generate_tax_export
from src.services.tax_calculator import calculate_tax_from_transactions

app = Flask(__name__)
app.config.from_object(Config)

# Create upload folder
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database
db.init_app(app)

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == app.config['AUTH_PASSWORD']:
            session['logged_in'] = True
            flash('Logged in successfully', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid password', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    """Dashboard showing recent statements and summary"""
    statements = Statement.query.order_by(Statement.upload_date.desc()).limit(10).all()
    total_transactions = Transaction.query.filter_by(is_deleted=False, is_duplicate=False).count()

    # Get uncategorized count
    uncategorized = Transaction.query.filter_by(
        category_id=None,
        is_deleted=False,
        is_duplicate=False
    ).count()

    return render_template('index.html',
                         statements=statements,
                         total_transactions=total_transactions,
                         uncategorized=uncategorized)


def auto_mark_duplicates():
    """
    Automatically mark 100% duplicate transactions
    Returns count of duplicates marked
    """
    # Get all non-deleted, non-duplicate transactions
    all_transactions = Transaction.query.filter_by(is_deleted=False, is_duplicate=False).all()

    trans_list = [{
        'id': t.id,
        'date': t.date,
        'description': t.description,
        'amount': float(t.amount)
    } for t in all_transactions]

    duplicate_pairs = detect_duplicates(trans_list)

    # Auto-mark only 100% matches (score == 1.0)
    marked_count = 0
    for idx1, idx2, score in duplicate_pairs:
        if score == 1.0:  # Only exact matches
            trans1 = all_transactions[idx1]
            trans2 = all_transactions[idx2]

            # Mark the second one as duplicate (keep the first)
            trans2.is_duplicate = True
            trans2.duplicate_of_id = trans1.id
            marked_count += 1

    if marked_count > 0:
        db.session.commit()

    return marked_count


@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Upload bank statement PDFs"""
    if request.method == 'POST':
        # Check if files were uploaded
        if 'files[]' not in request.files:
            flash('No files uploaded', 'error')
            return redirect(request.url)

        files = request.files.getlist('files[]')

        for file in files:
            if file and file.filename.endswith('.pdf'):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

                try:
                    # Parse the PDF
                    parser = BankStatementParser(filepath)
                    result = parser.parse()

                    # Get or create account
                    account = Account.query.filter_by(
                        account_number=result['account_number']
                    ).first()

                    if not account:
                        account = Account(
                            name=f"{result['account_type'].title()} Account",
                            account_type=result['account_type'],
                            account_number=result['account_number']
                        )
                        db.session.add(account)
                        db.session.flush()

                    # Create statement record
                    statement = Statement(
                        account_id=account.id,
                        start_date=result['start_date'],
                        end_date=result['end_date'],
                        filename=filename
                    )
                    db.session.add(statement)
                    db.session.flush()

                    # Add transactions
                    for trans_data in result['transactions']:
                        # Categorize
                        cat_key, confidence = categorize_transaction(
                            trans_data['description'],
                            trans_data['amount']
                        )

                        category = None
                        if cat_key:
                            cat_name = None
                            from src.services.categorizer import CATEGORIES
                            if cat_key in CATEGORIES:
                                cat_name = CATEGORIES[cat_key]['name']
                                category = get_category_by_name(db, Category, cat_name)

                        # Skip inter-account transfers for income tracking
                        skip_income = False
                        if is_inter_account_transfer(trans_data['description']):
                            skip_income = True

                        transaction = Transaction(
                            statement_id=statement.id,
                            date=trans_data['date'],
                            description=trans_data['description'],
                            amount=trans_data['amount'],
                            category_id=category.id if category else None,
                            notes='Skipped: inter-account transfer' if skip_income else None
                        )
                        db.session.add(transaction)

                    db.session.commit()

                    # Auto-mark 100% duplicates
                    auto_marked = auto_mark_duplicates()

                    success_msg = f'Successfully uploaded and parsed {filename}'
                    if auto_marked > 0:
                        success_msg += f' ({auto_marked} duplicate{"s" if auto_marked != 1 else ""} auto-marked)'
                    flash(success_msg, 'success')

                except Exception as e:
                    db.session.rollback()
                    flash(f'Error parsing {filename}: {str(e)}', 'error')

        return redirect(url_for('transactions'))

    return render_template('upload.html')


@app.route('/transactions')
@login_required
def transactions():
    """View all transactions with filtering"""
    page = request.args.get('page', 1, type=int)
    per_page = 50

    query = Transaction.query.filter_by(is_deleted=False, is_duplicate=False)

    # Filters
    category_id = request.args.get('category_id', type=int)
    if category_id:
        query = query.filter_by(category_id=category_id)

    start_date = request.args.get('start_date')
    if start_date:
        query = query.filter(Transaction.date >= datetime.strptime(start_date, '%Y-%m-%d').date())

    end_date = request.args.get('end_date')
    if end_date:
        query = query.filter(Transaction.date <= datetime.strptime(end_date, '%Y-%m-%d').date())

    transactions = query.order_by(Transaction.date.desc()).paginate(page=page, per_page=per_page)
    categories = Category.query.all()

    return render_template('transactions.html',
                         transactions=transactions,
                         categories=categories)


@app.route('/transaction/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_transaction(id):
    """Edit a transaction"""
    transaction = Transaction.query.get_or_404(id)

    if request.method == 'POST':
        transaction.description = request.form.get('description')
        transaction.amount = request.form.get('amount', type=float)
        transaction.category_id = request.form.get('category_id', type=int) or None
        transaction.notes = request.form.get('notes')
        transaction.is_manual = True

        db.session.commit()
        flash('Transaction updated successfully', 'success')
        return redirect(url_for('transactions'))

    categories = Category.query.all()
    return render_template('edit_transaction.html',
                         transaction=transaction,
                         categories=categories)


@app.route('/transaction/<int:id>/delete', methods=['POST'])
@login_required
def delete_transaction(id):
    """Soft delete a transaction"""
    transaction = Transaction.query.get_or_404(id)
    transaction.is_deleted = True
    db.session.commit()
    flash('Transaction deleted', 'success')
    return redirect(url_for('transactions'))


@app.route('/transaction/add', methods=['GET', 'POST'])
@login_required
def add_transaction():
    """Add a manual transaction"""
    if request.method == 'POST':
        # Get the first statement or create a placeholder
        statement = Statement.query.first()
        if not statement:
            # Create a placeholder account and statement for manual entries
            account = Account.query.filter_by(name='Manual Entries').first()
            if not account:
                account = Account(
                    name='Manual Entries',
                    account_type='manual',
                    account_number='MANUAL'
                )
                db.session.add(account)
                db.session.flush()

            statement = Statement(
                account_id=account.id,
                start_date=datetime(2025, 1, 1).date(),
                end_date=datetime(2025, 12, 31).date(),
                filename='manual_entries.txt'
            )
            db.session.add(statement)
            db.session.flush()

        # Create transaction
        transaction = Transaction(
            statement_id=statement.id,
            date=datetime.strptime(request.form.get('date'), '%Y-%m-%d').date(),
            description=request.form.get('description'),
            amount=Decimal(request.form.get('amount', '0')),
            category_id=request.form.get('category_id', type=int) or None,
            notes=request.form.get('notes'),
            is_manual=True
        )

        db.session.add(transaction)
        db.session.commit()
        flash('Manual transaction added successfully', 'success')
        return redirect(url_for('transactions'))

    categories = Category.query.all()
    return render_template('add_transaction.html', categories=categories)


@app.route('/transaction/<int:id>/split', methods=['GET', 'POST'])
@login_required
def split_transaction(id):
    """Split a transaction into business and personal portions"""
    parent = Transaction.query.get_or_404(id)

    if request.method == 'POST':
        business_amount = Decimal(request.form.get('business_amount', '0'))
        personal_amount = Decimal(request.form.get('personal_amount', '0'))
        business_category_id = request.form.get('business_category_id', type=int)
        personal_category_id = request.form.get('personal_category_id', type=int)
        business_notes = request.form.get('business_notes', '')
        personal_notes = request.form.get('personal_notes', '')

        # Validate amounts
        total = business_amount + personal_amount
        if abs(total - abs(parent.amount)) > Decimal('0.01'):
            flash(
                f'Split amounts (R{total}) must equal original amount '
                f'(R{abs(parent.amount)})',
                'error'
            )
            categories = Category.query.all()
            return render_template(
                'split_transaction.html',
                transaction=parent,
                categories=categories
            )

        # Mark original as deleted (it's being replaced by splits)
        parent.is_deleted = True

        # Create business portion
        if business_amount > 0:
            business_trans = Transaction(
                statement_id=parent.statement_id,
                date=parent.date,
                description=f"{parent.description} (Business portion)",
                amount=-business_amount,  # Negative for expense
                category_id=business_category_id,
                is_manual=True,
                notes=business_notes,
                original_amount=parent.amount,
                parent_transaction_id=parent.id
            )
            db.session.add(business_trans)

        # Create personal portion
        if personal_amount > 0:
            personal_trans = Transaction(
                statement_id=parent.statement_id,
                date=parent.date,
                description=f"{parent.description} (Personal portion)",
                amount=-personal_amount,  # Negative for expense
                category_id=personal_category_id,
                is_manual=True,
                notes=personal_notes,
                original_amount=parent.amount,
                parent_transaction_id=parent.id
            )
            db.session.add(personal_trans)

        db.session.commit()
        flash('Transaction split successfully', 'success')
        return redirect(url_for('transactions'))

    categories = Category.query.all()
    return render_template(
        'split_transaction.html',
        transaction=parent,
        categories=categories
    )


@app.route('/export')
@login_required
def export():
    """Export tax report to Excel"""
    # Get tax period from request
    period_type = request.args.get('period', 'first')  # first or second
    year = request.args.get('year', datetime.now().year, type=int)

    # Determine date range
    if period_type == 'first':
        start_date = datetime(year, 3, 1).date()
        end_date = datetime(year, 8, 31).date()
        filename = f'PnLMarAugforAug{year}.xlsx'
    else:
        start_date = datetime(year, 9, 1).date()
        end_date = datetime(year + 1, 2, 28).date()  # TODO: Handle leap years
        filename = f'PnLSepFebforFeb{year + 1}.xlsx'

    # Generate Excel file
    try:
        output_path = generate_tax_export(db, Transaction, Category, start_date, end_date, filename)
        return send_file(output_path, as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f'Error generating export: {str(e)}', 'error')
        return redirect(url_for('index'))


@app.route('/duplicates')
@login_required
def duplicates():
    """View potential duplicate transactions"""
    # Find duplicates - only among active (non-duplicate) transactions
    all_transactions = Transaction.query.filter_by(is_deleted=False, is_duplicate=False).all()

    trans_list = [{
        'id': t.id,
        'date': t.date,
        'description': t.description,
        'amount': float(t.amount)
    } for t in all_transactions]

    duplicate_pairs = detect_duplicates(trans_list)

    # Get actual transaction objects
    duplicates_data = []
    for idx1, idx2, score in duplicate_pairs:
        trans1 = all_transactions[idx1]
        trans2 = all_transactions[idx2]
        duplicates_data.append({
            'trans1': trans1,
            'trans2': trans2,
            'score': score
        })

    return render_template('duplicates.html', duplicates=duplicates_data)


@app.route('/api/mark_duplicate', methods=['POST'])
@login_required
def mark_duplicate():
    """Mark a transaction as duplicate"""
    data = request.get_json()
    trans_id = data.get('transaction_id')
    duplicate_of_id = data.get('duplicate_of_id')

    transaction = Transaction.query.get(trans_id)
    if transaction:
        transaction.is_duplicate = True
        transaction.duplicate_of_id = duplicate_of_id
        db.session.commit()
        return jsonify({'success': True})

    return jsonify({'success': False, 'error': 'Transaction not found'}), 404


@app.route('/api/auto_mark_duplicates', methods=['POST'])
@login_required
def auto_mark_all_duplicates():
    """Automatically mark all 100% duplicate transactions"""
    try:
        count = auto_mark_duplicates()
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/tax_calculator')
@login_required
def tax_calculator():
    """Tax calculator page"""
    return render_template('tax_calculator.html')


@app.route('/api/calculate_tax', methods=['POST'])
@login_required
def calculate_tax():
    """Calculate tax based on filters and parameters"""
    data = request.get_json()

    # Get filter parameters
    start_date_str = data.get('start_date')
    end_date_str = data.get('end_date')
    age = int(data.get('age', 0))
    medical_aid_members = int(data.get('medical_aid_members', 0))
    previous_payments = Decimal(data.get('previous_payments', '0'))

    # Parse dates
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return jsonify({
            'success': False,
            'error': 'Invalid date format'
        }), 400

    # Get transactions in date range
    transactions = Transaction.query.filter(
        Transaction.is_deleted == False,  # noqa: E712
        Transaction.is_duplicate == False,  # noqa: E712
        Transaction.date >= start_date,
        Transaction.date <= end_date
    ).all()

    # Convert to list of dicts
    trans_list = []
    for t in transactions:
        category_name = t.category.name if t.category else 'Uncategorized'
        trans_list.append({
            'id': t.id,
            'date': t.date,
            'description': t.description,
            'amount': t.amount,
            'category': category_name
        })

    # Calculate tax (pass db session for loading tax tables from database)
    tax_result = calculate_tax_from_transactions(
        transactions=trans_list,
        period_start=start_date,
        period_end=end_date,
        age=age,
        medical_aid_members=medical_aid_members,
        previous_payments=previous_payments,
        db_session=db.session
    )

    # Convert Decimals to strings for JSON serialization
    result = {
        'success': True,
        'calculation': {
            'period_months': tax_result['period_months'],
            'period_income': str(tax_result['period_income']),
            'period_expenses': str(tax_result['period_expenses']),
            'period_profit': str(tax_result['period_profit']),
            'annual_estimate': str(tax_result['annual_estimate']),
            'estimated_annual_tax': str(tax_result['estimated_annual_tax']),
            'previous_payments': str(tax_result['previous_payments']),
            'provisional_payment': str(tax_result['provisional_payment']),
            'effective_rate': str(tax_result['effective_rate']),
            'tax_breakdown': {
                'taxable_income': str(tax_result['tax_breakdown']['taxable_income']),
                'tax_before_rebates': str(
                    tax_result['tax_breakdown']['tax_before_rebates']
                ),
                'rebates': str(tax_result['tax_breakdown']['rebates']),
                'medical_credits': str(
                    tax_result['tax_breakdown']['medical_credits']
                ),
                'tax_liability': str(tax_result['tax_breakdown']['tax_liability']),
                'effective_rate': str(tax_result['tax_breakdown']['effective_rate']),
                'age': tax_result['tax_breakdown']['age'],
                'medical_aid_members': tax_result['tax_breakdown']['medical_aid_members'],
            },
            'expense_breakdown': {
                k: str(v) for k, v in tax_result['expense_breakdown'].items()
            }
        },
        'transaction_count': len(trans_list)
    }

    return jsonify(result)


@app.route('/income_sources')
@login_required
def income_sources():
    """Manage income sources and categorization rules"""
    # Get income category
    income_category = Category.query.filter_by(name='Income').first()

    if income_category:
        # Get all rules for income category
        income_rules = ExpenseRule.query.filter_by(
            category_id=income_category.id
        ).order_by(ExpenseRule.priority.desc()).all()
    else:
        income_rules = []

    # Get all categories for adding new rules
    all_categories = Category.query.order_by(Category.name).all()

    # Get all rules for display
    all_rules = ExpenseRule.query.order_by(
        ExpenseRule.priority.desc(),
        ExpenseRule.pattern
    ).all()

    return render_template(
        'income_sources.html',
        income_rules=income_rules,
        all_rules=all_rules,
        categories=all_categories,
        income_category=income_category
    )


@app.route('/api/income_source/add', methods=['POST'])
@login_required
def add_income_source():
    """Add a new income source pattern"""
    data = request.get_json()

    pattern = data.get('pattern', '').strip()
    category_id = int(data.get('category_id', 0)) if data.get('category_id') else None
    is_regex = data.get('is_regex', False)
    priority = int(data.get('priority', 0))

    if not pattern:
        return jsonify({'success': False, 'error': 'Pattern is required'}), 400

    if not category_id:
        return jsonify({'success': False, 'error': 'Category is required'}), 400

    # Create rule
    rule = ExpenseRule(
        pattern=pattern,
        category_id=category_id,
        is_regex=is_regex,
        priority=priority,
        is_active=True
    )

    db.session.add(rule)
    db.session.commit()

    return jsonify({
        'success': True,
        'rule_id': rule.id,
        'message': 'Income source added successfully'
    })


@app.route('/api/income_source/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_income_source(id):
    """Toggle active status of an income source"""
    rule = ExpenseRule.query.get_or_404(id)
    rule.is_active = not rule.is_active
    db.session.commit()

    return jsonify({
        'success': True,
        'is_active': rule.is_active
    })


@app.route('/api/income_source/<int:id>/delete', methods=['POST'])
@login_required
def delete_income_source(id):
    """Delete an income source pattern"""
    rule = ExpenseRule.query.get_or_404(id)
    db.session.delete(rule)
    db.session.commit()

    return jsonify({'success': True})


@app.cli.command()
def init_db():
    """Initialize the database"""
    db.create_all()
    init_categories_in_db(db, Category)
    print("Database initialized!")


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        init_categories_in_db(db, Category)
    app.run(debug=True)
