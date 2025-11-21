import subprocess
import pytest
from pathlib import Path
import sys

# Add project root to path to import conftest constants
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from tests.conftest import PARALLELR_BIN, PYTHON_FOR_PARALLELR

@pytest.mark.e2e
class TestCLIInvocations:
    """
    End-to-End tests for CLI invocations.
    
    Treats parallelr.py as a black box executable.
    """

    def test_help(self):
        """Test --help flag."""
        result = subprocess.run(
            [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN), "--help"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        assert result.returncode == 0
        assert "usage: parallelr.py" in result.stdout
        assert "Parallel Task Executor" in result.stdout

    def test_version(self):
        """Test --version flag."""
        result = subprocess.run(
            [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN), "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        assert result.returncode == 0
        # Version output might be in stdout or stderr depending on argparse version/config
        output = result.stdout + result.stderr
        assert "parallelr.py 1.0." in output

    def test_invalid_args_missing_required(self):
        """Test execution failure when required arguments are missing."""
        result = subprocess.run(
            [PYTHON_FOR_PARALLELR, str(PARALLELR_BIN), "-r"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        assert result.returncode != 0
        assert "required" in result.stderr or "error:" in result.stderr

    def test_simple_file_execution(self, temp_dir, isolated_env):
        """Test successful execution of a simple file task."""
        task_file = temp_dir / "simple_task.sh"
        task_file.write_text("#!/bin/bash\necho 'Hello E2E'\n")
        task_file.chmod(0o755)

        result = subprocess.run(
            [
                PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
                "-T", str(task_file),
                "-C", "bash @TASK@",
                "-r",
                "--max", "1"
            ],
            env=isolated_env['env'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        assert result.returncode == 0, f"Execution failed: {result.stderr}"
        assert "Task completed successfully" in result.stdout
        
        # Verify output log creation
        log_dir = isolated_env['home'] / "parallelr" / "logs"
        output_logs = list(log_dir.glob("*_output.txt"))
        assert len(output_logs) == 1
        assert "Hello E2E" in output_logs[0].read_text()
