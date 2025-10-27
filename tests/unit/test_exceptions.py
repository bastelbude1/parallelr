"""
Unit tests for custom exception classes.

Tests ParallelTaskExecutorError, SecurityError, UnmatchedPlaceholderError,
and ConfigurationError.
"""

import sys
from pathlib import Path

# Add bin directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'bin'))


def test_parallel_task_executor_error_basic():
    """Test basic ParallelTaskExecutorError."""
    from parallelr import ParallelTaskExecutorError

    error = ParallelTaskExecutorError("Test error")
    assert str(error) == "Test error"
    assert isinstance(error, Exception)


def test_security_error_inheritance():
    """Test SecurityError inherits from ParallelTaskExecutorError."""
    from parallelr import SecurityError, ParallelTaskExecutorError

    error = SecurityError("Security issue")
    assert isinstance(error, SecurityError)
    assert isinstance(error, ParallelTaskExecutorError)
    assert isinstance(error, Exception)


def test_unmatched_placeholder_error_single():
    """Test UnmatchedPlaceholderError with single placeholder."""
    from parallelr import UnmatchedPlaceholderError

    placeholders = ["@ARG_5@"]
    error = UnmatchedPlaceholderError(placeholders)

    # Check error message
    error_msg = str(error)
    assert "@ARG_5@" in error_msg
    assert "unmatched argument placeholder" in error_msg.lower()
    assert "insufficient arguments" in error_msg.lower()

    # Check stored placeholders
    assert hasattr(error, "unmatched_placeholders")
    assert error.unmatched_placeholders == ["@ARG_5@"]


def test_unmatched_placeholder_error_multiple():
    """Test UnmatchedPlaceholderError with multiple placeholders."""
    from parallelr import UnmatchedPlaceholderError

    placeholders = ["@ARG_3@", "@ARG_1@", "@ARG_2@"]
    error = UnmatchedPlaceholderError(placeholders)

    error_msg = str(error)
    assert "@ARG_1@" in error_msg
    assert "@ARG_2@" in error_msg
    assert "@ARG_3@" in error_msg

    # Should be sorted
    assert error.unmatched_placeholders == ["@ARG_1@", "@ARG_2@", "@ARG_3@"]


def test_unmatched_placeholder_error_duplicates():
    """Test UnmatchedPlaceholderError deduplicates placeholders."""
    from parallelr import UnmatchedPlaceholderError

    placeholders = ["@ARG_1@", "@ARG_1@", "@ARG_2@", "@ARG_2@"]
    error = UnmatchedPlaceholderError(placeholders)

    # Should deduplicate
    assert len(error.unmatched_placeholders) == 2
    assert "@ARG_1@" in error.unmatched_placeholders
    assert "@ARG_2@" in error.unmatched_placeholders


def test_unmatched_placeholder_error_sorting():
    """Test UnmatchedPlaceholderError sorts by length then alphabetically."""
    from parallelr import UnmatchedPlaceholderError

    # Mix of @ARG@ and @ARG_N@ - different lengths
    placeholders = ["@ARG_10@", "@ARG@", "@ARG_1@", "@ARG_2@"]
    error = UnmatchedPlaceholderError(placeholders)

    # @ARG@ (shorter) should come first, then indexed ones sorted
    expected_order = ["@ARG@", "@ARG_1@", "@ARG_2@", "@ARG_10@"]
    assert error.unmatched_placeholders == expected_order


def test_unmatched_placeholder_error_inheritance():
    """Test UnmatchedPlaceholderError inherits from SecurityError."""
    from parallelr import UnmatchedPlaceholderError, SecurityError, ParallelTaskExecutorError

    error = UnmatchedPlaceholderError(["@ARG_1@"])
    assert isinstance(error, UnmatchedPlaceholderError)
    assert isinstance(error, SecurityError)
    assert isinstance(error, ParallelTaskExecutorError)
    assert isinstance(error, Exception)


def test_configuration_error_inheritance():
    """Test ConfigurationError inherits from ParallelTaskExecutorError."""
    from parallelr import ConfigurationError, ParallelTaskExecutorError

    error = ConfigurationError("Config issue")
    assert isinstance(error, ConfigurationError)
    assert isinstance(error, ParallelTaskExecutorError)
    assert isinstance(error, Exception)


def test_exception_catching_hierarchy():
    """Test that exceptions can be caught at different levels."""
    import pytest
    from parallelr import (
        UnmatchedPlaceholderError,
        SecurityError,
        ParallelTaskExecutorError
    )

    # Should be catchable as SecurityError
    try:
        raise UnmatchedPlaceholderError(["@ARG@"])
    except SecurityError:
        pass  # Expected
    except Exception:
        pytest.fail("Should have been caught as SecurityError")

    # Should be catchable as ParallelTaskExecutorError
    try:
        raise UnmatchedPlaceholderError(["@ARG@"])
    except ParallelTaskExecutorError:
        pass  # Expected
    except Exception:
        pytest.fail("Should have been caught as ParallelTaskExecutorError")

    # Should be catchable as Exception
    try:
        raise UnmatchedPlaceholderError(["@ARG@"])
    except Exception:
        pass  # Expected


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
