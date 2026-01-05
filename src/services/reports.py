"""
Financial reporting service
Generates summaries for income, expenses, and categories
"""
from decimal import Decimal
from collections import defaultdict
from datetime import datetime

# Month name constants (calendar order)
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

# Tax year month order (Mar-Feb)
TAX_YEAR_MONTHS = [
    (3, 'Mar'), (4, 'Apr'), (5, 'May'), (6, 'Jun'),
    (7, 'Jul'), (8, 'Aug'), (9, 'Sep'), (10, 'Oct'),
    (11, 'Nov'), (12, 'Dec'), (1, 'Jan'), (2, 'Feb')
]


def get_tax_year_month_labels(tax_year):
    """
    Get month labels with year suffix for a tax year.
    Tax year 2026 = Mar 25, Apr 25, ... Dec 25, Jan 26, Feb 26
    """
    labels = []
    for month_num, month_name in TAX_YEAR_MONTHS:
        if month_num >= 3:  # Mar-Dec are in previous calendar year
            year_suffix = str(tax_year - 1)[-2:]
        else:  # Jan-Feb are in the tax year
            year_suffix = str(tax_year)[-2:]
        labels.append(f"{month_name} {year_suffix}")
    return labels


def aggregate_transactions(transactions, tax_year=None):
    """
    Aggregate transactions into monthly and category summaries.

    Args:
        transactions: List of Transaction objects with category relationships
        tax_year: The tax year (e.g., 2026 for TY2026). Used for month labels.

    Returns:
        Dictionary containing:
        - monthly_summary: List of monthly income/expense/profit data (in tax year order)
        - totals: Total income, expenses, profit
        - category_summary: Categories grouped by type with totals
        - detailed_monthly: Monthly breakdown by category (grouped by type)
    """
    # Get month labels with year suffix
    if tax_year:
        month_labels = get_tax_year_month_labels(tax_year)
    else:
        month_labels = MONTHS

    # Initialize data structures - use tax year month order key
    # Key is (month_num) which we'll reorder later
    monthly_data = defaultdict(lambda: {
        'income': Decimal('0'),
        'business_expenses': Decimal('0'),
        'personal_expenses': Decimal('0'),
        'excluded': Decimal('0')
    })

    category_data = defaultdict(lambda: {'total': Decimal('0'), 'count': 0, 'type': None})

    # For detailed monthly, key by month label with year
    detailed_monthly = defaultdict(lambda: {
        'months': defaultdict(lambda: Decimal('0')),
        'total': Decimal('0'),
        'type': None
    })

    # Process each transaction
    for trans in transactions:
        month_num = trans.date.month
        # Get the appropriate month label
        if tax_year:
            # Find the index in TAX_YEAR_MONTHS
            for idx, (m_num, m_name) in enumerate(TAX_YEAR_MONTHS):
                if m_num == month_num:
                    month_label = month_labels[idx]
                    break
        else:
            month_label = MONTHS[month_num - 1]

        amount = trans.amount

        cat_name = trans.category.name if trans.category else 'Uncategorized'
        # Uncategorized transactions should be excluded (not counted in P&L)
        cat_type = trans.category.category_type if trans.category else 'excluded'

        # Update category data
        category_data[cat_name]['count'] += 1
        category_data[cat_name]['type'] = cat_type

        # Update monthly and detailed data based on category type
        if cat_type == 'income':
            monthly_data[month_num]['income'] += amount
            category_data[cat_name]['total'] += amount
        elif cat_type == 'business_expense':
            monthly_data[month_num]['business_expenses'] += abs(amount)
            category_data[cat_name]['total'] += abs(amount)
        elif cat_type == 'excluded':
            monthly_data[month_num]['excluded'] += abs(amount)
            category_data[cat_name]['total'] += abs(amount)
        else:  # personal_expense
            monthly_data[month_num]['personal_expenses'] += abs(amount)
            category_data[cat_name]['total'] += abs(amount)

        # Update detailed monthly (always store raw amount for detailed view)
        detailed_monthly[cat_name]['type'] = cat_type
        detailed_monthly[cat_name]['months'][month_label] += amount
        detailed_monthly[cat_name]['total'] += amount

    # Build monthly summary list in TAX YEAR ORDER (Mar-Feb)
    monthly_summary = []
    for idx, (month_num, month_name) in enumerate(TAX_YEAR_MONTHS):
        data = monthly_data[month_num]
        profit = data['income'] - data['business_expenses']
        monthly_summary.append({
            'month_name': month_labels[idx] if tax_year else month_name,
            'income': data['income'],
            'business_expenses': data['business_expenses'],
            'personal_expenses': data['personal_expenses'],
            'profit': profit
        })

    # Calculate totals
    totals = {
        'income': sum(m['income'] for m in monthly_summary),
        'business_expenses': sum(m['business_expenses'] for m in monthly_summary),
        'personal_expenses': sum(m['personal_expenses'] for m in monthly_summary),
        'expenses': sum(m['business_expenses'] for m in monthly_summary),
        'profit': sum(m['income'] for m in monthly_summary) - sum(m['business_expenses'] for m in monthly_summary)
    }

    # Build category summary grouped by type
    category_summary = {
        'income': _sort_categories(category_data, 'income'),
        'business_expenses': _sort_categories(category_data, 'business_expense'),
        'personal_expenses': _sort_categories(category_data, 'personal_expense'),
        'excluded': _sort_categories(category_data, 'excluded'),
    }

    # Sort detailed monthly by type then total - separate into groups
    income_categories = {}
    business_categories = {}
    personal_categories = {}
    excluded_categories = {}

    for cat_name, data in detailed_monthly.items():
        if data['type'] == 'income':
            income_categories[cat_name] = data
        elif data['type'] == 'business_expense':
            business_categories[cat_name] = data
        elif data['type'] == 'excluded':
            excluded_categories[cat_name] = data
        else:  # personal_expense
            personal_categories[cat_name] = data

    # Sort each group by total (descending)
    def sort_by_total(cat_dict):
        return dict(sorted(cat_dict.items(), key=lambda x: -abs(x[1]['total'])))

    return {
        'monthly_summary': monthly_summary,
        'totals': totals,
        'category_summary': category_summary,
        'detailed_monthly': {
            'income': sort_by_total(income_categories),
            'business': sort_by_total(business_categories),
            'personal': sort_by_total(personal_categories),
            'excluded': sort_by_total(excluded_categories),
        },
        'months': month_labels,
    }


def _sort_categories(category_data, category_type):
    """Sort categories of a specific type by total descending"""
    return sorted(
        [{'name': k, 'total': v['total'], 'count': v['count']}
         for k, v in category_data.items() if v['type'] == category_type],
        key=lambda x: x['total'],
        reverse=True
    )


def get_tax_year_dates(tax_year):
    """
    Get start and end dates for a SA tax year.
    Tax year 2026 runs from 1 March 2025 to 28 Feb 2026.
    """
    from datetime import date
    import calendar

    start_date = date(tax_year - 1, 3, 1)  # 1 March of previous year
    # Handle leap years for February
    last_day_feb = 29 if calendar.isleap(tax_year) else 28
    end_date = date(tax_year, 2, last_day_feb)  # 28/29 Feb of tax year

    return start_date, end_date


def get_available_tax_years(db_session, Transaction):
    """Get list of tax years that have transactions"""
    from sqlalchemy import func

    # Get min and max transaction dates
    result = db_session.query(
        func.min(Transaction.date),
        func.max(Transaction.date)
    ).filter(
        Transaction.is_deleted == False,
        Transaction.is_duplicate == False
    ).first()

    if not result or not result[0]:
        # Default to current tax year
        today = datetime.now().date()
        current_tax_year = today.year if today.month >= 3 else today.year
        return [current_tax_year]

    min_date, max_date = result

    # Calculate tax years that span these dates
    # A date falls in tax year X if it's between 1 Mar (X-1) and 28 Feb X
    tax_years = set()

    # For min_date: if March or later, tax year is next year; otherwise current year
    min_tax_year = min_date.year + 1 if min_date.month >= 3 else min_date.year
    max_tax_year = max_date.year + 1 if max_date.month >= 3 else max_date.year

    for ty in range(min_tax_year, max_tax_year + 1):
        tax_years.add(ty)

    return sorted(tax_years, reverse=True)


def get_available_years(db_session, Transaction):
    """Get list of tax years that have transactions (alias for compatibility)"""
    return get_available_tax_years(db_session, Transaction)


def get_transactions_for_year(Transaction, year):
    """Get all active transactions for a specific tax year (1 Mar to 28 Feb)"""
    start_date, end_date = get_tax_year_dates(year)

    return Transaction.query.filter(
        Transaction.is_deleted == False,
        Transaction.is_duplicate == False,
        Transaction.date >= start_date,
        Transaction.date <= end_date
    ).all()
