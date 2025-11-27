"""
Pytest configuration and fixtures
"""
import pytest
import os
import sys
from datetime import date
from decimal import Decimal

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app as flask_app
from src.database.models import db, Account, Statement, Category, Transaction, ExpenseRule
from src.config import Config


class TestConfig(Config):
    """Test configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    AUTH_PASSWORD = 'test123'


@pytest.fixture(scope='function')
def app():
    """Create and configure a test Flask application"""
    # Force new configuration for each test
    flask_app.config.from_object(TestConfig)

    # Ensure we have a clean database for each test
    with flask_app.app_context():
        # Drop all tables first to ensure clean state
        db.drop_all()
        db.create_all()
        _seed_test_data()
        yield flask_app
        # Clean up after test
        db.session.rollback()
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create a test client for the Flask application"""
    return app.test_client()


@pytest.fixture
def authenticated_client(client):
    """Create an authenticated test client"""
    # Log in
    client.post('/login', data={'password': 'test123'}, follow_redirects=True)
    return client


@pytest.fixture
def db_session(app):
    """Create a database session for testing"""
    with app.app_context():
        yield db.session


def _seed_test_data():
    """Seed the test database with initial data"""
    # Create categories
    income_cat = Category(
        name='Income',
        category_type='income',
        description='Income from all sources'
    )
    tech_cat = Category(
        name='Technology/Software',
        category_type='business_expense',
        description='Technology and software expenses'
    )
    personal_cat = Category(
        name='Personal',
        category_type='personal_expense',
        description='Personal expenses'
    )

    db.session.add_all([income_cat, tech_cat, personal_cat])
    db.session.flush()

    # Create expense rules
    income_rule = ExpenseRule(
        pattern='PRECISE DIGITAL',
        category_id=income_cat.id,
        priority=100,
        is_regex=False,
        is_active=True
    )
    tech_rule = ExpenseRule(
        pattern='CLAUDE.AI',
        category_id=tech_cat.id,
        priority=90,
        is_regex=False,
        is_active=True
    )

    db.session.add_all([income_rule, tech_rule])

    # Create test account
    account = Account(
        name='Test Account',
        account_type='cheques',
        account_number='12345'
    )
    db.session.add(account)
    db.session.flush()

    # Create test statement
    statement = Statement(
        account_id=account.id,
        start_date=date(2025, 3, 1),
        end_date=date(2025, 3, 31),
        filename='test_statement.pdf'
    )
    db.session.add(statement)
    db.session.flush()

    # Create test transactions
    transactions = [
        Transaction(
            statement_id=statement.id,
            date=date(2025, 3, 15),
            description='PRECISE DIGITAIT25091ZA0799010',
            amount=Decimal('10000.00'),
            category_id=income_cat.id
        ),
        Transaction(
            statement_id=statement.id,
            date=date(2025, 3, 20),
            description='CLAUDE.AI SUBSCRIPTION',
            amount=Decimal('-99.00'),
            category_id=tech_cat.id
        ),
        Transaction(
            statement_id=statement.id,
            date=date(2025, 3, 25),
            description='NETFLIX.COM',
            amount=Decimal('-15.99'),
            category_id=personal_cat.id
        ),
    ]
    db.session.add_all(transactions)

    db.session.commit()


@pytest.fixture
def sample_transactions():
    """Sample transactions for testing - includes category_type for tax calculation"""
    return [
        {
            'date': date(2025, 3, 1),
            'description': 'PRECISE DIGITAL PAYMENT',
            'amount': Decimal('10000.00'),
            'category': 'Income',
            'category_type': 'income'
        },
        {
            'date': date(2025, 3, 15),
            'description': 'CLAUDE.AI SUBSCRIPTION',
            'amount': Decimal('-99.00'),
            'category': 'Technology/Software',
            'category_type': 'business_expense'
        },
        {
            'date': date(2025, 3, 20),
            'description': 'SYSTEM INTEREST DEBIT',
            'amount': Decimal('-5000.00'),
            'category': 'Interest (Mortgage)',
            'category_type': 'business_expense'
        },
    ]
