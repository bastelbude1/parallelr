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

# Import parallelr module (path set up in conftest.py)
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


@pytest.mark.unit
@pytest.mark.skipif(not hasattr(os, "getuid") or os.getuid() == 0, reason="Test requires non-root user")
def test_cleanup_preserves_pids_owned_by_other_users(config_with_temp_home):
    """Test that cleanup doesn't remove PIDs of processes owned by other users (PermissionError).

    Uses PID 1 (init/systemd) which is owned by root. When run as non-root,
    os.kill(1, 0) raises PermissionError, which should be treated as "process exists".
    """
    config = config_with_temp_home
    pid_file = config.get_pidfile_path()
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    # PID 1 is always running (init/systemd) and owned by root
    # If we're not root, we'll get PermissionError when checking it
    root_pid = 1

    # Also add a stale PID for comparison
    stale_pid = 999999999

    with open(str(pid_file), 'w') as f:
        f.write(f"{root_pid}\n")
        f.write(f"{stale_pid}\n")

    # Run cleanup
    result = config.cleanup_stale_pids()

    # Should only clean the stale PID, not the root-owned process
    assert result == 1, "Should have cleaned only the stale PID, not root's process"

    # PID file should still exist
    assert pid_file.exists(), "PID file should not be removed (root process still tracked)"

    # Should contain only PID 1
    pids = []
    with open(str(pid_file), 'r') as f:
        for line in f:
            pid = line.strip()
            if pid.isdigit():
                pids.append(int(pid))

    assert len(pids) == 1, f"Expected 1 PID (root process), got {len(pids)}: {pids}"
    assert pids[0] == root_pid, f"Expected PID 1 (root), got {pids[0]}"
    assert stale_pid not in pids, "Stale PID should have been removed"


@pytest.mark.unit
@pytest.mark.skipif(not hasattr(os, "getuid") or os.getuid() == 0, reason="Test requires non-root user")
def test_get_running_processes_includes_other_users_pids(config_with_temp_home):
    """Test that get_running_processes() includes PIDs owned by other users.

    Uses PID 1 (init/systemd) which is owned by root. When run as non-root,
    os.kill(1, 0) raises PermissionError, but PID should still be returned.
    """
    config = config_with_temp_home
    pid_file = config.get_pidfile_path()
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    # PID 1 is always running (init/systemd) and owned by root
    root_pid = 1
    current_pid = os.getpid()
    stale_pid = 999999999

    with open(str(pid_file), 'w') as f:
        f.write(f"{root_pid}\n")
        f.write(f"{current_pid}\n")
        f.write(f"{stale_pid}\n")

    # Get running processes
    running = config.get_running_processes()

    # Should include both root's PID and our PID, but not the stale one
    assert root_pid in running, f"PID 1 (root process) should be included, got: {running}"
    assert current_pid in running, f"Current PID should be included, got: {running}"
    assert stale_pid not in running, f"Stale PID should not be included, got: {running}"
    assert len(running) == 2, f"Expected 2 running PIDs, got {len(running)}: {running}"


@pytest.mark.unit
def test_cleanup_handles_file_read_errors_gracefully(config_with_temp_home, monkeypatch):
    """Test that cleanup handles file read errors without crashing."""
    config = config_with_temp_home
    pid_file = config.get_pidfile_path()
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    # Create a valid PID file
    with open(str(pid_file), 'w') as f:
        f.write("12345\n")

    # Mock the file open to raise an exception
    original_open = open
    def mock_open_that_fails(*args, **kwargs):
        # Let the first open succeed (exists check), fail on actual read
        if 'r' in str(args) or 'r' in str(kwargs.get('mode', '')):
            raise IOError("Mock file read error")
        return original_open(*args, **kwargs)

    monkeypatch.setattr('builtins.open', mock_open_that_fails)

    # Should return 0 and log warning, not crash
    result = config.cleanup_stale_pids()
    assert result == 0, "Should return 0 when file read fails"


@pytest.mark.unit
def test_get_running_processes_handles_file_errors(config_with_temp_home, monkeypatch):
    """Test that get_running_processes handles file errors gracefully."""
    config = config_with_temp_home
    pid_file = config.get_pidfile_path()
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    # Create a PID file
    with open(str(pid_file), 'w') as f:
        f.write("12345\n")

    # Mock open to fail
    def mock_open_that_fails(*args, **kwargs):
        raise IOError("Mock file error")

    monkeypatch.setattr('builtins.open', mock_open_that_fails)

    # Should return empty list, not crash
    result = config.get_running_processes()
    assert result == [], "Should return empty list when file read fails"


@pytest.mark.unit
def test_cleanup_with_oserror_eperm_fallback(config_with_temp_home, monkeypatch):
    """Test OSError with errno.EPERM fallback path in cleanup_stale_pids."""
    import errno as errno_module

    config = config_with_temp_home
    pid_file = config.get_pidfile_path()
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    # Use a PID that will trigger os.kill
    test_pid = 999999
    with open(str(pid_file), 'w') as f:
        f.write(f"{test_pid}\n")

    # Mock os.kill to raise OSError with EPERM (not PermissionError)
    original_kill = os.kill
    def mock_kill_oserror_eperm(pid, sig):
        if pid == test_pid and sig == 0:
            # Raise generic OSError with EPERM errno (not PermissionError)
            err = OSError("Operation not permitted")
            err.errno = errno_module.EPERM
            raise err
        return original_kill(pid, sig)

    monkeypatch.setattr('os.kill', mock_kill_oserror_eperm)

    # Should treat as running (EPERM = exists)
    result = config.cleanup_stale_pids()

    # Should not clean any PIDs (EPERM means it exists)
    assert result == 0, "Should not clean PID with EPERM error"

    # PID should still be in file
    pids = []
    with open(str(pid_file), 'r') as f:
        for line in f:
            if line.strip().isdigit():
                pids.append(int(line.strip()))
    assert test_pid in pids, "PID with EPERM should be preserved"


@pytest.mark.unit
def test_get_running_with_oserror_eperm_fallback(config_with_temp_home, monkeypatch):
    """Test OSError with errno.EPERM fallback in get_running_processes."""
    import errno as errno_module

    config = config_with_temp_home
    pid_file = config.get_pidfile_path()
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    test_pid = 999999
    with open(str(pid_file), 'w') as f:
        f.write(f"{test_pid}\n")

    # Mock os.kill to raise OSError with EPERM
    def mock_kill_oserror_eperm(pid, sig):
        if pid == test_pid and sig == 0:
            err = OSError("Operation not permitted")
            err.errno = errno_module.EPERM
            raise err
        return os.kill(pid, sig)

    monkeypatch.setattr('os.kill', mock_kill_oserror_eperm)

    # Should include PID (EPERM = running)
    running = config.get_running_processes()
    assert test_pid in running, f"PID with EPERM should be included, got: {running}"


@pytest.mark.unit
def test_cleanup_with_oserror_non_eperm(config_with_temp_home, monkeypatch):
    """Test OSError with non-EPERM errno is treated as stale."""
    import errno as errno_module

    config = config_with_temp_home
    pid_file = config.get_pidfile_path()
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    test_pid = 999999
    with open(str(pid_file), 'w') as f:
        f.write(f"{test_pid}\n")

    # Mock os.kill to raise OSError with ESRCH
    def mock_kill_oserror_esrch(pid, sig):
        if pid == test_pid and sig == 0:
            err = OSError("No such process")
            err.errno = errno_module.ESRCH
            raise err
        return os.kill(pid, sig)

    monkeypatch.setattr('os.kill', mock_kill_oserror_esrch)

    # Should clean the PID (ESRCH = dead)
    result = config.cleanup_stale_pids()
    assert result == 1, "Should clean PID with ESRCH error"

    # File should be removed (no running PIDs)
    assert not pid_file.exists(), "PID file should be removed after cleaning last PID"
