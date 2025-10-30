"""
Integration tests for task timeout enforcement.

Tests that tasks are killed after timeout_seconds and status is recorded correctly.
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


@pytest.fixture
def isolated_env(tmp_path):
    """
    Provide isolated environment for timeout tests.

    Creates a subprocess-only environment without mutating global os.environ.
    Safe for parallel test execution.
    """
    temp_home = tmp_path / 'home'
    temp_home.mkdir()

    # Create isolated environment copy for subprocess use only
    env_copy = {**os.environ, 'HOME': str(temp_home)}

    yield {
        'home': temp_home,
        'env': env_copy
    }


@pytest.mark.integration
def test_task_timeout_kills_long_running_task(temp_dir, isolated_env):
    """
    Test that task is killed when it exceeds timeout.

    Creates a task that sleeps longer than timeout, verifies it's killed.
    """
    # Create task that sleeps for 10 seconds (much longer than timeout)
    task = temp_dir / 'long_task.sh'
    task.write_text('#!/bin/bash\nsleep 10\necho "Should not reach here"\n')
    task.chmod(0o755)

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@',
         '-r', '-t', '2'],  # 2 second timeout
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    # Should complete (return code may vary due to timeout)
    # Execution should finish in ~2 seconds (timeout), not 10 seconds (sleep)
    # CSV should show TIMEOUT status
    csv_path = extract_log_path_from_stdout(result.stdout, 'summary')
    assert csv_path, "CSV should be created"

    csv_records = parse_csv_summary(csv_path)
    assert len(csv_records) == 1, "Should have 1 task record"

    # Task should have TIMEOUT status (not SUCCESS)
    record = csv_records[0]
    assert record['status'] == 'TIMEOUT', f"Expected TIMEOUT, got {record['status']}"


@pytest.mark.integration
def test_task_timeout_status_in_csv(temp_dir, isolated_env):
    """
    Test that CSV correctly records TIMEOUT status.

    Verifies status field is set to TIMEOUT for timed-out tasks.
    """
    # Create task that will timeout
    task = temp_dir / 'timeout_task.sh'
    task.write_text('#!/bin/bash\nsleep 5\n')
    task.chmod(0o755)

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@',
         '-r', '-t', '1'],  # 1 second timeout
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    csv_path = extract_log_path_from_stdout(result.stdout, 'summary')
    csv_records = parse_csv_summary(csv_path)

    assert len(csv_records) == 1
    assert csv_records[0]['status'] == 'TIMEOUT'


@pytest.mark.integration
def test_task_timeout_error_message(temp_dir, isolated_env):
    """
    Test that timeout error message is recorded correctly.

    Verifies error_message contains "Timeout after Xs".
    """
    # Create task that will timeout
    task = temp_dir / 'slow.sh'
    task.write_text('#!/bin/bash\nsleep 10\n')
    task.chmod(0o755)

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@',
         '-r', '-t', '2'],  # 2 second timeout
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    csv_path = extract_log_path_from_stdout(result.stdout, 'summary')
    csv_records = parse_csv_summary(csv_path)

    assert len(csv_records) == 1
    error_msg = csv_records[0].get('error_message', '').lower()

    # Error message should mention timeout
    assert 'timeout' in error_msg, f"Expected 'timeout' in error message, got: {error_msg}"


@pytest.mark.integration
def test_task_timeout_custom_value(temp_dir, isolated_env):
    """
    Test that -t flag sets custom timeout value.

    Creates task that sleeps 3s, timeout=5s, should succeed.
    Then same task with timeout=1s, should timeout.
    """
    # Create task that sleeps for 3 seconds
    task = temp_dir / 'three_second_task.sh'
    task.write_text('#!/bin/bash\nsleep 3\necho "completed"\n')
    task.chmod(0o755)

    # Test 1: With 5 second timeout (should succeed)
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@',
         '-r', '-t', '5'],  # 5 second timeout
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    csv_path = extract_log_path_from_stdout(result.stdout, 'summary')
    csv_records = parse_csv_summary(csv_path)

    # Should succeed (not timeout)
    assert csv_records[0]['status'] == 'SUCCESS', "Task should complete within 5s timeout"

    # Test 2: With 1 second timeout (should timeout)
    result2 = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@',
         '-r', '-t', '1'],  # 1 second timeout
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    csv_path2 = extract_log_path_from_stdout(result2.stdout, 'summary')
    csv_records2 = parse_csv_summary(csv_path2)

    # Should timeout
    assert csv_records2[0]['status'] == 'TIMEOUT', "Task should timeout with 1s timeout"


@pytest.mark.integration
def test_task_timeout_multiple_workers(temp_dir, isolated_env):
    """
    Test that timeout works correctly with multiple parallel workers.

    Each worker should enforce timeout independently.
    """
    # Create 4 tasks that will timeout
    for i in range(4):
        task = temp_dir / f'timeout_{i}.sh'
        task.write_text('#!/bin/bash\nsleep 10\n')
        task.chmod(0o755)

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@',
         '-r', '-t', '2', '-m', '2'],  # 2 workers, 2s timeout
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    csv_path = extract_log_path_from_stdout(result.stdout, 'summary')
    csv_records = parse_csv_summary(csv_path)

    # All 4 tasks should timeout
    assert len(csv_records) == 4, "All 4 tasks should be recorded"
    for record in csv_records:
        assert record['status'] == 'TIMEOUT', "All tasks should timeout"


@pytest.mark.integration
def test_fast_tasks_complete_before_timeout(temp_dir, isolated_env):
    """
    Test that fast tasks complete successfully before timeout.

    Verifies no false positives - timeout only kills actually slow tasks.
    """
    # Create fast tasks that complete well before timeout
    for i in range(3):
        task = temp_dir / f'fast_{i}.sh'
        task.write_text('#!/bin/bash\necho "quick task"\n')
        task.chmod(0o755)

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@',
         '-r', '-t', '10'],  # 10 second timeout (generous)
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    csv_path = extract_log_path_from_stdout(result.stdout, 'summary')
    csv_records = parse_csv_summary(csv_path)

    # All tasks should succeed (not timeout)
    assert len(csv_records) == 3
    for record in csv_records:
        assert record['status'] == 'SUCCESS', "Fast tasks should not timeout"
        assert record['exit_code'] == 0
