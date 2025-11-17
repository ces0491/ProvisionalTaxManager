from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from functools import wraps
import os
from werkzeug.utils import secure_filename
from datetime import datetime

from config import Config
from models import db, Account, Statement, Category, Transaction
from pdf_parser import BankStatementParser, detect_duplicates
from categorizer import categorize_transaction, is_inter_account_transfer, init_categories_in_db, get_category_by_name
from excel_export import generate_tax_export

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
                            from categorizer import CATEGORIES
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
                    flash(f'Successfully uploaded and parsed {filename}', 'success')

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
    # Find duplicates
    all_transactions = Transaction.query.filter_by(is_deleted=False).all()

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
