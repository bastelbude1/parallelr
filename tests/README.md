# parallelr Test Suite

Comprehensive test suite for the parallelr parallel task execution framework.

## 📋 Overview

This test suite provides comprehensive coverage of parallelr functionality including:
- **Unit Tests**: Individual component testing (placeholders, validators, exceptions)
- **Integration Tests**: Component interaction testing (file mode, daemon, signals)
- **Security Tests**: Injection prevention, input validation, resource limits

## ⚠️ Python 3.6.8 Compatibility

**CRITICAL**: All tests MUST be compatible with Python 3.6.8.

### Compatibility Requirements

- ✅ Use `stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True`
- ❌ Do NOT use `capture_output=True` (Python 3.7+)
- ❌ Do NOT use `text=True` parameter (use `universal_newlines=True` instead)
- ❌ Do NOT use walrus operator `:=` (Python 3.8+)
- ❌ Do NOT use `list[str]` type hints (use `List[str]` from typing)

## 🚀 Quick Start

### Install Test Dependencies

```bash
# Verify Python version first
python -V  # Must show Python 3.6.8 or higher

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
├── unit/                    # Unit tests (42 tests) ✅
│   ├── test_placeholders.py    # Placeholder replacement logic (17 tests)
│   ├── test_validators.py      # Input validation functions (16 tests)
│   └── test_exceptions.py      # Exception classes (9 tests)
├── integration/             # Integration tests (47 tests) ✅
│   ├── test_file_mode.py       # File mode execution (11 tests)
│   ├── test_arguments_mode.py  # Arguments mode (12 tests)
│   ├── test_daemon_mode.py     # Daemon execution (8 tests)
│   ├── test_workspace.py       # Workspace management (10 tests)
│   └── test_signal_handling.py # Signal handling (7 tests)
├── security/                # Security tests (20 tests) ✅
│   ├── test_injection.py       # Injection prevention (10 tests)
│   └── test_path_security.py   # Path security (10 tests)
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

### Unit Tests: 100% Complete ✅
- ✅ test_placeholders.py (15 tests)
- ✅ test_validators.py (18 tests)
- ✅ test_exceptions.py (9 tests)

### Integration Tests: 100% Complete ✅
- ✅ test_file_mode.py (10 tests)
- ✅ test_arguments_mode.py (12 tests)
- ✅ test_daemon_mode.py (8 tests)
- ✅ test_workspace.py (10 tests)
- ✅ test_signal_handling.py (7 tests)

### Security Tests: 100% Complete ✅
- ✅ test_injection.py (10 tests)
- ✅ test_path_security.py (10 tests)

**Total: 109 tests - All passing ✅**

**Goal Achievement**: 109/109 tests (100%) - Target met!

## 🚦 CI/CD Integration

GitHub Actions workflow is configured to run tests automatically on:
- Every push to any branch
- Every pull request
- Python 3.6.8 (minimum supported version)

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
