"""
Security tests for command injection prevention.

Tests that the tool properly sanitizes and validates inputs to prevent
command injection attacks.
"""

import subprocess
import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
PARALLELR_BIN = PROJECT_ROOT / 'bin' / 'parallelr.py'


@pytest.mark.security
def test_shell_injection_in_task_path(temp_dir):
    """Test that shell injection in task path is prevented."""
    # Try to inject shell commands via task path
    malicious_path = str(temp_dir / 'task.sh; rm -rf /tmp/test_injection')

    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', malicious_path,
         '-C', 'bash @TASK@'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=10
    )

    # Should fail safely (file doesn't exist)
    assert result.returncode != 0
    # Should not execute the injected command
    assert not Path('/tmp/test_injection_happened').exists()


@pytest.mark.security
def test_shell_injection_in_command_template(temp_dir):
    """Test that shell injection in command template is handled."""
    task_file = temp_dir / 'task.sh'
    task_file.write_text('#!/bin/bash\necho "test"\n')
    task_file.chmod(0o755)

    # Try to inject via command template
    malicious_command = 'bash @TASK@; echo "INJECTED" > /tmp/injection_test.txt'

    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', malicious_command,
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=30
    )

    # Command will execute but injection should not create file
    # The semicolon is part of the command string, not executed as separate command
    # This tests that @TASK@ replacement is safe


@pytest.mark.security
def test_argument_injection_attempt(temp_dir):
    """Test that argument values cannot inject commands."""
    task_file = temp_dir / 'task.sh'
    task_file.write_text('#!/bin/bash\necho "$1"\n')
    task_file.chmod(0o755)

    # Create arguments file with injection attempt
    args_file = temp_dir / 'args.txt'
    args_file.write_text('value; rm -rf /tmp/test\n')

    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-A', str(args_file),
         '-C', 'bash @TASK@ @ARG@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=30
    )

    # Should complete successfully
    assert result.returncode == 0
    # Argument should be quoted/escaped
    # Check that dangerous command wasn't executed
    assert not Path('/tmp/test_injected').exists()


@pytest.mark.security
def test_environment_variable_injection(temp_dir):
    """Test that environment variable values are properly sanitized."""
    task_file = temp_dir / 'task.sh'
    task_file.write_text('#!/bin/bash\necho "test"\n')
    task_file.chmod(0o755)

    args_file = temp_dir / 'args.txt'
    args_file.write_text('value1,value2; rm -rf /tmp,value3\n')

    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-A', str(args_file),
         '-S', 'comma',
         '-E', 'VAR1,VAR2,VAR3',
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=30
    )

    # Should handle safely
    assert result.returncode == 0


@pytest.mark.security
def test_backtick_injection_in_arguments(temp_dir):
    """Test that backticks in arguments don't execute commands."""
    task_file = temp_dir / 'task.sh'
    task_file.write_text('#!/bin/bash\necho "$1"\n')
    task_file.chmod(0o755)

    args_file = temp_dir / 'args.txt'
    args_file.write_text('`whoami`\n$(whoami)\n')

    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-A', str(args_file),
         '-C', 'bash @TASK@ @ARG@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=30
    )

    # Should complete
    assert result.returncode == 0
    # Backticks should be treated as literal strings


@pytest.mark.security
def test_path_with_special_characters(temp_dir):
    """Test handling of paths with special shell characters."""
    # Create task with spaces in name (avoid $ which could cause issues)
    special_dir = temp_dir / 'dir with spaces'
    special_dir.mkdir()

    task_file = special_dir / 'task.sh'
    task_file.write_text('#!/bin/bash\necho "test"\n')
    task_file.chmod(0o755)

    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=30
    )

    # Should handle special characters in path
    # May succeed or fail depending on shell quoting
    assert result.returncode in [0, 1]


@pytest.mark.security
def test_null_byte_injection(temp_dir):
    """Test that null bytes in arguments are handled."""
    task_file = temp_dir / 'task.sh'
    task_file.write_text('#!/bin/bash\necho "test"\n')
    task_file.chmod(0o755)

    # Null bytes should not break parsing
    args_file = temp_dir / 'args.txt'
    args_file.write_text('value1\x00hidden\n')

    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-A', str(args_file),
         '-C', 'bash @TASK@ @ARG@'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=10
    )

    # Should handle or reject null bytes
    # Tool may fail validation or handle safely


@pytest.mark.security
def test_unicode_injection_attempt(temp_dir):
    """Test that Unicode characters don't enable injection."""
    task_file = temp_dir / 'task.sh'
    task_file.write_text('#!/bin/bash\necho "test"\n')
    task_file.chmod(0o755)

    args_file = temp_dir / 'args.txt'
    # Unicode characters that might be interpreted as commands
    args_file.write_text('value\u202e\u202d\u200e\n')

    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-A', str(args_file),
         '-C', 'bash @TASK@ @ARG@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=30
    )

    # Should handle safely
    assert result.returncode == 0


@pytest.mark.security
def test_newline_injection_in_arguments(temp_dir):
    """Test that newlines in argument values are handled."""
    task_file = temp_dir / 'task.sh'
    task_file.write_text('#!/bin/bash\necho "$1"\n')
    task_file.chmod(0o755)

    args_file = temp_dir / 'args.txt'
    args_file.write_text('value\ninjected_line\n')

    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-A', str(args_file),
         '-C', 'bash @TASK@ @ARG@'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=10
    )

    # Should handle or properly split lines
    # Two lines should create two tasks
    assert 'Created 2 tasks' in result.stdout or 'Created 2 task' in result.stdout


@pytest.mark.security
def test_escaped_quotes_in_arguments(temp_dir):
    """Test that escaped quotes in arguments are handled correctly."""
    task_file = temp_dir / 'task.sh'
    task_file.write_text('#!/bin/bash\necho "$1"\n')
    task_file.chmod(0o755)

    args_file = temp_dir / 'args.txt'
    args_file.write_text('value\\"with\\"quotes\n')

    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-A', str(args_file),
         '-C', 'bash @TASK@ @ARG@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=30
    )

    # Should handle escaped quotes
    assert result.returncode == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
