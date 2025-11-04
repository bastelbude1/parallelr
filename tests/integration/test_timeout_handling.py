"""
Integration tests for timeout handling in parallel execution.

Tests the futures timeout exception path and related edge cases.
"""

import subprocess
import os
import shutil
from pathlib import Path
import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import PARALLELR_BIN, PYTHON_FOR_PARALLELR
from tests.integration.test_helpers import (
    extract_log_path_from_stdout,
    parse_csv_summary,
    verify_csv_completeness,
    verify_all_tasks_succeeded,
    verify_worker_assignments,
    verify_durations_reasonable,
    verify_summary_counts
)

# Skip all tests if bash is not available (POSIX dependency)
pytestmark = pytest.mark.skipif(shutil.which("bash") is None,
                                reason="Requires bash (POSIX)")

@pytest.mark.integration
def test_futures_timeout_with_slow_tasks(temp_dir, isolated_env):
    """
    Test futures timeout handling when workers are busy with slow tasks.

    This test exercises the timeout exception path at line 1478 in parallelr.py:
        except concurrent.futures.TimeoutError:

    The timeout occurs when as_completed() waits for futures longer than wait_time
    (default 0.1s) and all workers are busy with slow tasks.

    This test caught the bug where TimeoutError wasn't imported properly.
    """
    # Create multiple slow tasks that take longer than wait_time (0.1s)
    for i in range(3):
        slow_task = temp_dir / f'slow_task_{i}.sh'
        # Each task sleeps for 0.3s (longer than wait_time=0.1s)
        slow_task.write_text('#!/bin/bash\nsleep 0.3\necho "Task completed"\n')
        slow_task.chmod(0o755)

    # Run with max_workers=1 so only one task runs at a time
    # This ensures workers are busy long enough to trigger timeout
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '1'],  # Single worker forces sequential execution
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    # Basic success check
    assert result.returncode == 0, f"Command failed: {result.stderr}"

    # Verify summary counts in stdout
    verify_summary_counts(result.stdout, total=3, completed=3, failed=0)

    # Extract and parse CSV summary
    csv_path = extract_log_path_from_stdout(result.stdout, 'summary')
    assert csv_path, "Could not find CSV summary path in stdout"

    csv_records = parse_csv_summary(csv_path)

    # Verify CSV has exact 3 records with all required fields
    verify_csv_completeness(csv_records, expected_count=3)

    # Verify all tasks succeeded (STATUS=SUCCESS, exit_code=0)
    verify_all_tasks_succeeded(csv_records)

    # Verify worker IDs are all 1 (single worker configured)
    verify_worker_assignments(csv_records, max_workers=1)

    # Verify each task took at least 0.2s (we sleep for 0.3s)
    # Use lenient bounds for CI environments which can be slower
    verify_durations_reasonable(csv_records, min_duration=0.2, max_duration=5.0)

@pytest.mark.integration
def test_futures_timeout_with_arguments_mode(temp_dir, isolated_env):
    """
    Test futures timeout handling in arguments-only mode with slow commands.

    This verifies the timeout exception handling works correctly in the
    arguments-only execution path as well.
    """
    # Create arguments file with multiple entries
    args_file = temp_dir / 'args.txt'
    args_file.write_text('arg1\narg2\narg3\n')

    # Use a slow command (sleep longer than wait_time=0.1s)
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-A', str(args_file),
         '-C', 'bash -c "sleep 0.3 && echo Processing @ARG@"',
         '-r', '-m', '1'],  # Single worker
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    # Basic success check
    assert result.returncode == 0, f"Command failed: {result.stderr}"

    # Verify summary counts in stdout
    verify_summary_counts(result.stdout, total=3, completed=3, failed=0)

    # Extract and parse CSV summary
    csv_path = extract_log_path_from_stdout(result.stdout, 'summary')
    assert csv_path, "Could not find CSV summary path in stdout"

    csv_records = parse_csv_summary(csv_path)

    # Verify CSV has exact 3 records with all required fields
    verify_csv_completeness(csv_records, expected_count=3)

    # Verify all tasks succeeded (STATUS=SUCCESS, exit_code=0)
    verify_all_tasks_succeeded(csv_records)

    # Verify worker IDs are all 1 (single worker configured)
    verify_worker_assignments(csv_records, max_workers=1)

    # Verify each task took at least 0.2s (we sleep for 0.3s)
    # Use lenient bounds for CI environments
    verify_durations_reasonable(csv_records, min_duration=0.2, max_duration=5.0)

    # Verify @ARG@ placeholder was replaced in command_executed field
    for record in csv_records:
        assert '@ARG@' not in record['command_executed'], "Placeholder @ARG@ was not replaced in command_executed"

@pytest.mark.integration
def test_futures_timeout_with_multiple_workers(temp_dir, isolated_env):
    """
    Test futures timeout with multiple workers processing slow tasks.

    Even with multiple workers, if all are busy, timeouts should be handled properly.
    """
    # Create enough slow tasks to keep all workers busy
    for i in range(6):
        slow_task = temp_dir / f'task_{i}.sh'
        slow_task.write_text('#!/bin/bash\nsleep 0.3\necho "Done"\n')
        slow_task.chmod(0o755)

    # Run with 2 workers - still slower than wait_time
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '2'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    # Basic success check
    assert result.returncode == 0, f"Command failed: {result.stderr}"

    # Verify summary counts in stdout
    verify_summary_counts(result.stdout, total=6, completed=6, failed=0)

    # Extract and parse CSV summary
    csv_path = extract_log_path_from_stdout(result.stdout, 'summary')
    assert csv_path, "Could not find CSV summary path in stdout"

    csv_records = parse_csv_summary(csv_path)

    # Verify CSV has exact 6 records with all required fields
    verify_csv_completeness(csv_records, expected_count=6)

    # Verify all tasks succeeded (STATUS=SUCCESS, exit_code=0)
    verify_all_tasks_succeeded(csv_records)

    # Verify worker IDs are properly assigned (2 workers configured)
    verify_worker_assignments(csv_records, max_workers=2)

    # Verify each task took at least 0.2s (we sleep for 0.3s)
    # Use lenient bounds for CI environments
    verify_durations_reasonable(csv_records, min_duration=0.2, max_duration=5.0)

@pytest.mark.integration
def test_no_timeout_with_fast_tasks(temp_dir, isolated_env):
    """
    Test that fast tasks complete without triggering timeout path.

    This is the normal case - tasks complete faster than wait_time.
    Included for completeness to show the difference.
    """
    # Create fast tasks
    for i in range(3):
        fast_task = temp_dir / f'fast_{i}.sh'
        fast_task.write_text('#!/bin/bash\necho "Quick task"\n')
        fast_task.chmod(0o755)

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '2'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    assert result.returncode == 0
    assert 'Discovered 3 task files' in result.stdout
