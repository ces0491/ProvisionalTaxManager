# Tax Tables Management

Database-driven tax tables supporting multiple tax years and retrospective calculations.

## Overview

Tax brackets, rebates, and medical aid credits are stored in the database, allowing:

- **Multiple Tax Years**: Store tax tables for 2024, 2025, 2026, etc.
- **Retrospective Calculations**: Run calculations for previous years using historical rates
- **Easy Updates**: Update through database or seed scripts
- **Audit Support**: Rerun calculations with exact rates from specific years

## Database Structure

### TaxYear

Represents a tax year (e.g., 2025/2026):

| Field | Description |
|-------|-------------|
| `year` | 2025, 2026, etc. |
| `description` | "2025/2026 Tax Year" |
| `start_date` | March 1 |
| `end_date` | February 28/29 |
| `is_active` | Whether currently active |

### TaxBracket

Income tax brackets:

| Field | Description |
|-------|-------------|
| `min_income` | Lower bound (e.g., R237,100) |
| `max_income` | Upper bound (NULL for highest) |
| `rate` | Tax rate (e.g., 0.18 for 18%) |
| `base_tax` | Base tax for this bracket |
| `bracket_order` | Order (1, 2, 3...) |

### TaxRebate

Age-based rebates:

| Field | Description |
|-------|-------------|
| `rebate_type` | 'primary', 'secondary', 'tertiary' |
| `min_age` | Minimum age for rebate |
| `amount` | Annual rebate amount |

### MedicalAidCredit

Medical aid tax credits:

| Field | Description |
|-------|-------------|
| `credit_type` | 'main', 'first_dependent', 'additional' |
| `monthly_amount` | Monthly credit amount |

## Seeding Tax Tables

### Current Tax Year

The 2025/2026 tax tables are already seeded. To verify:

```bash
python scripts/seed_tax_tables.py
```

### Adding Future Tax Years

When SARS announces new tax tables (usually in February):

1. Copy the seed script:
   ```bash
   cp scripts/seed_tax_tables.py scripts/seed_tax_tables_2026.py
   ```

2. Update the values:
   - `year=2026`
   - New brackets with thresholds and rates
   - Updated rebate amounts
   - Updated medical aid credit amounts
   - Date ranges

3. Run the script:
   ```bash
   python scripts/seed_tax_tables_2026.py
   ```

## Calculator Usage

```python
# Uses database tables for specified year
calculator = SATaxCalculator(tax_year=2025, db_session=db.session)

# Falls back to hardcoded 2025/2026 values if database unavailable
calculator = SATaxCalculator(tax_year=2025)
```

The `calculate_tax_from_transactions()` function automatically:

1. Determines the tax year from the transaction date
2. Loads the correct tax tables from the database
3. Falls back to hardcoded values if tables don't exist

## Retrospective Calculations

```python
tax_result = calculate_tax_from_transactions(
    transactions=transactions,
    period_start=date(2024, 3, 1),
    period_end=date(2024, 8, 31),
    age=40,
    medical_aid_members=1,
    tax_year=2024,
    db_session=db.session
)
```

If `tax_year` is not specified, it's derived from `period_end`:
- Transactions in Mar-Dec belong to that year's tax year
- Transactions in Jan-Feb belong to previous year's tax year

## Viewing Current Tax Tables

```python
from app import app
from src.database.models import TaxYear

with app.app_context():
    tax_years = TaxYear.query.all()
    for ty in tax_years:
        print(f"\n{ty.description} ({ty.year})")
        print(f"  Brackets: {len(ty.brackets)}")
        print(f"  Rebates: {len(ty.rebates)}")
        print(f"  Medical Credits: {len(ty.medical_credits)}")
```

## SARS References

- **Tax Tables**: https://www.sars.gov.za/tax-rates/income-tax/rates-of-tax-for-individuals/
- **Budget Speech**: Published in February each year
- **Effective Date**: March 1st of each year
