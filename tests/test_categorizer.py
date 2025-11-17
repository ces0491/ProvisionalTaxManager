"""
Tests for categorizer module
"""
from categorizer import (
    categorize_transaction,
    categorize_transaction_with_rules,
    is_inter_account_transfer,
    is_personal_from_business_mixed,
    get_category_by_name
)


class TestCategorizeTransaction:
    """Test transaction categorization"""

    def test_categorize_income(self):
        """Test income categorization"""
        category, score = categorize_transaction(
            'PRECISE DIGITAIT25091ZA0799010',
            10000.00
        )
        assert category == 'income'
        assert score == 1.0

    def test_categorize_income_teletransmission_fee(self):
        """Test that teletransmission fees are categorized as banking fees"""
        category, score = categorize_transaction(
            'PRECISE DIGITAL TELETRANSMISSION FEE',
            -50.00
        )
        assert category == 'banking_fees'
        assert score == 1.0

    def test_categorize_mortgage_interest(self):
        """Test mortgage interest categorization"""
        category, score = categorize_transaction(
            'SYSTEM INTEREST DEBIT',
            -5000.00
        )
        assert category == 'interest_mortgage'
        assert score == 1.0

    def test_categorize_technology(self):
        """Test technology expense categorization"""
        test_cases = [
            'GOOGLE GSUITE_SHEETSOL',
            'CLAUDE.AI SUBSCRIPTION',
            'RENDER.COM',
            'MSFT MICROSOFT',
        ]

        for description in test_cases:
            category, score = categorize_transaction(description, -100.00)
            assert category == 'technology_software'
            assert score == 1.0

    def test_categorize_medical(self):
        """Test medical expense categorization"""
        test_cases = [
            'DISC PREM CONTRIBUTION',
            'SPECSAVERS PINELANDS',
            'CLICKS PINELA',
        ]

        for description in test_cases:
            category, score = categorize_transaction(description, -500.00)
            assert category in ['medical_aid', 'medical_fees']

    def test_categorize_personal(self):
        """Test personal expense categorization"""
        test_cases = [
            'NETFLIX.COM',
            'YOUTUBE PREMIUM',
            'VIRGIN ACT329618220',
        ]

        for description in test_cases:
            category, score = categorize_transaction(description, -100.00)
            assert category in ['entertainment', 'gym']

    def test_categorize_uncategorized(self):
        """Test uncategorized transaction"""
        category, score = categorize_transaction(
            'UNKNOWN MERCHANT XYZ',
            -50.00
        )
        assert category is None
        assert score == 0.0

    def test_categorize_case_insensitive(self):
        """Test that categorization is case-insensitive"""
        category1, _ = categorize_transaction('NETFLIX.COM', -100.00)
        category2, _ = categorize_transaction('netflix.com', -100.00)
        category3, _ = categorize_transaction('NeTfLiX.CoM', -100.00)

        assert category1 == category2 == category3


class TestCategorizeTransactionWithRules:
    """Test enhanced categorization with database rules"""

    def test_categorize_with_no_rules(self):
        """Test categorization falls back to hardcoded when no rules provided"""
        category, score = categorize_transaction_with_rules(
            'NETFLIX.COM',
            -100.00,
            db_rules=None
        )
        assert category == 'Entertainment'
        assert score == 1.0

    def test_categorize_with_rules(self, db_session):
        """Test categorization uses database rules"""
        from models import ExpenseRule, Category

        # Get a category
        income_cat = Category.query.filter_by(name='Income').first()

        # Create a custom rule
        custom_rule = ExpenseRule(
            pattern='CUSTOM INCOME SOURCE',
            category_id=income_cat.id,
            priority=200,
            is_regex=False,
            is_active=True
        )
        db_session.add(custom_rule)
        db_session.commit()

        # Get all rules
        rules = ExpenseRule.query.all()

        # Test categorization
        category, score = categorize_transaction_with_rules(
            'CUSTOM INCOME SOURCE PAYMENT',
            10000.00,
            db_rules=rules
        )

        assert category == 'Income'
        assert score == 1.0

    def test_categorize_with_regex_rule(self, db_session):
        """Test categorization with regex pattern"""
        from models import ExpenseRule, Category

        tech_cat = Category.query.filter_by(name='Technology/Software').first()

        # Create regex rule
        regex_rule = ExpenseRule(
            pattern='CLIENT.*(ABC|XYZ)',
            category_id=tech_cat.id,
            priority=150,
            is_regex=True,
            is_active=True
        )
        db_session.add(regex_rule)
        db_session.commit()

        rules = ExpenseRule.query.all()

        # Should match
        category1, _ = categorize_transaction_with_rules(
            'CLIENT ABC PAYMENT',
            -1000.00,
            db_rules=rules
        )
        assert category1 == 'Technology/Software'

        category2, _ = categorize_transaction_with_rules(
            'CLIENT XYZ INVOICE',
            -2000.00,
            db_rules=rules
        )
        assert category2 == 'Technology/Software'

    def test_categorize_priority_order(self, db_session):
        """Test that higher priority rules are matched first"""
        from models import ExpenseRule, Category

        income_cat = Category.query.filter_by(name='Income').first()
        tech_cat = Category.query.filter_by(name='Technology/Software').first()

        # Create two rules with different priorities
        low_priority = ExpenseRule(
            pattern='PAYMENT',
            category_id=tech_cat.id,
            priority=50,
            is_regex=False,
            is_active=True
        )
        high_priority = ExpenseRule(
            pattern='PAYMENT',
            category_id=income_cat.id,
            priority=150,
            is_regex=False,
            is_active=True
        )

        db_session.add_all([low_priority, high_priority])
        db_session.commit()

        rules = ExpenseRule.query.all()

        # Should match higher priority rule (Income)
        category, _ = categorize_transaction_with_rules(
            'PAYMENT FROM CLIENT',
            10000.00,
            db_rules=rules
        )
        assert category == 'Income'

    def test_categorize_inactive_rules_ignored(self, db_session):
        """Test that inactive rules are not matched"""
        from models import ExpenseRule, Category

        income_cat = Category.query.filter_by(name='Income').first()

        # Create inactive rule
        inactive_rule = ExpenseRule(
            pattern='INACTIVE SOURCE',
            category_id=income_cat.id,
            priority=100,
            is_regex=False,
            is_active=False
        )
        db_session.add(inactive_rule)
        db_session.commit()

        rules = ExpenseRule.query.all()

        # Should not match inactive rule
        category, score = categorize_transaction_with_rules(
            'INACTIVE SOURCE PAYMENT',
            10000.00,
            db_rules=rules
        )
        # Should return None (uncategorized) since rule is inactive
        assert category is None or score < 1.0


class TestIsInterAccountTransfer:
    """Test inter-account transfer detection"""

    def test_is_transfer_ib_transfer(self):
        """Test IB Transfer detection"""
        assert is_inter_account_transfer('IB TRANSFER TO SAVINGS')
        assert is_inter_account_transfer('IB TRANSFER FROM CHEQUE')

    def test_is_transfer_autobank(self):
        """Test Autobank transfer detection"""
        assert is_inter_account_transfer('AUTOBANK TRANSFER')

    def test_is_not_transfer(self):
        """Test non-transfer transactions"""
        assert not is_inter_account_transfer('PRECISE DIGITAL PAYMENT')
        assert not is_inter_account_transfer('NETFLIX.COM')


class TestIsPersonalFromBusinessMixed:
    """Test mixed business/personal detection"""

    def test_is_takealot(self):
        """Test Takealot detection"""
        assert is_personal_from_business_mixed('TAKEALO.T')
        assert is_personal_from_business_mixed('TAKEALOT ORDER')

    def test_is_not_mixed(self):
        """Test non-mixed transactions"""
        assert not is_personal_from_business_mixed('GOOGLE GSUITE')
        assert not is_personal_from_business_mixed('NETFLIX.COM')


class TestGetCategoryByName:
    """Test category lookup by name"""

    def test_get_category_by_name(self, db_session):
        """Test getting category by name"""
        from models import Category

        category = get_category_by_name(db_session, Category, 'Income')
        assert category is not None
        assert category.name == 'Income'
        assert category.category_type == 'income'

    def test_get_category_by_name_not_found(self, db_session):
        """Test getting non-existent category"""
        from models import Category

        category = get_category_by_name(db_session, Category, 'NonExistent')
        assert category is None
