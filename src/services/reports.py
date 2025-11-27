"""
Financial reporting service
Generates summaries for income, expenses, and categories
"""
from decimal import Decimal
from collections import defaultdict
from datetime import datetime

# Month name constants
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def aggregate_transactions(transactions):
    """
    Aggregate transactions into monthly and category summaries.

    Args:
        transactions: List of Transaction objects with category relationships

    Returns:
        Dictionary containing:
        - monthly_summary: List of monthly income/expense/profit data
        - totals: Total income, expenses, profit
        - category_summary: Categories grouped by type with totals
        - detailed_monthly: Monthly breakdown by category
    """
    # Initialize data structures
    monthly_data = defaultdict(lambda: {
        'income': Decimal('0'),
        'business_expenses': Decimal('0'),
        'personal_expenses': Decimal('0'),
        'excluded': Decimal('0')
    })

    category_data = defaultdict(lambda: {'total': Decimal('0'), 'count': 0, 'type': None})

    detailed_monthly = defaultdict(lambda: {
        'months': defaultdict(lambda: Decimal('0')),
        'total': Decimal('0'),
        'type': None
    })

    # Process each transaction
    for trans in transactions:
        month_idx = trans.date.month - 1
        month_name = MONTHS[month_idx]
        amount = trans.amount

        cat_name = trans.category.name if trans.category else 'Uncategorized'
        cat_type = trans.category.category_type if trans.category else 'personal_expense'

        # Update category data
        category_data[cat_name]['count'] += 1
        category_data[cat_name]['type'] = cat_type

        # Update monthly and detailed data based on category type
        if cat_type == 'income':
            monthly_data[month_idx]['income'] += amount
            category_data[cat_name]['total'] += amount
        elif cat_type == 'business_expense':
            monthly_data[month_idx]['business_expenses'] += abs(amount)
            category_data[cat_name]['total'] += abs(amount)
        elif cat_type == 'excluded':
            monthly_data[month_idx]['excluded'] += abs(amount)
            category_data[cat_name]['total'] += abs(amount)
        else:  # personal_expense
            monthly_data[month_idx]['personal_expenses'] += abs(amount)
            category_data[cat_name]['total'] += abs(amount)

        # Update detailed monthly (always store raw amount for detailed view)
        detailed_monthly[cat_name]['type'] = cat_type
        detailed_monthly[cat_name]['months'][month_name] += amount
        detailed_monthly[cat_name]['total'] += amount

    # Build monthly summary list
    monthly_summary = []
    for i, month_name in enumerate(MONTHS):
        data = monthly_data[i]
        profit = data['income'] - data['business_expenses']
        monthly_summary.append({
            'month_name': month_name,
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

    # Sort detailed monthly by type then total
    detailed_monthly_sorted = dict(sorted(
        detailed_monthly.items(),
        key=lambda x: (
            0 if x[1]['type'] == 'income' else
            1 if x[1]['type'] == 'business_expense' else 2,
            -abs(x[1]['total'])
        )
    ))

    return {
        'monthly_summary': monthly_summary,
        'totals': totals,
        'category_summary': category_summary,
        'detailed_monthly': detailed_monthly_sorted,
        'months': MONTHS,
    }


def _sort_categories(category_data, category_type):
    """Sort categories of a specific type by total descending"""
    return sorted(
        [{'name': k, 'total': v['total'], 'count': v['count']}
         for k, v in category_data.items() if v['type'] == category_type],
        key=lambda x: x['total'],
        reverse=True
    )


def get_available_years(db_session, Transaction):
    """Get list of years that have transactions"""
    from sqlalchemy import func, extract

    years_query = db_session.query(
        func.distinct(extract('year', Transaction.date))
    ).filter(
        Transaction.is_deleted == False,
        Transaction.is_duplicate == False
    ).all()

    years = sorted([int(y[0]) for y in years_query if y[0]], reverse=True)
    return years if years else [datetime.now().year]


def get_transactions_for_year(Transaction, year):
    """Get all active transactions for a specific year"""
    from sqlalchemy import extract

    return Transaction.query.filter(
        Transaction.is_deleted == False,
        Transaction.is_duplicate == False,
        extract('year', Transaction.date) == year
    ).all()
