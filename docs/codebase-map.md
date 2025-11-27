# Codebase Map

Quick reference for navigating the Provisional Tax Manager codebase.

## Project Structure

```
ProvisionalTaxManager/
├── app.py                  # Flask application and routes
├── src/                    # Source code package
│   ├── config.py          # Application configuration
│   ├── database/          # Database-related code
│   │   └── models.py      # SQLAlchemy models (9 models)
│   └── services/          # Business logic services
│       ├── categorizer.py      # Transaction categorization
│       ├── excel_export.py     # Excel report generation
│       ├── pdf_parser.py       # PDF statement parsing
│       ├── reports.py          # Financial reporting
│       ├── tax_calculator.py   # Tax calculations
│       └── vat_calculator.py   # VAT calculations
├── scripts/               # Utility scripts
│   ├── seed_tax_tables.py      # Seed SARS tax tables
│   ├── seed_vat_config.py      # Seed VAT rates
│   └── test_parser.py          # Parser testing script
├── templates/             # Jinja2 HTML templates
├── tests/                 # Test suite
├── docs/                  # Documentation
├── instance/              # Flask instance folder (database)
└── uploads/               # Uploaded PDF statements
```

## Core Files

| File | Purpose | Key Items |
|------|---------|-----------|
| `app.py` | Flask routes, handlers | All routes (`/`, `/upload`, `/transactions`, `/reports`, etc.) |
| `src/config.py` | Configuration | `Config` class |
| `src/database/models.py` | Database models | `Transaction`, `Category`, `Account`, `TaxYear`, `VATConfig` |

## Services

| File | Purpose | Key Functions |
|------|---------|---------------|
| `tax_calculator.py` | Income tax | `SATaxCalculator`, `calculate_tax_from_transactions()` |
| `vat_calculator.py` | VAT | `calculate_vat_summary()`, `calculate_transaction_vat()` |
| `categorizer.py` | Categorization | `categorize_transaction()`, `CATEGORIES` |
| `pdf_parser.py` | PDF parsing | `BankStatementParser`, `detect_duplicates()` |
| `excel_export.py` | Excel export | `generate_tax_export()` |
| `reports.py` | Reporting | `aggregate_transactions()`, `MONTHS` |

## Database Models

**Core Models**:
1. `Account` - Bank accounts
2. `Statement` - Uploaded statements
3. `Transaction` - Individual transactions
4. `Category` - Expense/income categories
5. `ExpenseRule` - Auto-categorization rules

**Tax Models**:
6. `TaxYear` - Tax year configuration
7. `TaxBracket` - Income tax brackets
8. `TaxRebate` - Age-based rebates
9. `MedicalAidCredit` - Medical aid credits

**VAT Model**:
10. `VATConfig` - VAT rate configuration

## Transaction Flow

1. **Upload PDF** → `pdf_parser.py` → Extract transactions
2. **Categorize** → `categorizer.py` → Assign categories
3. **Calculate VAT** → `vat_calculator.py` → Compute VAT amounts
4. **Calculate Tax** → `tax_calculator.py` → Provisional tax
5. **View Reports** → `reports.py` → Monthly/category summaries
6. **Export** → `excel_export.py` → Generate reports

## Common Tasks

### Run Application
```bash
python app.py
# Visit http://localhost:5000
```

### Run Tests
```bash
pytest                      # All tests
pytest tests/test_routes.py # Specific file
pytest -v                   # Verbose
```

### Seed Database
```bash
python scripts/seed_tax_tables.py   # Tax tables
python scripts/seed_vat_config.py   # VAT rates
```

### Code Quality
```bash
ruff check .           # Linting
ruff check . --fix     # Auto-fix
mypy app.py            # Type checking
```

### Database Reset
```bash
rm instance/database.db    # Delete database
python app.py              # Recreate on startup
# Re-run seed scripts
```

## Where to Add Features

| Feature | File(s) | Notes |
|---------|---------|-------|
| New tax year | `scripts/seed_tax_tables.py` | Copy, update values, run |
| New VAT rate | `scripts/seed_vat_config.py` | Add VATConfig record with dates |
| New category | `app.py` or database | Via `/income_sources` UI or seed script |
| New route/page | `app.py`, `templates/` | Follow existing patterns |
| New calculation | `src/services/` | Follow `tax_calculator.py` structure |
