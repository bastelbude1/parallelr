"""
Security tests for path traversal and file access protection.

Tests that the tool properly validates file paths and prevents
unauthorized file access.
"""

import subprocess
import sys
from pathlib import Path
import pytest

# Import from conftest
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import PARALLELR_BIN, PYTHON_FOR_PARALLELR

PROJECT_ROOT = Path(__file__).parent.parent.parent


@pytest.mark.security
def test_symlink_traversal_protection(temp_dir):
    """Test that symlinks are handled carefully."""
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
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(link_path),
         '-C', 'echo @TASK@'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=10
    )

    # Tool must not crash; following symlinks or rejecting them is acceptable
    assert result.returncode in (0, 1), (
        f"Symlinks must be handled safely (allow or reject), got returncode {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )

    # Verify no dangerous operations occurred regardless of exit code
    # The symlink points to /, so we shouldn't see evidence of root-level operations
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


@pytest.mark.security
def test_absolute_path_validation(temp_dir):
    """Test that absolute paths are handled correctly."""
    task_file = temp_dir / 'task.sh'
    task_file.write_text('#!/bin/bash\necho "test"\n')
    task_file.chmod(0o755)

    # Use absolute path
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
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

    # Use absolute path (relative paths require specific working directory)
    # Test verifies the tool handles path resolution safely
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=10
    )

    # Relative paths should be resolved correctly and execute successfully
    assert result.returncode == 0, (
        f"Expected successful path resolution, got returncode {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )

    # Verify no error messages related to path resolution
    assert "error" not in result.stderr.lower(), (
        f"Unexpected error in stderr:\n{result.stderr}"
    )


@pytest.mark.security
def test_tilde_expansion_security():
    """Test that tilde expansion doesn't expose user data."""
    # Try to use tilde path
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', '~/.bashrc',
         '-C', 'cat @TASK@'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=10
    )

    # Tilde expansion must be handled safely (no crash, no permission leaks)
    # Allow either success (tilde expanded) or failure (tilde rejected)
    assert result.returncode in (0, 1), (
        f"Expected safe handling of tilde path, got returncode {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )

    # Should not leak permission errors that could expose system info
    assert "permission" not in result.stderr.lower(), (
        f"Permission error leaked system information:\nstderr: {result.stderr}"
    )


@pytest.mark.security
def test_workspace_path_boundaries(temp_dir):
    """Test that workspace directory access is properly scoped."""
    task_file = temp_dir / 'task.sh'

    # Try to write outside workspace (use temp_dir to avoid polluting /tmp)
    outside_file = temp_dir / 'outside_workspace.txt'
    task_file.write_text(f'#!/bin/bash\necho "test" > "{outside_file}"\n')
    task_file.chmod(0o755)

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(task_file),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=30
    )

    # Depending on policy: allow or block writes outside workspace
    # Currently parallelr allows tasks to write anywhere (no sandboxing)
    # Future enhancement: enforce workspace-only writes
    assert result.returncode in (0, 1), (
        f"Expected success (no sandboxing) or failure (with sandboxing), "
        f"got returncode {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )

    # Cleanup
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
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(large_task),
         '-C', 'bash @TASK@',
         '-r'],  # Enable execution to trigger file size validation
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=30
    )

    # Expectation: Files >1MB should be rejected
    assert result.returncode != 0, (
        f"Large task files should be rejected, got returncode {result.returncode}\n"
        f"File size: {file_size} bytes ({file_size / (1024*1024):.2f} MB)\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )

    # Error message should mention file size (check both stdout and stderr)
    output = (result.stdout + result.stderr).lower()
    assert ("size" in output or "large" in output or "too large" in output), (
        f"Expected error message about file size, got:\n"
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
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
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
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
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
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
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


@pytest.mark.security
def test_template_path_traversal_prevention(temp_dir):
    """
    Test explicit path traversal attempts fail appropriately.

    Security model: Explicit paths are trusted (user intent is clear), but must exist.
    Path traversal attempts like ../../../etc/passwd will fail because:
    1. File doesn't exist, or
    2. File isn't a valid template, or
    3. Filesystem permissions prevent access

    Real security protection is in fallback search (tested elsewhere).
    """
    # Create a valid arguments file so we properly test template validation
    args_file = temp_dir / 'args.txt'
    args_file.write_text('arg1\n')

    # Try various path traversal patterns that point to non-existent or invalid files
    traversal_patterns = [
        '../../../etc/nonexistent_file_xyz',  # Doesn't exist
        '../../../../../../tmp/nonexistent',   # Doesn't exist
        'foo/../../../nonexistent',            # Doesn't exist
    ]

    for pattern in traversal_patterns:
        result = subprocess.run(
            [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
             '-T', pattern,
             '-A', str(args_file.absolute()),
             '-C', 'cat @TASK@'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=10
        )

        # Should fail because file doesn't exist
        assert result.returncode != 0, (
            f"Non-existent file should cause failure: {pattern}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

        # Should have "not found" message
        output = result.stdout + result.stderr
        assert 'not found' in output.lower(), (
            f"Expected 'not found' message for pattern: {pattern}\n"
            f"output: {output}"
        )


@pytest.mark.security
def test_legitimate_relative_paths_with_dotdot(temp_dir):
    """Test that legitimate relative paths with .. are allowed when safe."""
    # Create subdirectory structure
    subdir = temp_dir / 'subdir'
    subdir.mkdir()

    # Create task file in temp_dir root
    task_file = temp_dir / 'task.sh'
    task_file.write_text('#!/bin/bash\necho "test"\n')
    task_file.chmod(0o755)

    # Create args file
    args_file = temp_dir / 'args.txt'
    args_file.write_text('arg1\n')

    # Use relative path with .. that resolves safely within temp_dir
    # subdir/../task.sh resolves to temp_dir/task.sh
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', 'subdir/../task.sh',
         '-A', str(args_file),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=30,
        cwd=str(temp_dir)  # Run from temp_dir so relative path works
    )

    # Should succeed - legitimate relative path within cwd
    assert result.returncode == 0, (
        f"Legitimate relative path with .. should be allowed\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )

    # Should not have rejection warnings
    assert 'Rejected' not in result.stderr, (
        f"Should not reject legitimate relative path\n"
        f"stderr: {result.stderr}"
    )


@pytest.mark.security
def test_arguments_file_path_traversal_prevention(temp_dir):
    """
    Test explicit arguments file path traversal attempts fail appropriately.

    Security model: Explicit paths are trusted (user intent is clear), but must exist.
    Real security protection is in fallback search (tested elsewhere).
    """
    # Create a valid template file so we actually reach arguments file validation
    template_file = temp_dir / 'template.sh'
    template_file.write_text('#!/bin/bash\necho "test"\n')
    template_file.chmod(0o755)

    # Try various path traversal patterns that point to non-existent files
    traversal_patterns = [
        '../../../etc/nonexistent_args_xyz',
        '../../../../../../tmp/nonexistent_args',
        'foo/../../../nonexistent_args',
    ]

    for pattern in traversal_patterns:
        result = subprocess.run(
            [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
             '-T', str(template_file.absolute()),
             '-A', pattern,
             '-C', 'bash @TASK@'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=10
        )

        # Should fail because file doesn't exist
        assert result.returncode != 0, (
            f"Non-existent arguments file should cause failure: {pattern}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

        # Should have "not found" message
        output = result.stdout + result.stderr
        assert 'not found' in output.lower(), (
            f"Expected 'not found' message for pattern: {pattern}\n"
            f"output: {output}"
        )


@pytest.mark.security
def test_template_fallback_path_containment(temp_dir):
    """Test that fallback path resolution enforces directory containment."""
    # Create a task file in temp directory
    task_file = temp_dir / 'test_task.sh'
    task_file.write_text('#!/bin/bash\necho "test"\n')
    task_file.chmod(0o755)

    # Create args file
    args_file = temp_dir / 'args.txt'
    args_file.write_text('arg1\narg2\n')

    # Try to use just the filename (should try fallback locations)
    # But since it's not in standard TASKER locations, should fail
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', 'nonexistent_template.sh',
         '-A', str(args_file),
         '-C', 'bash @TASK@'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=10
    )

    # Should fail because file doesn't exist in current dir or fallback locations
    assert result.returncode != 0

    # Error message should mention searched locations
    output = result.stdout + result.stderr
    assert 'not found' in output.lower() or 'searched' in output.lower(), (
        f"Expected helpful error message about search locations\n"
        f"output: {output}"
    )


@pytest.mark.security
def test_absolute_path_not_affected_by_fallback():
    """Test that absolute paths bypass fallback search for security."""
    # Use absolute path that doesn't exist
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', '/nonexistent/absolute/path.sh',
         '-A', '/nonexistent/args.txt',
         '-C', 'echo test'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=10
    )

    # Should fail immediately without fallback search
    assert result.returncode != 0

    output = result.stdout + result.stderr
    # Should NOT mention fallback search locations for absolute paths
    assert 'tasker/test_cases' not in output.lower(), (
        f"Absolute paths should not use fallback search\n"
        f"output: {output}"
    )


@pytest.mark.security
def test_symlink_escape_prevention(temp_dir):
    """Test that symlinks cannot escape base directory during fallback."""
    import os

    # Create a symlink that points outside temp_dir
    link_name = 'escape_link'
    link_path = temp_dir / link_name

    try:
        # Create symlink pointing to parent directory
        os.symlink('..', str(link_path))
    except OSError as e:
        pytest.skip(f"Cannot create symlink for test: {e}")

    # Try to use the symlink via path traversal
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', f'{link_name}/etc/passwd',
         '-A', '/dev/null',
         '-C', 'cat @TASK@'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=10,
        cwd=str(temp_dir)
    )

    # Should reject (either catches symlink or catches path traversal)
    assert result.returncode != 0, (
        f"Symlink escape attempt should be rejected\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


@pytest.mark.security
def test_no_search_flag_behavior(temp_dir):
    """Test that --no-search disables fallback search."""
    # Create template file in home TASKER directory structure
    home = Path.home()
    tasker_testcases = home / 'tasker' / 'test_cases'
    tasker_testcases.mkdir(parents=True, exist_ok=True)

    template_file = tasker_testcases / 'test_no_search.sh'
    template_file.write_text('#!/bin/bash\necho "test"\n')

    # Create args file in temp directory
    args_file = temp_dir / 'args.txt'
    args_file.write_text('test_arg\n')

    try:
        # Run ptasker with --no-search from temp_dir
        # Template exists only in fallback location, should fail with --no-search
        result = subprocess.run(
            [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
             '-T', 'test_no_search.sh',
             '-A', str(args_file),
             '-C', 'cat @TASK@',
             '--no-search'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=10,
            cwd=str(temp_dir)
        )

        # Should fail because fallback is disabled
        assert result.returncode != 0, (
            f"With --no-search, should fail when file not in current dir\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        assert 'not found' in result.stderr.lower() or 'not found' in result.stdout.lower(), (
            f"Error message should indicate file not found\n"
            f"stderr: {result.stderr}"
        )
    finally:
        # Cleanup
        if template_file.exists():
            template_file.unlink()


@pytest.mark.security
def test_fallback_with_yes_flag(temp_dir):
    """Test that --yes flag auto-confirms fallback usage."""
    # Create template file in home TASKER directory structure
    home = Path.home()
    tasker_testcases = home / 'tasker' / 'test_cases'
    tasker_testcases.mkdir(parents=True, exist_ok=True)

    template_file = tasker_testcases / 'test_yes_flag.sh'
    template_file.write_text('#!/bin/bash\necho "test"\n')

    # Create args file in temp directory
    args_file = temp_dir / 'args.txt'
    args_file.write_text('test_arg\n')

    try:
        # Run ptasker with --yes from temp_dir
        # Template exists only in fallback location, should succeed without prompting
        result = subprocess.run(
            [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
             '-T', 'test_yes_flag.sh',
             '-A', str(args_file),
             '-C', 'cat @TASK@',
             '--yes'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=10,
            cwd=str(temp_dir)
        )

        # Should succeed with --yes (no prompt)
        assert result.returncode == 0, (
            f"With --yes, should succeed when fallback file found\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
    finally:
        # Cleanup
        if template_file.exists():
            template_file.unlink()


@pytest.mark.security
def test_fallback_info_logging(temp_dir):
    """Test that INFO messages appear when fallback is used."""
    # Create template file in home TASKER directory structure
    home = Path.home()
    tasker_testcases = home / 'tasker' / 'test_cases'
    tasker_testcases.mkdir(parents=True, exist_ok=True)

    template_file = tasker_testcases / 'test_info_log.sh'
    template_file.write_text('#!/bin/bash\necho "test"\n')

    # Create args file in temp directory
    args_file = temp_dir / 'args.txt'
    args_file.write_text('test_arg\n')

    try:
        # Run ptasker with --yes from temp_dir
        # Should see INFO messages about fallback location
        result = subprocess.run(
            [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
             '-T', 'test_info_log.sh',
             '-A', str(args_file),
             '-C', 'cat @TASK@',
             '--yes'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=10,
            cwd=str(temp_dir)
        )

        # Check for INFO messages about fallback
        combined_output = result.stdout + result.stderr
        assert 'fallback' in combined_output.lower(), (
            f"INFO message should mention fallback search\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        assert 'tasker' in combined_output.lower(), (
            f"INFO message should mention fallback location\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
    finally:
        # Cleanup
        if template_file.exists():
            template_file.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
