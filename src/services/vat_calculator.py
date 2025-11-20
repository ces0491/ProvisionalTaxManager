"""
VAT Calculator for South African VAT (Value Added Tax)

Handles:
- Standard-rated supplies (currently 15%)
- Zero-rated supplies (0%)
- Exempt supplies (no VAT)
- Input VAT (claimable on purchases)
- Output VAT (on sales)
- VAT extraction from amounts
"""
from decimal import Decimal
from datetime import date
from typing import Dict, Any, List


def get_vat_rate_for_date(transaction_date: date, rate_type: str = 'standard', db_session=None) -> Decimal:
    """
    Get the applicable VAT rate for a specific date

    Args:
        transaction_date: Date of the transaction
        rate_type: 'standard', 'zero', 'exempt', or 'no_vat'
        db_session: Database session for loading rates from database

    Returns:
        VAT rate as decimal (e.g., 0.15 for 15%)
    """
    if rate_type in ['zero', 'exempt', 'no_vat']:
        return Decimal('0')

    # Try to load from database
    if db_session:
        try:
            from models import VATConfig

            # Find the VAT rate effective on this date
            vat_config = VATConfig.query.filter(
                VATConfig.effective_from <= transaction_date,
                (VATConfig.effective_to.is_(None) | (VATConfig.effective_to >= transaction_date))
            ).order_by(VATConfig.effective_from.desc()).first()

            if vat_config:
                return vat_config.standard_rate
        except Exception:
            pass

    # Fallback to current rate
    return Decimal('0.15')  # 15% standard rate


def calculate_vat_from_inclusive(amount_incl_vat: Decimal, vat_rate: Decimal) -> Dict[str, Decimal]:
    """
    Calculate VAT components when amount includes VAT

    Args:
        amount_incl_vat: Total amount including VAT
        vat_rate: VAT rate (e.g., 0.15 for 15%)

    Returns:
        Dictionary with amount_excl_vat, vat_amount, amount_incl_vat
    """
    if vat_rate == 0:
        return {
            'amount_excl_vat': amount_incl_vat,
            'vat_amount': Decimal('0'),
            'amount_incl_vat': amount_incl_vat
        }

    # Formula: excl = incl / (1 + rate)
    amount_excl_vat = amount_incl_vat / (1 + vat_rate)
    vat_amount = amount_incl_vat - amount_excl_vat

    return {
        'amount_excl_vat': amount_excl_vat.quantize(Decimal('0.01')),
        'vat_amount': vat_amount.quantize(Decimal('0.01')),
        'amount_incl_vat': amount_incl_vat
    }


def calculate_vat_from_exclusive(amount_excl_vat: Decimal, vat_rate: Decimal) -> Dict[str, Decimal]:
    """
    Calculate VAT components when amount excludes VAT

    Args:
        amount_excl_vat: Amount excluding VAT
        vat_rate: VAT rate (e.g., 0.15 for 15%)

    Returns:
        Dictionary with amount_excl_vat, vat_amount, amount_incl_vat
    """
    if vat_rate == 0:
        return {
            'amount_excl_vat': amount_excl_vat,
            'vat_amount': Decimal('0'),
            'amount_incl_vat': amount_excl_vat
        }

    # Formula: vat = excl * rate
    vat_amount = amount_excl_vat * vat_rate
    amount_incl_vat = amount_excl_vat + vat_amount

    return {
        'amount_excl_vat': amount_excl_vat,
        'vat_amount': vat_amount.quantize(Decimal('0.01')),
        'amount_incl_vat': amount_incl_vat.quantize(Decimal('0.01'))
    }


def calculate_transaction_vat(
    transaction: Dict[str, Any],
    db_session=None
) -> Dict[str, Any]:
    """
    Calculate VAT for a transaction

    Args:
        transaction: Transaction dict with amount, date, vat_rate_type, amount_incl_vat
        db_session: Database session for loading VAT rates

    Returns:
        Transaction dict enriched with VAT calculations
    """
    amount = Decimal(str(transaction.get('amount', 0)))
    trans_date = transaction.get('date', date.today())
    vat_rate_type = transaction.get('vat_rate_type', 'standard')
    amount_incl_vat = transaction.get('amount_incl_vat', True)

    # Get applicable VAT rate
    vat_rate = get_vat_rate_for_date(trans_date, vat_rate_type, db_session)

    # Calculate VAT components
    if amount_incl_vat:
        vat_calc = calculate_vat_from_inclusive(abs(amount), vat_rate)
    else:
        vat_calc = calculate_vat_from_exclusive(abs(amount), vat_rate)

    # Preserve sign (negative for expenses, positive for income)
    sign = -1 if amount < 0 else 1

    return {
        **transaction,
        'vat_rate': vat_rate,
        'vat_rate_percent': float(vat_rate * 100),
        'amount_excl_vat': vat_calc['amount_excl_vat'] * sign,
        'vat_amount': vat_calc['vat_amount'] * sign,
        'amount_incl_vat': vat_calc['amount_incl_vat'] * sign
    }


def calculate_vat_summary(
    transactions: List[Dict[str, Any]],
    period_start: date,
    period_end: date,
    db_session=None
) -> Dict[str, Any]:
    """
    Calculate VAT summary for a period (for VAT201 return)

    Args:
        transactions: List of transactions
        period_start: Start of VAT period
        period_end: End of VAT period
        db_session: Database session

    Returns:
        VAT summary with output VAT, input VAT, net VAT
    """
    # Filter transactions in period
    period_transactions = [
        t for t in transactions
        if period_start <= t.get('date', date.today()) <= period_end
    ]

    # Calculate VAT for each transaction
    enriched_transactions = [
        calculate_transaction_vat(t, db_session)
        for t in period_transactions
    ]

    # Summarize by VAT rate type
    output_vat_total = Decimal('0')  # VAT on sales (you charge customers)
    input_vat_total = Decimal('0')   # VAT on purchases (you claim back)

    output_vat_by_rate = {}
    input_vat_by_rate = {}

    for trans in enriched_transactions:
        amount = Decimal(str(trans.get('amount', 0)))
        vat_amount = Decimal(str(trans.get('vat_amount', 0)))
        vat_rate_type = trans.get('vat_rate_type', 'standard')
        is_vat_claimable = trans.get('is_vat_claimable', True)

        if amount > 0:  # Income/Sales - Output VAT
            output_vat_total += abs(vat_amount)
            if vat_rate_type not in output_vat_by_rate:
                output_vat_by_rate[vat_rate_type] = Decimal('0')
            output_vat_by_rate[vat_rate_type] += abs(vat_amount)

        elif amount < 0 and is_vat_claimable:  # Expenses - Input VAT (claimable)
            input_vat_total += abs(vat_amount)
            if vat_rate_type not in input_vat_by_rate:
                input_vat_by_rate[vat_rate_type] = Decimal('0')
            input_vat_by_rate[vat_rate_type] += abs(vat_amount)

    # Net VAT = Output VAT - Input VAT
    # Positive = you owe SARS, Negative = SARS owes you (refund)
    net_vat = output_vat_total - input_vat_total

    return {
        'period_start': period_start,
        'period_end': period_end,
        'output_vat': output_vat_total.quantize(Decimal('0.01')),
        'input_vat': input_vat_total.quantize(Decimal('0.01')),
        'net_vat': net_vat.quantize(Decimal('0.01')),
        'output_vat_by_rate': output_vat_by_rate,
        'input_vat_by_rate': input_vat_by_rate,
        'transactions': enriched_transactions,
        'transaction_count': len(enriched_transactions)
    }


def format_vat_amount(amount: Decimal) -> str:
    """Format amount for display"""
    return f"R{abs(amount):,.2f}"
