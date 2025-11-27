# Test Suite

Comprehensive test suite for the Provisional Tax Manager application.

## Test Coverage

| Module | Tests | Status |
|--------|-------|--------|
| Tax Calculator | 12 | ✅ 100% |
| Categorizer | 17 | ✅ 100% |
| PDF Parser | 8 | ✅ 100% |
| Flask Routes | 26 | ✅ 100% |
| Database Models | 16 | ✅ 100% |

**Total: 79 tests passing**

## Running Tests

```bash
# All tests
pytest

# Specific file
pytest tests/test_tax_calculator.py

# Specific test class
pytest tests/test_tax_calculator.py::TestSATaxCalculator

# Verbose output
pytest -v

# With coverage
pytest --cov=. --cov-report=html
```

## Test Files

| File | Coverage |
|------|----------|
| `test_tax_calculator.py` | Tax brackets, rebates, medical credits, provisional tax |
| `test_categorizer.py` | Pattern matching, database rules, priority, transfers |
| `test_pdf_parser.py` | Date parsing, amount detection, duplicates |
| `test_routes.py` | Authentication, CRUD, splitting, API endpoints |
| `test_models.py` | Model constraints, relationships, foreign keys |
| `conftest.py` | Shared fixtures |

## Fixtures

Common fixtures in `conftest.py`:

- `app` - Flask application with test configuration
- `client` - Test client for making requests
- `authenticated_client` - Pre-authenticated test client
- `db_session` - Database session for testing
- `sample_transactions` - Sample transaction data

## Adding Tests

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
```

## CI/CD

```bash
pytest --tb=short --disable-warnings -v
```
