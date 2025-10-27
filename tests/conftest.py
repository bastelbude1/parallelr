"""
Shared pytest fixtures and configuration for parallelr test suite.

This file contains common fixtures used across all test modules.
"""

import os
import sys
import tempfile
import shutil
import subprocess
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
PARALLELR_BIN = PROJECT_ROOT / 'bin' / 'parallelr.py'


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp_path = tempfile.mkdtemp(prefix='parallelr_test_')
    yield Path(temp_path)
    # Cleanup
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def temp_config_dir(temp_dir):
    """Create a temporary configuration directory."""
    config_dir = temp_dir / 'cfg'
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


@pytest.fixture
def sample_task_file(temp_dir):
    """Create a sample task file."""
    task_file = temp_dir / 'task.sh'
    task_file.write_text('#!/bin/bash\necho "Test task"\n')
    task_file.chmod(0o755)
    return task_file


@pytest.fixture
def sample_task_dir(temp_dir):
    """Create a directory with multiple sample task files."""
    task_dir = temp_dir / 'tasks'
    task_dir.mkdir()

    # Create 5 sample tasks
    for i in range(1, 6):
        task_file = task_dir / f'task{i}.sh'
        task_file.write_text(f'#!/bin/bash\necho "Task {i}"\n')
        task_file.chmod(0o755)

    return task_dir


@pytest.fixture
def sample_arguments_file(temp_dir):
    """Create a sample arguments file."""
    args_file = temp_dir / 'args.txt'
    args_file.write_text('arg1\narg2\narg3\n')
    return args_file


@pytest.fixture
def sample_multi_args_file(temp_dir):
    """Create a sample multi-argument file (comma-separated)."""
    args_file = temp_dir / 'multi_args.txt'
    args_file.write_text('server1,8080,prod\nserver2,8081,dev\nserver3,8082,staging\n')
    return args_file


@pytest.fixture
def sample_config_yaml(temp_config_dir):
    """Create a sample YAML configuration file."""
    config_file = temp_config_dir / 'parallelr.yaml'
    config_content = """
limits:
  max_workers: 20
  timeout_seconds: 120
  max_allowed_workers: 100
  max_allowed_timeout: 3600
  task_start_delay: 0.1
  max_output_capture: 10485760

logging:
  level: INFO
  max_file_size_mb: 10
  backup_count: 5

execution:
  workspace_isolation: false
  stop_limits_enabled: false
  max_consecutive_failures: 5
  max_failure_rate: 0.5
  min_tasks_for_rate_check: 10

security:
  max_task_file_size_mb: 1
  max_argument_length: 1000
"""
    config_file.write_text(config_content)
    return config_file


@pytest.fixture
def mock_env(monkeypatch):
    """Fixture to safely mock environment variables via monkeypatch."""
    yield monkeypatch


@pytest.fixture
def capture_logs(caplog):
    """Fixture to capture log output."""
    import logging
    caplog.set_level(logging.DEBUG)
    return caplog


@pytest.fixture(autouse=True, scope="function")
def cleanup_daemon_processes():
    """
    Ensure all daemon processes are cleaned up after each test.

    This fixture runs automatically for every test (autouse=True) and ensures
    that any parallelr daemon processes started during the test are properly
    terminated, even if the test fails. This prevents test pollution and
    resource leaks.

    The cleanup happens in the teardown phase (after yield), ensuring it
    runs even when assertions fail or exceptions are raised.
    """
    # Setup phase - runs before test
    yield

    # Teardown phase - runs after test (even if test fails)
    try:
        # Kill all daemon processes with automatic 'yes' confirmation
        result = subprocess.run(
            [sys.executable, str(PARALLELR_BIN), '-k'],
            input='yes\n',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=10
        )
        # Silence is golden - we don't care if there were no processes to kill
    except subprocess.TimeoutExpired:
        # If cleanup times out, force kill via PID file
        pid_file = Path.home() / 'parallelr' / 'pids' / 'parallelr.pids'
        if pid_file.exists():
            try:
                pids = pid_file.read_text().strip().split('\n')
                for pid in pids:
                    if pid:
                        try:
                            os.kill(int(pid), 9)  # SIGKILL
                        except (ProcessLookupError, ValueError):
                            pass  # Process already dead or invalid PID
            except Exception:
                pass  # Best effort cleanup
    except Exception:
        # Best effort cleanup - don't fail tests due to cleanup issues
        pass


# Test markers
def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "security: marks tests as security tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )
    config.addinivalue_line(
        "markers", "smoke: marks tests as smoke tests (quick validation)"
    )
