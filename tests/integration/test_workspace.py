"""
Integration tests for workspace management.

Tests shared and isolated workspace modes.
"""

import subprocess
import sys
import os
import shutil
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
PARALLELR_BIN = PROJECT_ROOT / 'bin' / 'parallelr.py'


@pytest.fixture
def isolated_workspace(tmp_path):
    """
    Provide an isolated temporary workspace for testing.

    Sets HOME environment variable to a temp directory so parallelr creates
    its workspace in an isolated location. Guarantees cleanup even on failures.
    """
    # Create temporary home directory
    temp_home = tmp_path / 'home'
    temp_home.mkdir()

    # Store original HOME
    original_home = os.environ.get('HOME')

    try:
        # Set HOME to temp directory
        os.environ['HOME'] = str(temp_home)

        # Calculate workspace paths
        workspace_dir = temp_home / 'parallelr' / 'workspace'
        log_dir = temp_home / 'parallelr' / 'logs'

        yield {
            'home': temp_home,
            'workspace': workspace_dir,
            'logs': log_dir,
            'env': {'HOME': str(temp_home)}
        }
    finally:
        # Restore original HOME
        if original_home:
            os.environ['HOME'] = original_home
        else:
            os.environ.pop('HOME', None)

        # Cleanup is automatic via tmp_path fixture


@pytest.mark.integration
def test_workspace_directory_created(sample_task_dir, isolated_workspace):
    """Test that workspace directory is created when tasks execute."""
    workspace_dir = isolated_workspace['workspace']

    # Workspace doesn't exist yet in isolated environment
    assert not workspace_dir.exists(), "Workspace should not exist before task execution"

    # Run task which should create the workspace
    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '1'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env={**os.environ, **isolated_workspace['env']},
        timeout=30
    )

    assert result.returncode == 0
    # Workspace should now exist after task execution
    assert workspace_dir.exists(), "Workspace should be created during task execution"


@pytest.mark.integration
def test_shared_workspace_mode_default(sample_task_dir, isolated_workspace):
    """Test that shared workspace is the default mode."""
    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '1'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env={**os.environ, **isolated_workspace['env']},
        timeout=30
    )

    assert result.returncode == 0
    # Should show shared workspace in summary
    assert 'shared' in result.stdout.lower()


@pytest.mark.integration
def test_workspace_accessible_to_tasks(temp_dir, isolated_workspace):
    """Test that tasks can access the workspace directory."""
    workspace_dir = isolated_workspace['workspace']

    # Create a task that writes to workspace
    task_file = temp_dir / 'workspace_test.sh'
    task_file.write_text('''#!/bin/bash
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
        env={**os.environ, **isolated_workspace['env']},
        timeout=30
    )

    assert result.returncode == 0
    # Verify file was created in isolated workspace
    test_file = workspace_dir / 'test_file.txt'
    assert test_file.exists()
    assert 'test' in test_file.read_text()
    # No manual cleanup needed - fixture handles it


@pytest.mark.integration
def test_workspace_persists_between_runs(temp_dir, isolated_workspace):
    """Test that workspace persists between different runs."""
    import uuid

    workspace_dir = isolated_workspace['workspace']
    # Use unique marker name to avoid race conditions in parallel test execution
    marker_name = f'persistent_marker_{uuid.uuid4().hex[:8]}.txt'
    marker_file = workspace_dir / marker_name
    test_env = {**os.environ, **isolated_workspace['env']}

    # First run - create marker
    task1 = temp_dir / 'create_marker.sh'
    task1.write_text(f'#!/bin/bash\necho "persistent" > ~/parallelr/workspace/{marker_name}\n')
    task1.chmod(0o755)

    result1 = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(task1),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=test_env,
        timeout=30
    )

    assert result1.returncode == 0
    assert marker_file.exists()

    # Second run - verify marker exists (using same isolated workspace)
    task2 = temp_dir / 'check_marker.sh'
    task2.write_text(f'#!/bin/bash\ntest -f ~/parallelr/workspace/{marker_name} && echo "FOUND_MARKER"\n')
    task2.chmod(0o755)

    result2 = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(task2),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=test_env,
        timeout=30
    )

    assert result2.returncode == 0
    # The marker file should still exist from the first run
    assert marker_file.exists()
    # No manual cleanup needed - fixture handles it


@pytest.mark.integration
def test_workspace_directory_in_summary(sample_task_dir, isolated_workspace):
    """Test that workspace directory is shown in summary."""
    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '1'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env={**os.environ, **isolated_workspace['env']},
        timeout=30
    )

    assert result.returncode == 0
    # Summary should mention workspace
    assert 'workspace' in result.stdout.lower()
    assert 'working dir' in result.stdout.lower() or 'workspace type' in result.stdout.lower()


@pytest.mark.integration
def test_tasks_run_from_workspace(temp_dir, isolated_workspace):
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
        env={**os.environ, **isolated_workspace['env']},
        timeout=30
    )

    assert result.returncode == 0
    # Output should show workspace directory
    assert 'parallelr/workspace' in result.stdout


@pytest.mark.integration
def test_workspace_logs_directory(sample_task_dir, isolated_workspace):
    """Test that logs directory exists alongside workspace."""
    log_dir = isolated_workspace['logs']

    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '1'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env={**os.environ, **isolated_workspace['env']},
        timeout=30
    )

    assert result.returncode == 0
    # Log directory should exist
    assert log_dir.exists()
    assert 'log dir' in result.stdout.lower() or 'logs/' in result.stdout.lower()


@pytest.mark.integration
def test_workspace_summary_csv_created(sample_task_dir, isolated_workspace):
    """Test that summary CSV is created in logs directory."""
    log_dir = isolated_workspace['logs']

    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '1'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env={**os.environ, **isolated_workspace['env']},
        timeout=30
    )

    assert result.returncode == 0
    # Summary CSV should exist
    summary_files = list(log_dir.glob('*_summary.csv'))
    assert len(summary_files) > 0


@pytest.mark.integration
def test_workspace_task_output_log_created(sample_task_dir, isolated_workspace):
    """Test that task output log is created by default."""
    log_dir = isolated_workspace['logs']

    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '1'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env={**os.environ, **isolated_workspace['env']},
        timeout=30
    )

    assert result.returncode == 0
    # Output log should exist
    output_files = list(log_dir.glob('*_output.txt'))
    assert len(output_files) > 0


@pytest.mark.integration
def test_workspace_no_task_output_log_flag(sample_task_dir, isolated_workspace):
    """Test --no-task-output-log flag prevents output log creation."""
    log_dir = isolated_workspace['logs']

    # Get count of output files before
    output_files_before = list(log_dir.glob('*_output.txt')) if log_dir.exists() else []
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
        env={**os.environ, **isolated_workspace['env']},
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
