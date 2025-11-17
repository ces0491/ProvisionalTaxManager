from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Account(db.Model):  # type: ignore[name-defined]
    """Bank accounts (cheques, credit card, mortgage)"""
    __tablename__ = 'accounts'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # e.g., "Signature Account"
    account_type = db.Column(db.String(50), nullable=False)  # cheques, credit_card, mortgage
    account_number = db.Column(db.String(50))

    statements = db.relationship('Statement', backref='account', lazy=True, cascade='all, delete-orphan')

class Statement(db.Model):  # type: ignore[name-defined]
    """Uploaded bank statements"""
    __tablename__ = 'statements'

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)

    transactions = db.relationship('Transaction', backref='statement', lazy=True, cascade='all, delete-orphan')

class Category(db.Model):  # type: ignore[name-defined]
    """Expense/income categories"""
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    category_type = db.Column(db.String(50), nullable=False)  # income, business_expense, personal_expense
    description = db.Column(db.Text)

    transactions = db.relationship('Transaction', backref='category', lazy=True)
    rules = db.relationship('ExpenseRule', backref='category', lazy=True, cascade='all, delete-orphan')

class Transaction(db.Model):  # type: ignore[name-defined]
    """Individual bank transactions"""
    __tablename__ = 'transactions'

    id = db.Column(db.Integer, primary_key=True)
    statement_id = db.Column(db.Integer, db.ForeignKey('statements.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text, nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)  # Positive for income/deposits, negative for expenses
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))

    is_duplicate = db.Column(db.Boolean, default=False)
    duplicate_of_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)  # Soft delete
    is_manual = db.Column(db.Boolean, default=False)  # Manually added/edited
    notes = db.Column(db.Text)

    # For mixed orders (like Takealot)
    original_amount = db.Column(db.Numeric(12, 2))  # If split from a larger purchase
    parent_transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=True)

    # Relationships
    duplicate_of = db.relationship('Transaction', remote_side=[id], foreign_keys=[duplicate_of_id], backref='duplicates')
    parent_transaction = db.relationship('Transaction', remote_side=[id], foreign_keys=[parent_transaction_id], backref='split_items')

class ExpenseRule(db.Model):  # type: ignore[name-defined]
    """Pattern matching rules for auto-categorization"""
    __tablename__ = 'expense_rules'

    id = db.Column(db.Integer, primary_key=True)
    pattern = db.Column(db.String(200), nullable=False)  # String to match in description
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    priority = db.Column(db.Integer, default=0)  # Higher priority rules checked first
    is_regex = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)

class TaxPeriod(db.Model):  # type: ignore[name-defined]
    """Tax filing periods"""
    __tablename__ = 'tax_periods'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # e.g., "First Provisional 2025"
    period_type = db.Column(db.String(50), nullable=False)  # first, second
    start_date = db.Column(db.Date, nullable=False)  # Mar 1 or Sep 1
    end_date = db.Column(db.Date, nullable=False)  # Aug 31 or Feb 28/29
    due_date = db.Column(db.Date, nullable=False)  # End of Aug or Feb
    year = db.Column(db.Integer, nullable=False)
