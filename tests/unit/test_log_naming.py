"""
Unit tests for log file naming system.

Tests the simplified log naming format with date + unique ID.
"""

import os
import sys
import re
from pathlib import Path
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'bin'))

# Import after path is set
import parallelr
from parallelr import Configuration


@pytest.fixture
def temp_config_home(tmp_path, monkeypatch):
    """Create a temporary home directory for config tests."""
    temp_home = tmp_path / 'home'
    temp_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv('HOME', str(temp_home))

    # Create a minimal config file
    script_path = Path(__file__).parent.parent.parent / 'bin' / 'parallelr.py'
    config = Configuration.from_script(str(script_path))
    return config


@pytest.mark.unit
def test_generate_unique_id_length():
    """Test that generate_unique_id returns correct length."""
    # Test default length (6)
    uid = Configuration.generate_unique_id()
    assert len(uid) == 6, f"Expected 6 characters, got {len(uid)}: {uid}"

    # Test custom length
    uid_4 = Configuration.generate_unique_id(4)
    assert len(uid_4) == 4, f"Expected 4 characters, got {len(uid_4)}: {uid_4}"

    uid_8 = Configuration.generate_unique_id(8)
    assert len(uid_8) == 8, f"Expected 8 characters, got {len(uid_8)}: {uid_8}"


@pytest.mark.unit
def test_generate_unique_id_alphanumeric():
    """Test that generate_unique_id returns only alphanumeric characters."""
    # Test with alphabet from Configuration (no ambiguous chars)
    for _ in range(10):  # Test multiple times
        uid = Configuration.generate_unique_id()
        for char in uid:
            assert char in Configuration.UNIQUE_ID_ALPHABET, \
                f"Character '{char}' not in allowed alphabet"


@pytest.mark.unit
def test_generate_unique_id_is_unique():
    """Test that generate_unique_id generates different IDs."""
    # Generate multiple IDs and verify they're different
    ids = set()
    for _ in range(100):
        uid = Configuration.generate_unique_id()
        ids.add(uid)

    # Should have 100 unique IDs (collision extremely unlikely)
    assert len(ids) >= 99, f"Expected at least 99 unique IDs, got {len(ids)}"


@pytest.mark.unit
def test_get_custom_timestamp_format(temp_config_home):
    """Test that get_custom_timestamp returns correct format."""
    config = temp_config_home

    timestamp = config.get_custom_timestamp()

    # Should match format: DDmmmYY_uniqueid (e.g., 04Nov25_k8m2p5)
    pattern = r'^\d{2}[A-Z][a-z]{2}\d{2}_[a-z2-9]{6}$'
    assert re.match(pattern, timestamp), \
        f"Timestamp '{timestamp}' doesn't match expected format DDmmmYY_uniqueid"


@pytest.mark.unit
def test_get_custom_timestamp_date_part(temp_config_home):
    """Test that get_custom_timestamp includes correct date."""
    config = temp_config_home
    from datetime import datetime

    timestamp = config.get_custom_timestamp()

    # Extract date part (before underscore)
    date_part = timestamp.split('_')[0]

    # Should match current date in DDmmmYY format
    expected_date = datetime.now().strftime("%d%b%y")
    assert date_part == expected_date, \
        f"Date part '{date_part}' doesn't match expected '{expected_date}'"


@pytest.mark.unit
def test_get_custom_timestamp_unique_id_part(temp_config_home):
    """Test that get_custom_timestamp includes valid unique ID."""
    config = temp_config_home

    timestamp = config.get_custom_timestamp()

    # Extract unique ID part (after underscore)
    parts = timestamp.split('_')
    assert len(parts) == 2, f"Expected 2 parts separated by '_', got {len(parts)}"

    unique_id = parts[1]
    assert len(unique_id) == 6, f"Expected 6-char unique ID, got {len(unique_id)}: {unique_id}"

    # Should only contain allowed characters from Configuration.UNIQUE_ID_ALPHABET
    for char in unique_id:
        assert char in Configuration.UNIQUE_ID_ALPHABET, \
            f"Character '{char}' not in allowed alphabet"


@pytest.mark.unit
def test_timestamp_generates_different_values(temp_config_home):
    """Test that multiple calls generate different timestamps."""
    config = temp_config_home

    timestamps = set()
    for _ in range(10):
        ts = config.get_custom_timestamp()
        timestamps.add(ts)

    # Should have 10 different timestamps (unique IDs make them unique)
    assert len(timestamps) == 10, \
        f"Expected 10 unique timestamps, got {len(timestamps)}"


@pytest.mark.unit
def test_log_filename_format():
    """Test that log filenames follow the new format."""
    # Simulate log filename generation
    pid = 1314628
    timestamp = "04Nov25_k8m2p5"

    main_log = f"parallelr_{pid}_{timestamp}.log"
    summary = f"parallelr_{pid}_{timestamp}_summary.csv"
    output = f"parallelr_{pid}_{timestamp}_output.txt"

    # Verify format
    assert main_log == "parallelr_1314628_04Nov25_k8m2p5.log"
    assert summary == "parallelr_1314628_04Nov25_k8m2p5_summary.csv"
    assert output == "parallelr_1314628_04Nov25_k8m2p5_output.txt"


@pytest.mark.unit
def test_unique_id_no_ambiguous_characters():
    """Test that unique IDs don't contain ambiguous characters."""
    # Characters that are excluded: 0, O, 1, l, i, I
    excluded = set('0Ol1iI')

    for _ in range(50):
        uid = Configuration.generate_unique_id()
        for char in uid:
            assert char not in excluded, \
                f"Unique ID '{uid}' contains ambiguous character '{char}'"
