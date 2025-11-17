# VAT System Guide

Complete guide to VAT (Value Added Tax) functionality in the Provisional Tax Manager.

## Overview

The application now supports full VAT tracking and reporting for VAT-registered vendors, with features specifically designed for your use case:

- **Your Status**: VAT-registered vendor (R1M+ turnover)
- **Current Supplies**: Zero-rated (foreign income)
- **Input VAT**: Fully claimable on business expenses
- **Filing Frequency**: 6-monthly (bi-annual)
- **VAT Rate**: Configurable (currently 15%, historically 14%)

## Database Schema

### VAT Tables

**VATConfig**: Historical and current VAT rates

- `effective_from`: Date rate became effective
- `effective_to`: Date rate ended (NULL for current rate)
- `standard_rate`: Rate as decimal (0.15 = 15%)
- Historical: 14% (1993-2018), Current: 15% (2018-present)

**VATPeriod**: VAT return filing periods

- `period_name`: "VAT Jan-Jun 2025"
- `start_date`, `end_date`: Period dates
- `due_date`: Return submission deadline
- `output_vat`: VAT on sales
- `input_vat`: VAT on purchases (claimable)
- `net_vat`: Amount payable/(refundable)

### Transaction VAT Fields

**Category.default_vat_rate**:

- 'standard': 15% VAT
- 'zero': 0% VAT (exports, certain basic foods)
- 'exempt': No VAT (financial services, residential rent)
- 'no_vat': Not subject to VAT

**Transaction VAT fields**:

- `vat_rate_type`: Override category default
- `vat_amount`: Calculated VAT (or manual override)
- `amount_incl_vat`: Whether transaction amount includes VAT
- `is_vat_claimable`: Can claim input VAT on this purchase

## How VAT is Calculated

### Standard-Rated Supplies (15%)

**Amount Includes VAT** (most common for expenses):

```python
Amount incl VAT: R1,150.00
Amount excl VAT: R1,150.00 / 1.15 = R1,000.00
VAT Amount: R1,150.00 - R1,000.00 = R150.00
```

**Amount Excludes VAT** (common for sales/invoices):

```python
Amount excl VAT: R1,000.00
VAT Amount: R1,000.00 × 0.15 = R150.00
Amount incl VAT: R1,000.00 + R150.00 = R1,150.00
```

### Zero-Rated Supplies (0%)

Your foreign income falls here:

```python
Amount: R100,000.00
VAT: R0.00 (zero-rated export)
Claimable input VAT: Yes (on related expenses)
```

## Usage Examples

### Example 1: Foreign Income (Zero-Rated)

```python
transaction = {
    'date': date(2025, 3, 15),
    'description': 'PAYPAL USD PAYMENT',
    'amount': Decimal('100000.00'),  # R100k foreign income
    'category': 'Income',
    'vat_rate_type': 'zero',  # Zero-rated export
    'amount_incl_vat': False
}

# VAT calculation
vat_calc = calculate_transaction_vat(transaction)
# Result:
# - amount_excl_vat: R100,000.00
# - vat_amount: R0.00
# - amount_incl_vat: R100,000.00
```

### Example 2: Business Expense (Standard-Rated, Claimable)

```python
transaction = {
    'date': date(2025, 3, 20),
    'description': 'GOOGLE WORKSPACE',
    'amount': Decimal('-115.00'),  # R115 incl VAT
    'category': 'Technology/Software',
    'vat_rate_type': 'standard',
    'amount_incl_vat': True,  # Statement amount includes VAT
    'is_vat_claimable': True  # Can claim this back
}

# VAT calculation
vat_calc = calculate_transaction_vat(transaction)
# Result:
# - amount_excl_vat: -R100.00
# - vat_amount: -R15.00 (claimable)
# - amount_incl_vat: -R115.00
```

### Example 3: Personal Expense (Not Claimable)

```python
transaction = {
    'date': date(2025, 3, 25),
    'description': 'NETFLIX SUBSCRIPTION',
    'amount': Decimal('-99.00'),
    'category': 'Entertainment',
    'vat_rate_type': 'standard',
    'amount_incl_vat': True,
    'is_vat_claimable': False  # Personal - cannot claim VAT
}

# VAT shows in breakdown but not claimed on VAT return
```

## VAT Return (VAT201) Calculation

For a 6-month period, the system calculates:

```python
from vat_calculator import calculate_vat_summary

summary = calculate_vat_summary(
    transactions=all_transactions,
    period_start=date(2025, 1, 1),
    period_end=date(2025, 6, 30),
    db_session=db.session
)

# Result:
{
    'output_vat': Decimal('0.00'),      # VAT on sales (zero-rated)
    'input_vat': Decimal('5000.00'),    # VAT on purchases (claimable)
    'net_vat': Decimal('-5000.00'),     # Refund due from SARS
    'output_vat_by_rate': {
        'zero': Decimal('0.00')
    },
    'input_vat_by_rate': {
        'standard': Decimal('5000.00')
    }
}
```

## VAT Rates by Category

Recommended default VAT rates for common categories:

### Zero-Rated (0%)

- **Income (Foreign)**: Zero-rated exports
- **Basic Foods**: Certain staples (bread, maize meal, etc.)

### Standard-Rated (15%)

- **Technology/Software**: Google, Microsoft, etc.
- **Internet**: Afrihost, etc.
- **Professional Services**: Consultants, accountants
- **Most Business Expenses**

### Exempt (No VAT)

- **Financial Services**: Bank fees, insurance (some)
- **Residential Rent**: Accommodation

### No VAT

- **Medical Aid**: Not subject to VAT
- **International Transactions**: Some foreign services

## Viewing Transactions With/Without VAT

The system allows you to toggle VAT display:

### Incl VAT (Default View)

Shows actual bank statement amounts:

```
Date       Description          Amount
2025-03-20 GOOGLE WORKSPACE    -R115.00
```

### Excl VAT View

Shows amounts excluding VAT for accounting:

```
Date       Description          Amount Excl  VAT      Amount Incl
2025-03-20 GOOGLE WORKSPACE    -R100.00     -R15.00  -R115.00
```

## Configuration

### Update VAT Rate (If It Changes)

When SARS announces a rate change:

```python
from models import VATConfig
from datetime import date
from decimal import Decimal

# Close current rate
current = VATConfig.query.filter_by(is_active=True).first()
current.effective_to = date(2026, 3, 31)
current.is_active = False

# Add new rate
new_rate = VATConfig(
    effective_from=date(2026, 4, 1),
    effective_to=None,
    standard_rate=Decimal('0.16'),  # Example: 16%
    is_active=True,
    notes='VAT increased to 16% per 2026 Budget'
)
db.session.add(new_rate)
db.session.commit()
```

### Set Category VAT Defaults

```python
from models import Category

# Set income as zero-rated
income = Category.query.filter_by(name='Income').first()
income.default_vat_rate = 'zero'

# Set technology as standard-rated
tech = Category.query.filter_by(name='Technology/Software').first()
tech.default_vat_rate = 'standard'

db.session.commit()
```

## VAT Periods (6-Monthly Filing)

Your filing periods:

- **Period 1**: January - June (due 25 July)
- **Period 2**: July - December (due 25 January)

## Integration with Income Tax

VAT and Income Tax are separate:

**Income Tax Calculation**:

- Uses amounts **excluding VAT**
- Only VAT-exclusive amounts are taxable income/deductible expenses

**Example**:

```
Transaction: -R1,150 (incl VAT)
VAT (15%): -R150
Amount excl VAT: -R1,000

Income Tax Deduction: R1,000 (not R1,150)
VAT Claim: R150 (separate from income tax)
```

## Common Scenarios

### Scenario 1: You Only Have Foreign Income (Current)

- **Sales**: Zero-rated (0% VAT charged to foreign clients)
- **Purchases**: Standard-rated (15% VAT on local expenses)
- **VAT Position**: Refund every period (input VAT > output VAT)

### Scenario 2: You Start Charging VAT on Local Sales (Future)

- **Foreign Sales**: Still zero-rated
- **Local Sales**: Standard-rated (15% VAT charged)
- **Purchases**: Standard-rated (15% VAT claimable)
- **VAT Position**: May owe SARS if output VAT > input VAT

## Best Practices

1. **Always Specify VAT Rate Type**: Don't rely only on category defaults
2. **Mark Non-Claimable Expenses**: Personal expenses, entertainment
3. **Reconcile Monthly**: Even if filing 6-monthly
4. **Keep Proof**: Tax invoices for all input VAT claims
5. **Separate Personal**: Only claim VAT on business expenses

## Future Enhancements

Planned features:

1. **VAT Return (VAT201) Export**: Generate SARS eFiling format
2. **VAT Reconciliation**: Compare calculated vs submitted
3. **VAT on Imports**: Handle customs VAT
4. **Provisional VAT**: For VAT vending if required
5. **Web UI**: Manage VAT rates and periods through interface

## SARS Resources

- **VAT Guide**: <https://www.sars.gov.za/types-of-tax/value-added-tax/>
- **VAT Rates**: <https://www.sars.gov.za/tax-rates/vat/vat-rates/>
- **eFiling**: <https://www.sarsefiling.co.za>
- **VAT201 Form**: Available on eFiling portal

## Questions?

Common questions answered:

**Q: What if I make a mistake in VAT classification?**
A: Edit the transaction and change vat_rate_type. Historical calculations will update.

**Q: Can I use 14% rate for old transactions?**
A: Yes! The system automatically applies historical rates based on transaction date.

**Q: What if I'm not sure if something is zero-rated or exempt?**
A: Check SARS VAT Guide. General rule: zero-rated = can claim input VAT, exempt = cannot claim.

**Q: How do I handle VAT on foreign currency transactions?**
A: Convert to ZAR first, then apply VAT rules. Zero-rated exports have 0% VAT regardless of currency.
