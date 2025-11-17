# Test Suite for ProvisionalTaxManager

This directory contains the comprehensive test suite for the Provisional Tax
Manager application.

## Test Coverage

The test suite covers the following modules:

### 1. Tax Calculator Tests (`test_tax_calculator.py`)

- ✅ Annual tax calculation with 2025/2026 tax brackets
- ✅ Age-based rebates (primary, 65+, 75+)
- ✅ Medical aid tax credits
- ✅ Provisional tax calculation with period extrapolation
- ✅ Previous payments handling
- ✅ Transaction-based tax calculation
- ✅ Expense breakdown

**Status:** 12/12 tests passing

### 2. Categorizer Tests (`test_categorizer.py`)

- ✅ Income categorization (Precise Digital and others)
- ✅ Teletransmission fee handling
- ✅ Expense categorization (technology, medical, personal, etc.)
- ✅ Database rules with priority
- ✅ Regex pattern matching
- ✅ Active/inactive rule filtering
- ✅ Inter-account transfer detection
- ✅ Mixed business/personal detection (Takealot)

**Status:** 9/13 tests passing (4 tests require database setup fixes)

### 3. PDF Parser Tests (`test_pdf_parser.py`)

- ✅ Date parsing from various formats
- ✅ Amount detection and cleaning
- ✅ Duplicate transaction detection
- ✅ Similar transaction matching
- ✅ Amount and date validation

**Status:** 6/8 tests passing

### 4. Flask Routes Tests (`test_routes.py`)

- Authentication (login, logout, password protection)
- Transaction CRUD operations
- Manual transaction addition
- Transaction splitting
- Tax calculator API
- Income sources management
- Duplicate detection

**Status:** 0/26 tests passing (require Flask app context fixes)

### 5. Model Tests (`test_models.py`)

- Category model and constraints
- Account model and relationships
- Statement model
- Transaction model (soft delete, manual flag, duplicates, splits)
- ExpenseRule model
- Foreign key constraints

**Status:** 0/18 tests passing (require database setup fixes)

## Running Tests

### Run All Tests

```bash
pytest
```

or

```bash
python -m pytest
```

### Run Specific Test File

```bash
pytest tests/test_tax_calculator.py
```

### Run Specific Test Class

```bash
pytest tests/test_tax_calculator.py::TestSATaxCalculator
```

### Run Specific Test

```bash
pytest tests/test_tax_calculator.py::TestSATaxCalculator::test_calculate_annual_tax_basic
```

### Run with Verbose Output

```bash
pytest -v
```

### Run with Coverage Report

```bash
pytest --cov=. --cov-report=html
```

The HTML report will be in `htmlcov/index.html`

### Run Tests Matching a Pattern

```bash
pytest -k "tax_calculator"  # Run only tax calculator tests
pytest -k "categorize"       # Run only categorization tests
```

### Run Tests by Marker

```bash
pytest -m unit              # Run only unit tests
pytest -m integration       # Run only integration tests
pytest -m "not slow"        # Skip slow tests
```

## Test Markers

The following markers are available:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.slow` - Slow-running tests
- `@pytest.mark.routes` - Flask route tests
- `@pytest.mark.models` - Database model tests
- `@pytest.mark.calculator` - Tax calculator tests
- `@pytest.mark.parser` - PDF parser tests
- `@pytest.mark.categorizer` - Categorizer tests

## Test Fixtures

Common fixtures are defined in `conftest.py`:

- `app` - Flask application with test configuration
- `client` - Test client for making requests
- `authenticated_client` - Pre-authenticated test client
- `db_session` - Database session for testing
- `sample_transactions` - Sample transaction data

## Current Test Results

**Overall Status:**

- Total Tests: 80
- Passing: 30
- Failing: 4
- Errors: 46

**Passing Test Modules:**

- ✅ Tax Calculator: 12/12 tests passing (100%)
- ✅ Categorizer (basic): 9/13 tests passing (69%)
- ✅ PDF Parser: 6/8 tests passing (75%)

**Known Issues:**

- Route tests require Flask application context fixes
- Some database tests need transaction isolation fixes
- PDF parser tests for some methods need implementation

## Adding New Tests

### Test File Naming

- Test files must start with `test_`
- Place in the `tests/` directory

### Test Function Naming

- Test functions must start with `test_`
- Use descriptive names: `test_calculate_tax_with_rebates`

### Test Class Naming

- Test classes must start with `Test`
- Group related tests: `class TestTaxCalculator:`

### Example Test

```python
def test_example_calculation():
    """Test description"""
    # Arrange
    calculator = SATaxCalculator()

    # Act
    result = calculator.calculate_annual_tax(
        taxable_income=Decimal('500000'),
        age=40,
        medical_aid_members=1
    )

    # Assert
    assert result['tax_liability'] > 0
    assert result['effective_rate'] > 0
```

## Test Data

Test data is automatically seeded in `conftest.py`:

- 3 categories (Income, Technology/Software, Personal)
- 2 expense rules (Precise Digital, Claude.AI)
- 1 test account
- 1 test statement
- 3 test transactions

## Continuous Integration

To run tests in CI/CD:

```bash
pytest --tb=short --disable-warnings -v
```

## Troubleshooting

### Import Errors

If you get import errors, ensure the parent directory is in the Python path:

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest
```

### Database Errors

Tests use an in-memory SQLite database. If you encounter database errors,
ensure SQLAlchemy is properly configured in `conftest.py`.

### Flask App Context Errors

Some tests require Flask application context. These are automatically set up
in the fixtures, but if you encounter errors, check that you're using the
`app` or `client` fixtures.
