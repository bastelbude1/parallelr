"""
Unit tests for SecureTaskExecutor CPU monitoring priming.

Tests the CPU monitoring initialization that happens during task execution.
"""

import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock
import subprocess

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

# Import after path setup
from bin.parallelr import SecureTaskExecutor, TaskStatus


@pytest.mark.unit
def test_cpu_priming_with_psutil_available(tmp_path):
    """
    Test that CPU monitoring is primed when psutil is available.
    
    Verifies CPU priming code path is executed (lines 872-878).
    """
    task_file = tmp_path / "test.sh"
    task_file.write_text("#!/bin/bash\necho test\n")
    task_file.chmod(0o755)
    
    mock_logger = MagicMock()
    mock_config = MagicMock()
    mock_config.execution.workspace_isolation = False
    mock_config.execution.use_process_groups = False
    mock_config.security.max_argument_length = 10000
    mock_config.advanced.max_file_size = 10000000
    mock_config.get_working_directory.return_value = str(tmp_path)
    
    executor = SecureTaskExecutor(
        task_file=str(task_file),
        command_template="echo @TASK@",
        timeout=10,
        worker_id=1,
        logger=mock_logger,
        config=mock_config
    )
    
    # Mock process
    mock_process = MagicMock()
    mock_process.pid = 99999
    mock_process.returncode = 0
    mock_process.poll.return_value = 0  # Already finished
    mock_process.stdout = MagicMock()
    mock_process.stderr = MagicMock()
    mock_process.stdout.read.return_value = "test output"
    mock_process.stderr.read.return_value = ""
    mock_process.stdout.fileno.return_value = 100
    mock_process.stderr.fileno.return_value = 101
    
    # Mock psutil.Process
    mock_psutil_process = MagicMock()
    mock_psutil_process.cpu_percent.return_value = 15.5
    mock_psutil_process.memory_info.return_value = MagicMock(rss=10485760)  # 10MB
    
    with (
        patch('bin.parallelr.subprocess.Popen', return_value=mock_process),
        patch('bin.parallelr.HAS_PSUTIL', True),
        patch('psutil.Process', return_value=mock_psutil_process),
        patch('bin.parallelr.HAS_FCNTL', False)
    ):
        result = executor.execute()
    
    # Verify CPU monitoring was initialized (cpu_percent called)
    assert mock_psutil_process.cpu_percent.called, \
        "cpu_percent() should be called for CPU monitoring"
    assert result.status == TaskStatus.SUCCESS
    assert result.exit_code == 0


@pytest.mark.unit  
def test_cpu_priming_handles_process_not_found(tmp_path):
    """
    Test graceful handling when process doesn't exist during priming.
    
    Verifies exception handling in CPU priming (lines 877-878).
    """
    task_file = tmp_path / "test.sh"
    task_file.write_text("#!/bin/bash\necho test\n")
    task_file.chmod(0o755)
    
    mock_logger = MagicMock()
    mock_config = MagicMock()
    mock_config.execution.workspace_isolation = False
    mock_config.execution.use_process_groups = False
    mock_config.security.max_argument_length = 10000
    mock_config.advanced.max_file_size = 10000000
    mock_config.get_working_directory.return_value = str(tmp_path)
    
    executor = SecureTaskExecutor(
        task_file=str(task_file),
        command_template="echo @TASK@",
        timeout=10,
        worker_id=1,
        logger=mock_logger,
        config=mock_config
    )
    
    # Mock process
    mock_process = MagicMock()
    mock_process.pid = 99999
    mock_process.returncode = 0
    mock_process.poll.return_value = 0
    mock_process.stdout = MagicMock()
    mock_process.stderr = MagicMock()
    mock_process.stdout.read.return_value = ""
    mock_process.stderr.read.return_value = ""
    mock_process.stdout.fileno.return_value = 100
    mock_process.stderr.fileno.return_value = 101
    
    # Create a mock exception to simulate psutil.NoSuchProcess
    # We don't import psutil here to avoid circular import issues with patches
    no_such_process_exc = Exception("Process not found")
    
    with (
        patch('bin.parallelr.subprocess.Popen', return_value=mock_process),
        patch('bin.parallelr.HAS_PSUTIL', True),
        patch('psutil.Process', side_effect=no_such_process_exc),
        patch('bin.parallelr.HAS_FCNTL', False)
    ):
        # Should not crash, should handle exception gracefully
        result = executor.execute()
    
    assert result.status == TaskStatus.SUCCESS
    assert result.exit_code == 0


@pytest.mark.unit
def test_log_formatting_with_task_execution(tmp_path):
    """
    Test that log messages have correct spacing format.
    
    Verifies log formatting changes (lines 980, 985).
    """
    task_file = tmp_path / "test.sh"
    task_file.write_text("#!/bin/bash\necho test\n")
    task_file.chmod(0o755)
    
    mock_logger = MagicMock()
    mock_config = MagicMock()
    mock_config.execution.workspace_isolation = False
    mock_config.execution.use_process_groups = False
    mock_config.security.max_argument_length = 10000
    mock_config.advanced.max_file_size = 10000000
    mock_config.get_working_directory.return_value = str(tmp_path)
    
    executor = SecureTaskExecutor(
        task_file=str(task_file),
        command_template="echo @TASK@",
        timeout=10,
        worker_id=1,
        logger=mock_logger,
        config=mock_config,
        task_number=1,
        total_tasks=1
    )
    
    # Mock process with successful exit
    mock_process = MagicMock()
    mock_process.pid = 99999
    mock_process.returncode = 0
    mock_process.poll.return_value = 0
    mock_process.stdout = MagicMock()
    mock_process.stderr = MagicMock()
    mock_process.stdout.read.return_value = ""
    mock_process.stderr.read.return_value = ""
    mock_process.stdout.fileno.return_value = 100
    mock_process.stderr.fileno.return_value = 101
    
    with (
        patch('bin.parallelr.subprocess.Popen', return_value=mock_process),
        patch('bin.parallelr.HAS_PSUTIL', False),
        patch('bin.parallelr.HAS_FCNTL', False)
    ):
        result = executor.execute()
    
    # Find the exit code log message
    exit_code_logs = []
    for call in mock_logger.info.call_args_list:
        args = call[0]
        if args and 'Exit code:' in str(args[0]):
            exit_code_logs.append(str(args[0]))

    assert len(exit_code_logs) > 0, "Should have logged exit code"

    # Verify format has single space before "Exit code"
    exit_log = exit_code_logs[0]
    assert " Exit code:" in exit_log and "  Exit code:" not in exit_log, \
        f"Log should have single space before 'Exit code', got: {exit_log}"


@pytest.mark.unit
def test_windows_process_group_creation(tmp_path):
    """
    Test Windows-specific process group creation flag.

    Verifies line 868: popen_kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
    """
    task_file = tmp_path / "test.sh"
    task_file.write_text("#!/bin/bash\necho test\n")
    task_file.chmod(0o755)

    mock_logger = MagicMock()
    mock_config = MagicMock()
    mock_config.execution.workspace_isolation = False
    mock_config.execution.use_process_groups = True  # Enable process groups
    mock_config.security.max_argument_length = 10000
    mock_config.advanced.max_file_size = 10000000
    mock_config.get_working_directory.return_value = str(tmp_path)

    executor = SecureTaskExecutor(
        task_file=str(task_file),
        command_template="echo @TASK@",
        timeout=10,
        worker_id=1,
        logger=mock_logger,
        config=mock_config
    )

    # Mock process
    mock_process = MagicMock()
    mock_process.pid = 99999
    mock_process.returncode = 0
    mock_process.poll.return_value = 0
    mock_process.stdout = MagicMock()
    mock_process.stderr = MagicMock()
    mock_process.stdout.read.return_value = ""
    mock_process.stderr.read.return_value = ""
    mock_process.stdout.fileno.return_value = 100
    mock_process.stderr.fileno.return_value = 101

    # Mock subprocess.Popen to capture kwargs
    popen_mock = MagicMock(return_value=mock_process)

    # Mock Windows-specific constant first, before checking os.name
    with (
        patch.object(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0x00000200, create=True),
        patch('bin.parallelr.subprocess.Popen', popen_mock),
        patch('bin.parallelr.os.name', 'nt'),  # Mock Windows OS
        patch('bin.parallelr.HAS_PSUTIL', False),
        patch('bin.parallelr.HAS_FCNTL', False)
    ):
        result = executor.execute()

    # Verify Popen was called with creationflags
    assert popen_mock.called, "Popen should have been called"
    call_kwargs = popen_mock.call_args[1]

    # On Windows with use_process_groups, should have creationflags
    assert 'creationflags' in call_kwargs, \
        "Windows should have creationflags in Popen kwargs"
    assert call_kwargs['creationflags'] == 0x00000200, \
        "creationflags should be CREATE_NEW_PROCESS_GROUP (0x00000200)"

    assert result.status == TaskStatus.SUCCESS


@pytest.mark.unit
def test_posix_process_group_with_setsid(tmp_path):
    """
    Test POSIX-specific process group creation with setsid.

    Verifies line 865: popen_kwargs['preexec_fn'] = os.setsid
    """
    task_file = tmp_path / "test.sh"
    task_file.write_text("#!/bin/bash\necho test\n")
    task_file.chmod(0o755)

    mock_logger = MagicMock()
    mock_config = MagicMock()
    mock_config.execution.workspace_isolation = False
    mock_config.execution.use_process_groups = True  # Enable process groups
    mock_config.security.max_argument_length = 10000
    mock_config.advanced.max_file_size = 10000000
    mock_config.get_working_directory.return_value = str(tmp_path)

    executor = SecureTaskExecutor(
        task_file=str(task_file),
        command_template="echo @TASK@",
        timeout=10,
        worker_id=1,
        logger=mock_logger,
        config=mock_config
    )

    # Mock process
    mock_process = MagicMock()
    mock_process.pid = 99999
    mock_process.returncode = 0
    mock_process.poll.return_value = 0
    mock_process.stdout = MagicMock()
    mock_process.stderr = MagicMock()
    mock_process.stdout.read.return_value = ""
    mock_process.stderr.read.return_value = ""
    mock_process.stdout.fileno.return_value = 100
    mock_process.stderr.fileno.return_value = 101

    # Mock subprocess.Popen to capture kwargs
    popen_mock = MagicMock(return_value=mock_process)

    with (
        patch('bin.parallelr.subprocess.Popen', popen_mock),
        patch('bin.parallelr.os.name', 'posix'),  # Mock POSIX OS
        patch('bin.parallelr.HAS_PSUTIL', False),
        patch('bin.parallelr.HAS_FCNTL', False)
    ):
        result = executor.execute()

    # Verify Popen was called with preexec_fn
    assert popen_mock.called, "Popen should have been called"
    call_kwargs = popen_mock.call_args[1]

    # On POSIX with use_process_groups, should have preexec_fn
    assert 'preexec_fn' in call_kwargs, \
        "POSIX should have preexec_fn in Popen kwargs"

    assert result.status == TaskStatus.SUCCESS
