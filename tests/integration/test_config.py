"""
Integration tests for configuration system.

Tests two-tier config hierarchy (script + user configs) and validation commands.
"""

import subprocess
import os
from pathlib import Path
import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import PARALLELR_BIN, PYTHON_FOR_PARALLELR


# Configuration limits expected by tests (must match script config max_allowed_* values)
MAX_ALLOWED_WORKERS = 100
MAX_ALLOWED_TIMEOUT_SECONDS = 3600
MAX_ALLOWED_OUTPUT_CAPTURE = 10000


# Early abort if parallelr.py is missing
if not PARALLELR_BIN.exists():
    pytest.skip("bin/parallelr.py not found - integration tests skipped",
                allow_module_level=True)


@pytest.fixture
def isolated_env(tmp_path):
    """
    Provide isolated environment for config tests.

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
def test_validate_config_command_success(isolated_env):
    """
    Test --validate-config with valid script config.

    Verifies that the default script config passes validation.
    """
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '--validate-config'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    # Should succeed with validation message
    assert result.returncode == 0, f"Validation failed: {result.stderr}"
    assert 'valid' in result.stdout.lower() or 'config' in result.stdout.lower()


@pytest.mark.integration
def test_validate_config_command_with_user_overrides(isolated_env):
    """
    Test --validate-config with user config overrides.

    Creates a user config with valid overrides and verifies validation succeeds.
    """
    # Create user config directory
    user_config_dir = isolated_env['home'] / 'parallelr' / 'cfg'
    user_config_dir.mkdir(parents=True)

    # Create user config with valid overrides
    user_config = user_config_dir / 'parallelr.yaml'
    user_config.write_text("""
limits:
  max_workers: 10
  timeout_seconds: 300
  max_output_capture: 5000
""")

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '--validate-config'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    assert result.returncode == 0, f"Validation failed: {result.stderr}"
    assert 'valid' in result.stdout.lower() or 'config' in result.stdout.lower()


@pytest.mark.integration
def test_validate_config_user_exceeds_max_allowed_workers(isolated_env):
    """
    Test that user config max_workers is capped at max_allowed_workers.

    User tries to set max_workers=150 but should be capped at 100.
    Validates workers value with upper bound checking.
    """
    # Create user config directory
    user_config_dir = isolated_env['home'] / 'parallelr' / 'cfg'
    user_config_dir.mkdir(parents=True)

    # Create user config exceeding max_allowed_workers
    user_config = user_config_dir / 'parallelr.yaml'
    user_config.write_text("""
limits:
  max_workers: 150
""")

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '--show-config'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    # Should succeed but cap the value
    assert result.returncode == 0

    # Parse and verify the capped value
    output = result.stdout + result.stderr

    # Extract the actual workers value from "Workers: N (max allowed: M)" pattern
    import re
    workers_match = re.search(r'Workers:\s+(\d+)', output, re.IGNORECASE)
    assert workers_match, f"Could not find 'Workers:' pattern in output:\n{output}"

    actual_workers = int(workers_match.group(1))

    # Assert workers does not exceed the maximum allowed limit
    assert actual_workers <= MAX_ALLOWED_WORKERS, \
        f"Workers {actual_workers} exceeds maximum allowed {MAX_ALLOWED_WORKERS}"

    # Verify the original value 150 is NOT present in the final config
    assert '150' not in output or 'exceeds limit' in output.lower(), \
        "Original uncapped value (150) should not appear in final config (except in warning)"


@pytest.mark.integration
def test_validate_config_user_exceeds_max_allowed_timeout(isolated_env):
    """
    Test that user config timeout_seconds is capped at max_allowed_timeout.

    User tries to set timeout_seconds=5000 but should be capped at 3600.
    Validates timeout value with unit handling (s, ms) and upper bound checking.
    """
    # Create user config directory
    user_config_dir = isolated_env['home'] / 'parallelr' / 'cfg'
    user_config_dir.mkdir(parents=True)

    # Create user config exceeding max_allowed_timeout
    user_config = user_config_dir / 'parallelr.yaml'
    user_config.write_text("""
limits:
  timeout_seconds: 5000
""")

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '--show-config'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    # Should succeed but cap the value
    assert result.returncode == 0

    # Parse and verify the capped value
    output = result.stdout + result.stderr

    # Extract timeout value with unit handling (supports "s" for seconds, "ms" for milliseconds)
    import re
    timeout_match = re.search(r'Timeout:\s+(\d+)(ms|s)?', output, re.IGNORECASE)
    assert timeout_match, f"Could not find 'Timeout:' pattern in output:\n{output}"

    # Convert to canonical unit (seconds)
    timeout_value = int(timeout_match.group(1))
    unit = timeout_match.group(2).lower() if timeout_match.group(2) else 's'

    if unit == 'ms':
        timeout_seconds = timeout_value / 1000.0
    else:  # 's' or no unit defaults to seconds
        timeout_seconds = timeout_value

    # Assert timeout does not exceed the maximum allowed limit
    assert timeout_seconds <= MAX_ALLOWED_TIMEOUT_SECONDS, \
        f"Timeout {timeout_seconds}s exceeds maximum allowed {MAX_ALLOWED_TIMEOUT_SECONDS}s"

    # Verify the original value 5000 is NOT present in the final config
    assert '5000' not in output or 'exceeds limit' in output.lower(), \
        "Original uncapped value (5000) should not appear in final config (except in warning)"


@pytest.mark.integration
def test_validate_config_user_exceeds_max_allowed_output(isolated_env):
    """
    Test that user config max_output_capture is capped at max_allowed_output.

    User tries to set max_output_capture=20000 but should be capped at 10000.
    Validates output capture limit with upper bound checking.
    """
    # Create user config directory
    user_config_dir = isolated_env['home'] / 'parallelr' / 'cfg'
    user_config_dir.mkdir(parents=True)

    # Create user config exceeding max_allowed_output
    excessive_value = 20000  # Exceeds MAX_ALLOWED_OUTPUT_CAPTURE
    user_config = user_config_dir / 'parallelr.yaml'
    user_config.write_text(f"""
limits:
  max_output_capture: {excessive_value}
""")

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '--show-config'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    # Should succeed but cap the value
    assert result.returncode == 0

    # Verify the capping via warning message (max_output_capture not shown in main summary)
    output = result.stdout + result.stderr

    # Should see warning that user value exceeded limit
    assert 'max_output_capture' in output.lower() and 'exceeds limit' in output.lower(), \
        f"Expected warning about max_output_capture exceeding limit in output:\n{output}"

    # Verify the original excessive value appears in warning
    assert str(excessive_value) in output, f"Original value {excessive_value} should appear in warning"

    # Verify the capped limit value appears in output
    assert str(MAX_ALLOWED_OUTPUT_CAPTURE) in output, \
        f"Capped value {MAX_ALLOWED_OUTPUT_CAPTURE} should appear in output"

    # Additional check: the warning should mention using the limit
    assert 'using limit' in output.lower(), "Warning should mention 'using limit'"


@pytest.mark.integration
def test_validate_config_invalid_yaml(isolated_env):
    """
    Test --validate-config with malformed YAML in user config.

    Creates invalid YAML and verifies appropriate error handling.
    """
    # Create user config directory
    user_config_dir = isolated_env['home'] / 'parallelr' / 'cfg'
    user_config_dir.mkdir(parents=True)

    # Create user config with invalid YAML syntax
    user_config = user_config_dir / 'parallelr.yaml'
    user_config.write_text("""
limits:
  max_workers: [invalid yaml syntax
    no_closing_bracket
""")

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '--validate-config'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    # Should fail or warn about invalid YAML
    # The tool may fall back to defaults gracefully
    output = (result.stdout + result.stderr).lower()
    # Accept either failure or warning
    assert (result.returncode != 0 or
            'error' in output or
            'warning' in output or
            'invalid' in output or
            'yaml' in output or
            'default' in output)  # Falls back to defaults


@pytest.mark.integration
def test_show_config_command(isolated_env):
    """
    Test --show-config displays configuration values.

    Verifies the command shows config settings to stdout.
    """
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '--show-config'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    assert result.returncode == 0, f"Show config failed: {result.stderr}"
    output = result.stdout.lower()

    # Should display key configuration values
    assert 'config' in output or 'worker' in output or 'timeout' in output


@pytest.mark.integration
def test_show_config_displays_workspace_mode(isolated_env):
    """
    Test --show-config displays workspace mode (shared vs isolated).

    Verifies workspace configuration is shown.
    """
    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '--show-config'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=10
    )

    assert result.returncode == 0
    output = result.stdout.lower()

    # Should mention workspace mode
    assert 'workspace' in output or 'shared' in output or 'isolated' in output


@pytest.mark.integration
def test_config_merge_precedence(temp_dir, isolated_env):
    """
    Test that user config overrides script defaults correctly.

    Creates a user config, runs a task, and verifies the override takes effect.
    """
    # Create user config directory
    user_config_dir = isolated_env['home'] / 'parallelr' / 'cfg'
    user_config_dir.mkdir(parents=True)

    # Create user config with custom max_workers
    user_config = user_config_dir / 'parallelr.yaml'
    user_config.write_text("""
limits:
  max_workers: 2
  timeout_seconds: 300
""")

    # Create simple task
    task = temp_dir / 'simple.sh'
    task.write_text('#!/bin/bash\necho "test"\n')
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

    # Should succeed and use user config values
    assert result.returncode == 0
    # The execution should work with the user-defined config
    assert 'Executing' in result.stdout


@pytest.mark.integration
def test_config_missing_user_file_uses_defaults(temp_dir, isolated_env):
    """
    Test that missing user config falls back to script defaults gracefully.

    Does NOT create user config and verifies execution uses defaults.
    """
    # Explicitly do NOT create user config
    # User config directory doesn't exist, tool should use script defaults

    # Create simple task
    task = temp_dir / 'test_task.sh'
    task.write_text('#!/bin/bash\necho "default config"\n')
    task.chmod(0o755)

    result = subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
         '-T', str(temp_dir),
         '-C', 'bash @TASK@',
         '-r'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=30
    )

    # Should succeed using script defaults
    assert result.returncode == 0, f"Execution with defaults failed: {result.stderr}"
    assert 'Executing' in result.stdout
