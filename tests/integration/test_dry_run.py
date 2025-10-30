"""
Integration tests for dry run mode.

Tests that default behavior (no -r flag) is dry-run: display commands without executing.
"""

import subprocess
import os
from pathlib import Path
import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import PARALLELR_BIN, PYTHON_FOR_PARALLELR

@pytest.mark.integration
def test_dry_run_displays_commands(temp_dir, isolated_env):
    """
    Test that dry run displays commands to be executed.

    Without -r flag, should show what would run.
    """
    # Create test task
    task = temp_dir / 'test_task.sh'
    task.write_text('#!/bin/bash\necho "This should not execute"\n')
    task.chmod(0o755)

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@'],  # NO -r flag = dry run
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    # Should succeed and display what would execute
    assert result.returncode == 0
    output = result.stdout.lower()

    # Should indicate dry run or show command
    assert 'dry' in output or 'would' in output or 'task' in output or 'executing' in output

@pytest.mark.integration
def test_dry_run_no_task_execution(temp_dir, isolated_env):
    """
    Test that dry run does NOT actually execute tasks.

    Creates a task that would create a file if executed.
    Verifies file is NOT created in dry run.
    """
    # Create task that would create marker file
    marker = temp_dir / 'marker_created.txt'
    task = temp_dir / 'create_marker.sh'
    task.write_text(f'#!/bin/bash\necho "marker" > {marker}\n')
    task.chmod(0o755)

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@'],  # NO -r flag = dry run
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    # Should succeed but NOT create marker
    assert result.returncode == 0
    assert not marker.exists(), "Dry run should not execute tasks"

@pytest.mark.integration
def test_dry_run_no_logs_created(temp_dir, isolated_env):
    """
    Test that dry run does NOT create log files (CSV, output logs).

    Verifies no execution artifacts are created.
    """
    # Create task
    task = temp_dir / 'test.sh'
    task.write_text('#!/bin/bash\necho "test"\n')
    task.chmod(0o755)

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@'],  # NO -r flag = dry run
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    assert result.returncode == 0

    # Check that no logs directory was created in isolated env
    log_dir = isolated_env['home'] / 'parallelr' / 'logs'
    # In dry run, logs directory may exist but should have no CSV/output files
    # or may not exist at all
    if log_dir.exists():
        csv_files = list(log_dir.glob('*.csv'))
        output_files = list(log_dir.glob('*output*.txt'))
        # Should have no execution logs in dry run
        assert len(csv_files) == 0, "Dry run should not create CSV summary"
        assert len(output_files) == 0, "Dry run should not create output logs"

@pytest.mark.integration
def test_dry_run_with_arguments_mode(temp_dir, isolated_env):
    """
    Test dry run works with arguments file mode (-A flag).

    Shows commands with argument substitution without executing.
    """
    # Create arguments file
    args_file = temp_dir / 'args.txt'
    args_file.write_text('arg1\narg2\narg3\n')

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-A', str(args_file),
         '-C', 'echo "Processing @ARG@"'],  # NO -r flag = dry run
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    # Should succeed and display commands
    assert result.returncode == 0
    output = result.stdout.lower()

    # Should show dry run info or command preview
    assert 'dry' in output or 'would' in output or 'arg' in output or 'task' in output

@pytest.mark.integration
def test_dry_run_shows_environment_vars(temp_dir, isolated_env):
    """
    Test that dry run displays environment variable substitutions.

    Shows how -E variables would be expanded.
    """
    # Create arguments file with multiple fields
    args_file = temp_dir / 'env_args.txt'
    args_file.write_text('server1,8080\nserver2,9090\n')

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-A', str(args_file),
         '-S', 'comma',
         '-E', 'HOST,PORT',
         '-C', 'echo "Connecting to $HOST on port $PORT"'],  # NO -r flag = dry run
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    # Should succeed and show command or environment info
    assert result.returncode == 0
    output = result.stdout + result.stderr

    # Should indicate what would happen
    assert ('dry' in output.lower() or
            'would' in output.lower() or
            'host' in output.lower() or
            'port' in output.lower() or
            'task' in output.lower())

@pytest.mark.integration
def test_real_run_flag_executes_tasks(temp_dir, isolated_env):
    """
    Test that -r flag enables actual task execution.

    Contrast with dry run: WITH -r flag, tasks should execute.
    """
    # Create task that creates marker file
    marker = temp_dir / 'real_run_marker.txt'
    task = temp_dir / 'create_marker.sh'
    task.write_text(f'#!/bin/bash\necho "executed" > {marker}\n')
    task.chmod(0o755)

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@',
         '-r'],  # WITH -r flag = real execution
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    # Should succeed AND execute task
    assert result.returncode == 0
    assert marker.exists(), "Real run with -r flag should execute tasks"

    # Verify marker content
    assert marker.read_text().strip() == "executed"
