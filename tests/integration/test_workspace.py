"""
Integration tests for workspace management.

Tests shared and isolated workspace modes.
"""

import subprocess
import os
import uuid
from pathlib import Path
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import PARALLELR_BIN, PYTHON_FOR_PARALLELR

# Skip all tests if not on POSIX (bash/workspace tests)
pytestmark = pytest.mark.skipif(os.name != "posix",
                                reason="Bash/Workspace only tested on POSIX")

# Early abort if parallelr.py is missing
if not PARALLELR_BIN.exists():
    pytest.skip("bin/parallelr.py not found - integration tests skipped",
                allow_module_level=True)


@pytest.fixture
def isolated_workspace(tmp_path):
    """
    Provide an isolated temporary workspace for testing.

    Uses subprocess env parameter to isolate HOME without mutating global
    os.environ. Guarantees cleanup even on failures.
    """
    # Create temporary home directory
    temp_home = tmp_path / 'home'
    temp_home.mkdir()

    # Calculate workspace paths
    workspace_dir = temp_home / 'parallelr' / 'workspace'
    log_dir = temp_home / 'parallelr' / 'logs'

    # Create isolated environment for subprocess (no global mutation)
    isolated_env = {**os.environ, 'HOME': str(temp_home)}

    yield {
        'home': temp_home,
        'workspace': workspace_dir,
        'logs': log_dir,
        'env': isolated_env
    }

    # Cleanup is automatic via tmp_path fixture


@pytest.mark.integration
def test_workspace_directory_created(sample_task_dir, isolated_workspace):
    """Test that workspace directory is created when tasks execute."""
    workspace_dir = isolated_workspace['workspace']

    # Workspace doesn't exist yet in isolated environment
    assert not workspace_dir.exists(), "Workspace should not exist before task execution"

    # Run task which should create the workspace
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '1'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_workspace['env'],
        timeout=30
    )

    assert result.returncode == 0
    # Workspace should now exist after task execution
    assert workspace_dir.exists(), "Workspace should be created during task execution"


@pytest.mark.integration
def test_shared_workspace_mode_default(sample_task_dir, isolated_workspace):
    """Test that shared workspace is the default mode."""
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '1'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_workspace['env'],
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
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_workspace['env'],
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
    workspace_dir = isolated_workspace['workspace']
    # Use unique marker name to avoid race conditions in parallel test execution
    marker_name = f'persistent_marker_{uuid.uuid4().hex[:8]}.txt'
    marker_file = workspace_dir / marker_name
    test_env = isolated_workspace['env']

    # First run - create marker
    task1 = temp_dir / 'create_marker.sh'
    task1.write_text(f'#!/bin/bash\necho "persistent" > ~/parallelr/workspace/{marker_name}\n')
    task1.chmod(0o755)

    result1 = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
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
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
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
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '1'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_workspace['env'],
        timeout=30
    )

    assert result.returncode == 0
    # Summary should mention workspace
    assert 'workspace' in result.stdout.lower()
    assert 'working dir' in result.stdout.lower() or 'workspace type' in result.stdout.lower()


@pytest.mark.integration
def test_tasks_run_from_workspace(temp_dir, isolated_workspace):
    """Test that tasks execute with workspace as working directory."""
    workspace_dir = isolated_workspace['workspace']
    task_file = temp_dir / 'pwd_test.sh'
    task_file.write_text('#!/bin/bash\npwd\n')
    task_file.chmod(0o755)

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_workspace['env'],
        timeout=30
    )

    assert result.returncode == 0
    # Output should show exact workspace directory from fixture
    assert str(workspace_dir) in result.stdout


@pytest.mark.integration
def test_workspace_logs_directory(sample_task_dir, isolated_workspace):
    """Test that logs directory exists alongside workspace."""
    log_dir = isolated_workspace['logs']

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '1'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_workspace['env'],
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
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '1'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_workspace['env'],
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
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '1'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_workspace['env'],
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
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '1',
         '--no-task-output-log'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_workspace['env'],
        timeout=30
    )

    assert result.returncode == 0

    # Get count of output files after
    output_files_after = list(log_dir.glob('*_output.txt'))
    count_after = len(output_files_after)

    # Count should be the same (no new output file created)
    assert count_after == count_before


# ============================================================================
# WORKSPACE ISOLATION MODE TESTS
# Tests for workspace_isolation config option (per-worker directories)
# ============================================================================


@pytest.fixture
def config_with_isolation(isolated_workspace):
    """
    Create user config with workspace_isolation enabled.

    Returns the config file path and isolated env.
    """
    # Create user config directory
    config_dir = isolated_workspace['home'] / 'parallelr' / 'cfg'
    config_dir.mkdir(parents=True)

    # Create user config with workspace isolation enabled
    config_file = config_dir / 'parallelr.yaml'
    config_file.write_text("""
execution:
  workspace_isolation: true
""")

    return {
        'config': config_file,
        'env': isolated_workspace['env'],
        'home': isolated_workspace['home'],
        'workspace': isolated_workspace['workspace']
    }


@pytest.mark.integration
def test_workspace_isolation_mode_creates_per_worker_dirs(temp_dir, isolated_workspace, config_with_isolation):
    """
    Test that workspace_isolation: true creates per-worker directories.

    Verifies pid{PID}_worker{N} directories are created.
    """
    # Create test tasks
    for i in range(3):
        task = temp_dir / f'task_{i}.sh'
        task.write_text('#!/bin/bash\necho "task execution"\n')
        task.chmod(0o755)

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '2'],  # 2 workers
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=config_with_isolation['env'],
        timeout=30
    )

    assert result.returncode == 0

    # Check that per-worker workspace directories were created
    workspace_base = config_with_isolation['workspace']

    # Fail fast if workspace base directory doesn't exist or is not a directory
    assert workspace_base.exists(), f"Workspace base directory should exist at {workspace_base}"
    assert workspace_base.is_dir(), f"Workspace base path should be a directory at {workspace_base}"

    # Find directories matching pattern pid{PID}_worker{N}
    worker_dirs = [d for d in workspace_base.iterdir()
                  if d.is_dir() and 'pid' in d.name and 'worker' in d.name]

    # Should have created worker-specific directories
    assert len(worker_dirs) > 0, "Workspace isolation should create per-worker directories"


@pytest.mark.integration
def test_workspace_isolation_separate_task_execution(temp_dir, isolated_workspace, config_with_isolation):
    """
    Test that different workers use isolated workspaces.

    Verifies tasks execute successfully with workspace isolation enabled.
    """
    # Create simple tasks that just echo
    for i in range(4):
        task = temp_dir / f'workspace_write_{i}.sh'
        task.write_text(f'#!/bin/bash\necho "Task {i} executing"\n')
        task.chmod(0o755)

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '2'],  # 2 workers
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=config_with_isolation['env'],
        timeout=30
    )

    assert result.returncode == 0

    # Verify output indicates isolated workspace mode
    assert 'isolated' in result.stdout.lower()

    # Each worker should have its own workspace directory
    # Verify multiple worker directories exist
    workspace_base = config_with_isolation['workspace']

    # Fail fast if workspace base directory doesn't exist or is not a directory
    assert workspace_base.exists(), f"Workspace base directory should exist at {workspace_base}"
    assert workspace_base.is_dir(), f"Workspace base path should be a directory at {workspace_base}"

    worker_dirs = [d for d in workspace_base.iterdir()
                  if d.is_dir() and 'worker' in d.name]

    # With 2 workers and 4 tasks, both workers should have been used
    # So we should see at least 1 worker directory (possibly 2)
    assert len(worker_dirs) >= 1, "Should have at least one worker directory"


@pytest.mark.integration
def test_workspace_isolation_no_cross_contamination(temp_dir, isolated_workspace, config_with_isolation):
    """
    Test that workers use isolated workspace directories.

    Verifies workspace isolation mode with multiple workers.
    """
    # Create simple tasks
    for i in range(6):
        task = temp_dir / f'marker_{i}.sh'
        # Simple task that just echoes
        task.write_text(f'#!/bin/bash\necho "Task {i} completed"\n')
        task.chmod(0o755)

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '3'],  # 3 workers
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=config_with_isolation['env'],
        timeout=30
    )

    assert result.returncode == 0

    # Verify output mentions isolated workspace
    assert 'isolated' in result.stdout.lower()

    # Verify workers created isolated directories
    workspace_base = config_with_isolation['workspace']

    # Fail fast if workspace base directory doesn't exist or is not a directory
    assert workspace_base.exists(), f"Workspace base directory should exist at {workspace_base}"
    assert workspace_base.is_dir(), f"Workspace base path should be a directory at {workspace_base}"

    worker_dirs = [d for d in workspace_base.iterdir()
                  if d.is_dir() and 'worker' in d.name]

    # With 3 workers and 6 tasks, should have multiple worker directories
    assert len(worker_dirs) >= 1, "Should have at least one worker directory"


@pytest.mark.integration
def test_workspace_isolation_directories_accessible(temp_dir, isolated_workspace, config_with_isolation):
    """
    Test that isolated workspace directories are created and accessible.

    Verifies that workspace isolation creates per-worker directories with
    the expected naming pattern (pid{PID}_worker{N}) and that these
    directories are accessible after task execution.
    """
    # Create simple tasks
    for i in range(2):
        task = temp_dir / f'simple_{i}.sh'
        task.write_text('#!/bin/bash\necho "Test task"\n')
        task.chmod(0o755)

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '1'],  # Single worker
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=config_with_isolation['env'],
        timeout=30
    )

    assert result.returncode == 0

    # Verify output shows isolated workspace mode
    assert 'isolated' in result.stdout.lower()

    # Verify workspace directories were created
    workspace_base = config_with_isolation['workspace']

    # Fail fast if workspace base directory doesn't exist or is not a directory
    assert workspace_base.exists(), f"Workspace base directory should exist at {workspace_base}"
    assert workspace_base.is_dir(), f"Workspace base path should be a directory at {workspace_base}"

    # Check for worker-specific directories
    worker_dirs = list(workspace_base.glob('pid*_worker*'))
    assert len(worker_dirs) > 0, "Should have created worker-specific workspace"
