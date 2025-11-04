"""
Test helper functions for integration tests.

Provides utilities for:
- JSONL results parsing and validation
- Output log file reading
- Results statistics extraction
- Common assertion patterns
"""

import json
import re
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Any


def extract_log_path_from_stdout(stdout: str, log_type: str = 'results') -> Optional[str]:
    """
    Extract log file path from command stdout.

    Args:
        stdout: Command stdout output
        log_type: Type of log to extract ('results', 'output', or 'main')

    Returns:
        Path to log file or None if not found

    Example:
        >>> stdout = "- Results: /path/to/results.jsonl"
        >>> extract_log_path_from_stdout(stdout, 'results')
        '/path/to/results.jsonl'
    """
    patterns = {
        'results': r'- Results:\s+(.+\.jsonl)',
        'summary': r'- Results:\s+(.+\.jsonl)',  # Backwards compatibility alias
        'output': r'- Output:\s+(.+\.txt)',
        'main': r'- Main Log:\s+(.+\.log)'
    }

    pattern = patterns.get(log_type)
    if not pattern:
        raise ValueError(f"Unknown log_type: {log_type}")

    match = re.search(pattern, stdout)
    return match.group(1) if match else None


def wait_for_file(file_path: str, timeout: float = 2.0, interval: float = 0.1) -> bool:
    """
    Wait for a file to exist, with timeout.

    Args:
        file_path: Path to file to wait for
        timeout: Maximum time to wait in seconds
        interval: Check interval in seconds

    Returns:
        True if file exists within timeout, False otherwise
    """
    elapsed = 0.0
    while not os.path.exists(file_path) and elapsed < timeout:
        time.sleep(interval)
        elapsed += interval
    return os.path.exists(file_path)


def parse_jsonl_results(jsonl_path: str, wait_for_file_flag: bool = True) -> List[Dict[str, Any]]:
    """
    Parse JSONL results file and return session metadata and task records.

    Args:
        jsonl_path: Path to JSONL results file
        wait_for_file_flag: If True, wait for file to exist (default: True)

    Returns:
        List of dictionaries, each representing a task record with fields:
        - start_time, end_time, status, process_id, worker_id, task_file,
          command_executed, exit_code, duration_seconds, memory_mb, cpu_percent,
          error_message, env_vars (dict), arguments (list)

    Raises:
        FileNotFoundError: If JSONL file doesn't exist
        ValueError: If JSONL format is invalid
    """
    if wait_for_file_flag:
        if not wait_for_file(jsonl_path):
            raise FileNotFoundError(f"JSONL results file not found: {jsonl_path}")

    tasks = []
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                # Skip session metadata line, only collect task records
                if data.get('type') == 'task':
                    tasks.append(data)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in results file: {e}")

    return tasks


def parse_csv_summary(csv_path: str, wait_for_file_flag: bool = True) -> List[Dict[str, Any]]:
    """
    Backwards compatibility wrapper for parse_jsonl_results.

    DEPRECATED: Use parse_jsonl_results() instead.

    Args:
        csv_path: Path to JSONL results file (despite the name)
        wait_for_file_flag: If True, wait for file to exist (default: True)

    Returns:
        List of task record dictionaries

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If format is invalid
    """
    return parse_jsonl_results(csv_path, wait_for_file_flag)


def verify_csv_row(row: Dict[str, Any], expected: Dict[str, Any],
                   strict: bool = False) -> bool:
    """
    Verify that a CSV row matches expected values.

    Args:
        row: CSV row dictionary
        expected: Dictionary of expected field values
        strict: If True, row must contain exactly the fields in expected (no extra fields).
                If False, only checks that expected fields match (allows extra fields)

    Returns:
        True if row matches expected values

    Raises:
        AssertionError: If any expected field doesn't match or if strict=True and
                       row contains fields not in expected

    Example:
        >>> row = {'status': 'SUCCESS', 'exit_code': 0, 'worker_id': 1}
        >>> expected = {'status': 'SUCCESS', 'exit_code': 0}
        >>> verify_csv_row(row, expected)  # Passes (non-strict allows extra 'worker_id')
        True
        >>> verify_csv_row(row, expected, strict=True)  # Fails (extra field 'worker_id')
        AssertionError: Unexpected fields in CSV row: worker_id
    """
    # Validate expected fields are present and match
    for key, expected_value in expected.items():
        if key not in row:
            raise AssertionError(f"Expected field '{key}' not found in CSV row")

        actual_value = row[key]
        if actual_value != expected_value:
            raise AssertionError(
                f"Field '{key}' mismatch: expected {expected_value!r}, "
                f"got {actual_value!r}"
            )

    # If strict mode, check for unexpected fields
    if strict:
        unexpected_keys = set(row.keys()) - set(expected.keys())
        if unexpected_keys:
            raise AssertionError(
                f"Unexpected fields in CSV row: {', '.join(sorted(unexpected_keys))}"
            )

    return True


def read_task_output_log(log_path: str, wait_for_file_flag: bool = True) -> str:
    """
    Read task output log file.

    Args:
        log_path: Path to output log file
        wait_for_file_flag: If True, wait for file to exist (default: True)

    Returns:
        Contents of output log file

    Raises:
        FileNotFoundError: If log file doesn't exist
    """
    if wait_for_file_flag:
        if not wait_for_file(log_path):
            raise FileNotFoundError(f"Output log file not found: {log_path}")

    with open(log_path, 'r', encoding='utf-8') as f:
        return f.read()


def verify_summary_counts(stdout: str, total: int, completed: int, failed: int) -> bool:
    """
    Verify summary counts in stdout output.

    Args:
        stdout: Command stdout
        total: Expected total task count
        completed: Expected completed count
        failed: Expected failed count

    Returns:
        True if all counts match

    Raises:
        AssertionError: If any count doesn't match

    Example:
        >>> stdout = "Total Tasks: 5\\nCompleted Successfully: 5\\nFailed: 0"
        >>> verify_summary_counts(stdout, 5, 5, 0)
        True
    """
    # Extract counts from summary section
    total_match = re.search(r'Total Tasks:\s+(\d+)', stdout)
    completed_match = re.search(r'Completed Successfully:\s+(\d+)', stdout)
    failed_match = re.search(r'Failed:\s+(\d+)', stdout)

    if not total_match:
        raise AssertionError("Could not find 'Total Tasks' in stdout")
    if not completed_match:
        raise AssertionError("Could not find 'Completed Successfully' in stdout")
    if not failed_match:
        raise AssertionError("Could not find 'Failed' in stdout")

    actual_total = int(total_match.group(1))
    actual_completed = int(completed_match.group(1))
    actual_failed = int(failed_match.group(1))

    if actual_total != total:
        raise AssertionError(f"Total count mismatch: expected {total}, got {actual_total}")
    if actual_completed != completed:
        raise AssertionError(
            f"Completed count mismatch: expected {completed}, got {actual_completed}"
        )
    if actual_failed != failed:
        raise AssertionError(f"Failed count mismatch: expected {failed}, got {actual_failed}")

    return True


def parse_execution_message(stdout: str) -> Dict[str, int]:
    """
    Parse the "Executing N tasks with M workers" message.

    Args:
        stdout: Command stdout

    Returns:
        Dictionary with 'tasks' and 'workers' keys

    Example:
        >>> stdout = "Executing 5 tasks with 2 workers"
        >>> parse_execution_message(stdout)
        {'tasks': 5, 'workers': 2}
    """
    pattern = r'Executing\s+(\d+)\s+tasks?\s+with\s+(\d+)\s+workers?'
    match = re.search(pattern, stdout, re.IGNORECASE)

    if not match:
        raise ValueError("Could not parse execution message from stdout")

    return {
        'tasks': int(match.group(1)),
        'workers': int(match.group(2))
    }


def verify_results_completeness(results_records: List[Dict], expected_count: int) -> bool:
    """
    Verify JSONL results have the expected number of complete records.

    Args:
        results_records: List of task record dictionaries from JSONL
        expected_count: Expected number of records

    Returns:
        True if count matches and all records have required fields

    Raises:
        AssertionError: If count doesn't match or records are incomplete
    """
    if len(results_records) != expected_count:
        raise AssertionError(
            f"Results record count mismatch: expected {expected_count}, "
            f"got {len(results_records)}"
        )

    required_fields = [
        'start_time', 'end_time', 'status', 'process_id', 'worker_id',
        'command_executed', 'exit_code', 'duration_seconds'
    ]

    for i, record in enumerate(results_records):
        for field in required_fields:
            if field not in record:
                raise AssertionError(
                    f"Results record {i} missing required field: {field}"
                )
            # Allow None for task_file, error_message (optional fields)
            if record[field] is None and field not in ['task_file', 'error_message']:
                # Some fields can be None in certain cases
                if field not in ['end_time']:  # end_time can be None if task is still running
                    raise AssertionError(
                        f"Results record {i} has None value for required field: {field}"
                    )

    return True


def verify_csv_completeness(csv_records: List[Dict], expected_count: int) -> bool:
    """
    DEPRECATED: Use verify_results_completeness() instead.

    Backwards compatibility wrapper for verify_results_completeness.
    """
    return verify_results_completeness(csv_records, expected_count)


def verify_all_tasks_succeeded(csv_records: List[Dict]) -> bool:
    """
    Verify all tasks in CSV have SUCCESS status and exit_code 0.

    Args:
        csv_records: List of CSV record dictionaries

    Returns:
        True if all tasks succeeded

    Raises:
        AssertionError: If any task failed
    """
    for i, record in enumerate(csv_records):
        if record['status'] != 'SUCCESS':
            raise AssertionError(
                f"Task {i} failed: status={record['status']}, "
                f"error={record.get('error_message', 'N/A')}"
            )
        if record['exit_code'] != 0:
            raise AssertionError(
                f"Task {i} has non-zero exit code: {record['exit_code']}"
            )

    return True


def verify_worker_assignments(csv_records: List[Dict], max_workers: int) -> bool:
    """
    Verify worker IDs are properly assigned.

    Args:
        csv_records: List of CSV record dictionaries
        max_workers: Maximum number of workers configured

    Returns:
        True if all worker assignments are valid

    Raises:
        AssertionError: If any worker ID is invalid

    Note:
        Worker IDs are sequential task counters, not pool indexes.
        This function verifies:
        1. Each worker_id is a positive integer (> 0)
        2. Multiple workers are utilized when max_workers > 1 and enough tasks exist
    """
    # Validate each record has a positive integer worker_id
    for i, record in enumerate(csv_records):
        worker_id = record['worker_id']

        # Check worker_id is a positive integer
        if not isinstance(worker_id, int) or worker_id < 1:
            raise AssertionError(
                f"Task {i} has invalid worker_id: {worker_id!r} "
                f"(must be a positive integer)"
            )

    # If multiple workers configured, verify we're actually using parallelism
    # when we have enough tasks to warrant it
    if max_workers > 1 and len(csv_records) >= max_workers:
        unique_worker_ids = len(set(r['worker_id'] for r in csv_records))
        if unique_worker_ids < 2:
            raise AssertionError(
                f"Expected multiple workers to be used (max_workers={max_workers}), "
                f"but only {unique_worker_ids} unique worker ID(s) found"
            )

    return True


def verify_durations_reasonable(csv_records: List[Dict],
                               min_duration: float = 0.0,
                               max_duration: Optional[float] = None) -> bool:
    """
    Verify task durations are within reasonable bounds.

    Args:
        csv_records: List of CSV record dictionaries
        min_duration: Minimum expected duration in seconds
        max_duration: Maximum expected duration in seconds (None = no max)

    Returns:
        True if all durations are reasonable

    Raises:
        AssertionError: If any duration is out of bounds
    """
    for i, record in enumerate(csv_records):
        duration = record['duration_seconds']
        if duration < min_duration:
            raise AssertionError(
                f"Task {i} duration too short: {duration}s "
                f"(expected >= {min_duration}s)"
            )
        if max_duration is not None and duration > max_duration:
            raise AssertionError(
                f"Task {i} duration too long: {duration}s "
                f"(expected <= {max_duration}s)"
            )

    return True
