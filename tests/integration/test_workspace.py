"""
Integration tests for workspace management.

Tests shared and isolated workspace modes.
"""

import subprocess
import sys
from pathlib import Path
import pytest
import time

PROJECT_ROOT = Path(__file__).parent.parent.parent
PARALLELR_BIN = PROJECT_ROOT / 'bin' / 'parallelr.py'
WORKSPACE_DIR = Path.home() / 'parallelr' / 'workspace'


@pytest.mark.integration
def test_workspace_directory_created(sample_task_dir):
    """Test that workspace directory is created."""
    # Ensure workspace doesn't exist
    if WORKSPACE_DIR.exists():
        # Just verify it exists, don't delete
        pass

    # Run task
    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '1'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=30
    )

    assert result.returncode == 0
    # Workspace should be mentioned in output or exist
    assert WORKSPACE_DIR.exists() or 'workspace' in result.stdout.lower()


@pytest.mark.integration
def test_shared_workspace_mode_default(sample_task_dir):
    """Test that shared workspace is the default mode."""
    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '1'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=30
    )

    assert result.returncode == 0
    # Should show shared workspace in summary
    assert 'shared' in result.stdout.lower()


@pytest.mark.integration
def test_workspace_accessible_to_tasks(temp_dir):
    """Test that tasks can access the workspace directory."""
    # Create a task that writes to workspace
    task_file = temp_dir / 'workspace_test.sh'
    task_file.write_text(f'''#!/bin/bash
cd ~/parallelr/workspace
echo "test" > test_file.txt
ls -la
''')
    task_file.chmod(0o755)

    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=30
    )

    assert result.returncode == 0
    # Verify file was created
    test_file = WORKSPACE_DIR / 'test_file.txt'
    assert test_file.exists()
    assert 'test' in test_file.read_text()

    # Cleanup
    test_file.unlink()


@pytest.mark.integration
def test_workspace_persists_between_runs(temp_dir):
    """Test that workspace persists between different runs."""
    marker_file = WORKSPACE_DIR / 'persistent_marker.txt'

    # First run - create marker
    task1 = temp_dir / 'create_marker.sh'
    task1.write_text(f'#!/bin/bash\necho "persistent" > ~/parallelr/workspace/persistent_marker.txt\n')
    task1.chmod(0o755)

    result1 = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(task1),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=30
    )

    assert result1.returncode == 0
    assert marker_file.exists()

    # Second run - verify marker exists
    task2 = temp_dir / 'check_marker.sh'
    task2.write_text(f'#!/bin/bash\ntest -f ~/parallelr/workspace/persistent_marker.txt && echo "FOUND_MARKER"\n')
    task2.chmod(0o755)

    result2 = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(task2),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=30
    )

    assert result2.returncode == 0
    # The marker file should still exist from the first run
    assert marker_file.exists()

    # Cleanup
    marker_file.unlink()


@pytest.mark.integration
def test_workspace_directory_in_summary(sample_task_dir):
    """Test that workspace directory is shown in summary."""
    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '1'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=30
    )

    assert result.returncode == 0
    # Summary should mention workspace
    assert 'workspace' in result.stdout.lower()
    assert 'working dir' in result.stdout.lower() or 'workspace type' in result.stdout.lower()


@pytest.mark.integration
def test_tasks_run_from_workspace(temp_dir):
    """Test that tasks execute with workspace as working directory."""
    task_file = temp_dir / 'pwd_test.sh'
    task_file.write_text('#!/bin/bash\npwd\n')
    task_file.chmod(0o755)

    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=30
    )

    assert result.returncode == 0
    # Output should show workspace directory
    assert 'parallelr/workspace' in result.stdout


@pytest.mark.integration
def test_workspace_logs_directory(sample_task_dir):
    """Test that logs directory exists alongside workspace."""
    log_dir = Path.home() / 'parallelr' / 'logs'

    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '1'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=30
    )

    assert result.returncode == 0
    # Log directory should exist
    assert log_dir.exists()
    assert 'log dir' in result.stdout.lower() or 'logs/' in result.stdout.lower()


@pytest.mark.integration
def test_workspace_summary_csv_created(sample_task_dir):
    """Test that summary CSV is created in logs directory."""
    log_dir = Path.home() / 'parallelr' / 'logs'

    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '1'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=30
    )

    assert result.returncode == 0
    # Summary CSV should exist
    summary_files = list(log_dir.glob('*_summary.csv'))
    assert len(summary_files) > 0


@pytest.mark.integration
def test_workspace_task_output_log_created(sample_task_dir):
    """Test that task output log is created by default."""
    log_dir = Path.home() / 'parallelr' / 'logs'

    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '1'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=30
    )

    assert result.returncode == 0
    # Output log should exist
    output_files = list(log_dir.glob('*_output.txt'))
    assert len(output_files) > 0


@pytest.mark.integration
def test_workspace_no_task_output_log_flag(sample_task_dir):
    """Test --no-task-output-log flag prevents output log creation."""
    log_dir = Path.home() / 'parallelr' / 'logs'

    # Get count of output files before
    output_files_before = list(log_dir.glob('*_output.txt'))
    count_before = len(output_files_before)

    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '1',
         '--no-task-output-log'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=30
    )

    assert result.returncode == 0

    # Get count of output files after
    output_files_after = list(log_dir.glob('*_output.txt'))
    count_after = len(output_files_after)

    # Count should be the same (no new output file created)
    assert count_after == count_before


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
