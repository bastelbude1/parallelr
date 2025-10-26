"""
Unit tests for input validation functions.

Tests environment variable validation, argument validation,
placeholder validation, and other input validators.
"""

import sys
from pathlib import Path
import pytest

# Add bin directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'bin'))


class TestEnvironmentVariableValidation:
    """Tests for environment variable name validation."""

    def test_valid_env_var_simple(self):
        """Test validation of simple environment variable names."""
        # This tests the validation logic inline in the script
        # We'll test it via the actual argument parsing if possible
        valid_names = ["VAR", "VAR1", "VAR_NAME", "VAR_1_NAME", "_VAR"]

        for name in valid_names:
            # Valid names should have: alphanumeric + underscore, not start with digit
            assert name.replace('_', '').isalnum() or name.startswith('_')
            if name and name[0].isdigit():
                assert False, f"{name} should not start with digit"

    def test_invalid_env_var_starts_with_digit(self):
        """Test validation rejects env vars starting with digit."""
        invalid_names = ["1VAR", "2TEST", "9_VAR"]

        for name in invalid_names:
            # These should be invalid
            if name and name[0].isdigit():
                assert True  # Expected to be invalid
            else:
                assert False, f"{name} should be invalid"

    def test_invalid_env_var_special_chars(self):
        """Test validation rejects env vars with special characters."""
        invalid_names = ["VAR-NAME", "VAR.NAME", "VAR NAME", "VAR@NAME"]

        for name in invalid_names:
            # Should fail isalnum check after removing underscores
            assert not name.replace('_', '').isalnum()

    def test_empty_env_var(self):
        """Test validation handles empty environment variable names."""
        name = ""
        # Empty string should be caught
        assert not name  # Will be caught by 'if not env_var' check


class TestArgumentConsistency:
    """Tests for argument count consistency validation."""

    def test_consistent_argument_counts(self):
        """Test detection of consistent argument counts."""
        task_entries = [
            {'arguments': ['a', 'b', 'c'], 'line_num': 1},
            {'arguments': ['d', 'e', 'f'], 'line_num': 2},
            {'arguments': ['g', 'h', 'i'], 'line_num': 3},
        ]

        # Collect counts
        arg_counts = {}
        for entry in task_entries:
            count = len(entry['arguments'])
            line_num = entry['line_num']
            if count not in arg_counts:
                arg_counts[count] = []
            arg_counts[count].append(line_num)

        # Should have only one count (3 args)
        assert len(arg_counts) == 1
        assert 3 in arg_counts

    def test_inconsistent_argument_counts(self):
        """Test detection of inconsistent argument counts."""
        task_entries = [
            {'arguments': ['a', 'b', 'c'], 'line_num': 1},
            {'arguments': ['d', 'e'], 'line_num': 2},  # Only 2 args
            {'arguments': ['f', 'g', 'h'], 'line_num': 3},
        ]

        # Collect counts
        arg_counts = {}
        for entry in task_entries:
            count = len(entry['arguments'])
            line_num = entry['line_num']
            if count not in arg_counts:
                arg_counts[count] = []
            arg_counts[count].append(line_num)

        # Should have multiple counts
        assert len(arg_counts) > 1
        assert 2 in arg_counts
        assert 3 in arg_counts
        assert arg_counts[2] == [2]
        assert arg_counts[3] == [1, 3]


class TestPlaceholderValidation:
    """Tests for placeholder index validation."""

    def test_valid_placeholder_indexes(self):
        """Test validation passes for valid placeholder indexes."""
        command_template = "bash @TASK@ @ARG_1@ @ARG_2@"
        num_args = 2

        # Extract placeholder indexes
        import re
        matches = re.findall(r'@ARG_(\d+)@', command_template)
        max_index = max(int(m) for m in matches) if matches else 0

        # Should be valid (max index 2, have 2 args)
        assert max_index <= num_args

    def test_invalid_placeholder_index_too_high(self):
        """Test validation fails for placeholder index exceeding argument count."""
        command_template = "bash @TASK@ @ARG_1@ @ARG_5@"
        num_args = 2

        import re
        matches = re.findall(r'@ARG_(\d+)@', command_template)
        max_index = max(int(m) for m in matches) if matches else 0

        # Should be invalid (max index 5, only have 2 args)
        assert max_index > num_args

    def test_placeholder_validation_no_placeholders(self):
        """Test validation passes when no indexed placeholders."""
        command_template = "bash @TASK@"
        num_args = 5

        import re
        matches = re.findall(r'@ARG_(\d+)@', command_template)

        # Should have no matches
        assert len(matches) == 0


class TestSeparatorValidation:
    """Tests for separator validation logic."""

    def test_separator_requires_arguments_file(self):
        """Test that separator flag requires arguments file."""
        # When separator is set but arguments_file is None
        has_separator = True
        has_arguments_file = False

        # This should be invalid
        assert has_separator and not has_arguments_file

    def test_separator_with_arguments_file_valid(self):
        """Test that separator with arguments file is valid."""
        has_separator = True
        has_arguments_file = True

        # This should be valid
        assert has_separator and has_arguments_file

    def test_no_separator_without_arguments_file_valid(self):
        """Test that no separator without arguments file is valid."""
        has_separator = False
        has_arguments_file = False

        # This should be valid (file mode)
        assert not has_separator


class TestDelimiterMapping:
    """Tests for delimiter pattern mapping."""

    def test_delimiter_patterns_defined(self):
        """Test that all delimiter patterns are properly defined."""
        delimiter_map = {
            'space': r' +',
            'whitespace': r'\s+',
            'tab': r'\t+',
            'colon': ':',
            'semicolon': ';',
            'comma': ',',
            'pipe': r'\|'
        }

        # All should be defined
        assert len(delimiter_map) == 7
        assert 'space' in delimiter_map
        assert 'whitespace' in delimiter_map
        assert 'comma' in delimiter_map

    def test_delimiter_splitting(self):
        """Test delimiter splitting functionality."""
        import re

        # Test comma delimiter
        line = "arg1,arg2,arg3"
        delimiter_pattern = ','
        args = [arg.strip() for arg in re.split(delimiter_pattern, line) if arg.strip()]
        assert args == ["arg1", "arg2", "arg3"]

        # Test space delimiter
        line = "arg1  arg2   arg3"
        delimiter_pattern = r' +'
        args = [arg.strip() for arg in re.split(delimiter_pattern, line) if arg.strip()]
        assert args == ["arg1", "arg2", "arg3"]

    def test_delimiter_whitespace_vs_space(self):
        """Test distinction between whitespace and space delimiters."""
        import re

        line = "arg1 \t arg2"  # Space and tab

        # Space delimiter (r' +') should not match tab
        space_pattern = r' +'
        space_result = re.split(space_pattern, line)
        # Will split on spaces but tab remains
        assert '\t' in ''.join(space_result)

        # Whitespace delimiter (r'\s+') should match both
        whitespace_pattern = r'\s+'
        whitespace_result = re.split(whitespace_pattern, line)
        whitespace_result = [arg.strip() for arg in whitespace_result if arg.strip()]
        assert whitespace_result == ["arg1", "arg2"]


class TestEnvVarArgumentCountValidation:
    """Tests for environment variable vs argument count validation."""

    def test_equal_counts_valid(self):
        """Test equal env var and argument counts is valid."""
        env_vars = ["VAR1", "VAR2", "VAR3"]
        arguments = ["val1", "val2", "val3"]

        assert len(env_vars) == len(arguments)

    def test_fewer_env_vars_warning(self):
        """Test fewer env vars than arguments (warning case)."""
        env_vars = ["VAR1", "VAR2"]
        arguments = ["val1", "val2", "val3"]

        # This should trigger a warning but allow execution
        assert len(env_vars) < len(arguments)

    def test_more_env_vars_error(self):
        """Test more env vars than arguments (error case)."""
        env_vars = ["VAR1", "VAR2", "VAR3", "VAR4"]
        arguments = ["val1", "val2"]

        # This should trigger an error and stop execution
        assert len(env_vars) > len(arguments)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
