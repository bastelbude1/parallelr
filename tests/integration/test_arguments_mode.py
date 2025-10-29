"""
Integration tests for arguments mode execution.

Tests argument file processing with various delimiters and configurations.
"""

import subprocess
import os
import shutil
from pathlib import Path
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import PARALLELR_BIN, PYTHON_FOR_PARALLELR

# Skip all tests if bash is not available (POSIX dependency)
pytestmark = pytest.mark.skipif(shutil.which("bash") is None,
                                reason="Requires bash (POSIX)")


@pytest.fixture
def isolated_env(tmp_path):
    """
    Provide isolated environment for argument tests.

    Creates a subprocess-only environment without mutating global os.environ.
    Safe for parallel test execution.
    """
    temp_home = tmp_path / 'home'
    temp_home.mkdir()

    # Create isolated environment copy for subprocess use only
    # No global os.environ mutation - safe for parallel tests
    env_copy = {**os.environ, 'HOME': str(temp_home)}

    yield {
        'home': temp_home,
        'env': env_copy
    }

    # Cleanup is automatic via tmp_path fixture


@pytest.mark.integration
def test_arguments_mode_single_argument(sample_task_file, sample_arguments_file, isolated_env):
    """Test arguments mode with single argument per line."""
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_file),
         '-A', str(sample_arguments_file),
         '-E', 'HOSTNAME',
         '-C', 'bash @TASK@'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    assert result.returncode == 0
    # Should create 3 tasks (3 lines in args file)
    assert 'Created 3 tasks' in result.stdout


@pytest.mark.integration
def test_arguments_mode_multi_args_comma(sample_task_file, sample_multi_args_file, isolated_env):
    """Test multi-argument mode with comma delimiter."""
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_file),
         '-A', str(sample_multi_args_file),
         '-S', 'comma',
         '-E', 'HOSTNAME,PORT,ENV',
         '-C', 'bash @TASK@ @ARG_1@ @ARG_2@ @ARG_3@',
         '-r', '-m', '2'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    assert result.returncode == 0
    # Should create and execute 3 tasks
    assert 'Created 3 tasks' in result.stdout


@pytest.mark.integration
@pytest.mark.parametrize("delim_name,line_content", [
    ("comma", "val1,val2,val3"),
    ("semicolon", "val1;val2;val3"),
    ("pipe", "val1|val2|val3"),
    ("colon", "val1:val2:val3"),
    ("space", "val1 val2 val3"),
    ("tab", "val1\tval2\tval3"),
])
def test_arguments_mode_all_delimiters(temp_dir, sample_task_file, isolated_env, delim_name, line_content):
    """Test all supported delimiters."""
    args_file = temp_dir / f'args_{delim_name}.txt'
    args_file.write_text(f'{line_content}\n')

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_file),
         '-A', str(args_file),
         '-S', delim_name,
         '-C', 'bash @TASK@ @ARG_1@ @ARG_2@ @ARG_3@'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    assert result.returncode == 0, f"Failed for delimiter: {delim_name}"
    assert 'Created 1 tasks' in result.stdout or 'Created 1 task' in result.stdout


@pytest.mark.integration
def test_arguments_mode_indexed_placeholders(sample_task_file, temp_dir, isolated_env):
    """Test indexed placeholder replacement."""
    args_file = temp_dir / 'indexed_args.txt'
    args_file.write_text('host1,8080,prod\n')

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_file),
         '-A', str(args_file),
         '-S', 'comma',
         '-C', 'bash -c "echo @ARG_1@ @ARG_2@ @ARG_3@"'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    assert result.returncode == 0
    # Dry run should show the command
    assert 'host1' in result.stdout
    assert '8080' in result.stdout
    assert 'prod' in result.stdout


@pytest.mark.integration
def test_arguments_mode_env_var_mapping(sample_task_file, sample_multi_args_file, isolated_env):
    """Test environment variable mapping to arguments."""
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_file),
         '-A', str(sample_multi_args_file),
         '-S', 'comma',
         '-E', 'HOST,PORT,ENVIRONMENT',
         '-C', 'bash @TASK@'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    assert result.returncode == 0
    # Should show environment variable assignments in dry run
    assert 'HOST=' in result.stdout
    assert 'PORT=' in result.stdout
    assert 'ENVIRONMENT=' in result.stdout


@pytest.mark.integration
def test_arguments_mode_inconsistent_args_validation(sample_task_file, temp_dir, isolated_env):
    """Test validation of inconsistent argument counts."""
    args_file = temp_dir / 'inconsistent.txt'
    args_file.write_text('val1,val2,val3\nval1,val2\nval1,val2,val3\n')

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_file),
         '-A', str(args_file),
         '-S', 'comma',
         '-C', 'bash @TASK@'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    # Should fail validation
    assert result.returncode != 0
    assert 'Inconsistent argument counts' in result.stderr


@pytest.mark.integration
def test_arguments_mode_invalid_placeholder_validation(sample_task_file, temp_dir, isolated_env):
    """Test validation of invalid placeholder indexes."""
    args_file = temp_dir / 'two_args.txt'
    args_file.write_text('val1,val2\n')

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_file),
         '-A', str(args_file),
         '-S', 'comma',
         '-C', 'bash @TASK@ @ARG_1@ @ARG_2@ @ARG_5@'],  # Invalid: @ARG_5@
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    # Should fail validation
    assert result.returncode != 0
    assert '@ARG_5@' in result.stderr or 'placeholder' in result.stderr.lower()


@pytest.mark.integration
def test_arguments_mode_separator_without_args_file(sample_task_file, isolated_env):
    """Test that separator requires arguments file."""
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_file),
         '-S', 'comma',
         '-C', 'bash @TASK@'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    # Should fail validation
    assert result.returncode != 0
    assert 'separator' in result.stderr.lower() and 'arguments' in result.stderr.lower()


@pytest.mark.integration
def test_arguments_mode_empty_env_var_validation(sample_task_file, sample_arguments_file, isolated_env):
    """Test validation of empty environment variable names."""
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_file),
         '-A', str(sample_arguments_file),
         '-E', 'VAR1, ,VAR3',  # Empty entry
         '-C', 'bash @TASK@'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    # Should fail validation
    assert result.returncode != 0
    assert 'empty' in result.stderr.lower()


@pytest.mark.integration
def test_arguments_mode_more_env_vars_than_args(sample_task_file, sample_arguments_file, isolated_env):
    """Test error when more env vars than arguments."""
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_file),
         '-A', str(sample_arguments_file),
         '-E', 'VAR1,VAR2,VAR3,VAR4',  # 4 vars, but only 1 arg per line
         '-C', 'bash @TASK@'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    # Should fail with error
    assert result.returncode != 0
    assert 'mismatch' in result.stderr.lower() or 'cannot proceed' in result.stderr.lower()


@pytest.mark.integration
def test_arguments_mode_fewer_env_vars_than_args(sample_task_file, sample_multi_args_file, isolated_env):
    """Test warning when fewer env vars than arguments."""
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_file),
         '-A', str(sample_multi_args_file),
         '-S', 'comma',
         '-E', 'HOST,PORT',  # Only 2 vars, but 3 args per line
         '-C', 'bash @TASK@',
         '-r', '-m', '1'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    # Should warn but continue
    assert result.returncode == 0
    assert 'mismatch' in result.stdout.lower() or 'warning' in result.stdout.lower()


@pytest.mark.integration
def test_arguments_mode_backward_compatibility(sample_task_file, sample_arguments_file, isolated_env):
    """Test backward compatibility with single arguments (no separator)."""
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_file),
         '-A', str(sample_arguments_file),
         '-C', 'bash @TASK@ --arg @ARG@',  # Use old @ARG@ placeholder
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    assert result.returncode == 0
    # Should work with @ARG@ placeholder
    assert 'Created 3 tasks' in result.stdout


@pytest.mark.integration
def test_arguments_mode_no_template_single_arg(sample_arguments_file, isolated_env):
    """Test arguments-only mode without template file (single argument)."""
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-A', str(sample_arguments_file),
         '-C', 'echo "Testing @ARG@"',
         '-r', '-m', '2'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    assert result.returncode == 0
    # Should create 3 tasks from 3 lines in args file
    assert 'Created 3 tasks' in result.stdout
    # Should execute successfully
    assert 'completed successfully' in result.stdout.lower() or 'success' in result.stdout.lower()


@pytest.mark.integration
def test_arguments_mode_no_template_multi_args(sample_multi_args_file, isolated_env):
    """Test arguments-only mode without template file (multiple arguments)."""
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-A', str(sample_multi_args_file),
         '-S', 'comma',
         '-C', 'echo "Server: @ARG_1@, Port: @ARG_2@, Env: @ARG_3@"',
         '-r', '-m', '2'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    assert result.returncode == 0
    # Should create 3 tasks from 3 lines in multi-args file
    assert 'Created 3 tasks' in result.stdout
    # Should execute successfully
    assert 'completed successfully' in result.stdout.lower() or 'success' in result.stdout.lower()


@pytest.mark.integration
def test_arguments_mode_no_template_env_var(sample_multi_args_file, isolated_env):
    """Test arguments-only mode with environment variables (no template)."""
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-A', str(sample_multi_args_file),
         '-S', 'comma',
         '-E', 'HOSTNAME,PORT,ENVIRONMENT',
         '-C', 'echo "Host: $HOSTNAME, Port: $PORT, Env: $ENVIRONMENT"',
         '-r', '-m', '2'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    assert result.returncode == 0
    # Should create and execute 3 tasks with environment variables
    assert 'Created 3 tasks' in result.stdout

    # Extract output log file path from stdout
    import re
    import os
    import time
    output_match = re.search(r'- Output: (.+\.txt)', result.stdout)
    assert output_match, "Could not find output log file path in stdout"
    output_file = output_match.group(1)

    # Wait for output log file to be written (with timeout to avoid hanging)
    max_wait = 2.0  # seconds
    wait_interval = 0.1  # seconds
    elapsed = 0.0
    while not os.path.exists(output_file) and elapsed < max_wait:
        time.sleep(wait_interval)
        elapsed += wait_interval

    assert os.path.exists(output_file), f"Output log file was not created: {output_file}"

    # Read the output log file to verify environment variables were expanded
    with open(output_file, 'r') as f:
        output_content = f.read()

    # Verify environment variables were actually injected by checking the echo output
    # Each task should output the environment variables from its CSV line
    assert 'Host: server1, Port: 8080, Env: prod' in output_content
    assert 'Host: server2, Port: 8081, Env: dev' in output_content
    assert 'Host: server3, Port: 8082, Env: staging' in output_content


@pytest.mark.integration
def test_arguments_mode_template_must_be_file(sample_arguments_file, sample_task_dir, isolated_env):
    """Test that -T with -A must be a file, not a directory."""
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(sample_task_dir),  # Directory, not file
         '-A', str(sample_arguments_file),
         '-C', 'bash @TASK@ @ARG@'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    # Should fail validation
    assert result.returncode != 0
    # Error message should mention template file requirement
    assert 'template' in result.stderr.lower() and ('file' in result.stderr.lower() or 'directory' in result.stderr.lower())


@pytest.mark.integration
def test_arguments_mode_template_optional(sample_arguments_file, isolated_env):
    """Test that template is truly optional with -A."""
    # Test without -T - should work
    result_no_template = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-A', str(sample_arguments_file),
         '-C', 'echo @ARG@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    assert result_no_template.returncode == 0
    assert 'Created 3 tasks' in result_no_template.stdout
