"""
Excel export functionality - generates the 11-table tax report
Based on provisional_tax_calc_system.md specifications
"""

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from datetime import datetime
from decimal import Decimal


def generate_tax_export(db, Transaction, Category, start_date, end_date, filename):
    """
    Generate Excel file with 11 tables for tax practitioner
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Tax Report"

    # Get all transactions for the period
    transactions = Transaction.query.filter(
        Transaction.date >= start_date,
        Transaction.date <= end_date,
        Transaction.is_deleted == False,
        Transaction.is_duplicate == False
    ).order_by(Transaction.date).all()

    # Organize by month
    months_in_period = get_months_in_period(start_date, end_date)
    trans_by_month = organize_by_month(transactions, months_in_period)

    # Determine if we need to extrapolate (for incomplete months)
    current_month = datetime.now().date().replace(day=1)
    last_month_in_period = months_in_period[-1]
    needs_extrapolation = last_month_in_period >= current_month

    # Build the 11 tables
    row = 1

    # TABLE 1: Monthly Income Summary
    row = write_table1_income_summary(ws, row, trans_by_month, months_in_period, needs_extrapolation)
    row += 2

    # TABLES 2-7: Individual Month Expense Details
    for month in months_in_period:
        row = write_month_detail_table(ws, row, month, trans_by_month[month])
        row += 2

    # TABLE 8: Monthly Business Expense Summary
    row = write_table8_business_summary(ws, row, trans_by_month, months_in_period)
    row += 2

    # TABLE 9: Monthly Personal Expense Summary
    row = write_table9_personal_summary(ws, row, trans_by_month, months_in_period)
    row += 2

    # TABLE 10: Monthly Net Profit Summary
    row = write_table10_net_profit(ws, row, trans_by_month, months_in_period)
    row += 2

    # TABLE 11: Annual Summary for Tax Calculation
    row = write_table11_annual_summary(ws, row, trans_by_month, start_date, end_date)

    # Save workbook
    output_path = f'/tmp/{filename}'
    wb.save(output_path)
    return output_path


def get_months_in_period(start_date, end_date):
    """Get list of month start dates in the period"""
    months = []
    current = start_date.replace(day=1)
    end = end_date.replace(day=1)

    while current <= end:
        months.append(current)
        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    return months


def organize_by_month(transactions, months):
    """Organize transactions by month"""
    trans_by_month = {month: [] for month in months}

    for trans in transactions:
        month_start = trans.date.replace(day=1)
        if month_start in trans_by_month:
            trans_by_month[month_start].append(trans)

    return trans_by_month


def write_table1_income_summary(ws, start_row, trans_by_month, months, needs_extrapolation):
    """Table 1: Monthly Income Summary"""
    row = start_row

    # Header
    ws.merge_cells(f'A{row}:D{row}')
    ws[f'A{row}'] = 'Table 1: Monthly Income Summary'
    ws[f'A{row}'].font = Font(bold=True, size=14)
    row += 1

    # Column headers
    headers = ['Month', 'Description', 'Amount (R)', 'Source']
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=col)
        cell.value = header
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color='CCCCCC', end_color='CCCCCC', fill_type='solid')
    row += 1

    total_income = Decimal('0')

    for month in months:
        # Get income transactions for this month
        income_trans = [t for t in trans_by_month[month]
                       if t.category and t.category.category_type == 'income']

        if income_trans:
            month_name = month.strftime('%b-%y')
            for trans in income_trans:
                ws.cell(row=row, column=1).value = month_name
                ws.cell(row=row, column=2).value = trans.description
                ws.cell(row=row, column=3).value = float(trans.amount)
                ws.cell(row=row, column=3).number_format = '#,##0.00'
                ws.cell(row=row, column=4).value = f"Statement {trans.statement.account.name}"
                total_income += trans.amount
                row += 1

    # Total row
    ws.cell(row=row, column=1).value = 'TOTAL'
    ws.cell(row=row, column=1).font = Font(bold=True)
    ws.cell(row=row, column=3).value = float(total_income)
    ws.cell(row=row, column=3).number_format = '#,##0.00'
    ws.cell(row=row, column=3).font = Font(bold=True)
    row += 1

    return row


def write_month_detail_table(ws, start_row, month, transactions):
    """Tables 2-7: Individual Month Expense Details"""
    row = start_row
    month_name = month.strftime('%B %Y')

    # Header
    ws.merge_cells(f'A{row}:E{row}')
    ws[f'A{row}'] = f'Expenses for {month_name}'
    ws[f'A{row}'].font = Font(bold=True, size=12)
    row += 1

    # Column headers
    headers = ['Category', 'Description', 'Amount (R)', 'Date', 'Source']
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=col)
        cell.value = header
        cell.font = Font(bold=True)
    row += 1

    # Business expenses
    ws.cell(row=row, column=1).value = 'BUSINESS EXPENSES'
    ws.cell(row=row, column=1).font = Font(bold=True, underline='single')
    row += 1

    business_trans = [t for t in transactions
                     if t.category and t.category.category_type == 'business_expense'
                     and float(t.amount) < 0]
    business_total = Decimal('0')

    for trans in business_trans:
        ws.cell(row=row, column=1).value = trans.category.name
        ws.cell(row=row, column=2).value = trans.description
        ws.cell(row=row, column=3).value = abs(float(trans.amount))
        ws.cell(row=row, column=3).number_format = '#,##0.00'
        ws.cell(row=row, column=4).value = trans.date.strftime('%d-%b')
        ws.cell(row=row, column=5).value = f"{trans.statement.account.account_type}"
        business_total += abs(trans.amount)
        row += 1

    # Business subtotal
    ws.cell(row=row, column=1).value = 'SUBTOTAL BUSINESS'
    ws.cell(row=row, column=1).font = Font(bold=True)
    ws.cell(row=row, column=3).value = float(business_total)
    ws.cell(row=row, column=3).number_format = '#,##0.00'
    ws.cell(row=row, column=3).font = Font(bold=True)
    row += 2

    # Personal expenses
    ws.cell(row=row, column=1).value = 'PERSONAL EXPENSES'
    ws.cell(row=row, column=1).font = Font(bold=True, underline='single')
    row += 1

    personal_trans = [t for t in transactions
                     if t.category and t.category.category_type == 'personal_expense'
                     and float(t.amount) < 0]
    personal_total = Decimal('0')

    for trans in personal_trans:
        ws.cell(row=row, column=1).value = trans.category.name
        ws.cell(row=row, column=2).value = trans.description
        ws.cell(row=row, column=3).value = abs(float(trans.amount))
        ws.cell(row=row, column=3).number_format = '#,##0.00'
        ws.cell(row=row, column=4).value = trans.date.strftime('%d-%b')
        ws.cell(row=row, column=5).value = f"{trans.statement.account.account_type}"
        personal_total += abs(trans.amount)
        row += 1

    # Personal subtotal
    ws.cell(row=row, column=1).value = 'SUBTOTAL PERSONAL'
    ws.cell(row=row, column=1).font = Font(bold=True)
    ws.cell(row=row, column=3).value = float(personal_total)
    ws.cell(row=row, column=3).number_format = '#,##0.00'
    ws.cell(row=row, column=3).font = Font(bold=True)
    row += 1

    return row


def write_table8_business_summary(ws, start_row, trans_by_month, months):
    """Table 8: Monthly Business Expense Summary"""
    row = start_row

    # Header
    ws.merge_cells(f'A{row}:H{row}')
    ws[f'A{row}'] = 'Table 8: Monthly Business Expense Summary'
    ws[f'A{row}'].font = Font(bold=True, size=14)
    row += 1

    # Column headers
    ws.cell(row=row, column=1).value = 'Category'
    ws.cell(row=row, column=1).font = Font(bold=True)

    for col, month in enumerate(months, start=2):
        ws.cell(row=row, column=col).value = month.strftime('%b-%y')
        ws.cell(row=row, column=col).font = Font(bold=True)

    ws.cell(row=row, column=len(months) + 2).value = 'Total'
    ws.cell(row=row, column=len(months) + 2).font = Font(bold=True)
    row += 1

    # Category rows
    from src.services.categorizer import CATEGORIES
    business_categories = [cat['name'] for cat in CATEGORIES.values() if cat['type'] == 'business_expense']

    for cat_name in business_categories:
        ws.cell(row=row, column=1).value = cat_name
        row_total = Decimal('0')

        for col, month in enumerate(months, start=2):
            month_trans = [t for t in trans_by_month[month]
                          if t.category and t.category.name == cat_name
                          and float(t.amount) < 0]
            month_total = sum([abs(t.amount) for t in month_trans], Decimal('0'))
            ws.cell(row=row, column=col).value = float(month_total)
            ws.cell(row=row, column=col).number_format = '#,##0.00'
            row_total += month_total

        ws.cell(row=row, column=len(months) + 2).value = float(row_total)
        ws.cell(row=row, column=len(months) + 2).number_format = '#,##0.00'
        row += 1

    # Monthly totals row
    ws.cell(row=row, column=1).value = 'MONTHLY TOTALS'
    ws.cell(row=row, column=1).font = Font(bold=True)

    for col, month in enumerate(months, start=2):
        month_trans = [t for t in trans_by_month[month]
                      if t.category and t.category.category_type == 'business_expense'
                      and float(t.amount) < 0]
        month_total = sum([abs(t.amount) for t in month_trans], Decimal('0'))
        ws.cell(row=row, column=col).value = float(month_total)
        ws.cell(row=row, column=col).number_format = '#,##0.00'
        ws.cell(row=row, column=col).font = Font(bold=True)

    row += 1
    return row


def write_table9_personal_summary(ws, start_row, trans_by_month, months):
    """Table 9: Monthly Personal Expense Summary (Excluded)"""
    row = start_row

    # Header
    ws.merge_cells(f'A{row}:H{row}')
    ws[f'A{row}'] = 'Table 9: Monthly Personal Expense Summary (Excluded from Tax)'
    ws[f'A{row}'].font = Font(bold=True, size=14)
    row += 1

    # Similar structure to Table 8 but for personal expenses
    ws.cell(row=row, column=1).value = 'Category'
    ws.cell(row=row, column=1).font = Font(bold=True)

    for col, month in enumerate(months, start=2):
        ws.cell(row=row, column=col).value = month.strftime('%b-%y')
        ws.cell(row=row, column=col).font = Font(bold=True)

    ws.cell(row=row, column=len(months) + 2).value = 'Total'
    ws.cell(row=row, column=len(months) + 2).font = Font(bold=True)
    row += 1

    # Personal categories
    from src.services.categorizer import CATEGORIES
    personal_categories = [cat['name'] for cat in CATEGORIES.values() if cat['type'] == 'personal_expense']

    for cat_name in personal_categories:
        ws.cell(row=row, column=1).value = cat_name
        row_total = Decimal('0')

        for col, month in enumerate(months, start=2):
            month_trans = [t for t in trans_by_month[month]
                          if t.category and t.category.name == cat_name
                          and float(t.amount) < 0]
            month_total = sum([abs(t.amount) for t in month_trans], Decimal('0'))
            ws.cell(row=row, column=col).value = float(month_total)
            ws.cell(row=row, column=col).number_format = '#,##0.00'
            row_total += month_total

        ws.cell(row=row, column=len(months) + 2).value = float(row_total)
        ws.cell(row=row, column=len(months) + 2).number_format = '#,##0.00'
        row += 1

    row += 1
    return row


def write_table10_net_profit(ws, start_row, trans_by_month, months):
    """Table 10: Monthly Net Profit Summary"""
    row = start_row

    # Header
    ws.merge_cells(f'A{row}:D{row}')
    ws[f'A{row}'] = 'Table 10: Monthly Net Profit Summary'
    ws[f'A{row}'].font = Font(bold=True, size=14)
    row += 1

    # Column headers
    headers = ['Month', 'Income (R)', 'Business Expenses (R)', 'Net Profit (R)']
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=col)
        cell.value = header
        cell.font = Font(bold=True)
    row += 1

    period_income = Decimal('0')
    period_expenses = Decimal('0')

    for month in months:
        # Income
        income_trans = [t for t in trans_by_month[month]
                       if t.category and t.category.category_type == 'income']
        month_income = sum([t.amount for t in income_trans], Decimal('0'))

        # Business expenses
        expense_trans = [t for t in trans_by_month[month]
                        if t.category and t.category.category_type == 'business_expense'
                        and float(t.amount) < 0]
        month_expenses = sum([abs(t.amount) for t in expense_trans], Decimal('0'))

        net_profit = month_income - month_expenses

        ws.cell(row=row, column=1).value = month.strftime('%b-%y')
        ws.cell(row=row, column=2).value = float(month_income)
        ws.cell(row=row, column=2).number_format = '#,##0.00'
        ws.cell(row=row, column=3).value = float(month_expenses)
        ws.cell(row=row, column=3).number_format = '#,##0.00'
        ws.cell(row=row, column=4).value = float(net_profit)
        ws.cell(row=row, column=4).number_format = '#,##0.00'

        period_income += month_income
        period_expenses += month_expenses
        row += 1

    # Total row
    ws.cell(row=row, column=1).value = 'TOTAL'
    ws.cell(row=row, column=1).font = Font(bold=True)
    ws.cell(row=row, column=2).value = float(period_income)
    ws.cell(row=row, column=2).number_format = '#,##0.00'
    ws.cell(row=row, column=2).font = Font(bold=True)
    ws.cell(row=row, column=3).value = float(period_expenses)
    ws.cell(row=row, column=3).number_format = '#,##0.00'
    ws.cell(row=row, column=3).font = Font(bold=True)
    ws.cell(row=row, column=4).value = float(period_income - period_expenses)
    ws.cell(row=row, column=4).number_format = '#,##0.00'
    ws.cell(row=row, column=4).font = Font(bold=True)
    row += 1

    return row


def write_table11_annual_summary(ws, start_row, trans_by_month, start_date, end_date):
    """Table 11: Annual Summary for Tax Calculation"""
    row = start_row

    # Header
    ws.merge_cells(f'A{row}:B{row}')
    ws[f'A{row}'] = 'Table 11: Annual Summary for Tax Calculation'
    ws[f'A{row}'].font = Font(bold=True, size=14)
    row += 1

    # Calculate totals from all months
    all_income = Decimal('0')
    all_expenses = Decimal('0')

    for month_trans in trans_by_month.values():
        income_trans = [t for t in month_trans
                       if t.category and t.category.category_type == 'income']
        all_income += sum([t.amount for t in income_trans], Decimal('0'))

        expense_trans = [t for t in month_trans
                        if t.category and t.category.category_type == 'business_expense'
                        and float(t.amount) < 0]
        all_expenses += sum([abs(t.amount) for t in expense_trans], Decimal('0'))

    # Annualize (multiply by 2 since this is 6 months)
    annualized_income = all_income * 2
    annualized_expenses = all_expenses * 2
    annualized_profit = annualized_income - annualized_expenses

    ws.cell(row=row, column=1).value = 'Description'
    ws.cell(row=row, column=1).font = Font(bold=True)
    ws.cell(row=row, column=2).value = 'Amount (R)'
    ws.cell(row=row, column=2).font = Font(bold=True)
    row += 1

    ws.cell(row=row, column=1).value = f'Period Income ({start_date.strftime("%b %Y")} - {end_date.strftime("%b %Y")})'
    ws.cell(row=row, column=2).value = float(all_income)
    ws.cell(row=row, column=2).number_format = '#,##0.00'
    row += 1

    ws.cell(row=row, column=1).value = f'Period Expenses ({start_date.strftime("%b %Y")} - {end_date.strftime("%b %Y")})'
    ws.cell(row=row, column=2).value = float(all_expenses)
    ws.cell(row=row, column=2).number_format = '#,##0.00'
    row += 1

    ws.cell(row=row, column=1).value = 'Period Net Profit'
    ws.cell(row=row, column=2).value = float(all_income - all_expenses)
    ws.cell(row=row, column=2).number_format = '#,##0.00'
    row += 2

    ws.cell(row=row, column=1).value = 'Annualized Income (Projected)'
    ws.cell(row=row, column=1).font = Font(bold=True)
    ws.cell(row=row, column=2).value = float(annualized_income)
    ws.cell(row=row, column=2).number_format = '#,##0.00'
    ws.cell(row=row, column=2).font = Font(bold=True)
    row += 1

    ws.cell(row=row, column=1).value = 'Annualized Expenses (Projected)'
    ws.cell(row=row, column=1).font = Font(bold=True)
    ws.cell(row=row, column=2).value = float(annualized_expenses)
    ws.cell(row=row, column=2).number_format = '#,##0.00'
    ws.cell(row=row, column=2).font = Font(bold=True)
    row += 1

    ws.cell(row=row, column=1).value = 'Annualized Net Profit (for Provisional Tax)'
    ws.cell(row=row, column=1).font = Font(bold=True)
    ws.cell(row=row, column=2).value = float(annualized_profit)
    ws.cell(row=row, column=2).number_format = '#,##0.00'
    ws.cell(row=row, column=2).font = Font(bold=True)
    row += 1

    return row
