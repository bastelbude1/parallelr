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
    
    with patch('bin.parallelr.subprocess.Popen', return_value=mock_process), \
         patch('bin.parallelr.HAS_PSUTIL', True), \
         patch('bin.parallelr.psutil.Process', return_value=mock_psutil_process), \
         patch('bin.parallelr.HAS_FCNTL', False):
        
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
    
    # Import psutil to get exception class
    try:
        import psutil
        no_such_process_exc = psutil.NoSuchProcess(99999)
    except ImportError:
        # If psutil not available, use generic exception
        no_such_process_exc = Exception("Process not found")
    
    with patch('bin.parallelr.subprocess.Popen', return_value=mock_process), \
         patch('bin.parallelr.HAS_PSUTIL', True), \
         patch('bin.parallelr.psutil.Process', side_effect=no_such_process_exc), \
         patch('bin.parallelr.HAS_FCNTL', False):
        
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
    
    with patch('bin.parallelr.subprocess.Popen', return_value=mock_process), \
         patch('bin.parallelr.HAS_PSUTIL', False), \
         patch('bin.parallelr.HAS_FCNTL', False):
        
        result = executor.execute()
    
    # Find the exit code log message
    log_calls = [str(call) for call in mock_logger.info.call_args_list]
    exit_code_logs = [log for log in log_calls if 'Exit code:' in log]
    
    assert len(exit_code_logs) > 0, "Should have logged exit code"
    
    # Verify format has single space before "Exit code"
    exit_log = exit_code_logs[0]
    assert "' Exit code:" in exit_log, \
        f"Log should have single space before 'Exit code', got: {exit_log}"
