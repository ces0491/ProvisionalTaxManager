"""
Tests for database models
"""
import pytest
from datetime import date
from decimal import Decimal

from src.database.models import Account, Statement, Category, Transaction, ExpenseRule


class TestCategory:
    """Test Category model"""

    def test_create_category(self, db_session):
        """Test creating a category"""
        category = Category(
            name='Test Category',
            category_type='business_expense',
            description='Test description'
        )
        db_session.add(category)
        db_session.commit()

        assert category.id is not None
        assert category.name == 'Test Category'

    def test_category_unique_name(self, db_session):
        """Test that category names must be unique"""
        category1 = Category(
            name='Duplicate',
            category_type='business_expense'
        )
        db_session.add(category1)
        db_session.commit()

        # Attempting to create another with same name should raise error
        category2 = Category(
            name='Duplicate',
            category_type='income'
        )
        db_session.add(category2)

        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()


class TestAccount:
    """Test Account model"""

    def test_create_account(self, db_session):
        """Test creating an account"""
        account = Account(
            name='Test Cheque Account',
            account_type='cheques',
            account_number='12345678'
        )
        db_session.add(account)
        db_session.commit()

        assert account.id is not None
        assert account.name == 'Test Cheque Account'

    def test_account_relationship_with_statements(self, db_session):
        """Test account-statement relationship"""
        account = Account(
            name='Test Account',
            account_type='cheques',
            account_number='12345'
        )
        db_session.add(account)
        db_session.flush()

        statement = Statement(
            account_id=account.id,
            start_date=date(2025, 3, 1),
            end_date=date(2025, 3, 31),
            filename='test.pdf'
        )
        db_session.add(statement)
        db_session.commit()

        assert len(account.statements) == 1
        assert account.statements[0] == statement


class TestStatement:
    """Test Statement model"""

    def test_create_statement(self, db_session):
        """Test creating a statement"""
        account = Account.query.first()

        statement = Statement(
            account_id=account.id,
            start_date=date(2025, 4, 1),
            end_date=date(2025, 4, 30),
            filename='april_statement.pdf'
        )
        db_session.add(statement)
        db_session.commit()

        assert statement.id is not None
        assert statement.start_date == date(2025, 4, 1)

    def test_statement_relationship_with_transactions(self, db_session):
        """Test statement-transaction relationship"""
        from src.database.models import Transaction

        statement = Statement.query.first()
        initial_count = len(statement.transactions)

        # Add a transaction
        transaction = Transaction(
            statement_id=statement.id,
            date=date(2025, 3, 20),
            description='Test transaction',
            amount=Decimal('-100.00')
        )
        db_session.add(transaction)
        db_session.commit()

        assert len(statement.transactions) == initial_count + 1


class TestTransaction:
    """Test Transaction model"""

    def test_create_transaction(self, db_session):
        """Test creating a transaction"""
        statement = Statement.query.first()
        category = Category.query.first()

        transaction = Transaction(
            statement_id=statement.id,
            date=date(2025, 3, 25),
            description='Test purchase',
            amount=Decimal('-250.00'),
            category_id=category.id
        )
        db_session.add(transaction)
        db_session.commit()

        assert transaction.id is not None
        assert transaction.amount == Decimal('-250.00')

    def test_transaction_soft_delete(self, db_session):
        """Test soft delete of transaction"""
        transaction = Transaction.query.first()
        transaction.is_deleted = True
        db_session.commit()

        # Transaction still exists in database
        trans = Transaction.query.get(transaction.id)
        assert trans is not None
        assert trans.is_deleted is True

    def test_transaction_manual_flag(self, db_session):
        """Test manual transaction flag"""
        statement = Statement.query.first()

        transaction = Transaction(
            statement_id=statement.id,
            date=date(2025, 3, 30),
            description='Manual entry',
            amount=Decimal('-50.00'),
            is_manual=True
        )
        db_session.add(transaction)
        db_session.commit()

        assert transaction.is_manual is True

    def test_transaction_duplicate_relationship(self, db_session):
        """Test duplicate transaction relationship"""
        trans1 = Transaction.query.first()
        trans2 = Transaction.query.offset(1).first()

        if trans1 and trans2:
            # Mark trans2 as duplicate of trans1
            trans2.is_duplicate = True
            trans2.duplicate_of_id = trans1.id
            db_session.commit()

            assert trans2.duplicate_of == trans1
            assert trans2 in trans1.duplicates

    def test_transaction_split_relationship(self, db_session):
        """Test split transaction relationship"""
        statement = Statement.query.first()
        category = Category.query.first()

        # Create parent transaction
        parent = Transaction(
            statement_id=statement.id,
            date=date(2025, 3, 28),
            description='Original transaction',
            amount=Decimal('-500.00'),
            category_id=category.id
        )
        db_session.add(parent)
        db_session.flush()

        # Create split child
        child = Transaction(
            statement_id=statement.id,
            date=date(2025, 3, 28),
            description='Split portion',
            amount=Decimal('-300.00'),
            category_id=category.id,
            parent_transaction_id=parent.id,
            original_amount=Decimal('-500.00')
        )
        db_session.add(child)
        db_session.commit()

        assert child.parent_transaction == parent
        assert child in parent.split_items


class TestExpenseRule:
    """Test ExpenseRule model"""

    def test_create_expense_rule(self, db_session):
        """Test creating an expense rule"""
        category = Category.query.first()

        rule = ExpenseRule(
            pattern='TEST PATTERN',
            category_id=category.id,
            priority=100,
            is_regex=False,
            is_active=True
        )
        db_session.add(rule)
        db_session.commit()

        assert rule.id is not None
        assert rule.pattern == 'TEST PATTERN'

    def test_expense_rule_regex_flag(self, db_session):
        """Test regex flag on expense rule"""
        category = Category.query.first()

        rule = ExpenseRule(
            pattern='CLIENT.*(ABC|XYZ)',
            category_id=category.id,
            priority=150,
            is_regex=True,
            is_active=True
        )
        db_session.add(rule)
        db_session.commit()

        assert rule.is_regex is True

    def test_expense_rule_relationship_with_category(self, db_session):
        """Test rule-category relationship"""
        category = Category.query.first()
        initial_count = len(category.rules)

        rule = ExpenseRule(
            pattern='NEW PATTERN',
            category_id=category.id,
            priority=80,
            is_regex=False,
            is_active=True
        )
        db_session.add(rule)
        db_session.commit()

        assert len(category.rules) == initial_count + 1
        assert rule in category.rules

    def test_expense_rule_active_toggle(self, db_session):
        """Test toggling active status"""
        rule = ExpenseRule.query.first()
        original_status = rule.is_active

        rule.is_active = not original_status
        db_session.commit()

        # Reload from database
        rule = ExpenseRule.query.get(rule.id)
        assert rule.is_active != original_status


class TestModelConstraints:
    """Test model constraints and validations"""

    def test_transaction_requires_statement(self, db_session):
        """Test that transaction requires a statement"""
        with pytest.raises(Exception):
            transaction = Transaction(
                statement_id=None,  # Invalid
                date=date(2025, 3, 1),
                description='Invalid',
                amount=Decimal('100.00')
            )
            db_session.add(transaction)
            db_session.commit()

    def test_statement_requires_account(self, db_session):
        """Test that statement requires an account"""
        with pytest.raises(Exception):
            statement = Statement(
                account_id=None,  # Invalid
                start_date=date(2025, 3, 1),
                end_date=date(2025, 3, 31),
                filename='test.pdf'
            )
            db_session.add(statement)
            db_session.commit()

    def test_expense_rule_requires_category(self, db_session):
        """Test that expense rule requires a category"""
        with pytest.raises(Exception):
            rule = ExpenseRule(
                pattern='TEST',
                category_id=None,  # Invalid
                priority=100,
                is_regex=False
            )
            db_session.add(rule)
            db_session.commit()
