"""
Integration tests for arguments mode execution.

Tests argument file processing with various delimiters and configurations.
"""

import subprocess
import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
PARALLELR_BIN = PROJECT_ROOT / 'bin' / 'parallelr.py'


@pytest.mark.integration
def test_arguments_mode_single_argument(sample_task_file, sample_arguments_file):
    """Test arguments mode with single argument per line."""
    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_file),
         '-A', str(sample_arguments_file),
         '-E', 'HOSTNAME',
         '-C', 'bash @TASK@'],
        capture_output=True,
        text=True,
        timeout=10
    )

    assert result.returncode == 0
    # Should create 3 tasks (3 lines in args file)
    assert 'Created 3 tasks' in result.stdout


@pytest.mark.integration
def test_arguments_mode_multi_args_comma(sample_task_file, sample_multi_args_file):
    """Test multi-argument mode with comma delimiter."""
    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_file),
         '-A', str(sample_multi_args_file),
         '-S', 'comma',
         '-E', 'HOSTNAME,PORT,ENV',
         '-C', 'bash @TASK@ @ARG_1@ @ARG_2@ @ARG_3@',
         '-r', '-m', '2'],
        capture_output=True,
        text=True,
        timeout=30
    )

    assert result.returncode == 0
    # Should create and execute 3 tasks
    assert 'Created 3 tasks' in result.stdout


@pytest.mark.integration
def test_arguments_mode_all_delimiters(temp_dir, sample_task_file):
    """Test all supported delimiters."""
    delimiters = {
        'comma': 'val1,val2,val3',
        'semicolon': 'val1;val2;val3',
        'pipe': 'val1|val2|val3',
        'colon': 'val1:val2:val3',
        'space': 'val1 val2 val3',
        'tab': 'val1\tval2\tval3'
    }

    for delim_name, line_content in delimiters.items():
        args_file = temp_dir / f'args_{delim_name}.txt'
        args_file.write_text(f'{line_content}\n')

        result = subprocess.run(
            [sys.executable, str(PARALLELR_BIN),
             '-T', str(sample_task_file),
             '-A', str(args_file),
             '-S', delim_name,
             '-C', 'bash @TASK@ @ARG_1@ @ARG_2@ @ARG_3@'],
            capture_output=True,
            text=True,
            timeout=10
        )

        assert result.returncode == 0, f"Failed for delimiter: {delim_name}"
        assert 'Created 1 tasks' in result.stdout or 'Created 1 task' in result.stdout


@pytest.mark.integration
def test_arguments_mode_indexed_placeholders(sample_task_file, temp_dir):
    """Test indexed placeholder replacement."""
    args_file = temp_dir / 'indexed_args.txt'
    args_file.write_text('host1,8080,prod\n')

    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_file),
         '-A', str(args_file),
         '-S', 'comma',
         '-C', 'bash -c "echo @ARG_1@ @ARG_2@ @ARG_3@"'],
        capture_output=True,
        text=True,
        timeout=10
    )

    assert result.returncode == 0
    # Dry run should show the command
    assert 'host1' in result.stdout
    assert '8080' in result.stdout
    assert 'prod' in result.stdout


@pytest.mark.integration
def test_arguments_mode_env_var_mapping(sample_task_file, sample_multi_args_file):
    """Test environment variable mapping to arguments."""
    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_file),
         '-A', str(sample_multi_args_file),
         '-S', 'comma',
         '-E', 'HOST,PORT,ENVIRONMENT',
         '-C', 'bash @TASK@'],
        capture_output=True,
        text=True,
        timeout=10
    )

    assert result.returncode == 0
    # Should show environment variable assignments in dry run
    assert 'HOST=' in result.stdout
    assert 'PORT=' in result.stdout
    assert 'ENVIRONMENT=' in result.stdout


@pytest.mark.integration
def test_arguments_mode_inconsistent_args_validation(sample_task_file, temp_dir):
    """Test validation of inconsistent argument counts."""
    args_file = temp_dir / 'inconsistent.txt'
    args_file.write_text('val1,val2,val3\nval1,val2\nval1,val2,val3\n')

    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_file),
         '-A', str(args_file),
         '-S', 'comma',
         '-C', 'bash @TASK@'],
        capture_output=True,
        text=True,
        timeout=10
    )

    # Should fail validation
    assert result.returncode != 0
    assert 'Inconsistent argument counts' in result.stderr


@pytest.mark.integration
def test_arguments_mode_invalid_placeholder_validation(sample_task_file, temp_dir):
    """Test validation of invalid placeholder indexes."""
    args_file = temp_dir / 'two_args.txt'
    args_file.write_text('val1,val2\n')

    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_file),
         '-A', str(args_file),
         '-S', 'comma',
         '-C', 'bash @TASK@ @ARG_1@ @ARG_2@ @ARG_5@'],  # Invalid: @ARG_5@
        capture_output=True,
        text=True,
        timeout=10
    )

    # Should fail validation
    assert result.returncode != 0
    assert '@ARG_5@' in result.stderr or 'placeholder' in result.stderr.lower()


@pytest.mark.integration
def test_arguments_mode_separator_without_args_file(sample_task_file):
    """Test that separator requires arguments file."""
    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_file),
         '-S', 'comma',
         '-C', 'bash @TASK@'],
        capture_output=True,
        text=True,
        timeout=10
    )

    # Should fail validation
    assert result.returncode != 0
    assert 'separator' in result.stderr.lower() and 'arguments' in result.stderr.lower()


@pytest.mark.integration
def test_arguments_mode_empty_env_var_validation(sample_task_file, sample_arguments_file):
    """Test validation of empty environment variable names."""
    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_file),
         '-A', str(sample_arguments_file),
         '-E', 'VAR1, ,VAR3',  # Empty entry
         '-C', 'bash @TASK@'],
        capture_output=True,
        text=True,
        timeout=10
    )

    # Should fail validation
    assert result.returncode != 0
    assert 'empty' in result.stderr.lower()


@pytest.mark.integration
def test_arguments_mode_more_env_vars_than_args(sample_task_file, sample_arguments_file):
    """Test error when more env vars than arguments."""
    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_file),
         '-A', str(sample_arguments_file),
         '-E', 'VAR1,VAR2,VAR3,VAR4',  # 4 vars, but only 1 arg per line
         '-C', 'bash @TASK@'],
        capture_output=True,
        text=True,
        timeout=10
    )

    # Should fail with error
    assert result.returncode != 0
    assert 'mismatch' in result.stderr.lower() or 'cannot proceed' in result.stderr.lower()


@pytest.mark.integration
def test_arguments_mode_fewer_env_vars_than_args(sample_task_file, sample_multi_args_file):
    """Test warning when fewer env vars than arguments."""
    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_file),
         '-A', str(sample_multi_args_file),
         '-S', 'comma',
         '-E', 'HOST,PORT',  # Only 2 vars, but 3 args per line
         '-C', 'bash @TASK@',
         '-r', '-m', '1'],
        capture_output=True,
        text=True,
        timeout=30
    )

    # Should warn but continue
    assert result.returncode == 0
    assert 'mismatch' in result.stdout.lower() or 'warning' in result.stdout.lower()


@pytest.mark.integration
def test_arguments_mode_backward_compatibility(sample_task_file, sample_arguments_file):
    """Test backward compatibility with single arguments (no separator)."""
    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(sample_task_file),
         '-A', str(sample_arguments_file),
         '-C', 'bash @TASK@ --arg @ARG@',  # Use old @ARG@ placeholder
         '-r'],
        capture_output=True,
        text=True,
        timeout=30
    )

    assert result.returncode == 0
    # Should work with @ARG@ placeholder
    assert 'Created 3 tasks' in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
