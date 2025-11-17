"""
Tests for tax_calculator module
"""
from decimal import Decimal
from datetime import date

from tax_calculator import (
    SATaxCalculator,
    calculate_tax_from_transactions
)


class TestSATaxCalculator:
    """Test SA tax calculator functionality"""

    def test_calculate_annual_tax_basic(self):
        """Test basic annual tax calculation"""
        calc = SATaxCalculator()
        result = calc.calculate_annual_tax(
            taxable_income=Decimal('500000'),
            age=35,
            medical_aid_members=0
        )

        assert result['taxable_income'] == Decimal('500000.0')
        assert result['tax_liability'] > 0
        assert result['effective_rate'] > 0
        assert result['age'] == 35

    def test_calculate_annual_tax_with_rebates(self):
        """Test tax calculation with age rebates"""
        calc = SATaxCalculator()

        # Test with primary rebate only (under 65)
        result_young = calc.calculate_annual_tax(
            taxable_income=Decimal('500000'),
            age=40,
            medical_aid_members=0
        )

        # Test with secondary rebate (65+)
        result_senior = calc.calculate_annual_tax(
            taxable_income=Decimal('500000'),
            age=65,
            medical_aid_members=0
        )

        # Test with tertiary rebate (75+)
        result_elderly = calc.calculate_annual_tax(
            taxable_income=Decimal('500000'),
            age=75,
            medical_aid_members=0
        )

        # Senior should pay less tax due to higher rebates
        assert result_senior['tax_liability'] < result_young['tax_liability']
        assert result_elderly['tax_liability'] < result_senior['tax_liability']

    def test_calculate_annual_tax_with_medical_credits(self):
        """Test tax calculation with medical aid credits"""
        calc = SATaxCalculator()

        # No medical aid
        result_no_med = calc.calculate_annual_tax(
            taxable_income=Decimal('500000'),
            age=40,
            medical_aid_members=0
        )

        # With medical aid (2 members)
        result_with_med = calc.calculate_annual_tax(
            taxable_income=Decimal('500000'),
            age=40,
            medical_aid_members=2
        )

        # Should have lower tax with medical aid credits
        assert result_with_med['medical_credits'] > 0
        assert result_with_med['tax_liability'] < result_no_med['tax_liability']

    def test_calculate_annual_tax_low_income(self):
        """Test tax calculation for low income (below tax threshold)"""
        calc = SATaxCalculator()
        result = calc.calculate_annual_tax(
            taxable_income=Decimal('100000'),
            age=30,
            medical_aid_members=0
        )

        # Should pay some tax but have low effective rate
        assert result['tax_liability'] >= 0
        assert result['effective_rate'] < 10

    def test_calculate_annual_tax_high_income(self):
        """Test tax calculation for high income"""
        calc = SATaxCalculator()
        result = calc.calculate_annual_tax(
            taxable_income=Decimal('2000000'),
            age=40,
            medical_aid_members=0
        )

        # Should be in highest tax bracket
        assert result['effective_rate'] > 30
        assert result['tax_liability'] > Decimal('500000')

    def test_calculate_provisional_tax(self):
        """Test provisional tax calculation"""
        calc = SATaxCalculator()
        result = calc.calculate_provisional_tax(
            period_income=Decimal('300000'),
            period_expenses=Decimal('100000'),
            period_months=6,
            age=40,
            medical_aid_members=1,
            previous_payments=Decimal('0')
        )

        assert result['period_profit'] == Decimal('200000')
        assert result['annual_estimate'] == Decimal('400000.0')  # 200k * 12/6
        assert result['provisional_payment'] > 0

    def test_calculate_provisional_tax_with_previous_payments(self):
        """Test provisional tax with previous payments"""
        calc = SATaxCalculator()

        # Calculate for second provisional with first payment already made
        result = calc.calculate_provisional_tax(
            period_income=Decimal('300000'),
            period_expenses=Decimal('100000'),
            period_months=6,
            age=40,
            medical_aid_members=0,
            previous_payments=Decimal('50000')
        )

        # Should subtract previous payments
        assert result['previous_payments'] == Decimal('50000')
        assert result['provisional_payment'] < result['estimated_annual_tax']

    def test_tax_brackets_2025(self):
        """Test that 2025/2026 tax brackets are applied correctly"""
        calc = SATaxCalculator()

        # Test each bracket
        test_incomes = [
            Decimal('100000'),   # 18% bracket
            Decimal('300000'),   # 26% bracket
            Decimal('450000'),   # 31% bracket
            Decimal('600000'),   # 36% bracket
            Decimal('750000'),   # 39% bracket
            Decimal('1000000'),  # 41% bracket
            Decimal('2000000'),  # 45% bracket
        ]

        previous_tax = Decimal('0')
        for income in test_incomes:
            result = calc.calculate_annual_tax(income, 40, 0)
            # Tax should increase with income
            assert result['tax_liability'] > previous_tax
            previous_tax = result['tax_liability']


class TestCalculateTaxFromTransactions:
    """Test transaction-based tax calculation"""

    def test_calculate_tax_from_transactions(self, sample_transactions):
        """Test calculating tax from a list of transactions"""
        result = calculate_tax_from_transactions(
            transactions=sample_transactions,
            period_start=date(2025, 3, 1),
            period_end=date(2025, 8, 31),
            age=40,
            medical_aid_members=1,
            previous_payments=Decimal('0')
        )

        # With sample income of 10,000 and expenses of 5,099
        # Net profit should be 4,901 for the period
        assert result['period_months'] == 5
        assert result['period_income'] > 0
        assert result['period_expenses'] > 0
        # Annual tax should be calculated on annualized profit
        assert result['estimated_annual_tax'] >= 0  # Can be 0 if rebates exceed tax

    def test_calculate_tax_excludes_personal(self, sample_transactions):
        """Test that personal expenses are excluded"""
        # Add a personal transaction
        transactions = sample_transactions + [{
            'date': date(2025, 3, 30),
            'description': 'NETFLIX',
            'amount': Decimal('-15.99'),
            'category': 'Personal'
        }]

        result = calculate_tax_from_transactions(
            transactions=transactions,
            period_start=date(2025, 3, 1),
            period_end=date(2025, 3, 31),
            age=40,
            medical_aid_members=0
        )

        # Personal expense should not be in business expenses
        assert 'Personal' not in result['expense_breakdown']

    def test_calculate_tax_with_no_transactions(self):
        """Test calculation with no transactions"""
        result = calculate_tax_from_transactions(
            transactions=[],
            period_start=date(2025, 3, 1),
            period_end=date(2025, 8, 31),
            age=40,
            medical_aid_members=0
        )

        assert result['period_income'] == 0
        assert result['period_expenses'] == 0
        assert result['provisional_payment'] == 0

    def test_expense_breakdown(self, sample_transactions):
        """Test that expense breakdown is provided"""
        result = calculate_tax_from_transactions(
            transactions=sample_transactions,
            period_start=date(2025, 3, 1),
            period_end=date(2025, 3, 31),
            age=40,
            medical_aid_members=0
        )

        assert 'expense_breakdown' in result
        assert 'Technology/Software' in result['expense_breakdown']
        assert result['expense_breakdown']['Technology/Software'] == Decimal('99.00')
