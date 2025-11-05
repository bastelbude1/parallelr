"""
Unit tests for reporting and summary statistics.

Tests the memory statistics formatting and reporting functionality.
"""

import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch
import pytest

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import after path setup
from bin.parallelr import ParallelTaskManager, TaskResult, TaskStatus


@pytest.mark.unit
def test_memory_stats_per_task_formatting_with_psutil(tmp_path):
    """
    Test that memory statistics are correctly formatted with per-task labels.

    Verifies:
    - Memory stats show "(per task)" labels
    - Worst-case total memory calculation is correct
    - Worst-case label is present
    """
    # Create a temporary script path (doesn't need to exist, will be mocked)
    script_path = tmp_path / "parallelr.py"

    # Create logs directory
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Create mock configuration that Configuration.from_script will return
    mock_config = MagicMock()
    mock_config.limits.max_workers = 5
    mock_config.limits.timeout_seconds = 600
    mock_config.limits.task_start_delay = 0.1
    mock_config.limits.wait_time = 1.0
    mock_config.limits.max_output_capture = 1000
    mock_config.limits.stop_limits_enabled = False
    mock_config.execution.workspace_isolation = False
    mock_config.logging.level = 'INFO'
    mock_config.logging.max_log_size_mb = 10
    mock_config.logging.backup_count = 5
    mock_config.get_working_directory.return_value = str(tmp_path / "workspace")
    mock_config.get_log_directory.return_value = logs_dir
    mock_config.get_custom_timestamp.return_value = "01Jan25_120000"
    mock_config.validate.return_value = None

    # Patch Configuration.from_script to return our mock
    with patch('bin.parallelr.Configuration.from_script', return_value=mock_config):
        # Create ParallelTaskManager with real parameters
        manager = ParallelTaskManager(
            max_workers=5,
            timeout=600,
            task_start_delay=0.1,
            tasks_paths=[str(tmp_path / "tasks")],
            command_template="bash @TASK@",
            script_path=str(script_path),
            dry_run=False
        )

    # Override attributes needed for testing
    manager.log_dir = tmp_path / "logs"
    manager.process_id = 12345
    manager.timestamp = "01Jan25_120000"
    manager.task_files = [tmp_path / f"task{i}.sh" for i in range(3)]
    manager.failed_tasks = []

    # Create completed tasks with memory usage
    completed_tasks = []
    for i in range(3):
        task = TaskResult(
            task_file=str(tmp_path / f"task{i}.sh"),
            command=f"bash {tmp_path}/task{i}.sh",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            end_time=datetime(2025, 1, 1, 12, 0, 1),
            status=TaskStatus.SUCCESS,
            exit_code=0,
            duration=1.0,
            memory_usage=10.0 + i,  # 10MB, 11MB, 12MB
            cpu_usage=5.0,
            worker_id=i+1
        )
        completed_tasks.append(task)

    manager.completed_tasks = completed_tasks

    # Mock HAS_PSUTIL to True
    with patch('bin.parallelr.HAS_PSUTIL', True):
        # Call get_summary_report to generate the report
        summary = manager.get_summary_report()

    # Verify per-task labels are present
    assert "(per task)" in summary, "Summary should contain '(per task)' label"
    assert "Average Memory Usage (per task)" in summary
    assert "Peak Memory Usage (per task)" in summary

    # Verify worst-case label
    assert "(worst-case)" in summary, "Summary should contain '(worst-case)' label"

    # Verify total memory calculation
    # Peak memory is 12.0MB, workers is 5, so total should be 60.0MB
    assert "60.00MB (worst-case)" in summary, \
        "Total memory should be 60.00MB (12.0MB * 5 workers)"

    # Verify it says "5 workers" in the total line
    assert "(5 workers)" in summary

    # Verify average memory (10 + 11 + 12) / 3 = 11.0
    assert "11.00MB" in summary


@pytest.mark.unit
def test_memory_stats_formatting_without_psutil(tmp_path):
    """
    Test that summary gracefully handles missing psutil.

    Verifies:
    - Fallback message is shown when psutil is not available
    - No crash or error occurs
    """
    # Create temporary script path
    script_path = tmp_path / "parallelr.py"

    # Create logs directory
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Create mock configuration
    mock_config = MagicMock()
    mock_config.limits.max_workers = 5
    mock_config.limits.timeout_seconds = 600
    mock_config.limits.task_start_delay = 0.1
    mock_config.limits.wait_time = 1.0
    mock_config.limits.max_output_capture = 1000
    mock_config.limits.stop_limits_enabled = False
    mock_config.execution.workspace_isolation = False
    mock_config.logging.level = 'INFO'
    mock_config.logging.max_log_size_mb = 10
    mock_config.logging.backup_count = 5
    mock_config.get_working_directory.return_value = str(tmp_path / "workspace")
    mock_config.get_log_directory.return_value = logs_dir
    mock_config.get_custom_timestamp.return_value = "01Jan25_120000"
    mock_config.validate.return_value = None

    # Patch Configuration.from_script
    with patch('bin.parallelr.Configuration.from_script', return_value=mock_config):
        manager = ParallelTaskManager(
            max_workers=5,
            timeout=600,
            task_start_delay=0.1,
            tasks_paths=[str(tmp_path / "tasks")],
            command_template="bash @TASK@",
            script_path=str(script_path),
            dry_run=False
        )

    # Override attributes
    manager.log_dir = logs_dir
    manager.process_id = 12345
    manager.timestamp = "01Jan25_120000"
    manager.task_files = [tmp_path / "task.sh"]
    manager.failed_tasks = []

    # Create a completed task (memory stats won't show without completed tasks)
    task = TaskResult(
        task_file=str(tmp_path / "task.sh"),
        command=f"bash {tmp_path}/task.sh",
        start_time=datetime(2025, 1, 1, 12, 0, 0),
        end_time=datetime(2025, 1, 1, 12, 0, 1),
        status=TaskStatus.SUCCESS,
        exit_code=0,
        duration=1.0,
        memory_usage=10.0,
        cpu_usage=5.0,
        worker_id=1
    )
    manager.completed_tasks = [task]

    # Mock HAS_PSUTIL to False
    with patch('bin.parallelr.HAS_PSUTIL', False):
        summary = manager.get_summary_report()

    # Verify fallback message
    assert "Memory/CPU monitoring: Not available" in summary

    # Verify per-task labels are NOT present (since psutil is unavailable)
    assert "(per task)" not in summary


@pytest.mark.unit
def test_worst_case_memory_calculation_scaling(tmp_path):
    """
    Test that worst-case memory calculation scales correctly with worker count.

    Verifies:
    - Formula: total = peak_per_task * num_workers
    - Different worker counts produce proportional results
    """
    worker_counts = [2, 5, 10]
    peak_memory = 15.0  # 15MB peak per task
    script_path = tmp_path / "parallelr.py"

    # Create logs directory
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    for workers in worker_counts:
        # Create mock configuration
        mock_config = MagicMock()
        mock_config.limits.max_workers = workers
        mock_config.limits.timeout_seconds = 600
        mock_config.limits.task_start_delay = 0.1
        mock_config.limits.wait_time = 1.0
        mock_config.limits.max_output_capture = 1000
        mock_config.limits.stop_limits_enabled = False
        mock_config.execution.workspace_isolation = False
        mock_config.logging.level = 'INFO'
        mock_config.logging.max_log_size_mb = 10
        mock_config.logging.backup_count = 5
        mock_config.get_working_directory.return_value = str(tmp_path / "workspace")
        mock_config.get_log_directory.return_value = logs_dir
        mock_config.get_custom_timestamp.return_value = "01Jan25_120000"
        mock_config.validate.return_value = None

        # Patch Configuration.from_script
        with patch('bin.parallelr.Configuration.from_script', return_value=mock_config):
            manager = ParallelTaskManager(
                max_workers=workers,
                timeout=600,
                task_start_delay=0.1,
                tasks_paths=[str(tmp_path / "tasks")],
                command_template="bash @TASK@",
                script_path=str(script_path),
                dry_run=False
            )

        # Override attributes
        manager.log_dir = logs_dir
        manager.process_id = 12345
        manager.timestamp = "01Jan25_120000"
        manager.task_files = [tmp_path / "task.sh"]
        manager.failed_tasks = []

        # Create task with peak memory
        task = TaskResult(
            task_file=str(tmp_path / "task.sh"),
            command=f"bash {tmp_path}/task.sh",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            end_time=datetime(2025, 1, 1, 12, 0, 1),
            status=TaskStatus.SUCCESS,
            exit_code=0,
            duration=1.0,
            memory_usage=peak_memory,
            cpu_usage=5.0,
            worker_id=1
        )
        manager.completed_tasks = [task]

        # Generate summary
        with patch('bin.parallelr.HAS_PSUTIL', True):
            summary = manager.get_summary_report()

        # Verify calculation
        expected_total = peak_memory * workers
        expected_str = f"{expected_total:.2f}MB (worst-case)"

        assert expected_str in summary, \
            f"For {workers} workers: expected {expected_str} in summary"

        # Verify worker count is shown
        assert f"({workers} workers)" in summary
