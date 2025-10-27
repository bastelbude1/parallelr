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
    import os

    task_file = temp_dir / 'task.sh'
    task_file.write_text('#!/bin/bash\necho "test"\n')
    task_file.chmod(0o755)

    # Use deterministic sentinel in temp_dir for shell-breakout attempt
    sentinel = temp_dir / 'env_injection_sentinel'

    # Inject malicious payload in VAR2 to attempt creating sentinel
    args_file = temp_dir / 'args.txt'
    args_file.write_text(f'value1,value2; touch {sentinel},value3\n')

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

    # Should complete successfully (environment variables are properly escaped)
    assert result.returncode == 0, (
        f"Expected successful execution, got returncode {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )

    # Sentinel should NOT exist (injection should be prevented)
    assert not os.path.exists(sentinel), (
        f"SECURITY FAILURE: Environment variable injection succeeded - "
        f"sentinel {sentinel} was created"
    )

    # Cleanup: remove sentinel if it exists (avoid test pollution)
    if os.path.exists(sentinel):
        os.remove(sentinel)


@pytest.mark.security
def test_backtick_injection_in_arguments(temp_dir):
    """Test that backticks in arguments don't execute commands."""
    import os

    task_file = temp_dir / 'task.sh'
    task_file.write_text('#!/bin/bash\necho "$1"\n')
    task_file.chmod(0o755)

    # Use unique sentinel that would be produced if whoami executed
    current_user = os.environ.get('USER', 'unknown')
    sentinel = f"UNIQUE_SENTINEL_{current_user}"

    # Write backtick and $(...) injection attempts with sentinel
    args_file = temp_dir / 'args.txt'
    args_file.write_text(f'`whoami`{sentinel}\n$(whoami){sentinel}\n')

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

    # Should complete successfully (backticks treated as literals)
    assert result.returncode == 0, (
        f"Expected successful execution, got returncode {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )

    # Key security check: Sentinel should NOT appear alone (command substitution didn't execute)
    # If whoami executed, we'd see patterns like "baste" immediately followed by or near sentinel
    # But the sentinel is appended directly to the substitution attempt in the args file
    assert sentinel not in result.stdout and sentinel not in result.stderr, (
        f"SECURITY FAILURE: Command substitution executed - "
        f"sentinel '{sentinel}' found in output (should not appear alone if whoami didn't run)"
    )

    # Check pattern that would indicate execution: username appearing without the literal syntax
    # If command substitution executed, we'd see: {username}{sentinel}
    # Instead we should see: `whoami`{sentinel} or $(whoami){sentinel}
    executed_pattern = f'{current_user}{sentinel}'

    assert executed_pattern not in result.stdout, (
        f"SECURITY FAILURE: Command substitution executed - "
        f"pattern '{executed_pattern}' found (whoami returned username)"
    )
    assert executed_pattern not in result.stderr, (
        f"SECURITY FAILURE: Command substitution executed - "
        f"pattern '{executed_pattern}' found in stderr"
    )

    # Verify tasks completed successfully (both tasks should succeed)
    assert 'Completed Successfully: 2' in result.stdout or 'completed: 2' in result.stdout, (
        f"Expected 2 successful tasks, check output:\n{result.stdout}"
    )

    # Additional verification: read the task output log file
    # The log file will contain the actual command execution details
    import glob
    log_pattern = str(Path.home() / 'parallelr' / 'logs' / 'parallelr_*_output.txt')
    log_files = glob.glob(log_pattern)
    if log_files:
        latest_log = max(log_files, key=os.path.getmtime)
        with open(latest_log, 'r') as f:
            log_content = f.read()

        # Verify literals appear in the log (not executed)
        assert '`whoami`' in log_content, (
            f"Expected literal `whoami` in log file {latest_log}"
        )
        assert '$(whoami)' in log_content, (
            f"Expected literal $(whoami) in log file {latest_log}"
        )

        # Verify the sentinel appears with the literal syntax, not standalone
        # Pattern in log should be: `whoami`{sentinel} or $(whoami){sentinel}
        backtick_pattern = f'`whoami`{sentinel}'
        dollar_paren_pattern = f'$(whoami){sentinel}'

        assert backtick_pattern in log_content or dollar_paren_pattern in log_content, (
            f"Expected literal command substitution syntax with sentinel in log.\n"
            f"Looking for: {backtick_pattern} or {dollar_paren_pattern}\n"
            f"Log file: {latest_log}"
        )


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

    # Normalize newlines for cross-platform matching
    stdout_normalized = result.stdout.replace('\r\n', '\n')
    stderr_normalized = result.stderr.replace('\r\n', '\n')

    # Should handle or reject null bytes safely without crashing
    # Allow success (0) or validation failure (1), but not crashes
    assert result.returncode in [0, 1], (
        f"Process crashed or returned unexpected code: {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )

    # Verify no crash indicators
    assert 'Traceback' not in stderr_normalized, (
        f"Process crashed with Python traceback:\n{result.stderr}"
    )
    assert 'Segmentation' not in stderr_normalized, (
        f"Process crashed with segmentation fault:\n{result.stderr}"
    )

    # Verify stderr does not contain raw null bytes
    assert '\x00' not in stderr_normalized, (
        "Null bytes leaked into stderr - potential security issue"
    )

    # Check both acceptable behaviors
    if result.returncode == 0:
        # Tool accepted null bytes (dry-run mode handles them)
        # Verify task was created successfully
        assert 'Created 1 tasks' in stdout_normalized or 'Created 1 task' in stdout_normalized, (
            f"Expected task creation message in stdout:\n{result.stdout}"
        )
        # Verify dry-run mode shows the command
        assert 'DRY RUN MODE' in stdout_normalized or '@TASK@' in stdout_normalized, (
            f"Expected dry-run output or command template in stdout:\n{result.stdout}"
        )
        # stderr should be empty or only contain non-fatal warnings
        assert stderr_normalized == '' or 'warning' in stderr_normalized.lower(), (
            f"Expected empty stderr or warnings only, got:\n{result.stderr}"
        )
    else:
        # Tool rejected null bytes (execution mode validates input)
        assert result.returncode == 1, (
            f"Expected returncode 1 for validation failure, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        # Verify error message indicates null byte or validation failure
        output = stdout_normalized + stderr_normalized
        null_byte_indicators = [
            'null byte',
            'null character',
            'embedded null',
            'invalid input',
            'validation',
            'failed'
        ]
        found_indicator = any(indicator.lower() in output.lower() for indicator in null_byte_indicators)
        assert found_indicator, (
            f"Expected error message about null bytes or validation failure.\n"
            f"Looking for any of: {null_byte_indicators}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )


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
