# Tax Tables Management

This application uses database-driven tax tables to support multiple tax years and enable retrospective calculations for audits.

## How It Works

Tax brackets, rebates, and medical aid credits are stored in the database rather than being hardcoded. This allows:

1. **Multiple Tax Years**: Store tax tables for 2024, 2025, 2026, etc.
2. **Retrospective Calculations**: Run calculations for previous years using historical rates
3. **Easy Updates**: Update tax tables through database or future admin interface
4. **Audit Support**: Rerun calculations with exact rates that applied in specific years

## Database Structure

### Tax Tables

**TaxYear**: Represents a tax year (e.g., 2025/2026 tax year)

- `year`: 2025, 2026, etc.
- `description`: "2025/2026 Tax Year"
- `start_date`: March 1
- `end_date`: February 28/29
- `is_active`: Whether this tax year is currently active

**TaxBracket**: Income tax brackets

- `min_income`: Lower bound (e.g., R237,100)
- `max_income`: Upper bound (NULL for highest bracket)
- `rate`: Tax rate (e.g., 0.18 for 18%)
- `base_tax`: Base tax for this bracket
- `bracket_order`: Order of brackets (1, 2, 3...)

**TaxRebate**: Age-based rebates

- `rebate_type`: 'primary', 'secondary', 'tertiary'
- `min_age`: Minimum age for this rebate
- `amount`: Annual rebate amount

**MedicalAidCredit**: Medical aid tax credits

- `credit_type`: 'main', 'first_dependent', 'additional'
- `monthly_amount`: Monthly credit amount

## Seeding Tax Tables

### For 2025/2026 Tax Year (Already Done)

The 2025/2026 tax tables have been seeded. To verify:

```bash
python seed_tax_tables.py
```

Output: "2025 tax year already exists. Skipping..."

### For Future Tax Years

When SARS announces new tax tables (usually in February):

1. **Copy the seed script**:

   ```bash
   cp seed_tax_tables.py seed_tax_tables_2026.py
   ```

2. **Update the values** in the new script:
   - Update `year=2026`
   - Update brackets with new thresholds and rates
   - Update rebate amounts
   - Update medical aid credit amounts
   - Update date ranges

3. **Run the script**:

   ```bash
   python seed_tax_tables_2026.py
   ```

## How Tax Calculator Uses Database

The `SATaxCalculator` class automatically loads tax tables from the database:

```python
# Uses database tables for specified year
calculator = SATaxCalculator(tax_year=2025, db_session=db.session)

# Falls back to hardcoded 2025/2026 values if database unavailable
calculator = SATaxCalculator(tax_year=2025)
```

The `calculate_tax_from_transactions()` function automatically:

1. Determines the tax year from the transaction date
2. Loads the correct tax tables from the database
3. Falls back to hardcoded values if database tables don't exist

## Fallback Mechanism

If database tables are not available or don't exist for a specific year:

- The calculator uses hardcoded 2025/2026 values
- This ensures the app continues to work even if database is corrupted
- Hardcoded values are marked with `# FALLBACK:` comments in tax_calculator.py

## Retrospective Calculations

To calculate tax for a previous year:

```python
# Example: Calculate tax for 2024 (if 2024 tables exist in database)
tax_result = calculate_tax_from_transactions(
    transactions=transactions,
    period_start=date(2024, 3, 1),
    period_end=date(2024, 8, 31),
    age=40,
    medical_aid_members=1,
    tax_year=2024,  # Explicitly specify year
    db_session=db.session
)
```

If `tax_year` is not specified, it's automatically derived from `period_end`:

- Transactions in Mar-Dec belong to that year's tax year
- Transactions in Jan-Feb belong to previous year's tax year

## Viewing Current Tax Tables

To view tax tables currently in the database:

```python
from app import app
from models import db, TaxYear

with app.app_context():
    tax_years = TaxYear.query.all()
    for ty in tax_years:
        print(f"\n{ty.description} ({ty.year})")
        print(f"  Brackets: {len(ty.brackets)}")
        print(f"  Rebates: {len(ty.rebates)}")
        print(f"  Medical Credits: {len(ty.medical_credits)}")

        # Show brackets
        for bracket in sorted(ty.brackets, key=lambda b: b.bracket_order):
            print(f"    {bracket}")
```

## SARS Tax Table Sources

Official SARS tax tables are published annually:

- **Website**: <https://www.sars.gov.za>
- **Search for**: "Tax Tables" or "Individual Income Tax Tables"
- **Budget Speech**: Published in February each year
- **Effective Date**: March 1st of each year

### Key References

- Income Tax Tables: <https://www.sars.gov.za/tax-rates/income-tax/rates-of-tax-for-individuals/>
- Medical Aid Tax Credits: Included in Budget Speech documents
- Rebates: Included in annual tax tables

## Future Enhancement Ideas

1. **Admin Interface**: Web UI to manage tax years and brackets
2. **Import from SARS**: Automatically import tables from SARS website
3. **Version History**: Track changes to tax tables
4. **Validation**: Ensure brackets don't overlap and rates are valid
5. **Export**: Export tax tables to JSON/CSV for backup

## Migration Notes

- The database schema is backwards compatible
- Old calculations without `db_session` parameter still work (use fallback)
- The fallback ensures zero disruption to existing functionality
- Tests pass 100% with new database-driven approach
