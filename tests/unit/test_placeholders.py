"""
Unit tests for placeholder replacement functionality.

Tests the replace_argument_placeholders() and build_env_prefix() helper functions.
"""

import sys
from pathlib import Path

# Add bin directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'bin'))


def test_replace_argument_placeholders_single():
    """Test @ARG@ replacement with single argument."""
    from parallelr import replace_argument_placeholders

    command = "bash script.sh @ARG@"
    arguments = ["value1"]
    result = replace_argument_placeholders(command, arguments)

    assert "@ARG@" not in result
    assert "value1" in result
    # shlex.quote should add quotes if needed
    assert "bash script.sh" in result


def test_replace_argument_placeholders_indexed():
    """Test indexed placeholder replacement @ARG_1@, @ARG_2@, etc."""
    from parallelr import replace_argument_placeholders

    command = "bash script.sh @ARG_1@ @ARG_2@ @ARG_3@"
    arguments = ["host", "port", "env"]
    result = replace_argument_placeholders(command, arguments)

    assert "@ARG_1@" not in result
    assert "@ARG_2@" not in result
    assert "@ARG_3@" not in result
    assert "host" in result
    assert "port" in result
    assert "env" in result


def test_replace_argument_placeholders_mixed():
    """Test mixed @ARG@ and indexed placeholders."""
    from parallelr import replace_argument_placeholders

    command = "bash script.sh @ARG@ --arg1 @ARG_1@ --arg2 @ARG_2@"
    arguments = ["first", "second"]
    result = replace_argument_placeholders(command, arguments)

    # @ARG@ should be replaced with first argument
    # @ARG_1@ should also be replaced with first argument
    # @ARG_2@ should be replaced with second argument
    assert "@ARG@" not in result
    assert "@ARG_1@" not in result
    assert "@ARG_2@" not in result
    assert result.count("first") >= 2  # Appears twice
    assert "second" in result


def test_replace_argument_placeholders_empty():
    """Test placeholder replacement with no arguments."""
    from parallelr import replace_argument_placeholders

    command = "bash script.sh @ARG@"
    arguments = []
    result = replace_argument_placeholders(command, arguments)

    # Should return unchanged when no arguments
    assert result == command


def test_replace_argument_placeholders_none():
    """Test placeholder replacement with None arguments."""
    from parallelr import replace_argument_placeholders

    command = "bash script.sh @ARG@"
    arguments = None
    result = replace_argument_placeholders(command, arguments)

    # Should return unchanged when None
    assert result == command


def test_replace_argument_placeholders_special_chars():
    """Test placeholder replacement with special characters."""
    from parallelr import replace_argument_placeholders

    command = "bash script.sh @ARG_1@"
    arguments = ["val; rm -rf /"]  # Potential injection
    result = replace_argument_placeholders(command, arguments)

    # shlex.quote should properly escape
    assert "@ARG_1@" not in result
    # Should be quoted/escaped
    assert "'" in result or "\\" in result


def test_replace_argument_placeholders_spaces():
    """Test placeholder replacement with values containing spaces."""
    from parallelr import replace_argument_placeholders

    command = "bash script.sh @ARG_1@"
    arguments = ["value with spaces"]
    result = replace_argument_placeholders(command, arguments)

    assert "@ARG_1@" not in result
    # Should be quoted
    assert "'" in result or '"' in result


def test_replace_argument_placeholders_unicode():
    """Test placeholder replacement with Unicode characters."""
    from parallelr import replace_argument_placeholders

    command = "bash script.sh @ARG_1@ @ARG_2@"
    arguments = ["Ümläut", "日本語"]
    result = replace_argument_placeholders(command, arguments)

    assert "@ARG_1@" not in result
    assert "@ARG_2@" not in result
    assert "Ümläut" in result or "mlaut" in result  # May be quoted
    assert "日本語" in result


def test_build_env_prefix_single():
    """Test environment variable prefix with single variable."""
    from parallelr import build_env_prefix

    env_var = "HOSTNAME"
    arguments = ["server1.example.com"]
    result = build_env_prefix(env_var, arguments)

    assert "HOSTNAME=" in result
    assert "server1.example.com" in result
    assert result.endswith(" ")  # Should end with space


def test_build_env_prefix_multiple():
    """Test environment variable prefix with multiple variables."""
    from parallelr import build_env_prefix

    env_var = "HOSTNAME,PORT,ENV"
    arguments = ["server1", "8080", "prod"]
    result = build_env_prefix(env_var, arguments)

    assert "HOSTNAME=" in result
    assert "PORT=" in result
    assert "ENV=" in result
    assert "server1" in result
    assert "8080" in result
    assert "prod" in result


def test_build_env_prefix_empty_env():
    """Test environment variable prefix with no env vars."""
    from parallelr import build_env_prefix

    env_var = None
    arguments = ["value"]
    result = build_env_prefix(env_var, arguments)

    assert result == ""


def test_build_env_prefix_empty_args():
    """Test environment variable prefix with no arguments."""
    from parallelr import build_env_prefix

    env_var = "VAR"
    arguments = []
    result = build_env_prefix(env_var, arguments)

    assert result == ""


def test_build_env_prefix_more_vars_than_args():
    """Test environment variable prefix when more vars than args."""
    from parallelr import build_env_prefix

    env_var = "VAR1,VAR2,VAR3"
    arguments = ["val1", "val2"]  # Only 2 arguments
    result = build_env_prefix(env_var, arguments)

    # Should only set variables for available arguments
    assert "VAR1=" in result
    assert "VAR2=" in result
    assert "VAR3" not in result  # Not enough arguments


def test_build_env_prefix_special_chars():
    """Test environment variable prefix with special characters in values."""
    from parallelr import build_env_prefix

    env_var = "VAR"
    arguments = ["value; echo hacked"]
    result = build_env_prefix(env_var, arguments)

    assert "VAR=" in result
    # Should be properly escaped
    assert "'" in result or "\\" in result


def test_build_env_prefix_spaces():
    """Test environment variable prefix with spaces in values."""
    from parallelr import build_env_prefix

    env_var = "PATH_VAR"
    arguments = ["/path/with spaces/file"]
    result = build_env_prefix(env_var, arguments)

    assert "PATH_VAR=" in result
    # Should be quoted
    assert "'" in result or '"' in result


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
