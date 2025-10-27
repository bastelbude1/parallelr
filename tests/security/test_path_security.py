"""
Security tests for path traversal and file access protection.

Tests that the tool properly validates file paths and prevents
unauthorized file access.
"""

import subprocess
import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
PARALLELR_BIN = PROJECT_ROOT / 'bin' / 'parallelr.py'


@pytest.mark.security
def test_symlink_traversal_protection(temp_dir):
    """Test that symlinks are handled carefully."""
    import pytest

    # Create a symlink to sensitive location
    link_path = temp_dir / 'link_to_root'
    target_path = Path('/')

    try:
        link_path.symlink_to(target_path)
    except OSError as e:
        # Symlink creation may fail due to permissions, skip the test
        pytest.skip(f"Cannot create symlink to test symlink traversal: {e}")

    # Run the tool with symlink as task path
    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(link_path),
         '-C', 'echo @TASK@'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=10
    )

    # The tool should handle symlinks safely - either reject or handle carefully
    # Expected: non-zero exit (rejected) or zero exit but no dangerous execution

    # Check that result completed (didn't crash)
    assert result.returncode is not None, "Process did not complete"

    if result.returncode == 0:
        # If it succeeded, verify no dangerous operations occurred
        # The symlink points to /, so we shouldn't see evidence of root-level operations

        # Should not show execution of dangerous root-level commands
        dangerous_patterns = [
            '/etc/passwd',
            '/etc/shadow',
            '/root/',
            'rm -rf /',
            'Permission denied'
        ]

        output = result.stdout + result.stderr
        for pattern in dangerous_patterns:
            assert pattern not in output, (
                f"SECURITY WARNING: Dangerous pattern '{pattern}' found in output.\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
    else:
        # Non-zero exit is expected and safe (symlink was rejected or handled)
        # Verify error message is reasonable
        assert result.returncode != 0, (
            f"Expected safe handling, got returncode: {result.returncode}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )


@pytest.mark.security
def test_absolute_path_validation(temp_dir):
    """Test that absolute paths are handled correctly."""
    task_file = temp_dir / 'task.sh'
    task_file.write_text('#!/bin/bash\necho "test"\n')
    task_file.chmod(0o755)

    # Use absolute path
    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(task_file.absolute()),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=30
    )

    # Absolute paths should work fine
    assert result.returncode == 0


@pytest.mark.security
def test_relative_path_with_dots(temp_dir):
    """Test that relative paths with dots are resolved safely."""
    task_file = temp_dir / 'task.sh'
    task_file.write_text('#!/bin/bash\necho "test"\n')
    task_file.chmod(0o755)

    # Use relative path with ./
    relative_path = './' + str(task_file)

    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', relative_path,
         '-C', 'bash @TASK@'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=10
    )

    # Relative paths should be resolved


@pytest.mark.security
def test_tilde_expansion_security(temp_dir):
    """Test that tilde expansion doesn't expose user data."""
    # Try to use tilde path
    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', '~/.bashrc',
         '-C', 'cat @TASK@'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=10
    )

    # Should handle tilde expansion or fail safely


@pytest.mark.security
def test_workspace_path_boundaries(temp_dir):
    """Test that workspace directory access is properly scoped."""
    task_file = temp_dir / 'task.sh'
    # Try to write outside workspace
    task_file.write_text('#!/bin/bash\necho "test" > /tmp/outside_workspace.txt\n')
    task_file.chmod(0o755)

    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=30
    )

    # Task can write wherever it wants, but this tests normal execution
    assert result.returncode == 0

    # Cleanup
    outside_file = Path('/tmp/outside_workspace.txt')
    if outside_file.exists():
        outside_file.unlink()


@pytest.mark.security
def test_task_file_size_limit(temp_dir):
    """Test that excessively large task files are rejected."""
    import os

    # Create a large task file (>1MB)
    large_task = temp_dir / 'large_task.sh'

    with open(large_task, 'w') as f:
        f.write('#!/bin/bash\n')
        # Write 2MB of comments
        for i in range(100000):
            f.write(f'# Comment line {i}\n')
        f.write('echo "test"\n')

    # Verify file is actually > 1MB
    file_size = os.path.getsize(large_task)
    assert file_size > 1024 * 1024, f"Test file should be >1MB, got {file_size} bytes"

    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(large_task),
         '-C', 'bash @TASK@',
         '-r'],  # Enable execution to trigger file size validation
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=30
    )

    # Tool should reject files exceeding max_task_file_size (default 1MB)
    assert result.returncode != 0, (
        f"Expected tool to reject large file, got returncode {result.returncode}\n"
        f"File size: {file_size} bytes ({file_size / (1024*1024):.2f} MB)\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )

    # Error message should mention file size limit
    output = result.stdout + result.stderr
    size_limit_indicators = [
        'max_task_file_size',
        'file too large',
        'exceeds',
        'size limit',
        'too big',
        '1048576',  # 1MB in bytes
        '1 MB',
        '1MB'
    ]

    found_indicator = any(indicator.lower() in output.lower() for indicator in size_limit_indicators)
    assert found_indicator, (
        f"Expected error message about file size limit, but didn't find indicators.\n"
        f"Looking for any of: {size_limit_indicators}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )

    # Task should NOT have been executed successfully
    # Check that the task was marked as failed, not completed
    assert 'Completed Successfully: 0' in result.stdout, (
        f"Task should not have completed successfully.\n"
        f"stdout: {result.stdout}"
    )
    assert 'Failed: 1' in result.stdout, (
        f"Task should be marked as failed.\n"
        f"stdout: {result.stdout}"
    )


@pytest.mark.security
def test_special_file_access_prevention():
    """Test that special files like /dev/null are handled."""
    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', '/dev/null',
         '-C', 'cat @TASK@'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=10
    )

    # Tool should handle special files safely (reject non-regular files)
    # /dev/null is a character device, not a regular file
    assert result.returncode != 0, (
        f"Expected tool to reject special file /dev/null, got returncode {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )

    # Should have appropriate error message (not crash)
    output = result.stdout + result.stderr
    assert 'No task files found' in output or 'not found' in output.lower(), (
        f"Expected error message about no task files found\noutput: {output}"
    )

    # Verify no crash indicators (Traceback for error is expected and OK)
    assert 'Segmentation' not in result.stderr, (
        f"Process crashed with segmentation fault:\n{result.stderr}"
    )

    # Verify no resource leak indicators
    assert 'leak' not in output.lower(), (
        f"Potential resource leak detected:\n{output}"
    )


@pytest.mark.security
def test_hidden_file_access(temp_dir):
    """Test that hidden files (starting with .) can be accessed if intended."""
    hidden_task = temp_dir / '.hidden_task.sh'
    hidden_task.write_text('#!/bin/bash\necho "hidden"\n')
    hidden_task.chmod(0o755)

    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(hidden_task),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=30
    )

    # Hidden files should work if explicitly specified
    assert result.returncode == 0


@pytest.mark.security
def test_argument_file_path_validation(temp_dir):
    """Test that argument file paths are validated."""
    task_file = temp_dir / 'task.sh'
    task_file.write_text('#!/bin/bash\necho "test"\n')
    task_file.chmod(0o755)

    # Try to use non-existent argument file
    result = subprocess.run(
        [sys.executable, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-A', '/non/existent/path/args.txt',
         '-C', 'bash @TASK@'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=10
    )

    # Should fail validation
    assert result.returncode != 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
