import pytest
import json
import os
import sys
import subprocess
from pathlib import Path

# Add tests directory to path to import conftest
sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import PARALLELR_BIN, PYTHON_FOR_PARALLELR

@pytest.mark.integration
def test_env_vars_in_jsonl_command(temp_dir, isolated_env):
    """
    Verify that environment variables are included in the 'command_executed' field in results.jsonl.
    
    Regression test for issue where env vars were logged to console but not saved in JSONL result.
    """
    # Setup arguments file
    args_file = temp_dir / "args.txt"
    args_file.write_text("server1\n")
    
    # Setup template script
    template_file = temp_dir / "task.sh"
    template_file.write_text("#!/bin/bash\necho 'Task running'\n")
    template_file.chmod(0o755)
    
    # Command: parallelr -A args.txt -T task.sh -E SERVER -C "bash @TASK@" -r
    cmd = [
        PYTHON_FOR_PARALLELR, str(PARALLELR_BIN),
        "-A", str(args_file),
        "-T", str(template_file),
        "-E", "SERVER",
        "-C", "bash @TASK@",
        "-r",
        "--max", "1"
    ]
    
    # Run in isolated environment
    result = subprocess.run(
        cmd, 
        env=isolated_env['env'], 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE, 
        universal_newlines=True
    )
    
    assert result.returncode == 0, f"Execution failed: {result.stderr}"
    
    # Find the results.jsonl file
    # Logs are in ~/parallelr/logs relative to the isolated home
    log_dir = isolated_env['home'] / "parallelr" / "logs"
    assert log_dir.exists(), "Log directory not created"
    
    jsonl_files = list(log_dir.glob("*_results.jsonl"))
    assert len(jsonl_files) == 1, f"Expected 1 results file, found {len(jsonl_files)}"
    
    # Verify content
    found_task = False
    with open(str(jsonl_files[0]), "r") as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            if data.get("type") == "task":
                found_task = True
                command_executed = data.get("command_executed", "")
                
                # Check if SERVER=server1 is in the command string
                # Note: shlex.quote('server1') returns 'server1' (no quotes)
                assert "SERVER=server1" in command_executed, \
                    f"Env var missing from command_executed: '{command_executed}'"
                
                # Also check the base command is there
                assert str(template_file) in command_executed
                
    assert found_task, "No task record found in JSONL"
