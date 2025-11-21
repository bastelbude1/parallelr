import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add bin to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'bin'))
from parallelr import Configuration, ConfigurationError

class TestConfiguration(unittest.TestCase):
    def setUp(self):
        self.script_path = "mock_script.py"
        
    def test_defaults(self):
        """Test default configuration values."""
        with patch('parallelr.Path.exists', return_value=False):
            config = Configuration(self.script_path)
            
            self.assertEqual(config.limits.max_workers, 20)
            self.assertEqual(config.limits.timeout_seconds, 600)
            self.assertFalse(config.execution.workspace_isolation)

    def test_validation_clamping(self):
        """Test that user values are clamped to maximums."""
        # Prevent loading from disk
        with patch('parallelr.Configuration._load_script_config'), \
             patch('parallelr.Configuration._load_user_config'):
            
            config = Configuration(self.script_path)
            
            # Set max allowed limits
            config.limits.max_allowed_workers = 100
            config.limits.max_allowed_timeout = 3600
            
            # Apply user config with excess values
            user_data = {
                'max_workers': 999,
                'timeout_seconds': 99999
            }
            
            config._update_limits_with_validation(config.limits, user_data)
            
            # Should be clamped to defaults
            self.assertEqual(config.limits.max_workers, 100)
            self.assertEqual(config.limits.timeout_seconds, 3600)
            self.assertEqual(config.limits.timeout_seconds, 3600)

    def test_validation_errors(self):
        """Test validation of invalid values."""
        with patch('parallelr.Path.exists', return_value=False):
            config = Configuration(self.script_path)
            
            # Set invalid values
            config.limits.max_workers = 0
            
            with self.assertRaises(ConfigurationError):
                config.validate()
                
            config.limits.max_workers = 1
            config.limits.timeout_seconds = -1
            
            with self.assertRaises(ConfigurationError):
                config.validate()

if __name__ == '__main__':
    unittest.main()
