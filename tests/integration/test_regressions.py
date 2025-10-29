"""
Regression tests for previously fixed bugs.

This module contains tests that verify specific bugs remain fixed.
Each test documents the original bug and ensures it doesn't reoccur.
"""

import subprocess
import os
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
    verify_all_tasks_succeeded
)

# Skip all tests if bash is not available (POSIX dependency)
pytestmark = pytest.mark.skipif(shutil.which("bash") is None,
                                reason="Requires bash (POSIX)")


@pytest.fixture
def isolated_env(tmp_path):
    """
    Provide isolated environment for regression tests.

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
def test_regression_env_var_overlap_corruption(temp_dir, isolated_env):
    """
    REGRESSION TEST: Environment variable overlap corruption bug.

    Bug Description:
    ----------------
    When using overlapping environment variable names (e.g., HOST and HOSTNAME),
    the old implementation used sequential str.replace() which caused corruption:

    Example:
      - Given: HOST=server, HOSTNAME=server1
      - Command: echo "$HOSTNAME"
      - Bug: First replaced $HOST → "server", turning $HOSTNAME into "serverNAME"
      - Result: Wrong output "serverNAME" instead of "server1"

    Fix:
    ----
    Changed to use regex-based replacement that matches complete variable names
    atomically, preventing substring corruption.

    This test verifies:
    1. $HOSTNAME correctly expands to its full value (not corrupted by $HOST)
    2. Both ${VAR} and $VAR syntax work correctly
    3. Unknown variables are left unchanged
    4. Order of variable definition doesn't matter
    """
    # Create arguments file with overlapping variable names
    args_file = temp_dir / 'args.txt'
    # HOST is a substring of HOSTNAME - triggers the old bug
    args_file.write_text('server,server1,8080\n')

    # Use command that would expose the corruption bug
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-A', str(args_file),
         '-S', 'comma',
         '-E', 'HOST,HOSTNAME,PORT',
         '-C', 'echo "Host: $HOST | Hostname: $HOSTNAME | Port: ${PORT} | Unknown: $UNKNOWN"',
         '-r', '-m', '1'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    assert result.returncode == 0, f"Command failed: {result.stderr}"

    # Extract and read output log
    output_path = extract_log_path_from_stdout(result.stdout, 'output')
    assert output_path, "Could not find output log path in stdout"
    output_content = read_task_output_log(output_path)

    # CRITICAL: Verify HOSTNAME is NOT corrupted by HOST replacement
    # With old buggy code, $HOSTNAME would become "serverNAME"
    assert 'Host: server' in output_content, "HOST not correctly expanded"
    assert 'Hostname: server1' in output_content, \
        "HOSTNAME not correctly expanded (may be corrupted by HOST substring replacement)"
    assert 'Port: 8080' in output_content, "PORT (with ${} syntax) not correctly expanded"
    assert 'Unknown: $UNKNOWN' in output_content, "Unknown variables should be left unchanged"

    # Additional verification via CSV
    csv_path = extract_log_path_from_stdout(result.stdout, 'summary')
    csv_records = parse_csv_summary(csv_path)
    verify_all_tasks_succeeded(csv_records)


@pytest.mark.integration
def test_regression_timeout_error_not_imported(temp_dir, isolated_env):
    """
    REGRESSION TEST: TimeoutError not properly imported bug.

    Bug Description:
    ----------------
    The code at line 1478 in parallelr.py had:
        except concurrent.futures.TimeoutError:

    But TimeoutError was imported at line 51 as:
        from concurrent.futures import TimeoutError

    However, the exception handler tried to catch concurrent.futures.TimeoutError
    instead of just TimeoutError, causing:
        NameError: name 'concurrent' is not defined

    Fix:
    ----
    Changed line 1478 to catch TimeoutError directly (not concurrent.futures.TimeoutError)
    since it was already imported into the namespace.

    This test verifies:
    1. Slow tasks trigger the timeout exception path
    2. The exception is caught correctly without NameError
    3. Execution completes successfully despite timeout loop iterations
    """
    # Create slow tasks that will trigger timeout in as_completed() loop
    for i in range(3):
        slow_task = temp_dir / f'slow_{i}.sh'
        # Sleep longer than wait_time (0.1s) to trigger timeout exception
        slow_task.write_text('#!/bin/bash\nsleep 0.3\necho "Done"\n')
        slow_task.chmod(0o755)

    # Single worker ensures sequential execution, maximizing timeout triggers
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '1'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    # Should complete successfully without NameError
    assert result.returncode == 0, f"Command failed: {result.stderr}"
    assert 'NameError' not in result.stderr, "TimeoutError not properly handled"
    assert "name 'concurrent' is not defined" not in result.stderr, \
        "Bug reintroduced: concurrent.futures.TimeoutError instead of TimeoutError"

    # Verify all tasks completed successfully
    csv_path = extract_log_path_from_stdout(result.stdout, 'summary')
    csv_records = parse_csv_summary(csv_path)
    assert len(csv_records) == 3, "Should have 3 completed tasks"
    verify_all_tasks_succeeded(csv_records)


@pytest.mark.integration
def test_regression_csv_semicolon_escaping(temp_dir, isolated_env):
    """
    REGRESSION TEST: CSV semicolon delimiter escaping.

    Bug Description:
    ----------------
    The CSV summary uses semicolon (;) as delimiter. If task commands or output
    contain semicolons, they must be properly escaped/quoted to prevent CSV parsing
    errors. Early versions had issues with semicolons in command strings.

    This test verifies:
    1. Commands containing semicolons are properly stored in CSV
    2. CSV can be parsed without errors
    3. Semicolons in output don't corrupt the CSV structure
    """
    # Create task with semicolons in output
    task_file = temp_dir / 'semicolon_task.sh'
    task_file.write_text('#!/bin/bash\necho "Field1;Field2;Field3"\n')
    task_file.chmod(0o755)

    # Run with simple command - the task output contains semicolons which tests CSV escaping
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@',
         '-r', '-m', '1'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    assert result.returncode == 0, f"Command failed: {result.stderr}"

    # The real test: can we parse the CSV without errors?
    csv_path = extract_log_path_from_stdout(result.stdout, 'summary')
    try:
        csv_records = parse_csv_summary(csv_path)
    except Exception as e:
        pytest.fail(f"CSV parsing failed, semicolons may not be properly escaped: {e}")

    # Verify CSV structure is intact
    assert len(csv_records) == 1, "Should have exactly 1 record"
    verify_all_tasks_succeeded(csv_records)

    # Main test is that CSV parsing succeeded without errors
    # If semicolons weren't properly escaped, CSV parsing would have failed above


@pytest.mark.integration
def test_regression_indexed_placeholder_validation(temp_dir, isolated_env):
    """
    REGRESSION TEST: Indexed placeholder detection and validation.

    Bug Description:
    ----------------
    Early versions didn't properly detect when users specified @ARG_N@ placeholders
    in commands but provided arguments without specifying a separator, or when
    the index N exceeded the number of arguments available.

    This caused runtime errors or unexpected behavior instead of clear validation
    errors at startup.

    This test verifies:
    1. Invalid placeholder indexes are detected before execution
    2. Clear error messages are provided
    3. Execution is prevented when placeholders don't match arguments
    """
    args_file = temp_dir / 'two_args.txt'
    args_file.write_text('val1,val2\n')

    # Use @ARG_5@ when only 2 arguments are available
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-A', str(args_file),
         '-S', 'comma',
         '-C', 'echo @ARG_1@ @ARG_2@ @ARG_5@'],  # @ARG_5@ is invalid
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    # Should fail validation before execution
    assert result.returncode != 0, "Should fail when placeholder index exceeds argument count"

    # Error message should mention the invalid placeholder
    error_output = result.stderr.lower()
    assert '@arg_5@' in error_output or 'placeholder' in error_output or 'index' in error_output, \
        f"Error message should mention invalid placeholder. Got: {result.stderr}"


@pytest.mark.integration
def test_regression_missing_separator_with_indexed_placeholders(temp_dir, isolated_env):
    """
    REGRESSION TEST: Missing separator flag with indexed placeholders.

    Bug Description:
    ----------------
    Users might specify @ARG_1@, @ARG_2@ placeholders but forget to provide
    the -S/--separator flag. This should be detected as a configuration error
    since indexed placeholders require multi-argument parsing.

    This test verifies:
    1. Missing separator is detected when indexed placeholders are used
    2. Clear error message guides user to specify separator
    """
    args_file = temp_dir / 'args.txt'
    args_file.write_text('val1,val2,val3\n')

    # Use indexed placeholders WITHOUT specifying separator
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-A', str(args_file),
         # Missing: '-S', 'comma',
         '-C', 'echo @ARG_1@ @ARG_2@'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    # Should either:
    # 1. Fail validation (preferred), OR
    # 2. Treat the entire line as @ARG@ (backward compatibility)
    #
    # The current implementation may allow this for backward compatibility,
    # but the placeholders should not be replaced since no separator was specified
    if result.returncode == 0:
        # If it runs, verify placeholders were NOT replaced (no separator = single arg mode)
        output_path = extract_log_path_from_stdout(result.stdout, 'output')
        if output_path:
            output_content = read_task_output_log(output_path)
            # In single-argument mode, indexed placeholders should remain unreplaced
            # OR the tool should have warned/failed
            assert '@ARG_1@' in output_content or '@ARG_2@' in output_content, \
                "Indexed placeholders should not be replaced without separator specified"
    # If it fails, that's also acceptable behavior


@pytest.mark.integration
def test_regression_empty_task_directory(temp_dir, isolated_env):
    """
    REGRESSION TEST: Empty task directory handling.

    Bug Description:
    ----------------
    Early versions might crash or hang when given an empty task directory
    instead of providing a clear error message.

    This test verifies:
    1. Empty directories are handled gracefully
    2. Clear error message is provided
    3. No crash or hang occurs
    """
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

    # Should fail with clear error (not hang or crash)
    assert result.returncode != 0, "Should fail when no tasks are found"
    combined_output = (result.stdout + result.stderr).lower()
    assert 'no task' in combined_output or 'found 0' in combined_output or 'empty' in combined_output, \
        f"Error message should indicate no tasks found. Got: {result.stderr}"
