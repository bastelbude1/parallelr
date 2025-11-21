import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add bin to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'bin'))
from parallelr import ParallelTaskManager, TaskStatus, TaskResult

class TestTaskManager(unittest.TestCase):
    def setUp(self):
        self.mock_config = MagicMock()
        self.mock_config.limits.stop_limits_enabled = True
        self.mock_config.limits.max_consecutive_failures = 2
        self.mock_config.limits.max_failure_rate = 0.5
        self.mock_config.limits.min_tasks_for_rate_check = 4
        self.mock_config.get_log_directory.return_value = Path("/tmp")
        self.mock_config.get_custom_timestamp.return_value = "2025"
        # Configure logging mock to return strings/ints
        self.mock_config.logging.level = "INFO"
        self.mock_config.logging.max_log_size_mb = 10
        self.mock_config.logging.backup_count = 5
        
        with patch('parallelr.Configuration.from_script', return_value=self.mock_config), \
             patch('parallelr.Configuration.validate'), \
             patch('parallelr.Configuration.register_process'), \
             patch('parallelr.Configuration.cleanup_stale_pids'):
            
            self.manager = ParallelTaskManager(
                max_workers=1,
                timeout=10,
                task_start_delay=0,
                tasks_paths=[],
                command_template="echo",
                script_path="mock_script.py",
                dry_run=True,
                enable_stop_limits=True # Explicitly enable
            )
            
            # Ensure config limits are set on the mock
            self.manager.config.limits.max_consecutive_failures = 2
            self.manager.config.limits.max_failure_rate = 0.5
            self.manager.config.limits.min_tasks_for_rate_check = 4

    def test_error_limits_consecutive(self):
        """Test auto-stop on consecutive failures."""
        # 1st failure
        self.manager.consecutive_failures = 1
        self.assertFalse(self.manager._check_error_limits())
        
        # 2nd failure (hits limit)
        self.manager.consecutive_failures = 2
        self.assertTrue(self.manager._check_error_limits())

    def test_error_limits_rate(self):
        """Test auto-stop on failure rate."""
        # Not enough tasks
        self.manager.total_completed = 3
        self.manager.failed_tasks = [1, 2] # 2 failures
        self.assertFalse(self.manager._check_error_limits())
        
        # Enough tasks (4), 50% failure rate (<= 0.5 limit) -> OK
        self.manager.total_completed = 4
        self.manager.failed_tasks = [1, 2]
        self.assertFalse(self.manager._check_error_limits())
        
        # 3 failures / 4 total = 75% > 50% -> STOP
        self.manager.failed_tasks = [1, 2, 3]
        self.assertTrue(self.manager._check_error_limits())

if __name__ == '__main__':
    unittest.main()
