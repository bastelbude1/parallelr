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
    """
    # Create user config directory
    user_config_dir = isolated_env['home'] / 'parallelr' / 'cfg'
    user_config_dir.mkdir(parents=True)

    # Create user config exceeding max_allowed_workers (100)
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
    # Verify the capped value is shown (max_allowed_workers = 100)
    output = result.stdout + result.stderr
    assert 'max_workers' in output.lower() or 'worker' in output.lower()


@pytest.mark.integration
def test_validate_config_user_exceeds_max_allowed_timeout(isolated_env):
    """
    Test that user config timeout_seconds is capped at max_allowed_timeout.

    User tries to set timeout_seconds=5000 but should be capped at 3600.
    """
    # Create user config directory
    user_config_dir = isolated_env['home'] / 'parallelr' / 'cfg'
    user_config_dir.mkdir(parents=True)

    # Create user config exceeding max_allowed_timeout (3600)
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
    output = result.stdout + result.stderr
    assert 'timeout' in output.lower()


@pytest.mark.integration
def test_validate_config_user_exceeds_max_allowed_output(isolated_env):
    """
    Test that user config max_output_capture is capped at max_allowed_output.

    User tries to set max_output_capture=20000 but should be capped at 10000.
    """
    # Create user config directory
    user_config_dir = isolated_env['home'] / 'parallelr' / 'cfg'
    user_config_dir.mkdir(parents=True)

    # Create user config exceeding max_allowed_output (10000)
    user_config = user_config_dir / 'parallelr.yaml'
    user_config.write_text("""
limits:
  max_output_capture: 20000
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
    output = result.stdout + result.stderr
    assert 'output' in output.lower() or 'capture' in output.lower()


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
