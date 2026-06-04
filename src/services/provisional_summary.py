"""Builds the provisional-tax summary data structure shared by the in-app view
and the Excel export, so the on-screen figures and the exported workbook always
match. The structure carries the audited end-state (income, deductible expenses,
home-office apportionment, medical credit) plus the audit trail (per-month
transaction detail and a category x month grid).
"""
from collections import defaultdict
from datetime import date
from decimal import Decimal

from src.services.tax_calculator import (
    HOME_OFFICE_CATEGORIES,
    INSURANCE_CATEGORY,
    insurance_deductible_amount,
    DEFAULT_HOME_OFFICE_SQM,
    DEFAULT_HOUSE_TOTAL_SQM,
)

# Medical contributions/fees are not deductible - they support the medical tax
# credit (applied per member), so they are reported separately, never deducted.
MEDICAL_CATEGORIES = {'Medical Aid', 'Medical Fees'}


def office_pct():
    return (DEFAULT_HOME_OFFICE_SQM / DEFAULT_HOUSE_TOTAL_SQM) if DEFAULT_HOUSE_TOTAL_SQM else Decimal('0')


def qualifying_deductible(t):
    """Qualifying deductible portion of a transaction BEFORE home-office
    apportionment, using the signed expense impact (a debit is a positive
    expense; a refund/credit is negative and nets off). Insurance is reduced to
    its deductible building/household-contents portion. Non-business-expense
    transactions return 0."""
    if not t.category or t.category.category_type != 'business_expense':
        return Decimal('0')
    amt = -Decimal(str(t.amount))
    if t.category.name == INSURANCE_CATEGORY:
        return insurance_deductible_amount(t.description, amt)
    return amt


def claimed_deductible(t, pct=None):
    """Final claimed amount: qualifying, with home-office categories apportioned."""
    if pct is None:
        pct = office_pct()
    q = qualifying_deductible(t)
    if t.category and t.category.name in HOME_OFFICE_CATEGORIES:
        return q * pct
    return q


def months_in_period(start_date, end_date):
    """Month-start dates from start to end (inclusive)."""
    months = []
    y, m = start_date.year, start_date.month
    while (y, m) <= (end_date.year, end_date.month):
        months.append(date(y, m, 1))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return months


def build_provisional_summary(transactions, start_date, end_date):
    """Aggregate active transactions into the provisional summary + audit trail.

    `transactions` is any iterable of Transaction-like objects with category,
    description, amount, date, statement.account, is_deleted, is_duplicate.
    """
    pct = office_pct()
    txns = [t for t in transactions if not t.is_deleted and not t.is_duplicate]

    income_by_month = defaultdict(lambda: Decimal('0'))
    expense_by_category = defaultdict(lambda: Decimal('0'))
    home_office_base = defaultdict(lambda: Decimal('0'))
    medical_by_category = defaultdict(lambda: Decimal('0'))
    detail_by_month = defaultdict(list)  # month-start -> list of business expense txns

    for t in txns:
        cat = t.category.name if t.category else 'Uncategorized'
        ctype = t.category.category_type if t.category else 'personal_expense'
        if cat in MEDICAL_CATEGORIES:
            medical_by_category[cat] += abs(Decimal(str(t.amount)))
        elif ctype == 'income':
            income_by_month[t.date.strftime('%Y-%m')] += abs(Decimal(str(t.amount)))
        elif ctype == 'business_expense':
            q = qualifying_deductible(t)
            if cat in HOME_OFFICE_CATEGORIES:
                home_office_base[cat] += q
            else:
                expense_by_category[cat] += q
            detail_by_month[date(t.date.year, t.date.month, 1)].append(t)

    ho_subtotal = sum(home_office_base.values(), Decimal('0'))
    ho_deduction = (ho_subtotal * pct).quantize(Decimal('0.01'))
    total_income = sum(income_by_month.values(), Decimal('0'))
    total_expenses = sum(expense_by_category.values(), Decimal('0')) + ho_deduction
    net_profit = total_income - total_expenses

    months = months_in_period(start_date, end_date)

    # Per-month transaction detail (raw lines with statement amount vs deductible)
    detail = []
    for mth in months:
        rows = []
        gross_sub = Decimal('0')
        ded_sub = Decimal('0')
        for t in sorted(detail_by_month.get(mth, []), key=lambda x: x.date):
            gross = -Decimal(str(t.amount))
            ded = qualifying_deductible(t)
            source = t.statement.account.account_type if t.statement and t.statement.account else ''
            rows.append({
                'category': t.category.name, 'description': t.description,
                'amount': gross, 'deductible': ded, 'date': t.date, 'source': source,
            })
            gross_sub += gross
            ded_sub += ded
        detail.append({'month': mth, 'rows': rows,
                       'gross_subtotal': gross_sub, 'deductible_subtotal': ded_sub})

    # Category x month grid of qualifying deductibles (before apportionment)
    grid_rows = []
    cats = sorted({t.category.name for t in txns
                   if t.category and t.category.category_type == 'business_expense'})
    for c in cats:
        vals = []
        row_total = Decimal('0')
        for mth in months:
            v = sum((qualifying_deductible(t) for t in detail_by_month.get(mth, [])
                     if t.category.name == c), Decimal('0'))
            vals.append(v)
            row_total += v
        if row_total != 0:
            grid_rows.append({'category': c, 'amounts': vals, 'total': row_total})
    monthly_totals = [sum((qualifying_deductible(t) for t in detail_by_month.get(mth, [])),
                          Decimal('0')) for mth in months]
    grand_total = sum(monthly_totals, Decimal('0'))

    return {
        'start_date': start_date,
        'end_date': end_date,
        'income_by_month': [(mth.strftime('%b %Y'),
                             income_by_month.get(mth.strftime('%Y-%m'), Decimal('0')))
                            for mth in months],
        'total_income': total_income,
        'expenses': sorted(expense_by_category.items()),
        'home_office': {
            'components': sorted(home_office_base.items()),
            'subtotal': ho_subtotal,
            'office_sqm': DEFAULT_HOME_OFFICE_SQM,
            'house_sqm': DEFAULT_HOUSE_TOTAL_SQM,
            'office_pct': pct,
            'deduction': ho_deduction,
        },
        'home_office_line': ho_deduction,
        'total_expenses': total_expenses,
        'net_profit': net_profit,
        'medical': sorted(medical_by_category.items()),
        'months': months,
        'detail_by_month': detail,
        'grid': {'rows': grid_rows, 'monthly_totals': monthly_totals, 'grand_total': grand_total},
        'insurance_category': INSURANCE_CATEGORY,
    }
