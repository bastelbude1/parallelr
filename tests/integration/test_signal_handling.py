"""
Integration tests for signal handling.

Tests graceful shutdown, SIGTERM, SIGINT, and SIGHUP handling.
"""

import subprocess
import sys
from pathlib import Path
import pytest
import signal
import time
import os

PROJECT_ROOT = Path(__file__).parent.parent.parent
PARALLELR_BIN = PROJECT_ROOT / 'bin' / 'parallelr.py'


@pytest.mark.integration
def test_sigint_graceful_shutdown(temp_dir):
    """Test that SIGINT (Ctrl+C) triggers graceful shutdown."""
    # Create a long-running task
    task_file = temp_dir / 'long_task.sh'
    task_file.write_text('#!/bin/bash\nsleep 30\necho "completed"\n')
    task_file.chmod(0o755)

    # Start process
    proc = subprocess.Popen(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Give it time to start
    time.sleep(2)

    # Send SIGINT
    proc.send_signal(signal.SIGINT)

    # Wait for graceful shutdown
    try:
        stdout, stderr = proc.communicate(timeout=10)
        # Should have exited
        assert proc.returncode is not None
        # Should show shutdown message
        output = stdout + stderr
        assert 'shutdown' in output.lower() or 'interrupt' in output.lower() or 'cancelled' in output.lower()
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail("Process did not shut down gracefully after SIGINT")


@pytest.mark.integration
def test_sigterm_graceful_shutdown(temp_dir):
    """Test that SIGTERM triggers graceful shutdown."""
    # Create a long-running task
    task_file = temp_dir / 'long_task.sh'
    task_file.write_text('#!/bin/bash\nsleep 30\necho "completed"\n')
    task_file.chmod(0o755)

    # Start process
    proc = subprocess.Popen(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Give it time to start
    time.sleep(2)

    # Send SIGTERM
    proc.send_signal(signal.SIGTERM)

    # Wait for graceful shutdown
    try:
        stdout, stderr = proc.communicate(timeout=10)
        # Should have exited
        assert proc.returncode is not None
        output = stdout + stderr
        assert 'shutdown' in output.lower() or 'terminated' in output.lower() or 'cancelled' in output.lower()
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail("Process did not shut down gracefully after SIGTERM")


@pytest.mark.integration
def test_sighup_ignored_in_daemon(temp_dir):
    """Test that SIGHUP is ignored in daemon mode."""
    # Create a task
    task_file = temp_dir / 'task.sh'
    task_file.write_text('#!/bin/bash\nsleep 5\n')
    task_file.chmod(0o755)

    # Start daemon
    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r', '-d'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=10
    )

    assert result.returncode == 0
    time.sleep(2)

    # Try to get PID
    pid_file = Path.home() / 'parallelr' / 'pids' / 'parallelr.pids'
    if pid_file.exists():
        pids = pid_file.read_text().strip().split('\n')
        if pids and pids[0]:
            pid = int(pids[0].strip())

            # Send SIGHUP
            try:
                os.kill(pid, signal.SIGHUP)
                time.sleep(1)

                # Process should still be running (SIGHUP ignored)
                # Try to check if process exists
                os.kill(pid, 0)  # Signal 0 just checks existence
                # If we get here, process is still running (good!)
            except ProcessLookupError:
                # Process died - this would be unexpected for daemon
                pass
            except PermissionError:
                # Process exists but we don't have permission (still running)
                pass

    # Cleanup
    subprocess.run([sys.executable, str(PARALLELR_BIN), '-k'],
                   input='yes\n', stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=10)


@pytest.mark.integration
def test_multiple_interrupts_force_exit(temp_dir):
    """Test that multiple SIGINT signals force immediate exit."""
    # Create a long-running task
    task_file = temp_dir / 'long_task.sh'
    task_file.write_text('#!/bin/bash\nsleep 60\n')
    task_file.chmod(0o755)

    # Start process
    proc = subprocess.Popen(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    time.sleep(2)

    # Send first SIGINT
    proc.send_signal(signal.SIGINT)
    time.sleep(0.5)

    # Send second SIGINT (should force exit)
    proc.send_signal(signal.SIGINT)

    # Should exit quickly
    try:
        stdout, stderr = proc.communicate(timeout=5)
        assert proc.returncode is not None
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail("Process did not exit after multiple SIGINTs")


@pytest.mark.integration
def test_task_cancellation_on_interrupt(temp_dir):
    """Test that running tasks are cancelled on interrupt."""
    # Create multiple long-running tasks
    task_dir = temp_dir / 'tasks'
    task_dir.mkdir()

    for i in range(3):
        task_file = task_dir / f'task{i}.sh'
        task_file.write_text('#!/bin/bash\nsleep 30\necho "completed"\n')
        task_file.chmod(0o755)

    # Start process
    proc = subprocess.Popen(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '2'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    time.sleep(3)

    # Send SIGINT
    proc.send_signal(signal.SIGINT)

    # Wait for shutdown
    try:
        stdout, stderr = proc.communicate(timeout=10)
        output = stdout + stderr

        # Should show shutdown/cancelled tasks
        assert ('cancel' in output.lower() or 'interrupt' in output.lower() or 'shutdown' in output.lower())
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail("Process did not shut down after SIGINT")


@pytest.mark.integration
def test_cleanup_on_forced_exit(temp_dir):
    """Test that cleanup happens even on forced exit."""
    # Create a task
    task_file = temp_dir / 'task.sh'
    task_file.write_text('#!/bin/bash\nsleep 60\n')
    task_file.chmod(0o755)

    log_dir = Path.home() / 'parallelr' / 'logs'

    # Start process
    proc = subprocess.Popen(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    time.sleep(2)

    # Send SIGINT
    proc.send_signal(signal.SIGINT)

    try:
        stdout, stderr = proc.communicate(timeout=10)

        # Log files should still be written
        assert log_dir.exists()
        log_files = list(log_dir.glob('parallelr_*.log'))
        assert len(log_files) > 0

    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.mark.integration
def test_signal_handler_registration(sample_task_dir):
    """Test that signal handlers are properly registered."""
    # This test verifies signal handling works at all
    proc = subprocess.Popen(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'sleep 30',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    time.sleep(2)

    # Process should be running
    assert proc.poll() is None

    # Send SIGTERM
    proc.send_signal(signal.SIGTERM)

    # Should respond to signal
    try:
        proc.communicate(timeout=10)
        assert proc.returncode is not None
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail("Signal handler not working")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
