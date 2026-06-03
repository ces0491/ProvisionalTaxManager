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
| `year` | START calendar year of the tax year — `2025` == the 2025/2026 year, `2026` == the 2026/2027 year |
| `description` | "2025/2026 Tax Year" |
| `start_date` | March 1 |
| `end_date` | February 28/29 |
| `is_active` | Whether currently active |

> **Year-numbering convention.** `TaxYear.year` and `SATaxCalculator.tax_year`
> use the **start** calendar year: a period ending Feb 2026 resolves to
> `year=2025` (the 2025/2026 tax year). Note this differs from the reports page
> and the transactions filter, which label tax years by their **end** year
> (e.g. "2026" there means the 2025/2026 year). Both render the unambiguous
> "YYYY/YYYY" range in the UI.

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

### Seeded Tax Years

The seed script populates both the **2025/2026** (`year=2025`) and **2026/2027**
(`year=2026`) tax years. It is idempotent — each year is skipped if already
present, so it is safe to re-run:

```bash
python scripts/seed_tax_tables.py
```

Source figures: [SARS rates of tax for individuals](https://www.sars.gov.za/tax-rates/income-tax/rates-of-tax-for-individuals/)
and [SARS medical tax credit rates](https://www.sars.gov.za/tax-rates/medical-tax-credit-rates/).

Medical scheme fees credit: the main member and the first dependant are
credited at the **same** monthly rate (R364 for 2025/2026, R376 for 2026/2027);
each further dependant is credited at the lower rate (R246 / R254).

### Adding Future Tax Years

When SARS announces new tax tables (usually after the February Budget), add a
`seed_<start_year>_tax_year()` function in `scripts/seed_tax_tables.py` modelled
on the existing ones (remembering `year` is the **start** calendar year), call
it from `__main__`, then re-run the script.

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

- **Tax Tables**: <https://www.sars.gov.za/tax-rates/income-tax/rates-of-tax-for-individuals/>
- **Budget Speech**: Published in February each year
- **Effective Date**: March 1st of each year
