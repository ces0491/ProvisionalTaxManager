# Codebase Map - Quick Reference

Quick reference for navigating the Provisional Tax Manager codebase.

## File Purpose Guide

### Core Application Files

| File | Lines | Purpose | Key Functions/Classes |
|------|-------|---------|----------------------|
| `app.py` | 650 | Flask app, routes, handlers | All routes (`/`, `/upload`, `/transactions`, `/tax_calculator`, etc.) |
| `config.py` | 30 | Configuration settings | `Config` class |
| `models.py` | 200 | Database models (11 models) | `Transaction`, `Category`, `Account`, `TaxYear`, `VATConfig` |

### Business Logic

| File | Lines | Purpose | Key Functions/Classes |
|------|-------|---------|----------------------|
| `tax_calculator.py` | 340 | Income tax calculations | `SATaxCalculator`, `calculate_tax_from_transactions()` |
| `vat_calculator.py` | 190 | VAT calculations | `calculate_vat_summary()`, `calculate_transaction_vat()` |
| `categorizer.py` | 280 | Transaction categorization | `categorize_transaction()`, `categorize_transaction_with_rules()` |
| `pdf_parser.py` | 540 | PDF bank statement parsing | `BankStatementParser`, `detect_duplicates()` |
| `excel_export.py` | 80 | Excel export | `export_to_excel()` |

### Database Management

| File | Lines | Purpose | When to Run |
|------|-------|---------|-------------|
| `seed_tax_tables.py` | 110 | Seed SARS tax tables | Once (already run), or when adding new tax year |
| `seed_vat_config.py` | 50 | Seed VAT rates | Once (already run), or when VAT rate changes |

### Testing

| File | Tests | Purpose | Coverage |
|------|-------|---------|----------|
| `tests/test_models.py` | 18 | Database model tests | 100% |
| `tests/test_routes.py` | 26 | Flask route tests | 100% |
| `tests/test_tax_calculator.py` | 12 | Tax calculation tests | 100% |
| `tests/test_categorizer.py` | 20 | Categorization tests | 100% |
| `tests/test_pdf_parser.py` | 7 | PDF parsing tests | 100% |
| `tests/conftest.py` | - | Test fixtures | - |

### Documentation

| File | Pages | Purpose |
|------|-------|---------|
| `README.md` | 10 | Main user guide, installation, usage |
| `TAX_TABLES_README.md` | 5 | Tax tables management guide |
| `VAT_GUIDE.md` | 8 | VAT system usage guide |
| `REFACTOR_GUIDE.md` | 6 | Code organization guide |
| `CODEBASE_MAP.md` | 2 | This file |

## Module Dependencies

### Import Graph

```text
ProvisionalTaxManager/
├── app.py                  # Main Flask application and routes
├── src/                    # Source code package
│   ├── __init__.py
│   ├── config.py          # Application configuration
│   ├── database/          # Database-related code
│   │   ├── __init__.py
│   │   └── models.py      # SQLAlchemy models
│   ├── services/          # Business logic services
│   │   ├── __init__.py
│   │   ├── categorizer.py      # Transaction categorization
│   │   ├── excel_export.py     # Excel report generation
│   │   ├── pdf_parser.py       # PDF statement parsing
│   │   ├── tax_calculator.py   # Tax calculations
│   │   └── vat_calculator.py   # VAT calculations
│   └── utils/             # Utility functions (empty for now)
│       └── __init__.py
├── scripts/               # Utility scripts
│   ├── __init__.py
│   ├── seed_tax_tables.py      # Seed SARS tax tables
│   ├── seed_vat_config.py      # Seed VAT rates
│   └── test_parser.py          # Parser testing script
├── templates/             # Jinja2 HTML templates
│   ├── base.html
│   ├── index.html
│   ├── transactions.html
│   └── ... (other templates)
├── tests/                 # Test suite
│   ├── conftest.py       # Pytest configuration
│   ├── test_categorizer.py
│   ├── test_models.py
│   ├── test_pdf_parser.py
│   ├── test_routes.py
│   └── test_tax_calculator.py
├── instance/              # Flask instance folder (database)
├── uploads/               # Uploaded PDF statements
├── requirements.txt       # Python dependencies
├── pytest.ini            # Pytest configuration
├── .gitignore            # Git ignore rules
└── README.md             # Main documentation
```

### Circular Dependencies

**None!** ✓ Clean dependency tree

## Key Concepts

### Transaction Flow

1. **Upload PDF** → `pdf_parser.py` → Extract transactions
2. **Categorize** → `categorizer.py` → Assign categories
3. **Calculate VAT** → `vat_calculator.py` → Compute VAT amounts
4. **Calculate Tax** → `tax_calculator.py` → Provisional tax
5. **Export** → `excel_export.py` → Generate reports

### Database Models

**11 Total Models**:

**Core**:

1. `Account` - Bank accounts
2. `Statement` - Uploaded statements
3. `Transaction` - Individual transactions
4. `Category` - Expense/income categories
5. `ExpenseRule` - Auto-categorization rules

**Tax**:
6. `TaxYear` - Tax year configuration
7. `TaxBracket` - Income tax brackets
8. `TaxRebate` - Age-based rebates
9. `MedicalAidCredit` - Medical aid credits

**VAT**:
10. `VATConfig` - VAT rate configuration
11. `VATPeriod` - VAT filing periods (not yet fully implemented)

**Legacy**:
12. `TaxPeriod` - Provisional tax periods

## Where to Add Features

### New Tax Year

**File**: `seed_tax_tables.py`
**Steps**: Copy script, update values, run

### New VAT Rate

**File**: `seed_vat_config.py`
**Steps**: Add new VATConfig record with dates

### New Category

**File**: `app.py` or database directly
**Method**: Add via `/income_sources` UI or seed script

### New Route/Page

**File**: `app.py` (routes), `templates/` (HTML)
**Pattern**: Follow existing routes like `/tax_calculator`

### New Calculation

**File**: Create in `src/calculators/` (future) or root (current)
**Pattern**: Follow `tax_calculator.py` structure

### New Parser

**File**: Create in `src/parsers/` (future) or root (current)
**Pattern**: Follow `pdf_parser.py` structure

## Common Tasks Quick Reference

### Run App Locally

```bash
python app.py
# Visit http://localhost:5000
```

### Run Tests

```bash
pytest                  # All tests
pytest tests/test_routes.py  # Specific file
pytest -v              # Verbose
pytest --tb=short      # Short traceback
```

### Seed Database

```bash
python seed_tax_tables.py   # Tax tables
python seed_vat_config.py   # VAT rates
```

### Check Code Quality

```bash
ruff check .           # Linting
ruff check . --fix     # Auto-fix issues
mypy app.py            # Type checking
```

### Database Reset

```bash
rm data/database.db    # Delete database
python app.py          # Recreate on startup
# Then re-run seed scripts
```
