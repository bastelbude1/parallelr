"""
Integration tests for PID cleanup functionality.

Tests PID cleanup on exceptions, normal completion, stale PID removal,
and guaranteed cleanup via try-finally.
"""

import subprocess
import time
import os
import signal
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import PARALLELR_BIN, PYTHON_FOR_PARALLELR

# Skip all tests on non-POSIX platforms
pytestmark = pytest.mark.skipif(os.name != "posix",
                                reason="PID management is POSIX-specific")


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
def isolated_env(tmp_path):
    """
    Provide isolated environment for PID tests.

    Creates a temporary HOME directory to avoid conflicts with system PIDs.
    """
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


def read_pids_from_file(pid_file):
    """Read PIDs from file, return list of integers."""
    if not pid_file.exists():
        return []
    pids = []
    for line in pid_file.read_text().strip().split('\n'):
        pid = line.strip()
        if pid.isdigit():
            pids.append(int(pid))
    return pids


@pytest.mark.integration
def test_pid_removed_on_normal_completion(temp_dir, isolated_env):
    """Test that PID is removed from file after normal task completion."""
    # Create a quick task
    task_file = temp_dir / 'quick_task.sh'
    task_file.write_text('#!/bin/bash\necho "test"\n')
    task_file.chmod(0o755)

    # Run in foreground (not daemon) so we can wait for completion
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    assert result.returncode == 0, f"Execution failed: {result.stderr}"

    # After completion, PID file should either not exist or not contain this PID
    pid_file = isolated_env['pid_file']
    if pid_file.exists():
        pids = read_pids_from_file(pid_file)
        # The process ID from the execution should not be in the file anymore
        # We can't easily capture the exact PID, but the file should be empty
        # or cleaned up after successful completion
        assert len(pids) == 0, f"PID file should be empty after completion, but contains: {pids}"


@pytest.mark.integration
def test_pid_removed_on_task_failure(temp_dir, isolated_env):
    """Test that PID is removed even when tasks fail."""
    # Create a failing task
    task_file = temp_dir / 'failing_task.sh'
    task_file.write_text('#!/bin/bash\nexit 1\n')
    task_file.chmod(0o755)

    # Run in foreground - should complete but with failed tasks
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    # parallelr exits with code 1 when all tasks fail (expected behavior)
    # But should still clean up PID
    assert result.returncode == 1, f"Expected exit code 1 (all tasks failed), got {result.returncode}"

    # PID should be cleaned up
    pid_file = isolated_env['pid_file']
    if pid_file.exists():
        pids = read_pids_from_file(pid_file)
        assert len(pids) == 0, f"PID file should be empty after completion, but contains: {pids}"


@pytest.mark.integration
def test_stale_pids_cleaned_on_startup(temp_dir, isolated_env):
    """Test that stale PIDs are cleaned up when a new instance starts."""
    pid_file = isolated_env['pid_file']
    pid_dir = pid_file.parent
    pid_dir.mkdir(parents=True, exist_ok=True)

    # Manually write fake stale PIDs to the file
    # Use PIDs that are guaranteed not to exist (very high numbers)
    stale_pids = [999999998, 999999999]
    with open(str(pid_file), 'w') as f:
        for pid in stale_pids:
            f.write(f"{pid}\n")

    initial_pids = read_pids_from_file(pid_file)
    assert len(initial_pids) == 2, "Setup failed: stale PIDs not written"

    # Create a quick task
    task_file = temp_dir / 'quick_task.sh'
    task_file.write_text('#!/bin/bash\necho "test"\n')
    task_file.chmod(0o755)

    # Run parallelr - it should clean stale PIDs on startup
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    assert result.returncode == 0, f"Execution failed: {result.stderr}"

    # After completion, stale PIDs should be gone and file should be empty
    if pid_file.exists():
        final_pids = read_pids_from_file(pid_file)
        # File should be empty or contain no stale PIDs
        for pid in stale_pids:
            assert pid not in final_pids, f"Stale PID {pid} was not cleaned up"


@pytest.mark.integration
def test_cleanup_stale_pids_preserves_running_processes(temp_dir, isolated_env):
    """Test that stale PID cleanup doesn't remove running process PIDs."""
    pid_file = isolated_env['pid_file']
    pid_dir = pid_file.parent
    pid_dir.mkdir(parents=True, exist_ok=True)

    # Start a long-running daemon
    task_file = temp_dir / 'long_task.sh'
    task_file.write_text('#!/bin/bash\nsleep 30\n')
    task_file.chmod(0o755)

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r', '-D'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=15
    )

    assert result.returncode == 0, f"Daemon start failed: {result.stderr}"

    # Wait for PID file creation
    assert poll_until(lambda: pid_file.exists(), timeout=5), "PID file not created"

    # Get the running daemon PID
    running_pids = read_pids_from_file(pid_file)
    assert len(running_pids) > 0, "No PIDs registered for daemon"
    daemon_pid = running_pids[0]

    # Manually add a stale PID to the file
    stale_pid = 999999999
    with open(str(pid_file), 'a') as f:
        f.write(f"{stale_pid}\n")

    # Verify both PIDs are in the file
    pids_before = read_pids_from_file(pid_file)
    assert daemon_pid in pids_before, f"Daemon PID {daemon_pid} not in file"
    assert stale_pid in pids_before, f"Stale PID {stale_pid} not in file"

    # Start another quick task - should trigger cleanup
    quick_task = temp_dir / 'quick.sh'
    quick_task.write_text('#!/bin/bash\necho "quick"\n')
    quick_task.chmod(0o755)

    subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(quick_task),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    # After cleanup, stale PID should be gone but daemon PID should remain
    pids_after = read_pids_from_file(pid_file)
    assert daemon_pid in pids_after, f"Running daemon PID {daemon_pid} was incorrectly removed"
    assert stale_pid not in pids_after, f"Stale PID {stale_pid} was not cleaned up"

    # Cleanup daemon
    subprocess.run([PYTHON_FOR_PARALLELR, str(PARALLELR_BIN), '-k'],
                   input='yes\n', stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                   env=isolated_env['env'], universal_newlines=True, timeout=10)


@pytest.mark.integration
def test_pid_cleanup_actually_removes_stale_pids(temp_dir, isolated_env):
    """Test that cleanup actually removes stale PIDs from the file."""
    pid_file = isolated_env['pid_file']
    pid_dir = pid_file.parent
    pid_dir.mkdir(parents=True, exist_ok=True)

    # Write multiple stale PIDs
    stale_pids = [999999997, 999999998, 999999999]
    with open(str(pid_file), 'w') as f:
        for pid in stale_pids:
            f.write(f"{pid}\n")

    # Verify stale PIDs are in the file
    pids_before = read_pids_from_file(pid_file)
    assert len(pids_before) == 3, f"Setup failed: expected 3 stale PIDs, got {len(pids_before)}"

    # Create a task
    task_file = temp_dir / 'task.sh'
    task_file.write_text('#!/bin/bash\necho "test"\n')
    task_file.chmod(0o755)

    # Run parallelr - should clean stale PIDs on startup
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    assert result.returncode == 0, f"Execution failed: {result.stderr}"

    # Verify stale PIDs were removed
    if pid_file.exists():
        pids_after = read_pids_from_file(pid_file)
        # All stale PIDs should be gone
        for pid in stale_pids:
            assert pid not in pids_after, f"Stale PID {pid} was not cleaned up"
        # File should be empty after successful completion
        assert len(pids_after) == 0, f"Expected empty PID file, but contains: {pids_after}"


@pytest.mark.integration
def test_empty_pid_file_after_all_processes_complete(temp_dir, isolated_env):
    """Test that PID file is removed when last process completes."""
    # Create a quick task
    task_file = temp_dir / 'quick_task.sh'
    task_file.write_text('#!/bin/bash\necho "test"\n')
    task_file.chmod(0o755)

    # Run parallelr
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    assert result.returncode == 0, f"Execution failed: {result.stderr}"

    # PID file should be removed entirely when last process completes
    pid_file = isolated_env['pid_file']
    # Either file doesn't exist or is empty
    if pid_file.exists():
        content = pid_file.read_text().strip()
        assert content == '', f"PID file should be empty or removed, but contains: {content}"


@pytest.mark.integration
def test_pid_cleanup_on_invalid_task_directory(isolated_env):
    """Test that PID is cleaned up when execution fails due to invalid task directory."""
    # Try to run with non-existent task directory (will cause error)
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', '/nonexistent/directory/that/does/not/exist',
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    # Should fail with non-zero exit code
    assert result.returncode != 0, f"Expected failure but got success: {result.stdout}"

    # PID should still be cleaned up despite the error
    pid_file = isolated_env['pid_file']
    if pid_file.exists():
        pids = read_pids_from_file(pid_file)
        assert len(pids) == 0, f"PID file should be empty after error, but contains: {pids}"


@pytest.mark.integration
def test_pid_cleanup_on_invalid_command_template(temp_dir, isolated_env):
    """Test that PID is cleaned up when execution fails due to invalid command."""
    # Create a task file
    task_file = temp_dir / 'task.sh'
    task_file.write_text('#!/bin/bash\necho "test"\n')
    task_file.chmod(0o755)

    # Try to run with invalid command (non-existent command will cause task failures)
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', '/nonexistent/command/that/does/not/exist @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    # parallelr exits with code 1 when all tasks fail (expected behavior)
    # But should still clean up PID
    assert result.returncode == 1, f"Expected exit code 1 (all tasks failed), got {result.returncode}"

    # PID should be cleaned up
    pid_file = isolated_env['pid_file']
    if pid_file.exists():
        pids = read_pids_from_file(pid_file)
        assert len(pids) == 0, f"PID file should be empty after completion, but contains: {pids}"


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get('CI') == 'true',
    reason="Signal handling timing-sensitive in GitHub Actions (containerization/resource contention) - verified working locally"
)
def test_pid_cleanup_on_sigterm(temp_dir, isolated_env):
    """Test that PID is cleaned up when process receives SIGTERM signal."""
    # Create a long-running task
    task_file = temp_dir / 'long_task.sh'
    task_file.write_text('#!/bin/bash\nsleep 60\n')
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
        env=isolated_env['env'],
        timeout=15
    )

    assert result.returncode == 0, f"Daemon start failed: {result.stderr}"

    # Wait for PID file creation
    pid_file = isolated_env['pid_file']
    assert poll_until(lambda: pid_file.exists(), timeout=5), "PID file not created"

    # Get the daemon PID
    pids_before = read_pids_from_file(pid_file)
    assert len(pids_before) > 0, "No PIDs registered"
    daemon_pid = pids_before[0]

    # Send SIGTERM to the daemon process
    try:
        os.kill(daemon_pid, signal.SIGTERM)
    except ProcessLookupError:
        pytest.skip("Process already terminated")

    # Wait for graceful shutdown and PID cleanup
    # Longer timeout for environments where backup I/O can be slow
    assert poll_until(
        lambda: not pid_file.exists() or daemon_pid not in read_pids_from_file(pid_file),
        timeout=20
    ), f"PID {daemon_pid} was not cleaned up after SIGTERM"

    # Final cleanup of any remaining processes
    subprocess.run([PYTHON_FOR_PARALLELR, str(PARALLELR_BIN), '-k'],
                   input='yes\n', stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                   env=isolated_env['env'], universal_newlines=True, timeout=10)


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get('CI') == 'true',
    reason="Signal handling timing-sensitive in GitHub Actions (containerization/resource contention) - verified working locally"
)
def test_pid_cleanup_on_sigint(temp_dir, isolated_env):
    """Test that PID is cleaned up when process receives SIGINT (Ctrl+C) signal."""
    # Create a long-running task
    task_file = temp_dir / 'long_task.sh'
    task_file.write_text('#!/bin/bash\nsleep 60\n')
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
        env=isolated_env['env'],
        timeout=15
    )

    assert result.returncode == 0, f"Daemon start failed: {result.stderr}"

    # Wait for PID file creation
    pid_file = isolated_env['pid_file']
    assert poll_until(lambda: pid_file.exists(), timeout=5), "PID file not created"

    # Get the daemon PID
    pids_before = read_pids_from_file(pid_file)
    assert len(pids_before) > 0, "No PIDs registered"
    daemon_pid = pids_before[0]

    # Send SIGINT to the daemon process
    try:
        os.kill(daemon_pid, signal.SIGINT)
    except ProcessLookupError:
        pytest.skip("Process already terminated")

    # Wait for graceful shutdown and PID cleanup
    # Longer timeout for environments where backup I/O can be slow
    assert poll_until(
        lambda: not pid_file.exists() or daemon_pid not in read_pids_from_file(pid_file),
        timeout=20
    ), f"PID {daemon_pid} was not cleaned up after SIGINT"

    # Final cleanup of any remaining processes
    subprocess.run([PYTHON_FOR_PARALLELR, str(PARALLELR_BIN), '-k'],
                   input='yes\n', stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                   env=isolated_env['env'], universal_newlines=True, timeout=10)


@pytest.mark.integration
def test_multiple_stale_pids_from_different_crashes(temp_dir, isolated_env):
    """Test cleanup of multiple stale PIDs accumulated from various failure scenarios."""
    pid_file = isolated_env['pid_file']
    pid_dir = pid_file.parent
    pid_dir.mkdir(parents=True, exist_ok=True)

    # Simulate multiple crashed processes with fake PIDs
    stale_pids = [999999991, 999999992, 999999993, 999999994, 999999995]
    with open(str(pid_file), 'w') as f:
        for pid in stale_pids:
            f.write(f"{pid}\n")

    initial_count = len(read_pids_from_file(pid_file))
    assert initial_count == 5, "Setup failed: not all stale PIDs written"

    # Create a quick task
    task_file = temp_dir / 'quick_task.sh'
    task_file.write_text('#!/bin/bash\necho "test"\n')
    task_file.chmod(0o755)

    # Run parallelr - should clean all stale PIDs
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    assert result.returncode == 0, f"Execution failed: {result.stderr}"

    # All stale PIDs should be gone
    if pid_file.exists():
        final_pids = read_pids_from_file(pid_file)
        for pid in stale_pids:
            assert pid not in final_pids, f"Stale PID {pid} was not cleaned up"
        # File should be empty after cleanup
        assert len(final_pids) == 0, f"Expected empty PID file, but found: {final_pids}"
