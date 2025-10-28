"""
Integration tests for daemon mode execution.

Tests background daemon execution, PID management, and process control.
"""

import subprocess
import sys
import time
from pathlib import Path
import pytest
\n# Import from conftest
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import PARALLELR_BIN, PYTHON_FOR_PARALLELR
import signal
import os

PROJECT_ROOT = Path(__file__).parent.parent.parent
PARALLELR_BIN = PROJECT_ROOT / 'bin' / 'parallelr.py'

# Skip all daemon tests on non-POSIX platforms (daemon/signal handling is POSIX-specific)
pytestmark = pytest.mark.skipif(os.name != "posix",
                                reason="Daemon and signal handling only stable on POSIX")


def poll_until(condition_func, timeout=20, interval=0.5):
    """
    Poll until condition is met or timeout expires.

    Args:
        condition_func: Callable that returns True when condition is met
        timeout: Maximum seconds to wait (default 20s for slow CI)
        interval: Seconds between checks

    Returns:
        True if condition met, False if timeout
    """
    elapsed = 0
    while elapsed < timeout:
        if condition_func():
            return True
        time.sleep(interval)
        elapsed += interval
    return False


@pytest.fixture
def isolated_daemon_env(tmp_path):
    """
    Provide environment for daemon tests.

    Daemon processes inherit the environment, including HOME. This fixture
    isolates them to tmp_path to avoid side effects. Cleanup is automatic.
    """
    # Use tmp_path as isolated HOME for this test
    temp_home = tmp_path / 'home'
    temp_home.mkdir(parents=True, exist_ok=True)
    pid_file = temp_home / 'parallelr' / 'pids' / 'parallelr.pids'
    log_dir = temp_home / 'parallelr' / 'logs'

    yield {
        'home': temp_home,
        'pid_file': pid_file,
        'log_dir': log_dir,
        'env': {**os.environ, 'HOME': str(temp_home)}
    }


@pytest.mark.integration
def test_daemon_mode_starts_in_background(sample_task_dir, isolated_daemon_env):
    """Test that daemon mode starts process in background."""
    # Start daemon - daemon returns immediately
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-D'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_daemon_env['env'],
        timeout=5
    )

    # Daemon should return immediately with exit code 0
    assert result.returncode == 0
    # Output shows execution started
    assert 'starting' in result.stdout.lower() or 'executing' in result.stdout.lower()

    # Poll for PID file creation instead of fixed sleep
    pid_file = isolated_daemon_env['pid_file']
    assert poll_until(lambda: pid_file.exists(), timeout=5), \
        f"PID file not created at {pid_file} within 5 seconds"

    # Cleanup - kill any running instances
    subprocess.run([PYTHON_FOR_PARALLELR, str(PARALLELR_BIN), '-k'],
                   input='yes\n', stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                   env=isolated_daemon_env['env'], universal_newlines=True, timeout=10)


@pytest.mark.integration
def test_daemon_mode_pid_tracking(sample_task_dir, isolated_daemon_env):
    """Test that daemon mode tracks PIDs correctly."""
    # Start daemon
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'sleep 1',
         '-r', '-D'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_daemon_env['env'],
        timeout=10
    )

    assert result.returncode == 0

    # Poll for PID file creation
    pid_file = isolated_daemon_env['pid_file']
    assert poll_until(lambda: pid_file.exists(), timeout=5), \
        f"PID file not created at {pid_file}"

    # Check PID file contains valid PIDs
    pids = pid_file.read_text().strip().split('\n')
    assert len(pids) > 0

    # Cleanup
    subprocess.run([PYTHON_FOR_PARALLELR, str(PARALLELR_BIN), '-k'],
                   input='yes\n', stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                   env=isolated_daemon_env['env'], universal_newlines=True, timeout=10)


@pytest.mark.integration
def test_list_workers_command(sample_task_dir, isolated_daemon_env):
    """Test --list-workers shows running processes."""
    # Start a daemon
    subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'sleep 5',
         '-r', '-D'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_daemon_env['env'],
        timeout=10
    )

    # Poll for PID file creation
    pid_file = isolated_daemon_env['pid_file']
    assert poll_until(lambda: pid_file.exists(), timeout=5), "Daemon did not start"

    # List workers
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN), '--list-workers'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_daemon_env['env'],
        timeout=10
    )

    assert result.returncode == 0
    # Should show running processes, not "No running" message
    output = result.stdout.lower()
    assert ('running' in output or 'workers' in output or 'process' in output)
    assert 'no running' not in output, \
        f"Expected running workers but got 'no running' message: {result.stdout}"

    # Cleanup
    subprocess.run([PYTHON_FOR_PARALLELR, str(PARALLELR_BIN), '-k'],
                   input='yes\n', stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                   env=isolated_daemon_env['env'], universal_newlines=True, timeout=10)


@pytest.mark.integration
def test_kill_all_workers_requires_confirmation(sample_task_dir, isolated_daemon_env):
    """Test that kill all requires user confirmation."""
    # Start a daemon with fast tasks
    subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'echo test',
         '-r', '-D'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_daemon_env['env'],
        timeout=15
    )

    # Poll for daemon start
    pid_file = isolated_daemon_env['pid_file']
    assert poll_until(lambda: pid_file.exists(), timeout=5), "Daemon did not start"

    # Try to kill without confirmation (send 'no')
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN), '-k'],
        input='no\n',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_daemon_env['env'],
        timeout=10
    )

    # Should ask for confirmation or show no running workers
    output_lower = result.stdout.lower()
    assert 'confirm' in output_lower or 'sure' in output_lower or 'no running' in output_lower

    # Cleanup with confirmation
    subprocess.run([PYTHON_FOR_PARALLELR, str(PARALLELR_BIN), '-k'],
                   input='yes\n', stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                   env=isolated_daemon_env['env'], universal_newlines=True, timeout=10)


@pytest.mark.integration
def test_kill_specific_worker_by_pid(temp_dir, isolated_daemon_env):
    """Test killing a specific worker by PID."""
    # Create a task that runs long enough to be killed
    task_file = temp_dir / 'long_task.sh'
    task_file.write_text('#!/bin/bash\nsleep 5\necho "task"\n')
    task_file.chmod(0o755)

    # Start daemon with long-running task
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r', '-D'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_daemon_env['env'],
        timeout=15
    )

    assert result.returncode == 0

    # Poll for PID file creation
    pid_file = isolated_daemon_env['pid_file']
    assert poll_until(lambda: pid_file.exists(), timeout=5), \
        f"PID file not created at {pid_file} - daemon did not write PID file"

    pids = pid_file.read_text().strip().split('\n')
    non_empty_pids = [p.strip() for p in pids if p.strip()]
    assert len(non_empty_pids) > 0, f"PID file exists but contains no valid PIDs: {pids}"

    pid = non_empty_pids[0]

    # Kill specific PID while task is still running
    kill_result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN), '-k', pid],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_daemon_env['env'],
        timeout=10
    )

    # Should successfully kill the running process
    assert kill_result.returncode == 0, \
        f"Failed to kill process {pid}: {kill_result.stdout} {kill_result.stderr}"

    # Cleanup any remaining
    subprocess.run([PYTHON_FOR_PARALLELR, str(PARALLELR_BIN), '-k'],
                   input='yes\n', stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                   env=isolated_daemon_env['env'], universal_newlines=True, timeout=10)


@pytest.mark.integration
def test_daemon_mode_log_files_created(sample_task_dir, isolated_daemon_env):
    """Test that daemon creates log files."""
    log_dir = isolated_daemon_env['log_dir']

    # Start daemon
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-D'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_daemon_env['env'],
        timeout=10
    )

    assert result.returncode == 0

    # Poll for log directory and files creation
    assert poll_until(lambda: log_dir.exists(), timeout=5), \
        f"Log directory not created at {log_dir}"
    assert poll_until(lambda: len(list(log_dir.glob('parallelr_*.log'))) > 0, timeout=5), \
        "No log files created"

    # Cleanup
    subprocess.run([PYTHON_FOR_PARALLELR, str(PARALLELR_BIN), '-k'],
                   input='yes\n', stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                   env=isolated_daemon_env['env'], universal_newlines=True, timeout=10)


@pytest.mark.integration
def test_daemon_mode_completes_tasks(temp_dir, isolated_daemon_env):
    """Test that daemon actually completes tasks."""
    # Create an output marker file task
    marker_file = temp_dir / 'marker.txt'
    task_file = temp_dir / 'marker_task.sh'
    task_file.write_text(f'#!/bin/bash\necho "completed" > {marker_file}\n')
    task_file.chmod(0o755)

    # Start daemon
    subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r', '-D'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_daemon_env['env'],
        timeout=10
    )

    # Poll for task completion via marker file
    assert poll_until(lambda: marker_file.exists(), timeout=10), \
        f"Task did not complete - marker file not created at {marker_file}"
    assert 'completed' in marker_file.read_text()

    # Cleanup
    subprocess.run([PYTHON_FOR_PARALLELR, str(PARALLELR_BIN), '-k'],
                   input='yes\n', stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                   env=isolated_daemon_env['env'], universal_newlines=True, timeout=10)


@pytest.mark.integration
def test_multiple_daemon_instances(sample_task_dir, isolated_daemon_env):
    """Test running multiple daemon instances simultaneously."""
    # Start first daemon
    result1 = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'sleep 5',
         '-r', '-D'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_daemon_env['env'],
        timeout=10
    )

    assert result1.returncode == 0

    # Poll for first daemon start
    pid_file = isolated_daemon_env['pid_file']
    assert poll_until(lambda: pid_file.exists(), timeout=5), "First daemon did not start"

    # Get baseline PID count before starting second daemon
    initial_count = len([p for p in pid_file.read_text().strip().split('\n') if p.strip()])

    # Start second daemon
    result2 = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'sleep 5',
         '-r', '-D'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_daemon_env['env'],
        timeout=10
    )

    assert result2.returncode == 0

    # Poll until PID count increases by exactly 1
    assert poll_until(
        lambda: len([p for p in pid_file.read_text().strip().split('\n') if p.strip()]) >= initial_count + 1,
        timeout=10
    ), f"Second daemon not registered (baseline: {initial_count}, current: {len([p for p in pid_file.read_text().strip().split('\n') if p.strip()])})"

    # List workers should show multiple
    list_result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN), '--list-workers'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_daemon_env['env'],
        timeout=10
    )

    # Should list processes
    assert list_result.returncode == 0

    # Cleanup all
    subprocess.run([PYTHON_FOR_PARALLELR, str(PARALLELR_BIN), '-k'],
                   input='yes\n', stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                   env=isolated_daemon_env['env'], universal_newlines=True, timeout=10)
