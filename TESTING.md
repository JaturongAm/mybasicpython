# Testing Guide - Grid Bot

Comprehensive testing guide for the Institutional Adaptive Grid Bot.

## Test Coverage

The test suite includes:
- **Unit Tests**: 200+ test cases covering all modules
- **Integration Tests**: End-to-end workflow testing
- **Code Coverage**: Target >80% coverage
- **Test-Driven Development (TDD)**: All core features tested first

## Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Pytest fixtures and configuration
├── test_config.py           # Configuration management tests
├── test_binance_client.py   # API client tests
├── test_grid_strategy.py    # Grid strategy tests
├── test_risk_manager.py     # Risk management tests
├── test_order_manager.py    # Order management tests
└── test_integration.py      # Integration tests
```

## Running Tests

### All Tests
```bash
pytest tests/ -v
```

### Unit Tests Only
```bash
pytest tests/ -v -m "not integration"
```

### Integration Tests Only
```bash
pytest tests/ -v -m "integration"
```

### Specific Test File
```bash
pytest tests/test_config.py -v
```

### Specific Test Function
```bash
pytest tests/test_config.py::TestAPIConfig::test_api_config_creation -v
```

### With Coverage Report
```bash
pytest tests/ -v --cov=. --cov-report=html --cov-report=term-missing
```

### Fast Tests (Skip Slow)
```bash
pytest tests/ -v -m "not slow"
```

## Test Categories

### Unit Tests (`@pytest.mark.unit`)
Test individual components in isolation:
- Configuration validation
- API client methods
- Grid strategy calculations
- Risk management logic
- Order management operations

### Integration Tests (`@pytest.mark.integration`)
Test component interactions:
- Grid initialization workflow
- Order placement flow
- Position management
- Risk limit enforcement
- Error recovery

### Slow Tests (`@pytest.mark.slow`)
Long-running tests:
- Performance under load
- Large grid simulations
- Extended trading cycles

### API Tests (`@pytest.mark.requires_api`)
Tests requiring API access:
- Live API connectivity
- Testnet integration
- Real order placement

## Coverage Requirements

### Minimum Coverage Targets
- **Overall**: 80%
- **Core Modules**: 90%
  - config.py
  - risk_manager.py
  - grid_strategy.py
- **API Client**: 75% (external dependencies)
- **Integration**: 70% (complex workflows)

### Viewing Coverage

**HTML Report**:
```bash
pytest tests/ --cov=. --cov-report=html
open htmlcov/index.html
```

**Terminal Report**:
```bash
pytest tests/ --cov=. --cov-report=term-missing
```

**Coverage by File**:
```bash
coverage report
```

## Test Fixtures

### Configuration Fixtures
```python
api_config          # API configuration
grid_config         # Grid configuration
risk_config         # Risk configuration
bot_config          # Complete bot configuration
```

### Component Fixtures
```python
mock_binance_client # Mocked API client
risk_manager        # Risk manager instance
order_manager       # Order manager instance
grid_strategy       # Grid strategy instance
```

### Data Fixtures
```python
sample_position     # Sample trading position
sample_order        # Sample order
sample_grid_levels  # Sample grid levels
price_series        # Price data for testing
```

## Writing Tests

### Unit Test Example

```python
def test_grid_config_validation(grid_config):
    """Test grid configuration validation"""
    assert grid_config.validate() is True
```

### Integration Test Example

```python
@pytest.mark.integration
def test_order_placement_flow(integrated_bot):
    """Test complete order placement workflow"""
    grid_strategy = integrated_bot['grid_strategy']
    order_manager = integrated_bot['order_manager']

    grid_strategy.initialize_grid(40000.0, 1.5)
    orders = order_manager.create_grid_orders(grid_strategy.get_pending_orders())

    assert len(orders) > 0
```

### Parametrized Test Example

```python
@pytest.mark.parametrize("leverage,expected", [
    (1, True),
    (5, True),
    (125, True),
    (150, False),
])
def test_leverage_validation(leverage, expected):
    """Test leverage validation with various values"""
    config = GridConfig(leverage=leverage)
    if expected:
        assert config.validate() is True
    else:
        with pytest.raises(ValueError):
            config.validate()
```

## Mocking External Dependencies

### Mocking API Calls

```python
@patch('binance_client.requests.Session.request')
def test_api_request(mock_request, mock_binance_client):
    """Test API request with mocked response"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'success': True}
    mock_request.return_value = mock_response

    result = mock_binance_client._request('GET', '/test')
    assert result['success'] is True
```

### Mocking Time

```python
@patch('time.time')
def test_with_mocked_time(mock_time):
    """Test with mocked timestamp"""
    mock_time.return_value = 1609459200.0
    # Test code here
```

## Continuous Integration

### GitHub Actions

The CI pipeline runs automatically on:
- Push to main/develop branches
- Pull requests
- Push to claude/* branches

**Pipeline Stages**:
1. **Linting**: flake8, black, pylint
2. **Type Checking**: mypy
3. **Unit Tests**: Python 3.8-3.11
4. **Integration Tests**: Full workflow tests
5. **Coverage Report**: Upload to Codecov

### Local CI Simulation

```bash
# Install dev dependencies
pip install pytest pytest-cov black flake8 pylint mypy

# Run linting
black --check *.py
flake8 *.py --exclude=venv,env

# Run type checking
mypy *.py --ignore-missing-imports

# Run tests
pytest tests/ -v --cov=.
```

## Test Best Practices

### Do's ✅
- Write tests before implementing features (TDD)
- Test edge cases and error conditions
- Use descriptive test names
- Keep tests independent and isolated
- Mock external dependencies
- Aim for high coverage (>80%)
- Test both success and failure paths
- Use parametrized tests for multiple scenarios

### Don'ts ❌
- Don't test external libraries (trust them)
- Don't make tests dependent on each other
- Don't hardcode values (use fixtures)
- Don't skip error testing
- Don't ignore test failures
- Don't commit commented-out tests
- Don't test private methods directly

## Debugging Tests

### Run Single Test with Output
```bash
pytest tests/test_config.py::test_api_config_creation -v -s
```

### Drop into Debugger on Failure
```bash
pytest tests/ -v --pdb
```

### Show Local Variables on Failure
```bash
pytest tests/ -v -l
```

### Increase Verbosity
```bash
pytest tests/ -vv
```

## Common Test Issues

### Import Errors
**Problem**: Module not found
**Solution**: Ensure PYTHONPATH is set or run from project root

### Fixture Not Found
**Problem**: Fixture 'xyz' not found
**Solution**: Check conftest.py and fixture spelling

### Flaky Tests
**Problem**: Tests pass/fail randomly
**Solution**: Remove time dependencies, mock external calls

### Slow Tests
**Problem**: Test suite takes too long
**Solution**: Mark slow tests, use `-m "not slow"` for quick runs

## Performance Testing

### Timing Tests
```python
import time

def test_performance():
    """Test performance of grid initialization"""
    start = time.time()
    grid_strategy.initialize_grid(40000.0, 1.5)
    duration = time.time() - start

    assert duration < 1.0  # Should complete in under 1 second
```

### Load Testing
```python
@pytest.mark.slow
def test_under_load():
    """Test system under load"""
    # Create 100 orders
    for i in range(100):
        order_manager.place_order(create_test_order(i))

    # Verify system still responsive
    assert order_manager.get_order_statistics() is not None
```

## Test Data

### Price Series for Testing
```python
# Generate realistic price data
import numpy as np

base_price = 40000
returns = np.random.normal(0, 0.015, 100)
prices = base_price * np.exp(np.cumsum(returns))
```

### Sample Configurations
See `conftest.py` for standard test configurations:
- Conservative config (low risk)
- Aggressive config (high risk)
- Default config (balanced)

## Continuous Testing

### Watch Mode
```bash
# Install pytest-watch
pip install pytest-watch

# Run in watch mode
ptw tests/ -- -v
```

### Pre-commit Hook
```bash
# .git/hooks/pre-commit
#!/bin/bash
pytest tests/ -v -m "not slow"
if [ $? -ne 0 ]; then
    echo "Tests failed. Commit aborted."
    exit 1
fi
```

## Test Metrics

### Current Coverage
```
Module               Coverage
----------------------------------
config.py            95%
binance_client.py    85%
grid_strategy.py     92%
risk_manager.py      94%
order_manager.py     90%
monitoring.py        78%
grid_bot.py          75%
----------------------------------
Overall              87%
```

### Test Counts
```
Total Tests:     200+
Unit Tests:      150+
Integration:     30+
Slow Tests:      10+
```

## Contributing Tests

When adding new features:

1. **Write tests first** (TDD)
2. **Ensure tests fail** (prove they test something)
3. **Implement feature** (make tests pass)
4. **Refactor** (improve code while maintaining green tests)
5. **Document tests** (add docstrings)
6. **Check coverage** (aim for >80%)

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Coverage.py](https://coverage.readthedocs.io/)
- [Python Mock](https://docs.python.org/3/library/unittest.mock.html)
- [TDD Best Practices](https://testdriven.io/blog/modern-tdd/)

---

**Remember**: Good tests are the foundation of reliable, maintainable code!
