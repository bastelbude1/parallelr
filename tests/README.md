# parallelr Test Suite

Comprehensive test suite for the parallelr parallel task execution framework.

## 📋 Overview

This test suite provides comprehensive coverage of parallelr functionality including:
- **Unit Tests**: Individual component testing (placeholders, validators, exceptions)
- **Integration Tests**: Component interaction testing (file mode, daemon, signals)
- **Security Tests**: Injection prevention, input validation, resource limits
- **Performance Tests**: Scalability, concurrency, memory usage
- **E2E Tests**: Real-world workflow scenarios

## 🚀 Quick Start

### Install Test Dependencies

```bash
# From repository root
pip install -r tests/requirements-test.txt
```

### Run All Tests

```bash
# Run complete test suite
bash tests/run_all_tests.sh

# Or use pytest directly
pytest tests/ -v
```

### Run Specific Test Categories

```bash
# Unit tests only (fast)
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# Security tests
pytest tests/security/ -v

# Performance tests
RUN_PERFORMANCE=1 bash tests/run_all_tests.sh

# With coverage report
GENERATE_COVERAGE=1 bash tests/run_all_tests.sh
```

## 📁 Test Structure

```
tests/
├── unit/                    # Unit tests (~30 tests)
│   ├── test_placeholders.py    # Placeholder replacement logic
│   ├── test_validators.py      # Input validation functions
│   ├── test_exceptions.py      # Exception classes
│   ├── test_config.py          # Configuration system (TODO)
│   └── test_helpers.py         # Helper functions (TODO)
├── integration/             # Integration tests (~35 tests)
│   ├── test_file_mode.py       # File mode execution (TODO)
│   ├── test_arguments_mode.py  # Arguments mode (TODO)
│   ├── test_daemon_mode.py     # Daemon execution (TODO)
│   ├── test_workspace.py       # Workspace management (TODO)
│   └── test_signal_handling.py # Signal handling (TODO)
├── security/                # Security tests (~20 tests)
│   ├── test_injection.py       # Injection prevention (TODO)
│   ├── test_path_traversal.py  # Path security (TODO)
│   ├── test_input_validation.py# Input validation (TODO)
│   └── test_resource_limits.py # Resource protection (TODO)
├── performance/             # Performance tests (~15 tests)
│   ├── test_scalability.py     # Scaling behavior (TODO)
│   ├── test_concurrency.py     # Thread safety (TODO)
│   └── test_memory_leaks.py    # Memory usage (TODO)
├── e2e/                     # End-to-end tests (~10 tests)
│   ├── test_real_workloads.py  # Real scenarios (TODO)
│   └── test_error_recovery.py  # Error handling (TODO)
├── conftest.py              # Shared fixtures
├── requirements-test.txt    # Test dependencies
└── run_all_tests.sh         # Master test runner
```

## 🧪 Writing Tests

### Using Fixtures

Common fixtures are defined in `conftest.py`:

```python
def test_example(temp_dir, sample_task_file):
    """Example test using fixtures."""
    # temp_dir provides a temporary directory
    # sample_task_file provides a sample task file
    assert sample_task_file.exists()
```

### Test Markers

Use markers to categorize tests:

```python
import pytest

@pytest.mark.slow
def test_large_scale():
    """This test takes a long time."""
    pass

@pytest.mark.security
def test_injection_prevention():
    """Security-related test."""
    pass
```

### Running Specific Markers

```bash
# Run only smoke tests (fast)
pytest -m smoke -v

# Skip slow tests
pytest -m "not slow" -v

# Run only security tests
pytest -m security -v
```

## 📊 Coverage

Generate coverage reports:

```bash
# Terminal report
pytest --cov=bin/parallelr.py --cov-report=term-missing

# HTML report
pytest --cov=bin/parallelr.py --cov-report=html
# Open htmlcov/index.html in browser

# Both
GENERATE_COVERAGE=1 bash tests/run_all_tests.sh
```

## 🎯 Test Categories Explained

### Unit Tests
- Test individual functions and classes in isolation
- Fast execution (<1 second each)
- No external dependencies
- Mock any I/O or system calls

### Integration Tests
- Test multiple components working together
- May involve file I/O, process execution
- Moderate execution time (1-5 seconds each)
- Use real components where possible

### Security Tests
- Test security boundaries and validations
- Include injection attempts, malicious inputs
- Verify proper escaping and sanitization
- Check resource limits

### Performance Tests
- Benchmark scalability and concurrency
- Memory leak detection
- Thread safety verification
- Typically slower (5-30 seconds each)
- Use `@pytest.mark.slow` marker

### E2E Tests
- Full workflow scenarios
- Test real-world use cases
- Slowest tests (10-60 seconds each)
- Closest to actual usage

## 🔧 Test Development Workflow

1. **Write Test First** (TDD approach recommended)
   ```python
   def test_new_feature():
       """Test description."""
       # Arrange
       input_data = prepare_input()

       # Act
       result = function_under_test(input_data)

       # Assert
       assert result == expected_output
   ```

2. **Run Test** (should fail initially)
   ```bash
   pytest tests/unit/test_new_feature.py::test_new_feature -v
   ```

3. **Implement Feature**

4. **Run Test Again** (should pass now)

5. **Check Coverage**
   ```bash
   pytest tests/unit/test_new_feature.py --cov=bin/parallelr.py --cov-report=term-missing
   ```

## 🐛 Debugging Tests

### Verbose Output
```bash
pytest tests/unit/test_example.py -vv
```

### Show Local Variables
```bash
pytest tests/unit/test_example.py --showlocals
```

### Stop on First Failure
```bash
pytest tests/ -x
```

### Run Specific Test
```bash
pytest tests/unit/test_placeholders.py::test_replace_argument_placeholders_single -v
```

### Print Statements in Tests
```bash
pytest tests/unit/test_example.py -s  # Don't capture stdout
```

## 📈 Current Coverage Status

### Unit Tests: ~20% Complete
- ✅ test_placeholders.py (17 tests)
- ✅ test_exceptions.py (9 tests)
- ✅ test_validators.py (multiple test classes)
- ⏳ test_config.py (TODO)
- ⏳ test_helpers.py (TODO)

### Integration Tests: 0% Complete
- ⏳ All integration tests TODO

### Security Tests: 0% Complete
- ⏳ All security tests TODO

### Performance Tests: 0% Complete
- ⏳ All performance tests TODO

### E2E Tests: 0% Complete
- ⏳ All E2E tests TODO

**Goal**: 100+ tests with >90% code coverage

## 🚦 CI/CD Integration

GitHub Actions workflow is configured to run tests automatically on:
- Every push to any branch
- Every pull request
- Multiple Python versions (3.6, 3.7, 3.8, 3.9, 3.10, 3.11)

See `.github/workflows/test.yml` for configuration.

## 📝 Contributing Tests

1. Create feature branch
2. Write tests following existing patterns
3. Ensure all tests pass
4. Add docstrings to all test functions
5. Update this README if adding new test categories
6. Submit PR with tests

## 🔗 Related Documentation

- Main README: `../README.md`
- Development Workflow: `../CLAUDE.md`
- Configuration Guide: See main README
- Code Coverage Reports: `htmlcov/index.html` (after running with coverage)

## 📞 Help

If tests fail:
1. Check test output for specific failure
2. Run with `-vv --showlocals` for detailed info
3. Verify dependencies are installed
4. Check Python version compatibility
5. Review recent code changes

For questions about test suite design or implementation, see `CLAUDE.md`.
