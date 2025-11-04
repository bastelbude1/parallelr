"""
Unit tests for PID management functionality.

Tests the Configuration class methods related to PID tracking:
- cleanup_stale_pids()
- register_process()
- unregister_process()
- get_running_processes()
"""

import os
import sys
from pathlib import Path
import tempfile
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'bin'))

# Import after path is set
import parallelr
from parallelr import Configuration


@pytest.fixture
def temp_config_home(tmp_path):
    """Create a temporary home directory for config tests."""
    temp_home = tmp_path / 'home'
    temp_home.mkdir(parents=True, exist_ok=True)
    return temp_home


@pytest.fixture
def config_with_temp_home(temp_config_home, monkeypatch):
    """Create a Configuration instance with temporary home directory."""
    monkeypatch.setenv('HOME', str(temp_config_home))

    # Create a minimal config file
    script_path = Path(__file__).parent.parent.parent / 'bin' / 'parallelr.py'
    config = Configuration.from_script(str(script_path))
    return config


@pytest.mark.unit
def test_cleanup_stale_pids_empty_file(config_with_temp_home):
    """Test cleanup_stale_pids() with non-existent PID file."""
    config = config_with_temp_home

    # PID file doesn't exist yet
    result = config.cleanup_stale_pids()

    # Should return 0 (no PIDs cleaned)
    assert result == 0


@pytest.mark.unit
def test_cleanup_stale_pids_removes_dead_pids(config_with_temp_home):
    """Test that cleanup_stale_pids() removes non-existent PIDs."""
    config = config_with_temp_home
    pid_file = config.get_pidfile_path()
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    # Write fake stale PIDs that don't exist
    stale_pids = [999999998, 999999999]
    with open(str(pid_file), 'w') as f:
        for pid in stale_pids:
            f.write(f"{pid}\n")

    # Run cleanup
    result = config.cleanup_stale_pids()

    # Should report 2 PIDs cleaned
    assert result == 2

    # PID file should be removed (no running processes left)
    assert not pid_file.exists()


@pytest.mark.unit
def test_cleanup_stale_pids_preserves_running_pid(config_with_temp_home):
    """Test that cleanup_stale_pids() preserves PIDs of running processes."""
    config = config_with_temp_home
    pid_file = config.get_pidfile_path()
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    # Write both a running PID (this test process) and a stale PID
    current_pid = os.getpid()
    stale_pid = 999999999

    with open(str(pid_file), 'w') as f:
        f.write(f"{current_pid}\n")
        f.write(f"{stale_pid}\n")

    # Run cleanup
    result = config.cleanup_stale_pids()

    # Should report 1 stale PID cleaned
    assert result == 1

    # PID file should still exist
    assert pid_file.exists()

    # Should contain only the running PID
    pids = []
    with open(str(pid_file), 'r') as f:
        for line in f:
            pid = line.strip()
            if pid.isdigit():
                pids.append(int(pid))

    assert len(pids) == 1
    assert pids[0] == current_pid
    assert stale_pid not in pids


@pytest.mark.unit
def test_cleanup_stale_pids_multiple_dead_pids(config_with_temp_home):
    """Test cleanup of multiple stale PIDs at once."""
    config = config_with_temp_home
    pid_file = config.get_pidfile_path()
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    # Write many fake stale PIDs
    stale_pids = [999999991, 999999992, 999999993, 999999994, 999999995]
    with open(str(pid_file), 'w') as f:
        for pid in stale_pids:
            f.write(f"{pid}\n")

    # Run cleanup
    result = config.cleanup_stale_pids()

    # Should report 5 PIDs cleaned
    assert result == 5

    # PID file should be removed
    assert not pid_file.exists()


@pytest.mark.unit
def test_register_process_creates_pid_file(config_with_temp_home):
    """Test that register_process() creates PID file and adds PID."""
    config = config_with_temp_home
    pid_file = config.get_pidfile_path()

    test_pid = 12345
    config.register_process(test_pid)

    # PID file should exist
    assert pid_file.exists()

    # Should contain the registered PID
    pids = []
    with open(str(pid_file), 'r') as f:
        for line in f:
            pid = line.strip()
            if pid.isdigit():
                pids.append(int(pid))

    assert test_pid in pids


@pytest.mark.unit
def test_register_process_prevents_duplicates(config_with_temp_home):
    """Test that registering the same PID twice doesn't create duplicates."""
    config = config_with_temp_home
    pid_file = config.get_pidfile_path()

    test_pid = 12345

    # Register same PID twice
    config.register_process(test_pid)
    config.register_process(test_pid)

    # Read PIDs
    pids = []
    with open(str(pid_file), 'r') as f:
        for line in f:
            pid = line.strip()
            if pid.isdigit():
                pids.append(int(pid))

    # Should only appear once
    assert pids.count(test_pid) == 1


@pytest.mark.unit
def test_unregister_process_removes_pid(config_with_temp_home):
    """Test that unregister_process() removes PID from file."""
    config = config_with_temp_home
    pid_file = config.get_pidfile_path()

    test_pid = 12345

    # Register and then unregister
    config.register_process(test_pid)
    config.unregister_process(test_pid)

    # PID file should be removed (no PIDs left)
    assert not pid_file.exists()


@pytest.mark.unit
def test_unregister_process_preserves_other_pids(config_with_temp_home):
    """Test that unregister_process() only removes the specified PID."""
    config = config_with_temp_home
    pid_file = config.get_pidfile_path()

    pid1 = 12345
    pid2 = 67890

    # Register two PIDs
    config.register_process(pid1)
    config.register_process(pid2)

    # Unregister only one
    config.unregister_process(pid1)

    # PID file should still exist
    assert pid_file.exists()

    # Should contain only pid2
    pids = []
    with open(str(pid_file), 'r') as f:
        for line in f:
            pid = line.strip()
            if pid.isdigit():
                pids.append(int(pid))

    assert len(pids) == 1
    assert pids[0] == pid2
    assert pid1 not in pids


@pytest.mark.unit
def test_get_running_processes_filters_dead_pids(config_with_temp_home):
    """Test that get_running_processes() only returns actually running PIDs."""
    config = config_with_temp_home
    pid_file = config.get_pidfile_path()
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    # Write both a running PID (this test) and stale PIDs
    current_pid = os.getpid()
    stale_pids = [999999998, 999999999]

    with open(str(pid_file), 'w') as f:
        f.write(f"{current_pid}\n")
        for pid in stale_pids:
            f.write(f"{pid}\n")

    # Get running processes
    running = config.get_running_processes()

    # Should only return the current PID
    assert len(running) == 1
    assert running[0] == current_pid

    # Stale PIDs should be filtered out
    for pid in stale_pids:
        assert pid not in running


@pytest.mark.unit
def test_get_running_processes_empty_file(config_with_temp_home):
    """Test get_running_processes() with non-existent PID file."""
    config = config_with_temp_home

    # PID file doesn't exist
    running = config.get_running_processes()

    # Should return empty list
    assert running == []


@pytest.mark.unit
def test_cleanup_stale_pids_handles_malformed_file(config_with_temp_home):
    """Test that cleanup handles PID file with invalid entries gracefully."""
    config = config_with_temp_home
    pid_file = config.get_pidfile_path()
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    # Write file with valid and invalid entries
    with open(str(pid_file), 'w') as f:
        f.write("999999999\n")  # Valid stale PID
        f.write("not_a_pid\n")  # Invalid
        f.write("\n")            # Empty line
        f.write("   \n")         # Whitespace
        f.write("12345abc\n")    # Invalid

    # Should not crash
    result = config.cleanup_stale_pids()

    # Should clean the one valid stale PID
    assert result == 1

    # File should be removed (no valid running PIDs)
    assert not pid_file.exists()


@pytest.mark.unit
def test_pid_file_sorted_after_operations(config_with_temp_home):
    """Test that PID file entries are kept sorted."""
    config = config_with_temp_home
    pid_file = config.get_pidfile_path()

    # Register PIDs in non-sorted order
    pids_to_register = [99999, 11111, 55555, 33333]
    for pid in pids_to_register:
        config.register_process(pid)

    # Read PIDs back
    pids_in_file = []
    with open(str(pid_file), 'r') as f:
        for line in f:
            pid = line.strip()
            if pid.isdigit():
                pids_in_file.append(int(pid))

    # Should be sorted
    assert pids_in_file == sorted(pids_in_file)
    assert pids_in_file == sorted(pids_to_register)
