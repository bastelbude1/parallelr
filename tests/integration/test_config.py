"""
Integration tests for configuration system.

Tests two-tier config hierarchy (script + user configs) and validation commands.
"""

import subprocess
import os
import re
from pathlib import Path
import pytest
import yaml

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import PARALLELR_BIN, PYTHON_FOR_PARALLELR

# Early abort if parallelr.py is missing
if not PARALLELR_BIN.exists():
    pytest.skip("bin/parallelr.py not found - integration tests skipped",
                allow_module_level=True)

# Load configuration limits from script config (avoids hardcoding)
def _load_script_limits():
    """Load max_allowed_* limits from script config to avoid hardcoding."""
    script_config_path = PARALLELR_BIN.parent.parent / 'cfg' / 'parallelr.yaml'
    try:
        with open(script_config_path, 'r') as f:
            script_config = yaml.safe_load(f)
        return (
            script_config['limits']['max_allowed_workers'],
            script_config['limits']['max_allowed_timeout'],
            script_config['limits']['max_allowed_output']
        )
    except (FileNotFoundError, KeyError, yaml.YAMLError) as e:
        pytest.skip(f"Could not load script config limits: {e}",
                    allow_module_level=True)

MAX_ALLOWED_WORKERS, MAX_ALLOWED_TIMEOUT_SECONDS, MAX_ALLOWED_OUTPUT_CAPTURE = _load_script_limits()

# Helper function to reduce subprocess boilerplate
def run_parallelr(args, isolated_env, timeout=10):
    """
    Run parallelr with common subprocess settings.

    Args:
        args: List of command-line arguments (e.g., ['--validate-config'])
        isolated_env: The isolated_env fixture providing test isolation
        timeout: Command timeout in seconds (default: 10)

    Returns:
        subprocess.CompletedProcess with stdout, stderr, and returncode
    """
    return subprocess.run(
        [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=isolated_env['env'],
        timeout=timeout
    )

@pytest.mark.integration
def test_validate_config_command_success(isolated_env):
    """
    Test --validate-config with valid script config.

    Verifies that the default script config passes validation.
    """
    result = run_parallelr(['--validate-config'], isolated_env)

    # Should succeed with validation message
    assert result.returncode == 0, f"Validation failed: {result.stderr}"
    assert 'configuration is valid' in result.stdout.lower(), \
        f"Expected 'Configuration is valid' message in output:\n{result.stdout}"

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

    result = run_parallelr(['--validate-config'], isolated_env)

    assert result.returncode == 0, f"Validation failed: {result.stderr}"
    assert 'configuration is valid' in result.stdout.lower(), \
        f"Expected 'Configuration is valid' message in output:\n{result.stdout}"

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

    result = run_parallelr(['--show-config'], isolated_env)

    # Should succeed but cap the value
    assert result.returncode == 0

    # Parse and verify the capped value
    output = result.stdout + result.stderr

    # Extract the actual workers value from "Workers: N (max allowed: M)" pattern
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

    result = run_parallelr(['--show-config'], isolated_env)

    # Should succeed but cap the value
    assert result.returncode == 0

    # Parse and verify the capped value
    output = result.stdout + result.stderr

    # Extract timeout value with unit handling (supports "s" for seconds, "ms" for milliseconds)
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

    result = run_parallelr(['--show-config'], isolated_env)

    # Should succeed but cap the value
    assert result.returncode == 0

    # Parse output to validate numeric values
    output = result.stdout + result.stderr

    # Extract all numeric values from output that might be related to max_output_capture
    all_numbers = [int(m) for m in re.findall(r'\b(\d+)\b', output)]

    # Should see warning that user value exceeded limit
    assert 'max_output_capture' in output.lower() and 'exceeds limit' in output.lower(), \
        f"Expected warning about max_output_capture exceeding limit in output:\n{output}"

    # Verify numeric values found
    assert len(all_numbers) > 0, f"No numeric values found in output:\n{output}"

    # Extract max_output_capture related values from warning pattern
    # Pattern: "max_output_capture (20000) exceeds limit (10000)"
    capture_pattern = re.search(
        r'max_output_capture.*?(\d+).*?(?:exceeds|limit).*?(\d+)',
        output,
        re.IGNORECASE | re.DOTALL
    )

    if capture_pattern:
        user_value = int(capture_pattern.group(1))
        limit_value = int(capture_pattern.group(2))

        # Verify user's excessive value is present in warning
        assert user_value == excessive_value, \
            f"Expected user value {excessive_value} in warning, found {user_value}"

        # Verify capped limit is present
        assert limit_value == MAX_ALLOWED_OUTPUT_CAPTURE, \
            f"Expected limit {MAX_ALLOWED_OUTPUT_CAPTURE} in warning, found {limit_value}"

    # Fallback: at minimum, verify excessive value appears (in warning context)
    # and doesn't appear outside warning context
    assert str(excessive_value) in output, \
        f"Original excessive value {excessive_value} should appear in warning"

    # Verify the capped limit value appears
    assert str(MAX_ALLOWED_OUTPUT_CAPTURE) in output, \
        f"Capped value {MAX_ALLOWED_OUTPUT_CAPTURE} should appear in output"

    # Note: Unlike max_workers and timeout_seconds, max_output_capture is NOT displayed
    # in the human-readable configuration summary (Configuration.__str__ in parallelr.py:518-527).
    # Therefore, we cannot parse and verify the effective runtime value from --show-config output.
    # We can only verify:
    # 1. The warning appears with correct values
    # 2. The warning mentions "using limit"
    #
    # TODO: Consider adding max_output_capture to Configuration.__str__ for consistency
    # with max_workers and timeout_seconds, which would allow stronger runtime verification.

    # Ensure warning mentions using the limit (confirms capping behavior)
    assert 'using limit' in output.lower(), \
        "Warning should mention 'using limit' to confirm value will be capped at runtime"

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

    result = run_parallelr(['--validate-config'], isolated_env)

    # Tool should either fail or explicitly warn about YAML issues
    output = (result.stdout + result.stderr).lower()

    if result.returncode == 0:
        # If it succeeds, it must explicitly warn about YAML and fallback
        assert 'yaml' in output and ('warning' in output or 'error' in output), \
            f"Expected explicit YAML warning/error in output:\n{output}"
    else:
        # If it fails, error message should mention YAML or parsing
        assert 'yaml' in output or 'parse' in output or 'invalid' in output, \
            f"Expected YAML-related error message:\n{output}"

@pytest.mark.integration
def test_show_config_command(isolated_env):
    """
    Test --show-config displays configuration values.

    Verifies the command shows config settings to stdout.
    """
    result = run_parallelr(['--show-config'], isolated_env)

    assert result.returncode == 0, f"Show config failed: {result.stderr}"
    output = result.stdout.lower()

    # Should display multiple key configuration values
    assert 'worker' in output, "Expected workers config in output"
    assert 'timeout' in output, "Expected timeout config in output"
    # At least one numeric value should be present
    assert re.search(r'\d+', output), "Expected numeric config values in output"

@pytest.mark.integration
def test_show_config_displays_workspace_mode(isolated_env):
    """
    Test --show-config displays workspace mode (shared vs isolated).

    Verifies workspace configuration is shown.
    """
    result = run_parallelr(['--show-config'], isolated_env)

    assert result.returncode == 0
    output = result.stdout.lower()

    # Should explicitly display workspace mode with a value
    assert 'workspace' in output, "Expected 'workspace' in config output"
    assert ('shared' in output or 'isolated' in output), \
        "Expected workspace mode value ('shared' or 'isolated') in output"

@pytest.mark.integration
def test_config_merge_precedence(temp_dir, isolated_env):
    """
    Test that user config overrides script defaults correctly.

    Creates a user config with max_workers=2, runs tasks WITHOUT CLI override,
    and verifies the user config value is applied by checking program output.
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

    # Create multiple tasks to make concurrency observable
    for i in range(4):
        task = temp_dir / f'task_{i}.sh'
        task.write_text('#!/bin/bash\necho "test"\n')
        task.chmod(0o755)

    # Run WITHOUT -m flag so user config takes effect
    result = run_parallelr([
        '-T', str(temp_dir),
        '-C', 'bash @TASK@',
        '-r'  # No -m flag: user config should apply max_workers=2
    ], isolated_env, timeout=30)

    # Should succeed
    assert result.returncode == 0, f"Execution failed: {result.stderr}"

    # Verify execution completed
    assert 'Executing' in result.stdout or 'completed' in result.stdout.lower(), \
        "Expected execution output not found"

    # Verify user config was loaded by checking the Workers value in output
    # The program should display "Workers: 2" from the user config
    output = result.stdout + result.stderr

    # Extract the Workers value from output (e.g., "Workers: 2")
    workers_match = re.search(r'Workers:\s+(\d+)', output, re.IGNORECASE)
    assert workers_match, f"Could not find 'Workers:' pattern in output:\n{output}"

    actual_workers = int(workers_match.group(1))

    # Verify the user config value (max_workers: 2) was applied
    assert actual_workers == 2, \
        f"Expected Workers=2 from user config, got {actual_workers}. Output:\n{output}"

@pytest.mark.integration
def test_config_missing_user_file_uses_defaults(isolated_env):
    """
    Test that missing user config falls back to script defaults gracefully.

    Does NOT create user config and verifies execution uses script default values.
    """
    # Explicitly do NOT create user config
    # User config directory doesn't exist, tool should use script defaults

    # Use --show-config to verify default values are loaded
    result = run_parallelr(['--show-config'], isolated_env)

    # Should succeed with script defaults
    assert result.returncode == 0, f"Show config failed: {result.stderr}"
    output = result.stdout + result.stderr

    # Verify that NO user config was loaded (using script defaults instead)
    # The output should explicitly state "User Config: ... (exists: False)"
    assert 'user config' in output.lower() and 'exists: false' in output.lower(), \
        f"Expected 'User Config: ... (exists: False)' message in output:\n{output}"

    # Verify config output contains key settings
    assert 'timeout' in output.lower(), "Expected timeout in default config"
    assert 'worker' in output.lower(), "Expected workers in default config"

    # Read script config to get the expected default value
    script_config_path = PARALLELR_BIN.parent.parent / 'cfg' / 'parallelr.yaml'
    try:
        with open(script_config_path, 'r') as f:
            script_config = yaml.safe_load(f)
    except FileNotFoundError:
        pytest.fail(f"Script config file not found at {script_config_path}")
    except yaml.YAMLError as e:
        pytest.fail(f"Failed to parse script config at {script_config_path}: {e}")

    try:
        expected_default_workers = script_config['limits']['max_workers']
    except (KeyError, TypeError) as e:
        pytest.fail(f"Script config missing 'limits.max_workers' key: {e}")

    # Verify Workers value matches the script default
    workers_match = re.search(r'Workers:\s+(\d+)', output, re.IGNORECASE)
    assert workers_match, f"Could not find 'Workers:' pattern in output:\n{output}"

    actual_workers = int(workers_match.group(1))
    assert actual_workers == expected_default_workers, \
        f"Expected Workers={expected_default_workers} from script config, got {actual_workers}"
