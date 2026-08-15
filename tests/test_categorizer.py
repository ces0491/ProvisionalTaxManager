"""
Tests for categorizer module
"""
from src.services.categorizer import (
    CATEGORIES,
    categorize_transaction,
    categorize_transaction_with_rules,
    is_inter_account_transfer,
    is_personal_from_business_mixed,
    get_category_by_name
)


class TestCategorizeTransaction:
    """Test transaction categorization - returns category NAMES"""

    def test_categorize_income(self):
        """Test income categorization"""
        category, score = categorize_transaction(
            'PRECISE DIGITAIT25091ZA0799010',
            10000.00
        )
        assert category == 'Income'
        assert score == 1.0

    def test_categorize_income_teletransmission_fee(self):
        """Test that teletransmission fees are categorized as banking fees"""
        category, score = categorize_transaction(
            'PRECISE DIGITAL TELETRANSMISSION FEE',
            -50.00
        )
        assert category == 'Fees/Bank charges'
        assert score == 1.0

    def test_categorize_mortgage_interest(self):
        """Test mortgage interest categorization"""
        category, score = categorize_transaction(
            'SYSTEM INTEREST DEBIT',
            -5000.00
        )
        assert category == 'Interest (Mortgage)'
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
            assert category == 'Technology/Software'
            assert score == 1.0

    def test_categorize_technology_asterisk_descriptors(self):
        """Card descriptors join vendor and product with '*' as well as a space"""
        test_cases = [
            'GOOGLE WORKSPACE_SHEET DUBLI Debit',
            'GOOGLE*WORKSPACE SHEET CC GO Debit',
            'GOOGLE *COLAB DUBLI Debit',
            'GOOGLE*CLOUD 72PXVF CC GO Debit',
        ]

        for description in test_cases:
            category, score = categorize_transaction(description, -300.00)
            assert category == 'Technology/Software', description
            assert score == 1.0

    def test_personal_care_tokens_are_word_anchored(self):
        """Short personal-care tokens must not match inside unrelated words.

        Each case asserts the category the descriptor should land in, so a
        descriptor that stops matching anything fails here rather than passing
        on the absence of 'Personal Care'.
        """
        elsewhere = [
            # SPA inside WORKSPACE
            ('GOOGLE*WORKSPACE SHEET CC GO Debit', 'Technology/Software'),
            # SPA at the start of SPAR, the grocer
            ('SPAR PINELANDS Debit', 'Groceries'),
            # HAIR inside CHAIR, NAIL inside SNAIL - neither has a category
            ('THE CHAIR COMPANY Debit', None),
            ('SNAIL AND BUTTERFLY CAPE Debit', None),
        ]
        for description, expected in elsewhere:
            category, _ = categorize_transaction(description, -100.00)
            assert category == expected, description

        still_personal_care = [
            'HAIR ON HIGH CAPE Debit',
            'HAIRDRESSER PINELANDS Debit',
            'THE DAY SPA CAPE Debit',
            'HEALTH SPAS PINELANDS Debit',
            'NAILS BY ZOE CAPE Debit',
        ]
        for description in still_personal_care:
            category, _ = categorize_transaction(description, -100.00)
            assert category == 'Personal Care', description

    def test_categorize_anthropic(self):
        """Anthropic bills under several descriptors, all Technology/Software"""
        test_cases = [
            'ANTHROPIC SAN F Debit',
            'ANTHROPIC* CLAUDE SUB SAN F Debit',
            'CLAUDE.AI SUBSCRIPTION SAN F Debit',
        ]

        for description in test_cases:
            category, score = categorize_transaction(description, -1900.00)
            assert category == 'Technology/Software', description
            assert score == 1.0

    def test_youtube_stays_personal(self):
        """The Google patterns must not swallow GOOGLE YOUTUBE"""
        category, _ = categorize_transaction('GOOGLE YOUTUBE LONDO Debit', -149.99)
        assert category == 'Entertainment (Personal)'

    def test_categorize_govchain(self):
        """CIPC filings via GovChain are a professional service.

        The descriptor carrying the word CIPC is the case that matters: without
        the category priority it would be billed as one-off start-up
        expenditure instead of a recurring annual return.
        """
        for description in ('PAYSTACK *GOVCHAIN CAPE Debit',
                            'PAYSTACK *GOVCHAIN CIPC ANNUAL RETURN'):
            category, score = categorize_transaction(description, -1080.00)
            assert category == 'Professional Services', description
            assert score == 1.0

    def test_cipc_without_govchain_is_startup_cost(self):
        """The company-registration filing itself stays a start-up cost"""
        category, _ = categorize_transaction('CIPC COMPANY REGISTRATION', -175.00)
        assert category == 'Business Start-up Costs'

    def test_categorize_small_bank_fees(self):
        """Payment-confirmation, prepaid and transfer fees are bank charges.

        Each fee appears in more than one rendering across the statements, so
        the separator variants are asserted alongside the canonical form.
        """
        test_cases = [
            '#EMAIL PMT CONFIRM FEE MARSH Debit',
            '#SMS PMT CONFIRM FEE MARSH Debit',
            'FEE - PRE-PAID TOP UP FEE - PRE-PAID TOP UP',
            'FEE-PRE-PAID TOP UP',
            '#PREPAID FEE - #PREPAID FEE',
            '#INTER ACC TRANSFER FEE Debit',
            'INTER-ACC TRANSFER FEE',
        ]

        for description in test_cases:
            category, score = categorize_transaction(description, -1.00)
            assert category == 'Fees/Bank charges', description
            assert score == 1.0

    def test_prepaid_airtime_is_not_a_bank_fee(self):
        """The top-up is Phone/Data; only the charge on it is a fee.

        The second descriptor is the guard: the fee patterns are anchored on
        the word FEE, so widening one to a bare 'PRE-PAID TOP UP' would claim
        the airtime purchase itself as a bank charge.
        """
        for description in ('MTN PREPAID 0762783709 PRE-PAID PAYMENT TO',
                            'MTN PRE-PAID TOP UP 0762783709'):
            category, _ = categorize_transaction(description, -99.00)
            assert category == 'Phone/Data', description

    def test_home_loan_admin_fee_is_home_loan_cost(self):
        """The home-loan admin fee is apportioned rather than deducted in full.

        The statements render the separator inconsistently, so every form the
        fee arrives in has to reach the same category. 'HLOAN' is the guard on
        the other side: the pattern must not spill into unrelated descriptors.
        """
        for description in ('ADMINISTRATION FEE HL - SC',
                            'ADMINISTRATION FEE - HL',
                            'HL ADMINISTRATION FEE',
                            'ADMINISTRATION FEE HOME LOAN',
                            'HOME LOAN ADMIN FEE'):
            category, score = categorize_transaction(description, -69.00)
            assert category == 'Home Loan Costs', description
            assert score == 1.0

        category, _ = categorize_transaction('ADMINISTRATION FEE HLOAN', -69.00)
        assert category == 'Fees/Bank charges'

    def test_other_administration_fees_remain_bank_charges(self):
        """An ordinary admin fee stays a bank charge, deductible in full"""
        category, _ = categorize_transaction('ADMINISTRATION FEE Debit', -50.00)
        assert category == 'Fees/Bank charges'

    def test_credit_interest_is_not_a_deductible_charge(self):
        """Interest earned is income, so it must not match a bank-charge pattern"""
        category, _ = categorize_transaction('CREDIT INTEREST', 150.00)
        assert category != 'Fees/Bank charges'

    def test_unit_trust_purchase_is_savings_not_retirement(self):
        """Unit trusts are a savings contribution, so they are not deductible"""
        category, score = categorize_transaction(
            'OM UNITTRU21697083000000024778 UNIT TRUST PURCHASE', -2000.00
        )
        assert category == 'Savings/Investments'
        assert score == 1.0

    def test_oldgm_is_gym_regardless_of_suffix(self):
        """OLDGM is the gym debit order and is not bound to a suffix"""
        for description in ('OLD MUTUALOLDGM24484 DEBIT TRANSFER',
                            'OLD MUTUALOLDGM24484',
                            'OLDGM24484 INVEST'):
            category, _ = categorize_transaction(description, -820.00)
            assert category == 'Gym', description

    def test_oldgm_does_not_match_inside_other_words(self):
        """The gym token must not be found inside an unrelated merchant name"""
        for description in ('MARIGOLDGM STORE CAPE Debit', 'GOLDGMBH LTD PAYMENT'):
            category, _ = categorize_transaction(description, -100.00)
            assert category is None, description

    def test_other_retirement_never_auto_assigned(self):
        """10X is the only retirement product; the rest are savings or gym.

        Each descriptor asserts where it does land, so a pattern removed
        without a replacement fails here instead of passing on a None.
        """
        cases = [
            ('OLD MUTUAL INVESTMENT PLAN', 'Savings/Investments'),
            ('OM UNITTRU21697083000000024778 UNIT TRUST PURCHASE', 'Savings/Investments'),
            ('OLD MUTUALOLDGM24484 DEBIT TRANSFER', 'Gym'),
        ]
        for description, expected in cases:
            category, _ = categorize_transaction(description, -2000.00)
            assert category == expected, description

    def test_10x_still_categorized(self):
        """The one real retirement product must still be picked up"""
        for description in ('10XRA COL 960957 D67995 SERVICE AGREEMENT',
                            '10X RETIREMENT ANNUITY'):
            category, score = categorize_transaction(description, -6366.94)
            assert category == 'Retirement (10X)', description
            assert score == 1.0

    def test_10x_does_not_match_inside_a_card_reference(self):
        """An unanchored 10X would fabricate a retirement deduction"""
        category, _ = categorize_transaction('CARD PURCHASE 10X4832 WOOLWORTHS', -450.00)
        assert category == 'Groceries'

    def test_categorize_medical(self):
        """Test medical expense categorization"""
        test_cases = [
            'DISC PREM CONTRIBUTION',
            'SPECSAVERS PINELANDS',
            'CLICKS PINELA',
        ]

        for description in test_cases:
            category, score = categorize_transaction(description, -500.00)
            assert category in ['Medical Aid', 'Medical Fees']

    def test_categorize_personal(self):
        """Test personal expense categorization"""
        test_cases = [
            ('NETFLIX.COM', 'Entertainment (Personal)'),
            ('YOUTUBE PREMIUM', 'Entertainment (Personal)'),
            ('VIRGIN ACT329618220', 'Gym'),
        ]

        for description, expected in test_cases:
            category, score = categorize_transaction(description, -100.00)
            assert category == expected

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


class TestCategoryTableIntegrity:
    """The CATEGORIES table's own invariants, rather than one rule at a time"""

    def test_every_pattern_compiles(self):
        """A pattern that does not compile would silently never match"""
        from src.services.categorizer import _compile_categories

        compiled = _compile_categories()
        assert set(compiled) == set(CATEGORIES)

    def test_precedence_is_driven_by_priority_not_dict_order(self, monkeypatch):
        """Reordering CATEGORIES must not change any categorization.

        Three categories have to beat a more general one. Encoding that by
        position would make a routine re-alphabetize silently change how much
        is deducted, so it is encoded as 'priority' and asserted here against a
        fully re-sorted table.
        """
        from src.services import categorizer as cz

        reordered = dict(sorted(cz.CATEGORIES.items()))
        monkeypatch.setattr(cz, 'CATEGORIES', reordered)
        monkeypatch.setattr(cz, '_COMPILED', cz._compile_categories())
        monkeypatch.setattr(cz, '_EXCLUDED_ORDER', cz._match_order({'excluded'}))
        monkeypatch.setattr(
            cz, '_EXPENSE_ORDER', cz._match_order({'business_expense', 'personal_expense'})
        )

        cases = [
            ('ADMINISTRATION FEE HL - SC', 'Home Loan Costs'),
            ('DISCLIFE INSURANCE PREMIUM', 'Insurance (Life/Personal)'),
            ('PAYSTACK *GOVCHAIN CIPC ANNUAL RETURN', 'Professional Services'),
        ]
        for description, expected in cases:
            category, _ = cz.categorize_transaction(description, -100.00)
            assert category == expected, description

    def test_apportioned_categories_are_declared_on_the_entry(self):
        """HOME_OFFICE_CATEGORIES is derived, so the names cannot drift apart"""
        from src.services.tax_calculator import HOME_OFFICE_CATEGORIES

        declared = {c['name'] for c in CATEGORIES.values() if c.get('apportion')}
        assert set(HOME_OFFICE_CATEGORIES) == declared
        assert declared == {'Interest (Mortgage)', 'Home Loan Costs', 'Municipal', 'Insurance'}

    def test_every_category_name_resolves_to_a_database_row(self, db_session):
        """A category with no row stores its transactions as uncategorized.

        Uncategorized is then treated as a non-deductible personal expense, so
        a missing row is worse than a missing pattern. init_categories_in_db
        must reach every entry in the table.
        """
        from src.database.models import db, Category
        from src.services.categorizer import init_categories_in_db

        init_categories_in_db(db, Category)

        seeded = {c.name for c in Category.query.all()}
        missing = {c['name'] for c in CATEGORIES.values()} - seeded
        assert not missing, f'categories with no database row: {sorted(missing)}'


class TestCategorizeTransactionWithRules:
    """Test enhanced categorization with database rules"""

    def test_categorize_with_no_rules(self):
        """Test categorization falls back to hardcoded when no rules provided"""
        category, score = categorize_transaction_with_rules(
            'NETFLIX.COM',
            -100.00,
            db_rules=None
        )
        assert category == 'Entertainment (Personal)'
        assert score == 1.0

    def test_categorize_with_rules(self, db_session):
        """Test categorization uses database rules"""
        from src.database.models import ExpenseRule, Category

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
        from src.database.models import ExpenseRule, Category

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
        from src.database.models import ExpenseRule, Category

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

    def test_regex_rule_escapes_are_not_inverted(self, db_session):
        """A regex rule must keep its escapes.

        Upper-casing a pattern to match an upper-cased description turns \\b
        into \\B and \\d into \\D, inverting the rule. The word-anchored rule
        below would then match inside WORKSPACE, which is the collision the
        hardcoded patterns are anchored to avoid.
        """
        from src.database.models import ExpenseRule, Category

        personal_cat = Category.query.filter_by(name='Personal').first()
        db_session.add(ExpenseRule(
            pattern=r'\bSPA\b',
            category_id=personal_cat.id,
            priority=200,
            is_regex=True,
            is_active=True
        ))
        db_session.commit()
        rules = ExpenseRule.query.all()

        category, _ = categorize_transaction_with_rules(
            'GOOGLE*WORKSPACE SHEET CC GO Debit', -319.23, db_rules=rules
        )
        assert category == 'Technology/Software'

        category, _ = categorize_transaction_with_rules(
            'THE DAY SPA CAPE Debit', -450.00, db_rules=rules
        )
        assert category == 'Personal'

    def test_regex_rule_digit_class_is_not_inverted(self, db_session):
        """\\d must keep matching digits rather than becoming \\D"""
        from src.database.models import ExpenseRule, Category

        tech_cat = Category.query.filter_by(name='Technology/Software').first()
        db_session.add(ExpenseRule(
            pattern=r'ACCT \d{6}',
            category_id=tech_cat.id,
            priority=200,
            is_regex=True,
            is_active=True
        ))
        db_session.commit()
        rules = ExpenseRule.query.all()

        matched, _ = categorize_transaction_with_rules('ACCT 123456 DEBIT', -10.00, db_rules=rules)
        assert matched == 'Technology/Software'

        unmatched, _ = categorize_transaction_with_rules('ACCT ABCDEF DEBIT', -10.00, db_rules=rules)
        assert unmatched != 'Technology/Software'

    def test_categorize_inactive_rules_ignored(self, db_session):
        """Test that inactive rules are not matched"""
        from src.database.models import ExpenseRule, Category

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
        from src.database.models import Category

        category = get_category_by_name(db_session, Category, 'Income')
        assert category is not None
        assert category.name == 'Income'
        assert category.category_type == 'income'

    def test_get_category_by_name_not_found(self, db_session):
        """Test getting non-existent category"""
        from src.database.models import Category

        category = get_category_by_name(db_session, Category, 'NonExistent')
        assert category is None
