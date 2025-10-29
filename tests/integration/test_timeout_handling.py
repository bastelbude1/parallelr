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
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import PARALLELR_BIN, PYTHON_FOR_PARALLELR

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

    # Should complete successfully despite timeout loop iterations
    assert result.returncode == 0, f"Command failed: {result.stderr}"
    assert 'Created 3 tasks' in result.stdout
    assert 'completed successfully' in result.stdout.lower() or 'success' in result.stdout.lower()


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

    assert result.returncode == 0, f"Command failed: {result.stderr}"
    assert 'Created 3 tasks' in result.stdout


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

    assert result.returncode == 0, f"Command failed: {result.stderr}"
    assert 'Created 6 tasks' in result.stdout


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
    assert 'Created 3 tasks' in result.stdout
