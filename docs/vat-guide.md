# VAT System Guide

VAT (Value Added Tax) tracking and reporting for VAT-registered vendors.

## Overview

- **Current Status**: VAT-registered vendor (R1M+ turnover)
- **Current Supplies**: Zero-rated (foreign income)
- **Input VAT**: Fully claimable on business expenses
- **Filing Frequency**: 6-monthly (bi-annual)
- **VAT Rate**: 15% (historically 14% until 2018)

## Database Schema

### VATConfig

Historical and current VAT rates:

| Field | Description |
|-------|-------------|
| `effective_from` | Date rate became effective |
| `effective_to` | Date rate ended (NULL for current) |
| `standard_rate` | Rate as decimal (0.15 = 15%) |
| `is_active` | Currently active rate |

### Category VAT Defaults

Categories have a `default_vat_rate` field:

- `'standard'`: 15% VAT
- `'zero'`: 0% VAT (exports, certain basic foods)
- `'exempt'`: No VAT (financial services, residential rent)
- `'no_vat'`: Not subject to VAT

### Transaction VAT Fields

| Field | Description |
|-------|-------------|
| `vat_rate_type` | Override category default |
| `vat_amount` | Calculated VAT (or manual override) |
| `amount_incl_vat` | Whether amount includes VAT |
| `is_vat_claimable` | Can claim input VAT |

## VAT Calculation

### Standard-Rated (15%)

**Amount Includes VAT** (most expenses):
```
Amount incl VAT: R1,150.00
Amount excl VAT: R1,150.00 / 1.15 = R1,000.00
VAT Amount: R150.00
```

**Amount Excludes VAT** (sales/invoices):
```
Amount excl VAT: R1,000.00
VAT Amount: R1,000.00 × 0.15 = R150.00
Amount incl VAT: R1,150.00
```

### Zero-Rated (0%)

Foreign income:
```
Amount: R100,000.00
VAT: R0.00 (zero-rated export)
Claimable input VAT: Yes (on related expenses)
```

## VAT Return Calculation

```python
from src.services.vat_calculator import calculate_vat_summary

summary = calculate_vat_summary(
    transactions=all_transactions,
    period_start=date(2025, 1, 1),
    period_end=date(2025, 6, 30),
    db_session=db.session
)

# Result:
# {
#     'output_vat': Decimal('0.00'),      # VAT on sales (zero-rated)
#     'input_vat': Decimal('5000.00'),    # VAT on purchases (claimable)
#     'net_vat': Decimal('-5000.00'),     # Refund due from SARS
# }
```

## VAT Rates by Category

### Zero-Rated (0%)
- Income (Foreign): Zero-rated exports
- Basic Foods: Certain staples

### Standard-Rated (15%)
- Technology/Software
- Internet
- Professional Services
- Most Business Expenses

### Exempt (No VAT)
- Financial Services: Bank fees, some insurance
- Residential Rent

### No VAT
- Medical Aid
- Some international transactions

## Filing Periods

6-monthly filing:
- **Period 1**: January - June (due 25 July)
- **Period 2**: July - December (due 25 January)

## Integration with Income Tax

VAT and Income Tax are separate calculations:

```
Transaction: -R1,150 (incl VAT)
VAT (15%): -R150
Amount excl VAT: -R1,000

Income Tax Deduction: R1,000 (not R1,150)
VAT Claim: R150 (separate from income tax)
```

## Configuration

### Update VAT Rate

```python
from src.database.models import VATConfig

# Close current rate
current = VATConfig.query.filter_by(is_active=True).first()
current.effective_to = date(2026, 3, 31)
current.is_active = False

# Add new rate
new_rate = VATConfig(
    effective_from=date(2026, 4, 1),
    standard_rate=Decimal('0.16'),
    is_active=True
)
db.session.add(new_rate)
db.session.commit()
```

### Set Category VAT Defaults

```python
from src.database.models import Category

income = Category.query.filter_by(name='Income').first()
income.default_vat_rate = 'zero'
db.session.commit()
```

## Best Practices

1. Always specify VAT rate type explicitly
2. Mark non-claimable expenses (personal, entertainment)
3. Reconcile monthly, even if filing 6-monthly
4. Keep tax invoices for all input VAT claims
5. Only claim VAT on business expenses

## SARS Resources

- **VAT Guide**: https://www.sars.gov.za/types-of-tax/value-added-tax/
- **VAT Rates**: https://www.sars.gov.za/tax-rates/vat/vat-rates/
- **eFiling**: https://www.sarsefiling.co.za
