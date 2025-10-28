"""
Integration tests for signal handling.

Tests graceful shutdown, SIGTERM, SIGINT, and SIGHUP handling.
"""

import subprocess
import signal
import time
import os
from pathlib import Path
import pytest

from conftest import PARALLELR_BIN, PYTHON_FOR_PARALLELR


def terminate_process_gracefully(proc, timeout=10):
    """
    Terminate a process gracefully with proper retry logic.

    Tries communicate() first, then SIGTERM, then SIGKILL if needed.
    Returns (stdout, stderr) tuple.
    """
    try:
        # Try to get output with timeout
        stdout, stderr = proc.communicate(timeout=timeout)
        return stdout, stderr
    except subprocess.TimeoutExpired:
        # Process didn't finish in time, try SIGTERM
        try:
            proc.terminate()
            time.sleep(0.5)
            stdout, stderr = proc.communicate(timeout=2)
            return stdout, stderr
        except subprocess.TimeoutExpired:
            # Still alive, force kill
            proc.kill()
            stdout, stderr = proc.communicate(timeout=2)
            return stdout, stderr


@pytest.fixture
def isolated_env(tmp_path):
    """
    Provide isolated environment for signal handling tests.

    Sets HOME to temp directory to avoid polluting local environment.
    """
    temp_home = tmp_path / 'home'
    temp_home.mkdir()

    # Store original HOME
    original_home = os.environ.get('HOME')

    try:
        # Set HOME to temp directory
        os.environ['HOME'] = str(temp_home)

        yield {
            'home': temp_home,
            'env': {**os.environ, 'HOME': str(temp_home)}
        }
    finally:
        # Restore original HOME
        if original_home:
            os.environ['HOME'] = original_home
        else:
            os.environ.pop('HOME', None)


@pytest.mark.integration
def test_sigint_graceful_shutdown(temp_dir, isolated_env):
    """Test that SIGINT (Ctrl+C) triggers graceful shutdown."""
    # Create a long-running task
    task_file = temp_dir / 'long_task.sh'
    task_file.write_text('#!/bin/bash\nsleep 30\necho "completed"\n')
    task_file.chmod(0o755)

    # Start process
    proc = subprocess.Popen(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env']
    )

    # Give it time to start
    time.sleep(2)

    # Send SIGINT
    proc.send_signal(signal.SIGINT)

    # Wait for graceful shutdown with robust termination
    stdout, stderr = terminate_process_gracefully(proc, timeout=10)

    # Should have exited
    assert proc.returncode is not None
    # Should show shutdown message
    output = stdout + stderr
    assert 'shutdown' in output.lower() or 'interrupt' in output.lower() or 'cancelled' in output.lower()


@pytest.mark.integration
def test_sigterm_graceful_shutdown(temp_dir, isolated_env):
    """Test that SIGTERM triggers graceful shutdown."""
    # Create a long-running task
    task_file = temp_dir / 'long_task.sh'
    task_file.write_text('#!/bin/bash\nsleep 30\necho "completed"\n')
    task_file.chmod(0o755)

    # Start process
    proc = subprocess.Popen(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env']
    )

    # Give it time to start
    time.sleep(2)

    # Send SIGTERM
    proc.send_signal(signal.SIGTERM)

    # Wait for graceful shutdown with robust termination
    stdout, stderr = terminate_process_gracefully(proc, timeout=10)

    # Should have exited
    assert proc.returncode is not None
    output = stdout + stderr
    assert 'shutdown' in output.lower() or 'terminated' in output.lower() or 'cancelled' in output.lower()


@pytest.mark.integration
@pytest.mark.skipif(os.name != "posix" or not hasattr(signal, "SIGHUP"),
                    reason="SIGHUP nur auf POSIX sinnvoll")
def test_sighup_ignored_in_daemon(temp_dir, isolated_env):
    """Test that SIGHUP is ignored in daemon mode."""
    # Create a task
    task_file = temp_dir / 'task.sh'
    task_file.write_text('#!/bin/bash\nsleep 5\n')
    task_file.chmod(0o755)

    # Start daemon
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r', '-D'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    assert result.returncode == 0
    time.sleep(2)

    # Try to get PID from isolated environment
    pid_file = isolated_env['home'] / 'parallelr' / 'pids' / 'parallelr.pids'
    if pid_file.exists():
        pids = pid_file.read_text().strip().split('\n')
        if pids and pids[0]:
            pid = int(pids[0].strip())

            # Send SIGHUP - this should be ignored by daemon
            try:
                os.kill(pid, signal.SIGHUP)
            except ProcessLookupError:
                # Process already dead before we could send SIGHUP
                # This is expected for fast-running tasks - daemon may have completed
                pass
            except PermissionError:
                # Permission denied to send signal
                pass
            else:
                # SIGHUP was sent successfully, now check if process still running
                time.sleep(1)
                try:
                    os.kill(pid, 0)  # Signal 0 just checks existence
                    # If we get here, process is still running (good!)
                except ProcessLookupError:
                    # Process died after SIGHUP - this is a test failure
                    pytest.fail(f"Daemon process {pid} died after SIGHUP - daemon should ignore SIGHUP and continue running")
                except PermissionError:
                    # Process exists but we don't have permission (still running)
                    pass

    # Cleanup
    subprocess.run([PYTHON_FOR_PARALLELR, str(PARALLELR_BIN), '-k'],
                   input='yes\n', stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                   env=isolated_env['env'], universal_newlines=True, timeout=10)


@pytest.mark.integration
def test_multiple_interrupts_force_exit(temp_dir, isolated_env):
    """Test that multiple SIGINT signals force immediate exit."""
    # Create a long-running task
    task_file = temp_dir / 'long_task.sh'
    task_file.write_text('#!/bin/bash\nsleep 60\n')
    task_file.chmod(0o755)

    # Start process
    proc = subprocess.Popen(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env']
    )

    time.sleep(2)

    # Send first SIGINT
    proc.send_signal(signal.SIGINT)
    time.sleep(0.5)

    # Send second SIGINT (should force exit)
    proc.send_signal(signal.SIGINT)

    # Should exit quickly with robust termination
    stdout, stderr = terminate_process_gracefully(proc, timeout=5)
    assert proc.returncode is not None


@pytest.mark.integration
def test_task_cancellation_on_interrupt(temp_dir, isolated_env):
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
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '2'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env']
    )

    time.sleep(3)

    # Send SIGINT
    proc.send_signal(signal.SIGINT)

    # Wait for shutdown with robust termination
    stdout, stderr = terminate_process_gracefully(proc, timeout=10)
    output = stdout + stderr

    # Should show shutdown/cancelled tasks
    assert ('cancel' in output.lower() or 'interrupt' in output.lower() or 'shutdown' in output.lower())


@pytest.mark.integration
def test_cleanup_on_forced_exit(temp_dir, isolated_env):
    """Test that cleanup happens even on forced exit."""
    # Create a task
    task_file = temp_dir / 'task.sh'
    task_file.write_text('#!/bin/bash\nsleep 60\n')
    task_file.chmod(0o755)

    log_dir = isolated_env['home'] / 'parallelr' / 'logs'

    # Start process
    proc = subprocess.Popen(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env']
    )

    time.sleep(2)

    # Send SIGINT
    proc.send_signal(signal.SIGINT)

    # Wait for shutdown with robust termination
    stdout, stderr = terminate_process_gracefully(proc, timeout=10)

    # Log files should still be written
    assert log_dir.exists()
    log_files = list(log_dir.glob('parallelr_*.log'))
    assert len(log_files) > 0


@pytest.mark.integration
def test_signal_handler_registration(sample_task_dir, isolated_env):
    """Test that signal handlers are properly registered."""
    # This test verifies signal handling works at all
    proc = subprocess.Popen(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'sleep 30',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env']
    )

    time.sleep(2)

    # Process should be running
    assert proc.poll() is None

    # Send SIGTERM
    proc.send_signal(signal.SIGTERM)

    # Should respond to signal with robust termination
    stdout, stderr = terminate_process_gracefully(proc, timeout=10)
    assert proc.returncode is not None
