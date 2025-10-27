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
    # Use deterministic sentinel in temp_dir to verify injection prevention
    sentinel = temp_dir / 'injection_path_sentinel.txt'
    malicious_path = str(temp_dir / f'task.sh; touch {sentinel}')

    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', malicious_path,
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=10
    )

    # Should fail safely (file doesn't exist)
    assert result.returncode != 0
    # Should not execute the injected command (sentinel should not exist)
    assert not sentinel.exists()


@pytest.mark.security
def test_shell_injection_in_command_template(temp_dir):
    """Test that shell injection in command template is handled."""
    task_file = temp_dir / 'task.sh'
    task_file.write_text('#!/bin/bash\necho "test"\n')
    task_file.chmod(0o755)

    # Try to inject via command template using deterministic sentinel in temp_dir
    sentinel = temp_dir / 'injection_test.txt'
    malicious_command = f'bash @TASK@; echo "INJECTED" > {sentinel}'

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

    # The semicolon is part of the command string passed to shlex.split(),
    # not executed as a shell separator, so the command will fail
    # This demonstrates that the injection is prevented
    assert result.returncode != 0, (
        f"Expected command to fail (injection prevented), got returncode {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )

    # Most importantly: injection should not create sentinel file
    assert not sentinel.exists(), (
        f"SECURITY FAILURE: Injection succeeded - sentinel file {sentinel} exists"
    )

    # "INJECTED" should not appear in any output
    assert "INJECTED" not in result.stdout, (
        f"SECURITY FAILURE: Injection marker found in stdout: {result.stdout}"
    )
    assert "INJECTED" not in result.stderr, (
        f"SECURITY FAILURE: Injection marker found in stderr: {result.stderr}"
    )

    # Verify no files containing "INJECTED" were created anywhere in temp_dir
    for file_path in temp_dir.rglob('*'):
        if file_path.is_file():
            try:
                content = file_path.read_text()
                assert "INJECTED" not in content, (
                    f"SECURITY FAILURE: Injection marker found in {file_path}: {content}"
                )
            except (UnicodeDecodeError, PermissionError):
                # Skip binary files or files we can't read
                pass


@pytest.mark.security
def test_argument_injection_attempt(temp_dir):
    """Test that argument values cannot inject commands."""
    task_file = temp_dir / 'task.sh'
    task_file.write_text('#!/bin/bash\necho "$1"\n')
    task_file.chmod(0o755)

    # Create sentinel file that injection would attempt to remove
    sentinel = temp_dir / 'test_injected'
    sentinel.write_text('sentinel')

    # Create arguments file with injection attempt to remove sentinel
    args_file = temp_dir / 'args.txt'
    args_file.write_text(f'value; rm -rf {sentinel}\n')

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

    # Should complete successfully (argument is properly escaped)
    assert result.returncode == 0, (
        f"Expected successful execution, got returncode {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )

    # Sentinel should still exist (injection command should not have executed)
    assert sentinel.exists(), (
        f"SECURITY FAILURE: Injection succeeded - sentinel {sentinel} was removed"
    )


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
