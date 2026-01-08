from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from functools import wraps
import os
import shutil
import tempfile
import zipfile
from werkzeug.utils import secure_filename
from datetime import datetime
from decimal import Decimal

from src.config import Config
from src.database.models import db, Account, Statement, Category, Transaction, ExpenseRule, Receipt, DismissedDuplicate
from src.services.pdf_parser import BankStatementParser, detect_duplicates
from src.services.categorizer import categorize_transaction, is_inter_account_transfer, init_categories_in_db, get_category_by_name
from src.services.excel_export import generate_tax_export
from src.services.tax_calculator import calculate_tax_from_transactions
from src.services.reports import aggregate_transactions, get_available_years, get_transactions_for_year, MONTHS

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


@app.route('/reports')
@login_required
def reports():
    """Financial reports - income and expenses by month and category"""
    selected_year = request.args.get('year', datetime.now().year, type=int)
    years = get_available_years(db.session, Transaction)
    transactions = get_transactions_for_year(Transaction, selected_year)

    report_data = aggregate_transactions(transactions, tax_year=selected_year)

    return render_template('reports.html',
                          selected_year=selected_year,
                          years=years,
                          monthly_summary=report_data['monthly_summary'],
                          totals=type('obj', (object,), report_data['totals'])(),
                          category_summary=report_data['category_summary'],
                          detailed_monthly=report_data['detailed_monthly'],
                          months=report_data['months'])


def auto_mark_duplicates():
    """
    Automatically mark duplicate transactions.
    - 100% matches: always mark as duplicate
    - 80% matches: mark if from same account (different statement formats)
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

    marked_count = 0
    for idx1, idx2, score in duplicate_pairs:
        trans1 = all_transactions[idx1]
        trans2 = all_transactions[idx2]

        should_mark = False

        if score == 1.0:
            # Exact match - always mark
            should_mark = True
        elif score >= 0.8:
            # Partial match - mark if same account (likely different statement format)
            if trans1.statement.account_id == trans2.statement.account_id:
                should_mark = True

        if should_mark:
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
                        # Categorize - returns category name directly
                        cat_name, confidence = categorize_transaction(
                            trans_data['description'],
                            trans_data['amount']
                        )

                        category = None
                        if cat_name:
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
    categories = Category.query.order_by(Category.name).all()

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

        # Preserve filter parameters when redirecting back
        category_id = request.form.get('filter_category_id')
        start_date = request.form.get('filter_start_date')
        end_date = request.form.get('filter_end_date')
        page = request.form.get('filter_page', 1)

        return redirect(url_for('transactions',
                               category_id=category_id if category_id else None,
                               start_date=start_date if start_date else None,
                               end_date=end_date if end_date else None,
                               page=page))

    categories = Category.query.order_by(Category.name).all()

    # Get filter parameters from query string to pass to template
    filter_params = {
        'category_id': request.args.get('category_id', ''),
        'start_date': request.args.get('start_date', ''),
        'end_date': request.args.get('end_date', ''),
        'page': request.args.get('page', 1)
    }

    return render_template('edit_transaction.html',
                         transaction=transaction,
                         categories=categories,
                         filter_params=filter_params)


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

    categories = Category.query.order_by(Category.name).all()
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
            categories = Category.query.order_by(Category.name).all()
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

        # Preserve filter parameters when redirecting back
        category_id = request.form.get('filter_category_id')
        start_date = request.form.get('filter_start_date')
        end_date = request.form.get('filter_end_date')
        page = request.form.get('filter_page', 1)

        return redirect(url_for('transactions',
                               category_id=category_id if category_id else None,
                               start_date=start_date if start_date else None,
                               end_date=end_date if end_date else None,
                               page=page))

    categories = Category.query.order_by(Category.name).all()

    # Get filter parameters from query string to pass to template
    filter_params = {
        'category_id': request.args.get('category_id', ''),
        'start_date': request.args.get('start_date', ''),
        'end_date': request.args.get('end_date', ''),
        'page': request.args.get('page', 1)
    }

    return render_template(
        'split_transaction.html',
        transaction=parent,
        categories=categories,
        filter_params=filter_params
    )


# Receipt routes
@app.route('/transaction/<int:id>/receipts')
@login_required
def transaction_receipts(id):
    """View receipts for a transaction"""
    transaction = Transaction.query.get_or_404(id)
    return render_template('receipts.html', transaction=transaction)


@app.route('/transaction/<int:id>/receipt/add', methods=['GET', 'POST'])
@login_required
def add_receipt(id):
    """Attach a receipt to a transaction"""
    transaction = Transaction.query.get_or_404(id)

    if request.method == 'POST':
        file_path = request.form.get('file_path', '').strip()
        description = request.form.get('description', '').strip()

        if not file_path:
            flash('Please provide a file path', 'error')
            return render_template('add_receipt.html', transaction=transaction)

        # Normalize path
        file_path = os.path.normpath(file_path)

        # Validate file exists
        if not os.path.exists(file_path):
            flash(f'File not found: {file_path}', 'error')
            return render_template('add_receipt.html', transaction=transaction)

        # Extract filename and type
        filename = os.path.basename(file_path)
        file_type = os.path.splitext(filename)[1].lower().lstrip('.')

        receipt = Receipt(
            transaction_id=transaction.id,
            file_path=file_path,
            filename=filename,
            file_type=file_type,
            description=description
        )
        db.session.add(receipt)
        db.session.commit()

        flash(f'Receipt "{filename}" attached successfully', 'success')
        return redirect(url_for('edit_transaction', id=transaction.id))

    return render_template('add_receipt.html', transaction=transaction)


@app.route('/receipt/<int:id>/view')
@login_required
def view_receipt(id):
    """View/download a receipt file"""
    receipt = Receipt.query.get_or_404(id)

    if not os.path.exists(receipt.file_path):
        flash(f'Receipt file not found: {receipt.file_path}', 'error')
        return redirect(url_for('edit_transaction', id=receipt.transaction_id))

    return send_file(receipt.file_path, as_attachment=False)


@app.route('/receipt/<int:id>/delete', methods=['POST'])
@login_required
def delete_receipt(id):
    """Remove a receipt attachment (doesn't delete the file)"""
    receipt = Receipt.query.get_or_404(id)
    transaction_id = receipt.transaction_id

    db.session.delete(receipt)
    db.session.commit()

    flash('Receipt removed', 'success')
    return redirect(url_for('edit_transaction', id=transaction_id))


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


@app.route('/export/receipts')
@login_required
def export_receipts():
    """Export all receipts for a period as a ZIP file with an index"""
    period_type = request.args.get('period', 'first')
    year = request.args.get('year', datetime.now().year, type=int)

    # Determine date range
    if period_type == 'first':
        start_date = datetime(year, 3, 1).date()
        end_date = datetime(year, 8, 31).date()
        period_name = f'Mar-Aug_{year}'
    else:
        start_date = datetime(year, 9, 1).date()
        end_date = datetime(year + 1, 2, 28).date()
        period_name = f'Sep_{year}-Feb_{year + 1}'

    # Get all transactions with receipts in this period
    transactions = Transaction.query.filter(
        Transaction.date >= start_date,
        Transaction.date <= end_date,
        Transaction.is_deleted == False
    ).all()

    receipts_to_export = []
    for trans in transactions:
        for receipt in trans.receipts:
            if os.path.exists(receipt.file_path):
                receipts_to_export.append({
                    'receipt': receipt,
                    'transaction': trans
                })

    if not receipts_to_export:
        flash('No receipts found for this period', 'warning')
        return redirect(url_for('index'))

    # Create ZIP file
    temp_dir = tempfile.mkdtemp()
    zip_filename = f'Receipts_{period_name}.zip'
    zip_path = os.path.join(temp_dir, zip_filename)

    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Create index CSV
            index_lines = ['Date,Description,Amount,Category,Receipt Filename']

            for i, item in enumerate(receipts_to_export, 1):
                receipt = item['receipt']
                trans = item['transaction']

                # Create unique filename in zip
                ext = os.path.splitext(receipt.filename)[1]
                zip_name = f"{trans.date.strftime('%Y%m%d')}_{i:03d}_{secure_filename(trans.description[:30])}{ext}"

                # Add file to zip
                zipf.write(receipt.file_path, zip_name)

                # Add to index
                cat_name = trans.category.name if trans.category else 'Uncategorized'
                index_lines.append(
                    f'{trans.date},{trans.description[:50]},{trans.amount},{cat_name},{zip_name}'
                )

            # Add index to zip
            zipf.writestr('_index.csv', '\n'.join(index_lines))

        return send_file(zip_path, as_attachment=True, download_name=zip_filename)
    except Exception as e:
        flash(f'Error exporting receipts: {str(e)}', 'error')
        return redirect(url_for('index'))
    finally:
        # Cleanup temp dir after a delay (let send_file complete)
        pass  # Flask handles cleanup of temp files


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

    # Get dismissed pairs to filter them out
    dismissed = DismissedDuplicate.query.all()
    dismissed_set = set()
    for d in dismissed:
        # Store both orderings
        dismissed_set.add((d.transaction1_id, d.transaction2_id))
        dismissed_set.add((d.transaction2_id, d.transaction1_id))

    # Get actual transaction objects, filtering out dismissed pairs
    duplicates_data = []
    for idx1, idx2, score in duplicate_pairs:
        trans1 = all_transactions[idx1]
        trans2 = all_transactions[idx2]

        # Skip if this pair was dismissed
        if (trans1.id, trans2.id) in dismissed_set:
            continue

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
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data received'}), 400

        trans_id = data.get('transaction_id')
        duplicate_of_id = data.get('duplicate_of_id')

        if not trans_id:
            return jsonify({'success': False, 'error': 'Missing transaction_id'}), 400

        transaction = Transaction.query.get(trans_id)
        if not transaction:
            return jsonify({'success': False, 'error': f'Transaction {trans_id} not found'}), 404

        transaction.is_duplicate = True
        transaction.duplicate_of_id = duplicate_of_id
        db.session.commit()

        # Verify the change was saved
        db.session.refresh(transaction)
        if transaction.is_duplicate:
            return jsonify({
                'success': True,
                'message': f'Transaction {trans_id} marked as duplicate of {duplicate_of_id}'
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to save changes'}), 500

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auto_mark_duplicates', methods=['POST'])
@login_required
def auto_mark_all_duplicates():
    """Automatically mark all 100% duplicate transactions"""
    try:
        count = auto_mark_duplicates()
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/dismiss_duplicate', methods=['POST'])
@login_required
def dismiss_duplicate():
    """Dismiss a duplicate pair (mark as 'not a duplicate')"""
    data = request.get_json()
    trans1_id = data.get('transaction1_id')
    trans2_id = data.get('transaction2_id')

    if not trans1_id or not trans2_id:
        return jsonify({'success': False, 'error': 'Both transaction IDs required'}), 400

    # Check if already dismissed
    existing = DismissedDuplicate.query.filter(
        ((DismissedDuplicate.transaction1_id == trans1_id) & (DismissedDuplicate.transaction2_id == trans2_id)) |
        ((DismissedDuplicate.transaction1_id == trans2_id) & (DismissedDuplicate.transaction2_id == trans1_id))
    ).first()

    if not existing:
        dismissed = DismissedDuplicate(
            transaction1_id=trans1_id,
            transaction2_id=trans2_id
        )
        db.session.add(dismissed)
        db.session.commit()

    return jsonify({'success': True})


@app.route('/api/bulk_update_category', methods=['POST'])
@login_required
def bulk_update_category():
    """Bulk update category for multiple transactions"""
    data = request.get_json()
    transaction_ids = data.get('transaction_ids', [])
    category_id = data.get('category_id')

    if not transaction_ids:
        return jsonify({'success': False, 'error': 'No transactions selected'}), 400

    if not category_id:
        return jsonify({'success': False, 'error': 'No category selected'}), 400

    try:
        count = Transaction.query.filter(
            Transaction.id.in_(transaction_ids)
        ).update({
            Transaction.category_id: category_id,
            Transaction.is_manual: True
        }, synchronize_session=False)

        db.session.commit()
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bulk_delete', methods=['POST'])
@login_required
def bulk_delete():
    """Bulk soft-delete multiple transactions"""
    data = request.get_json()
    transaction_ids = data.get('transaction_ids', [])

    if not transaction_ids:
        return jsonify({'success': False, 'error': 'No transactions selected'}), 400

    try:
        count = Transaction.query.filter(
            Transaction.id.in_(transaction_ids)
        ).update({
            Transaction.is_deleted: True
        }, synchronize_session=False)

        db.session.commit()
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        db.session.rollback()
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

    # Home office parameters (optional - uses defaults if not provided)
    home_office_sqm = data.get('home_office_sqm')
    house_total_sqm = data.get('house_total_sqm')
    if home_office_sqm is not None:
        home_office_sqm = Decimal(str(home_office_sqm))
    if house_total_sqm is not None:
        house_total_sqm = Decimal(str(house_total_sqm))

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

    # Convert to list of dicts with category_type for proper classification
    trans_list = []
    for t in transactions:
        category_name = t.category.name if t.category else 'Uncategorized'
        category_type = t.category.category_type if t.category else 'personal_expense'
        trans_list.append({
            'id': t.id,
            'date': t.date,
            'description': t.description,
            'amount': t.amount,
            'category': category_name,
            'category_type': category_type
        })

    # Calculate tax (pass db session for loading tax tables from database)
    tax_result = calculate_tax_from_transactions(
        transactions=trans_list,
        period_start=start_date,
        period_end=end_date,
        age=age,
        medical_aid_members=medical_aid_members,
        previous_payments=previous_payments,
        db_session=db.session,
        home_office_sqm=home_office_sqm,
        house_total_sqm=house_total_sqm
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
            'tax_year': tax_result['tax_year'],
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
            # Breakdowns by category type for transparency
            'income_breakdown': {
                k: str(v) for k, v in tax_result['income_breakdown'].items()
            },
            'expense_breakdown': {
                k: str(v) for k, v in tax_result['expense_breakdown'].items()
            },
            'personal_breakdown': {
                k: str(v) for k, v in tax_result['personal_breakdown'].items()
            },
            'excluded_breakdown': {
                k: str(v) for k, v in tax_result['excluded_breakdown'].items()
            },
            # Totals for transparency
            'total_personal_expenses': str(tax_result['total_personal_expenses']),
            'total_excluded': str(tax_result['total_excluded']),
            # Transaction counts
            'transaction_counts': tax_result['transaction_counts'],
            # Home office apportionment
            'home_office': {
                'office_sqm': str(tax_result['home_office']['office_sqm']),
                'house_sqm': str(tax_result['home_office']['house_sqm']),
                'percentage': tax_result['home_office']['percentage'],
                'apportioned_categories': tax_result['home_office']['apportioned_categories'],
                'total_reduction': str(tax_result['home_office']['total_reduction']),
                'detail': {
                    cat: {
                        'full': str(vals['full']),
                        'apportioned': str(vals['apportioned']),
                        'reduction': str(vals['reduction'])
                    }
                    for cat, vals in tax_result['home_office']['detail'].items()
                }
            },
            # Full expense breakdown before apportionment
            'expense_breakdown_full': {
                k: str(v) for k, v in tax_result['expense_breakdown_full'].items()
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
