"""
South African Tax Calculator
Calculates tax liability based on SARS tax tables and provisional tax rules

Tax tables are loaded from the database if available, otherwise fallback to
hardcoded 2025/2026 tax year values.

To update tax tables for a new tax year, use the /admin/tax_tables route.
"""
from decimal import Decimal
from datetime import date
from typing import Dict, Any, Optional


class SATaxCalculator:
    """Calculate South African personal income tax"""

    # FALLBACK: 2025/2026 Tax Year (Mar 2025 - Feb 2026) - Individual Tax Tables
    # Source: SARS Tax Tables
    # These are used only if database tables are not available
    TAX_BRACKETS_2025 = [
        {'min': 0, 'max': 237100, 'rate': 0.18, 'base': 0},
        {'min': 237100, 'max': 370500, 'rate': 0.26, 'base': 42678},
        {'min': 370500, 'max': 512800, 'rate': 0.31, 'base': 77362},
        {'min': 512800, 'max': 673000, 'rate': 0.36, 'base': 121475},
        {'min': 673000, 'max': 857900, 'rate': 0.39, 'base': 179147},
        {'min': 857900, 'max': 1817000, 'rate': 0.41, 'base': 251258},
        {'min': 1817000, 'max': float('inf'), 'rate': 0.45, 'base': 644489},
    ]

    # FALLBACK: Rebates for 2025/2026
    PRIMARY_REBATE_2025 = 17235
    SECONDARY_REBATE_2025 = 9444
    TERTIARY_REBATE_2025 = 3145

    # FALLBACK: Medical aid tax credits (2025/2026)
    MEDICAL_AID_CREDIT_MAIN = 364  # Per month for main member
    MEDICAL_AID_CREDIT_DEPENDENT = 246  # Per month per first dependent
    MEDICAL_AID_CREDIT_ADDITIONAL = 246  # Per month per additional dependent

    def __init__(self, tax_year: int = 2025, db_session=None):
        """
        Initialize calculator for specific tax year

        Args:
            tax_year: Tax year (e.g., 2025 for 2025/2026 tax year)
            db_session: SQLAlchemy session for loading tax tables from database
        """
        self.tax_year = tax_year
        self.db_session = db_session

        # Try to load from database first, fallback to hardcoded values
        if db_session:
            self._load_from_database()
        else:
            self._load_fallback_values()

    def _load_from_database(self):
        """Load tax tables from database"""
        try:
            from src.database.models import TaxYear

            # Find the tax year
            tax_year_obj = TaxYear.query.filter_by(year=self.tax_year).first()

            if tax_year_obj:
                # Load brackets
                brackets = sorted(tax_year_obj.brackets, key=lambda b: b.bracket_order)
                self.tax_brackets = []
                for bracket in brackets:
                    self.tax_brackets.append({
                        'min': float(bracket.min_income),
                        'max': float(bracket.max_income) if bracket.max_income else float('inf'),
                        'rate': float(bracket.rate),
                        'base': float(bracket.base_tax)
                    })

                # Load rebates into a dict for easy lookup
                rebates_dict = {}
                for rebate in tax_year_obj.rebates:
                    rebates_dict[rebate.rebate_type] = float(rebate.amount)

                self.primary_rebate = rebates_dict.get('primary', self.PRIMARY_REBATE_2025)
                self.secondary_rebate = rebates_dict.get('secondary', self.SECONDARY_REBATE_2025)
                self.tertiary_rebate = rebates_dict.get('tertiary', self.TERTIARY_REBATE_2025)

                # Load medical aid credits
                credits_dict = {}
                for credit in tax_year_obj.medical_credits:
                    credits_dict[credit.credit_type] = float(credit.monthly_amount)

                self.medical_aid_credit_main = credits_dict.get('main', self.MEDICAL_AID_CREDIT_MAIN)
                self.medical_aid_credit_dependent = credits_dict.get('first_dependent', self.MEDICAL_AID_CREDIT_DEPENDENT)
                self.medical_aid_credit_additional = credits_dict.get('additional', self.MEDICAL_AID_CREDIT_ADDITIONAL)

                return  # Successfully loaded from database

        except Exception:
            # If database load fails, fall back to hardcoded values
            pass

        # Fallback if database load failed or tax year not found
        self._load_fallback_values()

    def _load_fallback_values(self):
        """Load hardcoded fallback values"""
        self.tax_brackets = self.TAX_BRACKETS_2025
        self.primary_rebate = self.PRIMARY_REBATE_2025
        self.secondary_rebate = self.SECONDARY_REBATE_2025
        self.tertiary_rebate = self.TERTIARY_REBATE_2025
        self.medical_aid_credit_main = self.MEDICAL_AID_CREDIT_MAIN
        self.medical_aid_credit_dependent = self.MEDICAL_AID_CREDIT_DEPENDENT
        self.medical_aid_credit_additional = self.MEDICAL_AID_CREDIT_ADDITIONAL

    def calculate_annual_tax(
        self,
        taxable_income: Decimal,
        age: int = 0,
        medical_aid_members: int = 0
    ) -> Dict[str, Any]:
        """
        Calculate annual tax liability

        Args:
            taxable_income: Annual taxable income (gross income - deductions)
            age: Taxpayer age (for age rebates)
            medical_aid_members: Number of medical aid members
                (0 = none, 1 = main only, 2+ = main + dependents)

        Returns:
            Dictionary with tax calculation breakdown
        """
        income = float(taxable_income)

        # Calculate tax before rebates
        tax_before_rebates = self._calculate_tax_on_income(income)

        # Calculate rebates
        rebates = self._calculate_rebates(age)

        # Calculate medical aid tax credits (annual)
        medical_credits = self._calculate_medical_credits(medical_aid_members)

        # Final tax liability
        tax_liability = max(0, tax_before_rebates - rebates - medical_credits)

        # Calculate effective tax rate
        effective_rate = (tax_liability / income * 100) if income > 0 else 0

        return {
            'taxable_income': Decimal(str(income)),
            'tax_before_rebates': Decimal(str(tax_before_rebates)),
            'rebates': Decimal(str(rebates)),
            'medical_credits': Decimal(str(medical_credits)),
            'tax_liability': Decimal(str(tax_liability)),
            'effective_rate': Decimal(str(round(effective_rate, 2))),
            'age': age,
            'medical_aid_members': medical_aid_members,
        }

    def calculate_provisional_tax(
        self,
        period_income: Decimal,
        period_expenses: Decimal,
        period_months: int,
        age: int = 0,
        medical_aid_members: int = 0,
        previous_payments: Decimal = Decimal('0')
    ) -> Dict[str, Any]:
        """
        Calculate provisional tax payment required

        Args:
            period_income: Income for the period
            period_expenses: Deductible expenses for the period
            period_months: Number of months in the period (usually 6)
            age: Taxpayer age
            medical_aid_members: Number of medical aid members
            previous_payments: Tax already paid in current year

        Returns:
            Dictionary with provisional tax calculation
        """
        # Calculate net profit for period
        period_profit = period_income - period_expenses

        # Extrapolate to annual figure (12 months)
        annual_estimate = (period_profit / period_months) * 12

        # Calculate annual tax
        annual_tax_calc = self.calculate_annual_tax(
            annual_estimate, age, medical_aid_members
        )

        # Provisional tax is estimated annual tax minus payments already made
        provisional_payment = max(
            0, annual_tax_calc['tax_liability'] - previous_payments
        )

        # For first provisional (August): pay full estimated amount
        # For second provisional (February): pay balance
        # Basic estimate assumes 50/50 split if no previous payments

        return {
            'period_months': period_months,
            'period_income': period_income,
            'period_expenses': period_expenses,
            'period_profit': period_profit,
            'annual_estimate': annual_tax_calc['taxable_income'],
            'estimated_annual_tax': annual_tax_calc['tax_liability'],
            'previous_payments': previous_payments,
            'provisional_payment': Decimal(str(provisional_payment)),
            'effective_rate': annual_tax_calc['effective_rate'],
            'tax_breakdown': annual_tax_calc,
        }

    def _calculate_tax_on_income(self, income: float) -> float:
        """Calculate tax on income using brackets"""
        if income <= 0:
            return 0

        for bracket in self.tax_brackets:
            if income <= bracket['max']:
                tax = bracket['base'] + (
                    (income - bracket['min']) * bracket['rate']
                )
                return tax

        # Shouldn't reach here, but handle edge case
        last_bracket = self.tax_brackets[-1]
        return last_bracket['base'] + (
            (income - last_bracket['min']) * last_bracket['rate']
        )

    def _calculate_rebates(self, age: int) -> float:
        """Calculate age-based tax rebates"""
        rebate = self.primary_rebate

        if age >= 65:
            rebate += self.secondary_rebate

        if age >= 75:
            rebate += self.tertiary_rebate

        return rebate

    def _calculate_medical_credits(self, members: int) -> float:
        """Calculate annual medical aid tax credits"""
        if members == 0:
            return 0

        if members == 1:
            # Main member only
            return self.medical_aid_credit_main * 12

        # Main member + first dependent + additional dependents
        credits = (
            self.medical_aid_credit_main +
            self.medical_aid_credit_dependent +
            (self.medical_aid_credit_additional * (members - 2))
        ) * 12

        return credits


# Home office apportionment configuration
# Categories that should be apportioned based on home office percentage
HOME_OFFICE_CATEGORIES = [
    'Interest (Mortgage)',
    'Maintenance',
    'Municipal',
    'Insurance',
]

# Default home office dimensions (can be overridden in function call)
DEFAULT_HOME_OFFICE_SQM = Decimal('22')
DEFAULT_HOUSE_TOTAL_SQM = Decimal('268')


def calculate_tax_from_transactions(
    transactions: list,
    period_start: date,
    period_end: date,
    age: int = 0,
    medical_aid_members: int = 0,
    previous_payments: Decimal = Decimal('0'),
    tax_year: Optional[int] = None,
    db_session=None,
    home_office_sqm: Optional[Decimal] = None,
    house_total_sqm: Optional[Decimal] = None
) -> Dict[str, Any]:
    """
    Calculate tax liability from transaction data

    Args:
        transactions: List of transaction dicts with:
            - 'category': Category name
            - 'category_type': One of 'income', 'business_expense',
                               'personal_expense', 'excluded'
            - 'amount': Transaction amount
        period_start: Start date of tax period
        period_end: End date of tax period
        age: Taxpayer age
        medical_aid_members: Number on medical aid
        previous_payments: Tax already paid
        tax_year: Tax year to use (if None, derived from period_end)
        db_session: Database session for loading tax tables
        home_office_sqm: Home office size in square meters (default: 22)
        house_total_sqm: Total house size in square meters (default: 268)

    Returns:
        Dictionary with comprehensive tax calculation including breakdown
    """
    # Determine tax year from period_end if not specified
    if tax_year is None:
        # SA tax year runs Mar 1 - Feb 28/29
        # If transaction is in Mar-Dec, it belongs to that year's tax year
        # If transaction is in Jan-Feb, it belongs to previous year's tax year
        if period_end.month >= 3:
            tax_year = period_end.year
        else:
            tax_year = period_end.year - 1

    # Calculate period months
    months_diff = (
        (period_end.year - period_start.year) * 12 +
        (period_end.month - period_start.month)
    )
    period_months = max(1, months_diff)

    # Home office apportionment
    office_sqm = home_office_sqm if home_office_sqm is not None else DEFAULT_HOME_OFFICE_SQM
    house_sqm = house_total_sqm if house_total_sqm is not None else DEFAULT_HOUSE_TOTAL_SQM
    home_office_percentage = (office_sqm / house_sqm) if house_sqm > 0 else Decimal('0')

    # Summarize transactions by category_type
    total_income = Decimal('0')
    total_business_expenses = Decimal('0')
    total_personal_expenses = Decimal('0')
    total_excluded = Decimal('0')

    # Track apportionment adjustments
    total_apportioned_reduction = Decimal('0')

    # Detailed breakdowns (full amounts before apportionment)
    income_breakdown: Dict[str, Decimal] = {}
    expense_breakdown: Dict[str, Decimal] = {}
    expense_breakdown_full: Dict[str, Decimal] = {}  # Before apportionment
    personal_breakdown: Dict[str, Decimal] = {}
    excluded_breakdown: Dict[str, Decimal] = {}
    apportionment_detail: Dict[str, Dict[str, Decimal]] = {}  # Category -> {full, apportioned, reduction}

    # Transaction counts for transparency
    income_count = 0
    business_expense_count = 0
    personal_expense_count = 0
    excluded_count = 0
    uncategorized_count = 0

    for trans in transactions:
        amount = Decimal(str(trans.get('amount', 0)))
        category = trans.get('category', 'Uncategorized')
        category_type = trans.get('category_type', 'personal_expense')

        if category_type == 'income':
            total_income += abs(amount)
            income_count += 1
            if category not in income_breakdown:
                income_breakdown[category] = Decimal('0')
            income_breakdown[category] += abs(amount)

        elif category_type == 'business_expense':
            full_amount = abs(amount)
            business_expense_count += 1

            # Track full amount before apportionment
            if category not in expense_breakdown_full:
                expense_breakdown_full[category] = Decimal('0')
            expense_breakdown_full[category] += full_amount

            # Apply home office apportionment to relevant categories
            if category in HOME_OFFICE_CATEGORIES:
                apportioned_amount = (full_amount * home_office_percentage).quantize(Decimal('0.01'))
                reduction = full_amount - apportioned_amount
                total_apportioned_reduction += reduction

                # Track apportionment details
                if category not in apportionment_detail:
                    apportionment_detail[category] = {
                        'full': Decimal('0'),
                        'apportioned': Decimal('0'),
                        'reduction': Decimal('0')
                    }
                apportionment_detail[category]['full'] += full_amount
                apportionment_detail[category]['apportioned'] += apportioned_amount
                apportionment_detail[category]['reduction'] += reduction

                # Use apportioned amount for tax calculation
                total_business_expenses += apportioned_amount
                if category not in expense_breakdown:
                    expense_breakdown[category] = Decimal('0')
                expense_breakdown[category] += apportioned_amount
            else:
                # Non-apportioned categories: use full amount
                total_business_expenses += full_amount
                if category not in expense_breakdown:
                    expense_breakdown[category] = Decimal('0')
                expense_breakdown[category] += full_amount

        elif category_type == 'personal_expense':
            total_personal_expenses += abs(amount)
            personal_expense_count += 1
            if category not in personal_breakdown:
                personal_breakdown[category] = Decimal('0')
            personal_breakdown[category] += abs(amount)

        elif category_type == 'excluded':
            total_excluded += abs(amount)
            excluded_count += 1
            if category not in excluded_breakdown:
                excluded_breakdown[category] = Decimal('0')
            excluded_breakdown[category] += abs(amount)

        else:
            # Uncategorized - treat as personal (non-deductible) to be safe
            uncategorized_count += 1
            total_personal_expenses += abs(amount)

    # Calculate tax using the appropriate tax year
    calculator = SATaxCalculator(tax_year=tax_year, db_session=db_session)
    tax_calc = calculator.calculate_provisional_tax(
        period_income=total_income,
        period_expenses=total_business_expenses,  # Only business expenses are deductible
        period_months=period_months,
        age=age,
        medical_aid_members=medical_aid_members,
        previous_payments=previous_payments
    )

    # Add detailed breakdowns for transparency
    tax_calc['expense_breakdown'] = expense_breakdown
    tax_calc['expense_breakdown_full'] = expense_breakdown_full  # Before apportionment
    tax_calc['income_breakdown'] = income_breakdown
    tax_calc['personal_breakdown'] = personal_breakdown
    tax_calc['excluded_breakdown'] = excluded_breakdown
    tax_calc['tax_year'] = tax_year

    # Add totals for transparency
    tax_calc['total_personal_expenses'] = total_personal_expenses
    tax_calc['total_excluded'] = total_excluded

    # Add home office apportionment details
    tax_calc['home_office'] = {
        'office_sqm': office_sqm,
        'house_sqm': house_sqm,
        'percentage': round(float(home_office_percentage * 100), 1),
        'apportioned_categories': list(HOME_OFFICE_CATEGORIES),
        'total_reduction': total_apportioned_reduction,
        'detail': apportionment_detail
    }

    # Add transaction counts for transparency
    tax_calc['transaction_counts'] = {
        'income': income_count,
        'business_expense': business_expense_count,
        'personal_expense': personal_expense_count,
        'excluded': excluded_count,
        'uncategorized': uncategorized_count,
        'total': income_count + business_expense_count + personal_expense_count + excluded_count + uncategorized_count
    }

    return tax_calc
