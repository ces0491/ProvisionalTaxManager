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

    # VAT configuration for this category
    default_vat_rate = db.Column(db.String(20), default='standard')  # 'standard', 'zero', 'exempt', 'no_vat'

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

    # VAT fields
    vat_rate_type = db.Column(db.String(20))  # 'standard', 'zero', 'exempt', 'no_vat' (NULL = use category default)
    vat_amount = db.Column(db.Numeric(12, 2))  # Calculated VAT amount (NULL = calculate from amount)
    amount_incl_vat = db.Column(db.Boolean, default=True)  # Whether amount includes VAT
    is_vat_claimable = db.Column(db.Boolean, default=True)  # Can claim input VAT on this

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

class TaxYear(db.Model):  # type: ignore[name-defined]
    """Tax year configuration (e.g., 2025/2026 tax year)"""
    __tablename__ = 'tax_years'

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False, unique=True)  # 2025, 2026, etc.
    description = db.Column(db.String(100))  # e.g., "2025/2026 Tax Year"
    start_date = db.Column(db.Date, nullable=False)  # March 1
    end_date = db.Column(db.Date, nullable=False)  # February 28/29
    is_active = db.Column(db.Boolean, default=True)

    # Relationships
    brackets = db.relationship('TaxBracket', backref='tax_year', lazy=True, cascade='all, delete-orphan')
    rebates = db.relationship('TaxRebate', backref='tax_year', lazy=True, cascade='all, delete-orphan')
    medical_credits = db.relationship('MedicalAidCredit', backref='tax_year', lazy=True, cascade='all, delete-orphan')


class TaxBracket(db.Model):  # type: ignore[name-defined]
    """Income tax brackets for a specific tax year"""
    __tablename__ = 'tax_brackets'

    id = db.Column(db.Integer, primary_key=True)
    tax_year_id = db.Column(db.Integer, db.ForeignKey('tax_years.id'), nullable=False)
    min_income = db.Column(db.Numeric(12, 2), nullable=False)  # Lower bound of bracket
    max_income = db.Column(db.Numeric(12, 2))  # Upper bound (NULL = infinity)
    rate = db.Column(db.Numeric(5, 4), nullable=False)  # Tax rate (e.g., 0.18 for 18%)
    base_tax = db.Column(db.Numeric(12, 2), nullable=False)  # Base tax for this bracket
    bracket_order = db.Column(db.Integer, nullable=False)  # Order of brackets (1, 2, 3...)

    def __repr__(self):
        max_str = f"R{self.max_income:,.2f}" if self.max_income else "∞"
        return f"<TaxBracket R{self.min_income:,.2f} - {max_str} @ {self.rate*100:.0f}%>"


class TaxRebate(db.Model):  # type: ignore[name-defined]
    """Age-based tax rebates for a specific tax year"""
    __tablename__ = 'tax_rebates'

    id = db.Column(db.Integer, primary_key=True)
    tax_year_id = db.Column(db.Integer, db.ForeignKey('tax_years.id'), nullable=False)
    rebate_type = db.Column(db.String(50), nullable=False)  # 'primary', 'secondary', 'tertiary'
    min_age = db.Column(db.Integer, nullable=False)  # Minimum age for this rebate
    amount = db.Column(db.Numeric(12, 2), nullable=False)  # Annual rebate amount
    description = db.Column(db.String(200))  # e.g., "Primary rebate (all taxpayers)"

    def __repr__(self):
        return f"<TaxRebate {self.rebate_type} age {self.min_age}+ R{self.amount:,.2f}>"


class MedicalAidCredit(db.Model):  # type: ignore[name-defined]
    """Medical aid tax credits for a specific tax year"""
    __tablename__ = 'medical_aid_credits'

    id = db.Column(db.Integer, primary_key=True)
    tax_year_id = db.Column(db.Integer, db.ForeignKey('tax_years.id'), nullable=False)
    credit_type = db.Column(db.String(50), nullable=False)  # 'main', 'first_dependent', 'additional'
    monthly_amount = db.Column(db.Numeric(12, 2), nullable=False)  # Monthly credit amount
    description = db.Column(db.String(200))  # e.g., "Main member credit"

    def __repr__(self):
        return f"<MedicalAidCredit {self.credit_type} R{self.monthly_amount:,.2f}/month>"


class VATConfig(db.Model):  # type: ignore[name-defined]
    """VAT configuration - rates and settings"""
    __tablename__ = 'vat_config'

    id = db.Column(db.Integer, primary_key=True)
    effective_from = db.Column(db.Date, nullable=False)  # When this rate became effective
    effective_to = db.Column(db.Date)  # NULL if current rate
    standard_rate = db.Column(db.Numeric(5, 4), nullable=False)  # e.g., 0.15 for 15%
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)  # e.g., "Increased from 14% to 15% per Budget 2018"

    def __repr__(self):
        rate_pct = float(self.standard_rate) * 100
        return f"<VATConfig {rate_pct}% from {self.effective_from}>"
