import unittest
from unittest.mock import Mock, patch
import sys
import os

from parallelr import _configure_ptasker_mode

class TestPTaskerConfig(unittest.TestCase):
    def setUp(self):
        self.args = Mock()
        # Default args state
        self.args.list_workers = False
        self.args.kill = None
        self.args.validate_config = False
        self.args.show_config = False
        self.args.check_dependencies = False
        self.args.project = None
        self.args.arguments_file = None
        self.args.env_var = None
        self.args.Command = None

    def test_configure_ptasker_skip_non_execution(self):
        """Test that configuration is skipped for non-execution commands."""
        self.args.list_workers = True
        _configure_ptasker_mode(self.args)
        self.assertIsNone(self.args.project)
        self.assertIsNone(self.args.Command)

    def test_configure_ptasker_auto_generate_project(self):
        """Test auto-generation of project name."""
        with patch('builtins.print') as mock_print:
            _configure_ptasker_mode(self.args)
            
            self.assertTrue(self.args.project.startswith('parallelr_'))
            self.assertEqual(len(self.args.project), 16)  # parallelr_ + 6 chars
            self.assertEqual(self.args.Command, f"tasker @TASK@ -p {self.args.project} -r")

    def test_configure_ptasker_use_provided_project(self):
        """Test using provided project name."""
        self.args.project = "my_project"
        
        with patch('builtins.print') as mock_print:
            _configure_ptasker_mode(self.args)
            
            self.assertEqual(self.args.project, "my_project")
            self.assertEqual(self.args.Command, "tasker @TASK@ -p my_project -r")

    def test_configure_ptasker_auto_env_var(self):
        """Test auto-setting env var when arguments file is present."""
        self.args.arguments_file = "args.txt"
        
        with patch('builtins.print') as mock_print:
            _configure_ptasker_mode(self.args)
            
            self.assertEqual(self.args.env_var, "HOSTNAME")

    def test_configure_ptasker_preserve_env_var(self):
        """Test preserving existing env var."""
        self.args.arguments_file = "args.txt"
        self.args.env_var = "CUSTOM_VAR"
        
        with patch('builtins.print') as mock_print:
            _configure_ptasker_mode(self.args)
            
            self.assertEqual(self.args.env_var, "CUSTOM_VAR")

if __name__ == '__main__':
    unittest.main()
