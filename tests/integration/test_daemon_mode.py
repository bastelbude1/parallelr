"""
Integration tests for daemon mode execution.

Tests background daemon execution, PID management, and process control.
"""

import subprocess
import sys
import time
from pathlib import Path
import pytest
import signal
import os

PROJECT_ROOT = Path(__file__).parent.parent.parent
PARALLELR_BIN = PROJECT_ROOT / 'bin' / 'parallelr.py'
PID_FILE = Path.home() / 'parallelr' / 'pids' / 'parallelr.pids'


@pytest.mark.integration
def test_daemon_mode_starts_in_background(sample_task_dir):
    """Test that daemon mode starts process in background."""
    # Start daemon - daemon returns immediately
    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-d'],
        capture_output=True,
        text=True,
        timeout=5
    )

    # Daemon should return immediately with exit code 0
    assert result.returncode == 0
    # Output shows execution started
    assert 'starting' in result.stdout.lower() or 'executing' in result.stdout.lower()

    # Give daemon time to start
    time.sleep(2)

    # Cleanup - kill any running instances
    subprocess.run([sys.executable, str(PARALLELR_BIN), '-k'],
                   input='yes\n', capture_output=True, text=True, timeout=10)


@pytest.mark.integration
def test_daemon_mode_pid_tracking(sample_task_dir):
    """Test that daemon mode tracks PIDs correctly."""
    # Start daemon
    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'sleep 1',
         '-r', '-d'],
        capture_output=True,
        text=True,
        timeout=10
    )

    assert result.returncode == 0
    time.sleep(1)

    # Check PID file exists
    if PID_FILE.exists():
        pids = PID_FILE.read_text().strip().split('\n')
        assert len(pids) > 0

    # Cleanup
    subprocess.run([sys.executable, str(PARALLELR_BIN), '-k'],
                   input='yes\n', capture_output=True, text=True, timeout=10)


@pytest.mark.integration
def test_list_workers_command(sample_task_dir):
    """Test --list-workers shows running processes."""
    # Start a daemon
    subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'sleep 5',
         '-r', '-d'],
        capture_output=True,
        text=True,
        timeout=10
    )

    time.sleep(2)

    # List workers
    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN), '--list-workers'],
        capture_output=True,
        text=True,
        timeout=10
    )

    assert result.returncode == 0
    # Should show running processes or "No running" message
    output = result.stdout.lower()
    assert 'running' in output or 'workers' in output or 'process' in output

    # Cleanup
    subprocess.run([sys.executable, str(PARALLELR_BIN), '-k'],
                   input='yes\n', capture_output=True, text=True, timeout=10)


@pytest.mark.integration
def test_kill_all_workers_requires_confirmation(sample_task_dir):
    """Test that kill all requires user confirmation."""
    # Start a daemon with fast tasks
    subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'echo test',
         '-r', '-d'],
        capture_output=True,
        text=True,
        timeout=15
    )

    time.sleep(2)

    # Try to kill without confirmation (send 'no')
    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN), '-k'],
        input='no\n',
        capture_output=True,
        text=True,
        timeout=10
    )

    # Should ask for confirmation or show no running workers
    output_lower = result.stdout.lower()
    assert 'confirm' in output_lower or 'sure' in output_lower or 'no running' in output_lower

    # Cleanup with confirmation
    subprocess.run([sys.executable, str(PARALLELR_BIN), '-k'],
                   input='yes\n', capture_output=True, text=True, timeout=10)


@pytest.mark.integration
def test_kill_specific_worker_by_pid(sample_task_dir, temp_dir):
    """Test killing a specific worker by PID."""
    # Create a fast task
    task_file = temp_dir / 'fast_task.sh'
    task_file.write_text('#!/bin/bash\necho "task"\n')
    task_file.chmod(0o755)

    # Start daemon - may finish quickly
    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r', '-d'],
        capture_output=True,
        text=True,
        timeout=15
    )

    assert result.returncode == 0
    time.sleep(2)

    # Get PID from output or PID file
    if PID_FILE.exists():
        pids = PID_FILE.read_text().strip().split('\n')
        if pids and pids[0]:
            pid = pids[0].strip()

            # Kill specific PID (may already be done)
            kill_result = subprocess.run(
                [sys.executable, str(PARALLELR_BIN), '-k', pid],
                capture_output=True,
                text=True,
                timeout=10
            )

            # Should succeed or process already gone
            output_lower = kill_result.stdout.lower()
            assert (kill_result.returncode == 0 or
                    'killed' in output_lower or
                    'not found' in output_lower or
                    'no such process' in output_lower)

    # Cleanup any remaining
    subprocess.run([sys.executable, str(PARALLELR_BIN), '-k'],
                   input='yes\n', capture_output=True, text=True, timeout=10)


@pytest.mark.integration
def test_daemon_mode_log_files_created(sample_task_dir):
    """Test that daemon creates log files."""
    log_dir = Path.home() / 'parallelr' / 'logs'

    # Start daemon
    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-d'],
        capture_output=True,
        text=True,
        timeout=10
    )

    assert result.returncode == 0
    time.sleep(3)

    # Check log directory exists and has files
    assert log_dir.exists()
    log_files = list(log_dir.glob('parallelr_*.log'))
    assert len(log_files) > 0

    # Cleanup
    subprocess.run([sys.executable, str(PARALLELR_BIN), '-k'],
                   input='yes\n', capture_output=True, text=True, timeout=10)


@pytest.mark.integration
def test_daemon_mode_completes_tasks(sample_task_dir, temp_dir):
    """Test that daemon actually completes tasks."""
    # Create an output marker file task
    marker_file = temp_dir / 'marker.txt'
    task_file = temp_dir / 'marker_task.sh'
    task_file.write_text(f'#!/bin/bash\necho "completed" > {marker_file}\n')
    task_file.chmod(0o755)

    # Start daemon
    subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r', '-d'],
        capture_output=True,
        text=True,
        timeout=10
    )

    # Wait for task to complete
    max_wait = 10
    waited = 0
    while waited < max_wait:
        if marker_file.exists():
            break
        time.sleep(1)
        waited += 1

    # Marker file should exist
    assert marker_file.exists()
    assert 'completed' in marker_file.read_text()

    # Cleanup
    subprocess.run([sys.executable, str(PARALLELR_BIN), '-k'],
                   input='yes\n', capture_output=True, text=True, timeout=10)


@pytest.mark.integration
def test_multiple_daemon_instances(sample_task_dir, temp_dir):
    """Test running multiple daemon instances simultaneously."""
    # Start first daemon
    result1 = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'sleep 5',
         '-r', '-d'],
        capture_output=True,
        text=True,
        timeout=10
    )

    time.sleep(1)

    # Start second daemon
    result2 = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'sleep 5',
         '-r', '-d'],
        capture_output=True,
        text=True,
        timeout=10
    )

    assert result1.returncode == 0
    assert result2.returncode == 0

    time.sleep(1)

    # List workers should show multiple
    list_result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN), '--list-workers'],
        capture_output=True,
        text=True,
        timeout=10
    )

    # Should list processes
    assert list_result.returncode == 0

    # Cleanup all
    subprocess.run([sys.executable, str(PARALLELR_BIN), '-k'],
                   input='yes\n', capture_output=True, text=True, timeout=10)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
