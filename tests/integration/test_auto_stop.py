"""
Integration tests for auto-stop protection.

Tests --enable-stop-limits flag and failure thresholds.
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
    parse_csv_summary
)

# Skip all tests if bash is not available (POSIX dependency)
pytestmark = pytest.mark.skipif(shutil.which("bash") is None,
                                reason="Requires bash (POSIX)")

@pytest.mark.integration
def test_auto_stop_consecutive_failures(temp_dir, isolated_env):
    """
    Test auto-stop after 5 consecutive failures (default threshold).

    Creates 10 failing tasks, expects execution to stop after 5.
    """
    # Create 10 failing tasks
    for i in range(10):
        task = temp_dir / f'fail_{i}.sh'
        task.write_text('#!/bin/bash\nexit 1\n')  # Always fail
        task.chmod(0o755)

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@',
         '-r', '--enable-stop-limits', '-m', '1'],  # Single worker for consecutive
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    # Should fail/stop due to consecutive failures
    # Exit code may be non-zero due to auto-stop
    combined = result.stdout + result.stderr

    # Verify auto-stop was triggered
    assert 'auto-stop' in combined.lower() or 'consecutive' in combined.lower()

    # Check CSV - should have stopped before completing all 10 tasks
    csv_path = extract_log_path_from_stdout(result.stdout, 'summary')
    if csv_path:
        csv_records = parse_csv_summary(csv_path)
        # Should have stopped, likely around 5-6 tasks
        assert len(csv_records) < 10, "Auto-stop should prevent all 10 tasks from completing"

@pytest.mark.integration
def test_auto_stop_failure_rate_threshold(temp_dir, isolated_env):
    """
    Test auto-stop when failure rate exceeds 50% threshold.

    Creates mix of passing and failing tasks to trigger rate threshold.
    """
    # Create 15 tasks: 3 succeed, 12 fail (80% failure rate)
    for i in range(3):
        task = temp_dir / f'pass_{i}.sh'
        task.write_text('#!/bin/bash\necho "success"\nexit 0\n')
        task.chmod(0o755)

    for i in range(12):
        task = temp_dir / f'fail_{i}.sh'
        task.write_text('#!/bin/bash\nexit 1\n')
        task.chmod(0o755)

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@',
         '-r', '--enable-stop-limits', '-m', '2'],  # Multiple workers
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    combined = result.stdout + result.stderr

    # Should trigger auto-stop due to high failure rate
    assert 'auto-stop' in combined.lower() or 'failure rate' in combined.lower() or 'rate' in combined.lower()

@pytest.mark.integration
def test_auto_stop_requires_min_tasks_for_rate(temp_dir, isolated_env):
    """
    Test that failure rate check requires min_tasks_for_rate_check (default: 10).

    With only 5 failing tasks, rate check should NOT trigger (need >=10).
    Consecutive check should trigger instead.
    """
    # Create only 5 failing tasks (below min_tasks_for_rate_check=10)
    for i in range(5):
        task = temp_dir / f'fail_{i}.sh'
        task.write_text('#!/bin/bash\nexit 1\n')
        task.chmod(0o755)

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@',
         '-r', '--enable-stop-limits', '-m', '1'],  # Sequential
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    combined = result.stdout + result.stderr

    # Should stop via consecutive failures (5 consecutive), NOT rate
    # Rate check needs >=10 tasks
    assert 'consecutive' in combined.lower() or 'auto-stop' in combined.lower()

@pytest.mark.integration
def test_auto_stop_not_triggered_without_flag(temp_dir, isolated_env):
    """
    Test that auto-stop is disabled by default (requires --enable-stop-limits).

    Creates failing tasks WITHOUT flag, verifies all execute.
    """
    # Create 10 failing tasks
    for i in range(10):
        task = temp_dir / f'fail_{i}.sh'
        task.write_text('#!/bin/bash\nexit 1\n')
        task.chmod(0o755)

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '1'],  # NO --enable-stop-limits
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    # Should complete all tasks (no auto-stop)
    csv_path = extract_log_path_from_stdout(result.stdout, 'summary')
    if csv_path:
        csv_records = parse_csv_summary(csv_path)
        # All 10 tasks should execute
        assert len(csv_records) == 10, "Without --enable-stop-limits, all tasks should run"

@pytest.mark.integration
def test_auto_stop_logs_reason(temp_dir, isolated_env):
    """
    Test that auto-stop logs the specific reason (consecutive vs rate).

    Creates scenario for consecutive failures and checks error message.
    """
    # Create 10 failing tasks
    for i in range(10):
        task = temp_dir / f'fail_{i}.sh'
        task.write_text('#!/bin/bash\nexit 1\n')
        task.chmod(0o755)

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@',
         '-r', '--enable-stop-limits', '-m', '1'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    combined = result.stdout + result.stderr

    # Should log specific reason for stop
    # Expect "consecutive failures" message
    assert ('consecutive' in combined.lower() or
            'limit' in combined.lower() or
            'auto-stop' in combined.lower())

@pytest.mark.integration
def test_auto_stop_partial_completion_in_csv(temp_dir, isolated_env):
    """
    Test that CSV shows partial task completion when auto-stop triggers.

    Verifies CSV contains the tasks that were executed before stopping.
    """
    # Create 15 failing tasks
    for i in range(15):
        task = temp_dir / f'fail_{i}.sh'
        task.write_text('#!/bin/bash\nexit 1\n')
        task.chmod(0o755)

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@',
         '-r', '--enable-stop-limits', '-m', '1'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    # Extract CSV and verify partial completion
    csv_path = extract_log_path_from_stdout(result.stdout, 'summary')
    assert csv_path, "CSV summary should be created even with auto-stop"

    csv_records = parse_csv_summary(csv_path)

    # Should have some records but not all 15
    assert len(csv_records) > 0, "Some tasks should be recorded before auto-stop"
    assert len(csv_records) < 15, "Auto-stop should prevent all tasks from completing"

    # All recorded tasks should have failed (status != SUCCESS)
    for record in csv_records:
        assert record['status'] != 'SUCCESS', "All tasks in this test fail"
