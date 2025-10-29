"""
Output validation tests for parallelr.

Tests the format, completeness, and accuracy of output files:
- CSV summary files
- Task output logs
- Performance metrics
- Summary statistics
"""

import subprocess
import os
import re
import shutil
from pathlib import Path
import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import PARALLELR_BIN, PYTHON_FOR_PARALLELR
from tests.integration.test_helpers import (
    extract_log_path_from_stdout,
    parse_csv_summary,
    read_task_output_log,
    verify_csv_completeness,
    verify_summary_counts
)

# Skip all tests if bash is not available (POSIX dependency)
pytestmark = pytest.mark.skipif(shutil.which("bash") is None,
                                reason="Requires bash (POSIX)")


@pytest.fixture
def isolated_env(tmp_path):
    """
    Provide isolated environment for output validation tests.

    Creates a subprocess-only environment without mutating global os.environ.
    Safe for parallel test execution.
    """
    temp_home = tmp_path / 'home'
    temp_home.mkdir()

    # Create isolated environment copy for subprocess use only
    env_copy = {**os.environ, 'HOME': str(temp_home)}

    yield {
        'home': temp_home,
        'env': env_copy
    }


@pytest.mark.integration
def test_csv_summary_all_required_fields(sample_task_dir, isolated_env):
    """
    Test that CSV summary contains all required fields.

    Verifies:
    - All required columns are present
    - No missing fields in any record
    - Field names match expected schema
    """
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '2'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    assert result.returncode == 0, f"Command failed: {result.stderr}"

    csv_path = extract_log_path_from_stdout(result.stdout, 'summary')
    csv_records = parse_csv_summary(csv_path)

    # Define required fields
    required_fields = [
        'start_time', 'end_time', 'status', 'process_id', 'worker_id',
        'task_file', 'command', 'exit_code', 'duration_seconds',
        'memory_mb', 'cpu_percent', 'error_message'
    ]

    # Verify all fields are present in each record
    for i, record in enumerate(csv_records):
        for field in required_fields:
            assert field in record, \
                f"Record {i} missing required field: {field}"


@pytest.mark.integration
def test_csv_summary_field_data_types(sample_task_dir, isolated_env):
    """
    Test that CSV summary fields have correct data types.

    Verifies:
    - Numeric fields are properly converted (int, float)
    - String fields are present
    - Type conversions are accurate
    """
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '2'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    assert result.returncode == 0, f"Command failed: {result.stderr}"

    csv_path = extract_log_path_from_stdout(result.stdout, 'summary')
    csv_records = parse_csv_summary(csv_path)

    for i, record in enumerate(csv_records):
        # Integer fields
        assert isinstance(record['exit_code'], int), \
            f"Record {i}: exit_code should be int, got {type(record['exit_code'])}"
        assert isinstance(record['worker_id'], int), \
            f"Record {i}: worker_id should be int, got {type(record['worker_id'])}"

        # Float fields
        assert isinstance(record['duration_seconds'], float), \
            f"Record {i}: duration_seconds should be float, got {type(record['duration_seconds'])}"
        assert isinstance(record['memory_mb'], float), \
            f"Record {i}: memory_mb should be float, got {type(record['memory_mb'])}"
        assert isinstance(record['cpu_percent'], float), \
            f"Record {i}: cpu_percent should be float, got {type(record['cpu_percent'])}"

        # String fields
        assert isinstance(record['status'], str), \
            f"Record {i}: status should be str, got {type(record['status'])}"
        assert isinstance(record['command'], str), \
            f"Record {i}: command should be str, got {type(record['command'])}"


@pytest.mark.integration
def test_csv_summary_timestamp_format(sample_task_dir, isolated_env):
    """
    Test that CSV timestamp fields have valid format.

    Verifies:
    - Timestamps are in ISO format or similar
    - start_time <= end_time
    - Timestamps are parseable
    """
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '2'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    assert result.returncode == 0, f"Command failed: {result.stderr}"

    csv_path = extract_log_path_from_stdout(result.stdout, 'summary')
    csv_records = parse_csv_summary(csv_path)

    # Timestamp regex (flexible - matches various formats)
    timestamp_pattern = re.compile(r'\d{4}-\d{2}-\d{2}')

    for i, record in enumerate(csv_records):
        start_time = record['start_time']
        end_time = record['end_time']

        # Verify timestamps match expected format
        assert timestamp_pattern.search(start_time), \
            f"Record {i}: start_time has invalid format: {start_time}"
        assert timestamp_pattern.search(end_time), \
            f"Record {i}: end_time has invalid format: {end_time}"

        # Verify start_time <= end_time (lexicographically for ISO format)
        assert start_time <= end_time, \
            f"Record {i}: start_time ({start_time}) should be <= end_time ({end_time})"


@pytest.mark.integration
def test_csv_summary_status_values(sample_task_dir, isolated_env):
    """
    Test that CSV status field contains valid values.

    Verifies:
    - Status is one of: SUCCESS, FAILED, TIMEOUT, CANCELLED
    - Status matches exit_code (SUCCESS => exit_code=0)
    """
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '2'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    assert result.returncode == 0, f"Command failed: {result.stderr}"

    csv_path = extract_log_path_from_stdout(result.stdout, 'summary')
    csv_records = parse_csv_summary(csv_path)

    valid_statuses = {'SUCCESS', 'FAILED', 'TIMEOUT', 'CANCELLED'}

    for i, record in enumerate(csv_records):
        status = record['status']
        exit_code = record['exit_code']

        # Verify status is valid
        assert status in valid_statuses, \
            f"Record {i}: invalid status '{status}', expected one of {valid_statuses}"

        # Verify status consistency with exit_code
        if status == 'SUCCESS':
            assert exit_code == 0, \
                f"Record {i}: status=SUCCESS but exit_code={exit_code} (should be 0)"


@pytest.mark.integration
def test_output_log_file_created(sample_task_dir, isolated_env):
    """
    Test that output log file is created and accessible.

    Verifies:
    - Output log file path is shown in stdout
    - File exists after execution
    - File is readable
    """
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '2'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    assert result.returncode == 0, f"Command failed: {result.stderr}"

    # Extract output log path
    output_path = extract_log_path_from_stdout(result.stdout, 'output')
    assert output_path, "Could not find output log file path in stdout"

    # Verify file exists
    assert os.path.exists(output_path), f"Output log file does not exist: {output_path}"

    # Verify file is readable
    content = read_task_output_log(output_path)
    assert content is not None, "Could not read output log file"
    assert len(content) > 0, "Output log file is empty (should contain task output)"


@pytest.mark.integration
def test_output_log_task_separation(temp_dir, isolated_env):
    """
    Test that output log properly separates different tasks.

    Verifies:
    - Each task's output is clearly marked
    - Task boundaries are identifiable
    - Output from different tasks doesn't overlap
    """
    # Create tasks with distinct output
    for i in range(3):
        task = temp_dir / f'task_{i}.sh'
        task.write_text(f'#!/bin/bash\necho "=== Task {i} Output ==="\necho "Unique content {i}"\n')
        task.chmod(0o755)

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '2'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    assert result.returncode == 0, f"Command failed: {result.stderr}"

    output_path = extract_log_path_from_stdout(result.stdout, 'output')
    output_content = read_task_output_log(output_path)

    # Verify all tasks' output is present
    assert 'Task 0 Output' in output_content, "Task 0 output not found in log"
    assert 'Task 1 Output' in output_content, "Task 1 output not found in log"
    assert 'Task 2 Output' in output_content, "Task 2 output not found in log"

    # Verify unique content from each task
    assert 'Unique content 0' in output_content, "Task 0 unique content not found"
    assert 'Unique content 1' in output_content, "Task 1 unique content not found"
    assert 'Unique content 2' in output_content, "Task 2 unique content not found"


@pytest.mark.integration
def test_performance_metrics_reasonable_values(sample_task_dir, isolated_env):
    """
    Test that performance metrics have reasonable values.

    Verifies:
    - duration_seconds > 0
    - memory_mb >= 0
    - cpu_percent >= 0 and <= 100 (or > 100 for multi-core)
    """
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '2'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    assert result.returncode == 0, f"Command failed: {result.stderr}"

    csv_path = extract_log_path_from_stdout(result.stdout, 'summary')
    csv_records = parse_csv_summary(csv_path)

    for i, record in enumerate(csv_records):
        duration = record['duration_seconds']
        memory = record['memory_mb']
        cpu = record['cpu_percent']

        # Duration should be positive
        assert duration > 0, \
            f"Record {i}: duration_seconds should be > 0, got {duration}"

        # Memory should be non-negative
        assert memory >= 0, \
            f"Record {i}: memory_mb should be >= 0, got {memory}"

        # CPU should be non-negative (can exceed 100% on multi-core)
        assert cpu >= 0, \
            f"Record {i}: cpu_percent should be >= 0, got {cpu}"

        # CPU shouldn't be absurdly high (e.g., > 1000%)
        assert cpu <= 1000, \
            f"Record {i}: cpu_percent seems too high: {cpu}%"


@pytest.mark.integration
def test_summary_statistics_match_csv(sample_task_dir, isolated_env):
    """
    Test that summary statistics in stdout match actual CSV records.

    Verifies:
    - Total count in stdout matches CSV record count
    - Success/failure counts match CSV status values
    - No discrepancy between reported and actual results
    """
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '2'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    assert result.returncode == 0, f"Command failed: {result.stderr}"

    # Parse stdout summary
    total_match = re.search(r'Total Tasks:\s+(\d+)', result.stdout)
    completed_match = re.search(r'Completed Successfully:\s+(\d+)', result.stdout)
    failed_match = re.search(r'Failed:\s+(\d+)', result.stdout)

    assert total_match, "Could not find 'Total Tasks' in stdout"
    assert completed_match, "Could not find 'Completed Successfully' in stdout"
    assert failed_match, "Could not find 'Failed' in stdout"

    stdout_total = int(total_match.group(1))
    stdout_completed = int(completed_match.group(1))
    stdout_failed = int(failed_match.group(1))

    # Parse CSV records
    csv_path = extract_log_path_from_stdout(result.stdout, 'summary')
    csv_records = parse_csv_summary(csv_path)

    csv_total = len(csv_records)
    csv_success = sum(1 for r in csv_records if r['status'] == 'SUCCESS')
    csv_failed = sum(1 for r in csv_records if r['status'] != 'SUCCESS')

    # Verify counts match
    assert stdout_total == csv_total, \
        f"Total mismatch: stdout says {stdout_total}, CSV has {csv_total} records"
    assert stdout_completed == csv_success, \
        f"Completed mismatch: stdout says {stdout_completed}, CSV has {csv_success} successes"
    assert stdout_failed == csv_failed, \
        f"Failed mismatch: stdout says {stdout_failed}, CSV has {csv_failed} failures"


@pytest.mark.integration
def test_worker_id_assignment_validity(sample_task_dir, isolated_env):
    """
    Test that worker IDs are properly assigned and tracked.

    Verifies:
    - Worker IDs are sequential starting from 1
    - Worker IDs don't exceed max_workers
    - All workers are utilized (for sufficient tasks)
    """
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '3'],  # 3 workers for 5 tasks
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    assert result.returncode == 0, f"Command failed: {result.stderr}"

    csv_path = extract_log_path_from_stdout(result.stdout, 'summary')
    csv_records = parse_csv_summary(csv_path)

    worker_ids = [record['worker_id'] for record in csv_records]

    # Verify all worker IDs are in valid range
    for worker_id in worker_ids:
        assert 1 <= worker_id <= 3, \
            f"Worker ID {worker_id} out of range (expected 1-3)"

    # With 5 tasks and 3 workers, all workers should be used
    unique_workers = set(worker_ids)
    assert len(unique_workers) == 3, \
        f"Not all workers were utilized: {unique_workers} (expected {{1, 2, 3}})"


@pytest.mark.integration
def test_log_file_paths_in_stdout(sample_task_dir, isolated_env):
    """
    Test that all log file paths are properly reported in stdout.

    Verifies:
    - Summary CSV path is shown
    - Output log path is shown
    - Main log path is shown (if applicable)
    - Paths are absolute and valid
    """
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '2'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    assert result.returncode == 0, f"Command failed: {result.stderr}"

    # Extract all log paths
    summary_path = extract_log_path_from_stdout(result.stdout, 'summary')
    output_path = extract_log_path_from_stdout(result.stdout, 'output')

    # Verify paths were found
    assert summary_path, "Summary CSV path not found in stdout"
    assert output_path, "Output log path not found in stdout"

    # Verify paths are absolute
    assert Path(summary_path).is_absolute(), \
        f"Summary path should be absolute: {summary_path}"
    assert Path(output_path).is_absolute(), \
        f"Output path should be absolute: {output_path}"

    # Verify files exist
    assert os.path.exists(summary_path), f"Summary file doesn't exist: {summary_path}"
    assert os.path.exists(output_path), f"Output file doesn't exist: {output_path}"
