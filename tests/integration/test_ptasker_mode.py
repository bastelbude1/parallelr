"""
Integration tests for ptasker mode behavior.

Tests the ptasker symlink functionality and validation requirements.

Note: Tests that create symlinks require admin rights or developer mode on Windows.
      Set ENABLE_SYMLINKS=1 environment variable to run these tests on Windows.
"""

import os
import subprocess
import sys
from pathlib import Path
import pytest

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Use same Python version for subprocess as current process
PYTHON_FOR_PARALLELR = sys.executable
PARALLELR_BIN = Path(__file__).parent.parent.parent / 'bin' / 'parallelr.py'


@pytest.mark.integration
@pytest.mark.skipif(
    os.name == 'nt' and not os.getenv('ENABLE_SYMLINKS'),
    reason="Requires admin rights or developer mode on Windows. Set ENABLE_SYMLINKS=1 to run."
)
def test_ptasker_requires_template_with_arguments(tmp_path):
    """
    Test that ptasker mode requires -T even when using -A.

    Note: Requires symlink support (admin/developer mode on Windows).
    """
    # Create a ptasker symlink
    ptasker_link = tmp_path / "ptasker"
    ptasker_link.symlink_to(PARALLELR_BIN)

    # Create a dummy arguments file
    args_file = tmp_path / "args.txt"
    args_file.write_text("arg1\narg2\n")

    # Try to run ptasker with -A but without -T (should fail)
    result = subprocess.run(  # noqa: S603  # Controlled test execution of project binary
        [PYTHON_FOR_PARALLELR, str(ptasker_link),
         '-A', str(args_file),
         '-p', 'test_project'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=10
    )

    # Should exit with error
    assert result.returncode != 0, "ptasker should fail without -T"

    # Check error message content
    combined_output = result.stdout + result.stderr
    assert "ptasker mode requires --TasksDir (-T)" in combined_output, \
        "Error message should explain -T requirement"
    assert "template file for tasker" in combined_output, \
        "Error message should mention template file"


@pytest.mark.integration
@pytest.mark.skipif(
    os.name == 'nt' and not os.getenv('ENABLE_SYMLINKS'),
    reason="Requires admin rights or developer mode on Windows. Set ENABLE_SYMLINKS=1 to run."
)
def test_ptasker_works_with_template(tmp_path):
    """
    Test that ptasker mode works when -T is provided.

    Note: Requires symlink support (admin/developer mode on Windows).
    """
    # Create a ptasker symlink
    ptasker_link = tmp_path / "ptasker"
    ptasker_link.symlink_to(PARALLELR_BIN)

    # Create a template file
    template_file = tmp_path / "template.sh"
    template_file.write_text("#!/bin/bash\necho 'test'\n")
    template_file.chmod(0o755)

    # Create arguments file
    args_file = tmp_path / "args.txt"
    args_file.write_text("arg1\n")

    # Run ptasker with both -T and -A (dry run)
    result = subprocess.run(  # noqa: S603  # Controlled test execution of project binary
        [PYTHON_FOR_PARALLELR, str(ptasker_link),
         '-T', str(template_file),
         '-A', str(args_file),
         '-p', 'test_project'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=10
    )

    # Should succeed in dry run mode
    assert result.returncode == 0, f"ptasker should work with -T. Output: {result.stdout}\n{result.stderr}"

    # Check that command was auto-generated
    combined_output = result.stdout + result.stderr
    assert "tasker @TASK@" in combined_output, \
        "Should auto-generate tasker command"
    assert "test_project" in combined_output, \
        "Should use provided project name"


@pytest.mark.integration
def test_regular_parallelr_allows_arguments_without_template(tmp_path):
    """Test that regular parallelr (not ptasker) still allows -A without -T."""
    # Create arguments file
    args_file = tmp_path / "args.txt"
    args_file.write_text("test_arg\n")

    # Run parallelr directly with -A but no -T (dry run with direct command)
    result = subprocess.run(  # noqa: S603  # Controlled test execution of project binary
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-C', 'echo @ARG@',
         '-A', str(args_file)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=10
    )

    # Should start execution (may fail on args file not found, but shouldn't reject for missing -T)
    combined_output = result.stdout + result.stderr
    assert "ptasker mode requires" not in combined_output, \
        "Regular parallelr should not show ptasker validation error"
    assert "Starting parallel execution" in combined_output or \
           "Command template: echo @ARG@" in combined_output, \
        "Regular parallelr should accept -A without -T"


@pytest.mark.integration
@pytest.mark.skipif(
    os.name == 'nt' and not os.getenv('ENABLE_SYMLINKS'),
    reason="Requires admin rights or developer mode on Windows. Set ENABLE_SYMLINKS=1 to run."
)
def test_ptasker_help_shows_required_flag(tmp_path):
    """
    Test that ptasker help text shows -T as required.

    Note: Requires symlink support (admin/developer mode on Windows).
    """
    # Create a ptasker symlink
    ptasker_link = tmp_path / "ptasker"
    ptasker_link.symlink_to(PARALLELR_BIN)

    # Get help text
    result = subprocess.run(  # noqa: S603  # Controlled test execution of project binary
        [PYTHON_FOR_PARALLELR, str(ptasker_link), '-h'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=10
    )

    # Check help text mentions -T is required
    assert "[REQUIRED in ptasker mode]" in result.stdout, \
        "Help text should indicate -T is required in ptasker mode"
    # Help text may wrap across lines, so check for key components
    assert "Template file path" in result.stdout and "TASKER execution" in result.stdout, \
        "Help text should explain -T purpose for ptasker"


@pytest.mark.integration
def test_regular_parallelr_help_shows_optional_flag():
    """Test that regular parallelr help text shows -T as optional with -A."""
    # Get help text from regular parallelr
    result = subprocess.run(  # noqa: S603  # Controlled test execution of project binary
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN), '-h'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=10
    )

    # Check help text mentions -T is optional with -A
    assert "[Optional with -A]" in result.stdout, \
        "Help text should indicate -T is optional with -A in regular parallelr"
    assert "Omit -T with -A to execute commands directly" in result.stdout, \
        "Help text should explain -T can be omitted in arguments mode"
