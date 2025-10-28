"""
Integration tests for file mode execution.

Tests traditional directory-based task discovery and execution.
"""

import subprocess
import os
import re
import shutil
from pathlib import Path
import pytest

from conftest import PARALLELR_BIN, PYTHON_FOR_PARALLELR

# Skip all tests if bash is not available (POSIX dependency)
pytestmark = pytest.mark.skipif(shutil.which("bash") is None,
                                reason="Requires bash (POSIX)")

# Early abort if parallelr.py is missing
if not PARALLELR_BIN.exists():
    pytest.skip("bin/parallelr.py not found - integration tests skipped",
                allow_module_level=True)


@pytest.fixture
def isolated_env(tmp_path):
    """
    Provide isolated environment for file mode tests.

    Returns a dict with 'home' and 'env' keys. The 'env' dict contains
    a copy of os.environ with HOME set to temp directory, avoiding
    global os.environ mutation.
    """
    temp_home = tmp_path / 'home'
    temp_home.mkdir()

    # Create isolated environment dict without mutating global os.environ
    env = os.environ.copy()
    env['HOME'] = str(temp_home)

    yield {
        'home': temp_home,
        'env': env
    }


@pytest.mark.integration
def test_file_mode_directory_execution(sample_task_dir, isolated_env):
    """Test executing tasks from a directory."""
    # Run parallelr in dry-run mode
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    assert result.returncode == 0
    # Robust dry-run assertion (case-insensitive)
    out_lower = result.stdout.lower()
    assert 'dry' in out_lower and 'run' in out_lower
    # Should discover 5 tasks
    assert 'task1.sh' in result.stdout
    assert 'task5.sh' in result.stdout


@pytest.mark.integration
def test_file_mode_actual_execution(sample_task_dir, isolated_env):
    """Test actual task execution in file mode."""
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '2'],  # Run with 2 workers
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    assert result.returncode == 0
    # Should complete all 5 tasks
    assert 'Completed Successfully: 5' in result.stdout or 'completed: 5' in result.stdout.lower()


@pytest.mark.integration
def test_file_mode_specific_files(sample_task_dir, isolated_env):
    """Test executing specific task files."""
    task1 = sample_task_dir / 'task1.sh'
    task2 = sample_task_dir / 'task2.sh'

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(task1),
         '-T', str(task2),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    assert result.returncode == 0
    # Should only execute 2 tasks (robust text check with regex)
    assert re.search(r'(?i)\bexecut(?:e|ing)\b.*\b2\b.*\btasks?\b', result.stdout)


@pytest.mark.integration
def test_file_mode_glob_patterns(sample_task_dir, isolated_env):
    """Test executing tasks using glob patterns."""
    # Expand glob in Python for deterministic behavior
    matches = sorted(sample_task_dir.glob('task[12].sh'))

    # Build command with expanded paths
    cmd = [sys.executable, str(PARALLELR_BIN)]
    for p in matches:
        cmd += ['-T', str(p)]
    cmd += ['-r', '-C', 'bash @TASK@']

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    # Should successfully execute both tasks
    assert result.returncode == 0
    assert 'task1.sh' in result.stdout
    assert 'task2.sh' in result.stdout


@pytest.mark.integration
def test_file_mode_file_extension_filter(temp_dir, isolated_env):
    """Test file extension filtering."""
    # Create mixed file types
    task_dir = temp_dir / 'mixed_tasks'
    task_dir.mkdir()

    (task_dir / 'task1.sh').write_text('#!/bin/bash\necho "SH task"\n')
    (task_dir / 'task2.py').write_text('#!/usr/bin/env python3\nprint("PY task")\n')
    (task_dir / 'task3.sh').write_text('#!/bin/bash\necho "SH task 2"\n')
    (task_dir / 'readme.txt').write_text('Not a task')

    # Filter for .sh files only
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(task_dir),
         '--file-extension', 'sh',
         '-C', 'bash @TASK@'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    assert result.returncode == 0
    # Should find only 2 .sh files
    assert 'task1.sh' in result.stdout
    assert 'task3.sh' in result.stdout
    assert 'task2.py' not in result.stdout
    assert 'readme.txt' not in result.stdout


@pytest.mark.integration
def test_file_mode_empty_directory(temp_dir, isolated_env):
    """Test handling of empty task directory."""
    empty_dir = temp_dir / 'empty'
    empty_dir.mkdir()

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(empty_dir),
         '-C', 'bash @TASK@'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    # Should fail or warn about no tasks found
    assert result.returncode != 0 or 'No task files found' in result.stderr


@pytest.mark.integration
def test_file_mode_nonexistent_path(temp_dir, isolated_env):
    """Test handling of nonexistent task path."""
    nonexistent = temp_dir / 'does_not_exist'

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(nonexistent),
         '-C', 'bash @TASK@'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    # Should fail with error about path not existing
    assert result.returncode != 0
    assert 'does not exist' in result.stderr.lower() or 'not found' in result.stderr.lower()


@pytest.mark.integration
def test_file_mode_worker_count(sample_task_dir, isolated_env):
    """Test execution with different worker counts."""
    # Test with 1 worker
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '1'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    assert result.returncode == 0
    # Check for worker count with robust regex (handles singular/plural, case variations)
    assert re.search(r'\bworkers?\b[:=]?\s*1\b', result.stdout, re.I)


@pytest.mark.integration
def test_file_mode_timeout(temp_dir, isolated_env):
    """Test task timeout handling."""
    task_dir = temp_dir / 'timeout_tasks'
    task_dir.mkdir()

    # Create a task that sleeps longer than timeout
    slow_task = task_dir / 'slow.sh'
    slow_task.write_text('#!/bin/bash\nsleep 10\necho "Done"\n')
    slow_task.chmod(0o755)

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(task_dir),
         '-C', 'bash @TASK@',
         '-r', '-t', '2'],  # 2 second timeout
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=15
    )

    # Should timeout (check both stdout and stderr)
    combined = (result.stdout + result.stderr).lower()
    assert ('timeout' in combined) or ('timed out' in combined)


@pytest.mark.integration
def test_file_mode_multiple_directories(temp_dir, isolated_env):
    """Test executing tasks from multiple directories."""
    dir1 = temp_dir / 'tasks1'
    dir2 = temp_dir / 'tasks2'
    dir1.mkdir()
    dir2.mkdir()

    (dir1 / 'task1.sh').write_text('#!/bin/bash\necho "Task 1"\n')
    (dir2 / 'task2.sh').write_text('#!/bin/bash\necho "Task 2"\n')

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(dir1),
         '-T', str(dir2),
         '-C', 'bash @TASK@'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    assert result.returncode == 0
    # Should find tasks from both directories
    assert 'task1.sh' in result.stdout
    assert 'task2.sh' in result.stdout
