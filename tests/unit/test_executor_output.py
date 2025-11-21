import unittest
from unittest.mock import Mock, MagicMock
import sys
import os
from datetime import datetime

# Adjust path to import parallelr
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../bin')))
from parallelr import SecureTaskExecutor, TaskResult, TaskStatus, Configuration

class TestExecutorOutput(unittest.TestCase):
    def setUp(self):
        # Mock dependencies
        self.mock_logger = Mock()
        self.mock_config = Mock()
        
        # Setup limits config
        self.mock_config.limits = Mock()
        self.mock_config.limits.max_output_capture = 100  # Small limit for testing
        
        # Partial mock of SecureTaskExecutor to access _process_output
        # We don't need real file/command for checking output processing
        self.executor = SecureTaskExecutor(
            task_file="dummy.sh",
            command_template="echo test",
            timeout=30,
            worker_id=1,
            logger=self.mock_logger,
            config=self.mock_config
        )

    def test_process_output_no_truncation(self):
        """Test output processing within limits."""
        result = TaskResult(task_file="dummy.sh", command="cmd", start_time=datetime.now())
        stdout_lines = ["Line 1\n", "Line 2\n"]
        stderr_lines = ["Error 1\n"]
        
        self.executor._process_output(result, stdout_lines, stderr_lines)
        
        self.assertEqual(result.stdout, "Line 1\nLine 2\n")
        self.assertEqual(result.stderr, "Error 1\n")
        self.assertFalse(result.stdout_truncated)
        self.assertFalse(result.stderr_truncated)

    def test_process_output_with_truncation(self):
        """Test output processing exceeding limits."""
        result = TaskResult(task_file="dummy.sh", command="cmd", start_time=datetime.now())
        
        # Create output larger than max_output_capture (100 chars)
        long_line = "x" * 150
        stdout_lines = [long_line]
        stderr_lines = ["y" * 150]
        
        self.executor._process_output(result, stdout_lines, stderr_lines)
        
        # Should keep LAST 100 chars
        self.assertEqual(len(result.stdout), 100)
        self.assertEqual(result.stdout, "x" * 100)
        self.assertTrue(result.stdout_truncated)
        
        self.assertEqual(len(result.stderr), 100)
        self.assertEqual(result.stderr, "y" * 100)
        self.assertTrue(result.stderr_truncated)

    def test_process_output_exact_boundary(self):
        """Test output processing exactly at limits."""
        result = TaskResult(task_file="dummy.sh", command="cmd", start_time=datetime.now())
        
        exact_line = "x" * 100
        stdout_lines = [exact_line]
        
        self.executor._process_output(result, stdout_lines, [])
        
        self.assertEqual(len(result.stdout), 100)
        self.assertEqual(result.stdout, exact_line)
        self.assertFalse(result.stdout_truncated)

    def test_process_output_empty(self):
        """Test processing empty output."""
        result = TaskResult(task_file="dummy.sh", command="cmd", start_time=datetime.now())
        
        self.executor._process_output(result, [], [])
        
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")
        self.assertFalse(result.stdout_truncated)

if __name__ == '__main__':
    unittest.main()
