# parallelr - Parallel Task Executor

A robust, production-ready Python framework for executing tasks in parallel with comprehensive configuration, monitoring, and error handling capabilities.

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Quick Start](#quick-start)
- [Requirements](#requirements)
- [Usage](#usage)
  - [Command Line Arguments](#command-line-arguments)
  - [Basic Examples](#basic-examples)
- [Configuration](#configuration)
  - [Configuration Hierarchy](#configuration-hierarchy)
  - [Configuration Sections](#configuration-sections)
  - [Creating Custom Configurations](#creating-custom-configurations)
- [Advanced Features](#advanced-features)
  - [Daemon Mode](#daemon-mode)
  - [Workspace Isolation](#workspace-isolation)
  - [Auto-Stop Protection](#auto-stop-protection)
  - [Resource Monitoring](#resource-monitoring)
- [Process Management](#process-management)
- [Logging and Output](#logging-and-output)
- [Task File Format](#task-file-format)
- [Troubleshooting](#troubleshooting)
- [Security Considerations](#security-considerations)

## Overview

**parallelr** is a Python 3.6.8+ compatible parallel task execution framework designed for reliability, flexibility, and production use. It executes multiple tasks concurrently using a configurable worker pool, with built-in timeout handling, resource monitoring, comprehensive logging, and automatic error detection.

Perfect for batch processing, data pipelines, test suites, or any scenario where you need to execute multiple independent tasks efficiently.

## Key Features

- ✓ **Parallel Execution**: Execute tasks concurrently with configurable worker pools (1-100 workers)
- ✓ **Flexible Task Selection**: Support for directories, files, glob patterns, and multiple sources
- ✓ **File Type Filtering**: Filter tasks by extension(s) with `--file-extension`
- ✓ **Flexible Configuration**: Two-tier YAML configuration system with user overrides
- ✓ **Resource Monitoring**: Track memory and CPU usage per task (requires psutil)
- ✓ **Workspace Management**: Shared or isolated workspace modes
- ✓ **Auto-Stop Protection**: Automatic halt on consecutive failures or high error rates
- ✓ **Daemon Mode**: Background execution with process tracking
- ✓ **Comprehensive Logging**: Rotating logs with timestamp-based naming to prevent conflicts
- ✓ **Timeout Management**: Per-task timeout with graceful termination
- ✓ **Security Validation**: Input validation and argument length checking
- ✓ **Graceful Shutdown**: Signal handling for clean termination
- ✓ **Real-time Output Capture**: Non-blocking I/O for live output collection
- ✓ **TASKER Integration**: Simplified `ptasker` mode with auto-generated project IDs

## Quick Start

```bash
# 1. Create a directory with task files
mkdir my_tasks
echo "echo 'Task 1 complete'" > my_tasks/task1.sh
echo "echo 'Task 2 complete'" > my_tasks/task2.sh

# 2. Execute tasks with 5 parallel workers (dry-run first)
python bin/parallelr.py -T my_tasks -C "bash @TASK@"

# 3. Run for real
python bin/parallelr.py -T my_tasks -C "bash @TASK@" -r

# 4. Run with custom settings
python bin/parallelr.py -T my_tasks -C "bash @TASK@" -r -m 10 -t 300
```

### Quick Start for TASKER Users (ptasker mode)

The `ptasker` symlink provides a simplified interface specifically for running TASKER test cases:

```bash
# 1. Execute TASKER tests with auto-generated project ID
python bin/ptasker -T /path/to/test_cases -r

# 2. Execute only .txt test cases
python bin/ptasker -T /path/to/test_cases --file-extension txt -r

# 3. Execute specific test files using glob patterns
python bin/ptasker -T /path/to/test_cases/*.txt -r

# 4. Execute with custom project name
python bin/ptasker -T /path/to/test_cases -p myproject -r

# 5. Run as daemon
python bin/ptasker -T /path/to/test_cases -p myproject -r -d
```

**How it works**: ptasker automatically generates the command as `tasker @TASK@ -p <project> -r`. You don't need to specify `-C`. If no project name is provided, one is auto-generated (e.g., `parallelr_1a811c`).

## Requirements

**Python**: 3.6.8 or higher

**Platform**: Linux/Unix (Windows supported except daemon mode)

**Standard Library**: pathlib, argparse, threading, subprocess, signal, logging, queue, csv, json, shlex, select, errno, fcntl

### Optional Python Modules

The script works without these modules but provides enhanced functionality when available. Dependencies are bundled in the `lib/` directory and loaded automatically.

**Check module availability**:
```bash
python bin/parallelr.py --check-dependencies
```

**PyYAML** (bundled: 6.0.1):
- **Purpose**: Load YAML configuration files (`cfg/parallelr.yaml`)
- **Without it**: Configuration files are ignored; only hardcoded defaults are used
- **Why use it**: Allows customizing workers, timeouts, logging levels, and all other settings without modifying code
- **Install**: `pip install --target=lib pyyaml`

**psutil** (bundled: 7.1.0):
- **Purpose**: Monitor memory and CPU usage per task during execution
- **Without it**: Memory/CPU metrics show 0.00 (not collected)
- **Why use it**: Essential for performance analysis, debugging resource issues, and capacity planning
- **Install**: `pip install --target=lib psutil`

**Custom library path**: Set `PARALLELR_LIB_PATH` environment variable to use an alternative library location (default: `/app/COOL/lib` if exists)

## Usage

### Command Line Arguments

#### Required Arguments

| Argument | Description |
|----------|-------------|
| `-T, --TasksDir PATHS...` | Directory, file paths, or glob patterns. Can be used multiple times:<br>• Directory: `-T /path/to/dir`<br>• Specific files: `-T /path/*.txt` (shell expansion)<br>• Multiple sources: `-T /dir1 -T /dir2 -T file.txt` |
| `-C, --Command CMD` | Command template with `@TASK@` placeholder for task file path |

#### Execution Control

| Argument | Description |
|----------|-------------|
| `-r, --run` | Execute tasks (without this flag, runs in dry-run mode) |
| `-m, --max N` | Maximum parallel workers (default: 20, max: 100, overrides config) |
| `-t, --timeout N` | Task timeout in seconds (default: 600, max: 3600, overrides config) |
| `-s, --sleep N` | Delay between starting new tasks (0-60 seconds, default: 0). Use to throttle resource consumption |
| `--file-extension EXT` | Filter task files by extension(s). Single: `txt`, Multiple: `txt,log,dat` |

#### Advanced Execution

| Argument | Description |
|----------|-------------|
| `-d, --daemon` | Run as background daemon (detached from session) |
| `--enable-stop-limits` | Enable automatic halt on excessive failures |
| `--no-task-output-log` | Disable detailed stdout/stderr logging to TaskResults file (enabled by default) |

#### Process Management

| Argument | Description |
|----------|-------------|
| `--list-workers` | List all running parallelr processes (safe, read-only) |
| `-k, --kill [PID]` | Kill processes: `-k` kills all (requires confirmation), `-k PID` kills specific process |

#### Configuration

| Argument | Description |
|----------|-------------|
| `--check-dependencies` | Check optional Python module availability and exit |
| `--validate-config` | Validate configuration files and exit |
| `--show-config` | Display current effective configuration and file locations |

### Basic Examples

```bash
# Dry-run to preview commands (safe, no execution)
python bin/parallelr.py -T ./tasks -C "python3 @TASK@"

# Execute Python scripts with 5 workers
python bin/parallelr.py -T ./tasks -C "python3 @TASK@" -r -m 5

# Execute only .txt files from a directory
python bin/parallelr.py -T ./tasks --file-extension txt -C "process @TASK@" -r

# Execute specific files using shell glob patterns
python bin/parallelr.py -T ./tasks/*.py -C "python3 @TASK@" -r

# Execute from multiple sources
python bin/parallelr.py -T ./scripts -T ./tests -T config.json -C "process @TASK@" -r

# Filter multiple extensions
python bin/parallelr.py -T ./data --file-extension "csv,tsv,txt" -C "analyze @TASK@" -r

# Execute bash scripts with 600s timeout
python bin/parallelr.py -T ./scripts -C "bash @TASK@" -r -t 600

# Throttle resource consumption with 2-second delay between task starts
python bin/parallelr.py -T ./tasks -C "curl @TASK@" -r -s 2.0

# Run as daemon with auto-stop protection
python bin/parallelr.py -T ./tasks -C "python3 @TASK@" -r -d --enable-stop-limits

# Execute without detailed output logging (logging is enabled by default)
python bin/parallelr.py -T ./tasks -C "./process.sh @TASK@" -r --no-task-output-log

# List running workers
python bin/parallelr.py --list-workers

# Kill specific worker
python bin/parallelr.py -k 12345

# Kill all workers (requires 'yes' confirmation)
python bin/parallelr.py -k
```

## Configuration

### Configuration Hierarchy

parallelr uses a two-tier configuration system:

1. **Script Configuration** (`cfg/parallelr.yaml`)
   - Ships with the tool
   - Defines system defaults and maximum limits
   - Controls security boundaries
   - Cannot be overridden by users for security settings

2. **User Configuration** (`~/parallelr/cfg/parallelr.yaml`)
   - Optional user-specific overrides
   - Subject to validation against script limits
   - Allows customization within safe boundaries

**Loading Order**: Script config → User config (validated overrides)

### Configuration Sections

#### 1. Limits Section

Controls execution limits and safety thresholds.

```yaml
limits:
  # Worker and timeout settings
  max_workers: 20              # Number of parallel workers
  timeout_seconds: 600         # Task timeout (10 minutes)
  wait_time: 0.1               # Polling interval when all workers busy (config file only, 0.01-10.0 seconds)
  task_start_delay: 0.0       # Delay between starting new tasks (0-60 seconds)
  max_output_capture: 1000     # Maximum characters of stdout/stderr to capture (last N chars)

  # System-enforced maximums (script config only)
  max_allowed_workers: 100     # Upper limit for max_workers
  max_allowed_timeout: 3600    # Upper limit for timeout_seconds (1 hour)
  max_allowed_output: 10000    # Upper limit for max_output_capture (last N chars)

  # Auto-stop protection (requires --enable-stop-limits)
  stop_limits_enabled: false           # Must be enabled via CLI or config
  max_consecutive_failures: 5          # Halt after N consecutive failures
  max_failure_rate: 0.5                # Halt if >50% of tasks fail
  min_tasks_for_rate_check: 10         # Need N tasks before checking failure rate
```

**Details**:

- **max_workers**: Number of concurrent tasks. Higher values = more parallelism but more resource usage. Range: 1-100.

- **timeout_seconds**: Maximum execution time per task. Tasks exceeding this are terminated (SIGTERM, then SIGKILL). Range: 1-3600.

- **wait_time**: Polling interval to check if running tasks have completed when all worker slots are occupied. This is a system-level parameter for responsiveness and should only be configured via config file. Range: 0.01-10.0 seconds.
  - `0.01-0.1`: Very responsive, minimal delay detecting task completion (recommended)
  - `0.5-1.0`: Balanced, slight delay acceptable
  - `>2.0`: Not recommended - workers may sit idle waiting for next poll
  - **Note**: Config file only - not available as command line argument

- **task_start_delay**: Delay in seconds between starting new tasks. Use this to throttle resource consumption when running many small tasks. Range: 0-60 seconds.
  - `0`: No delay - tasks start as fast as possible (default)
  - `0.1-1.0`: Light throttling for API rate limits or I/O management
  - `1.0-5.0`: Moderate throttling for database connections or network bandwidth
  - `>5.0`: Heavy throttling for very resource-intensive tasks
  - **Use cases**: API rate limiting, gradual connection pooling, filesystem I/O throttling, load ramp-up
  - **Command line**: Override with `-s/--sleep` argument

- **max_output_capture**: Limits memory usage from task output. Captures the **LAST N characters** (errors appear at end). If output exceeds this limit, earlier output is discarded. Useful for tasks with verbose output while preserving error messages.

- **max_allowed_\***: Hard limits enforced by script config. User configs cannot exceed these values. If user specifies higher, value is capped with a warning.

- **stop_limits_enabled**: When `true` (or with `--enable-stop-limits`), automatically halts execution if error thresholds are breached. Prevents runaway failed jobs.

- **max_consecutive_failures**: Stops if N tasks fail in a row without any success. Detects systematic failures (missing dependencies, wrong command, etc.).

- **max_failure_rate**: Stops if failure percentage exceeds this (0.5 = 50%). Only checked after `min_tasks_for_rate_check` tasks complete.

- **min_tasks_for_rate_check**: Minimum completed tasks before checking failure rate. Prevents premature stops on small samples.

#### 2. Security Section

Controls security validation and limits.

```yaml
security:
  max_argument_length: 1000    # Maximum length for command arguments
```

**Details**:

- **max_argument_length**: Prevents injection attacks via overly long arguments. Each parsed command argument is checked. Typical: 1000-10000 characters.

**Note**: Security section can only be set in script config, not user config.

#### 3. Execution Section

Controls task execution behavior.

```yaml
execution:
  workspace_isolation: false   # false = shared workspace, true = isolated per worker
  use_process_groups: true     # Enable process group management for cleanup
```

**Details**:

- **workspace_isolation**:
  - `false` (default): All workers share `~/parallelr/workspace/`
    - Use when: Tasks are independent or read-only
    - Pros: Simple, less disk I/O
    - Cons: Tasks may conflict if writing to same files

  - `true`: Each worker gets `~/parallelr/workspace/pid{PID}_worker{N}/`
    - Use when: Tasks create temporary files or need isolation
    - Pros: No conflicts, clean separation
    - Cons: More disk usage, slower for file-heavy tasks

- **use_process_groups**: Enables process group management for better cleanup. Recommended: `true`.

#### 4. Logging Section

Controls logging behavior and formats.

```yaml
logging:
  level: "INFO"                                                            # Log verbosity
  console_format: "%(asctime)s - %(levelname)s - %(message)s"             # Console output format
  file_format: "%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s"  # File log format
  custom_date_format: "%d%b%y_%H%M%S"                                     # Timestamp format for filenames
  max_log_size_mb: 10                                                      # Log rotation size
  backup_count: 5                                                          # Number of backup logs
```

**Details**:

- **level**: Log verbosity. Options: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
  - `DEBUG`: Verbose, shows all operations (use for troubleshooting)
  - `INFO`: Normal, shows task starts/completions/failures
  - `WARNING`: Only warnings and errors
  - `ERROR`: Only errors
  - `CRITICAL`: Only critical failures

- **console_format**: Format string for console output (when not daemon). Uses Python logging format.

- **file_format**: Format string for log files. More detailed than console.

- **custom_date_format**: Timestamp format for log/summary filenames. Default: `17Jun25_181623`

- **max_log_size_mb**: When main log exceeds this size, it's rotated (renamed to `.log.1`, `.log.2`, etc.)

- **backup_count**: How many rotated logs to keep. Oldest is deleted when exceeded.

#### 5. Advanced Section

Optional advanced settings.

```yaml
advanced:
  max_file_size: 1048576       # Maximum task file size in bytes (1MB)
  memory_limit_mb: null        # Memory limit per worker (null = no limit)
  retry_failed_tasks: false    # Retry failed tasks (not yet implemented)
```

**Details**:

- **max_file_size**: Task files larger than this are rejected as a security measure. Default: 1MB. Range: 1KB - 100MB.

- **memory_limit_mb**: Future feature for memory limiting per worker. Currently not enforced. Set to `null` (no limit).

- **retry_failed_tasks**: Future feature for automatic retry. Currently not implemented. Must be `false`.

### Creating Custom Configurations

#### User Configuration Example

Create `~/parallelr/cfg/parallelr.yaml`:

```yaml
# User overrides for parallelr
# Values are validated against script config limits

limits:
  max_workers: 50              # Override default (capped at max_allowed_workers)
  timeout_seconds: 1800        # 30 minutes (capped at max_allowed_timeout)

execution:
  workspace_isolation: true    # Use isolated workspaces

logging:
  level: "DEBUG"               # More verbose logging
  max_log_size_mb: 50          # Larger logs before rotation
```

**Validation Rules**:
- User cannot override `security` section
- `max_workers`, `timeout_seconds`, `max_output_capture` are capped at `max_allowed_*` values
- Invalid values cause warnings and fall back to script defaults
- Type mismatches are automatically converted if possible

## Advanced Features

### Daemon Mode

Run parallelr as a background daemon, detached from your terminal session.

```bash
# Start as daemon
python bin/parallelr.py -T ./tasks -C "bash @TASK@" -r -d

# Check running daemons
python bin/parallelr.py --list-workers

# View daemon logs
tail -f ~/parallelr/logs/tasker_<PID>.log

# Kill daemon
python bin/parallelr.py -k <PID>
```

**How It Works**:
- Uses Unix double-fork technique
- Detaches from terminal (can close SSH session)
- Redirects stdout/stderr to `/dev/null`
- All output goes to log files
- Process ID tracked in `~/parallelr/pids/parallelr.pids`

**Limitations**:
- Linux/Unix only (not supported on Windows)
- Cannot interact after daemonizing
- Must use log files to monitor progress

### Workspace Isolation

Control whether workers share or isolate their working directories.

#### Shared Workspace (Default)

```yaml
execution:
  workspace_isolation: false
```

- All workers use: `~/parallelr/workspace/`
- Tasks see each other's files
- Best for: Read-only tasks, independent tasks, data processing

#### Isolated Workspace

```yaml
execution:
  workspace_isolation: true
```

- Each worker uses: `~/parallelr/workspace/pid{PID}_worker{N}/`
- Complete isolation between workers
- Best for: Tasks creating temp files, compilation, tests

**Example**:
```bash
# Worker 1: ~/parallelr/workspace/pid12345_worker1/
# Worker 2: ~/parallelr/workspace/pid12345_worker2/
# Worker 3: ~/parallelr/workspace/pid12345_worker3/
```

### Auto-Stop Protection

Automatically halt execution when failure thresholds are exceeded.

**Enable via CLI**:
```bash
python bin/parallelr.py -T ./tasks -C "python @TASK@" -r --enable-stop-limits
```

**Enable via Config**:
```yaml
limits:
  stop_limits_enabled: true
  max_consecutive_failures: 5
  max_failure_rate: 0.5
  min_tasks_for_rate_check: 10
```

**Triggers**:

1. **Consecutive Failures**: 5 failures in a row → STOP
   - Example: Missing dependency, syntax error in all scripts

2. **Failure Rate**: >50% failures after 10 tasks → STOP
   - Example: 7 failures out of 10 tasks = 70% → STOP

**Use Cases**:
- Prevent wasting resources on systematically broken jobs
- Fast-fail for misconfigured pipelines
- Automatic alerts for production failures

**Disable** (default):
- All tasks execute regardless of failures
- Full summary at end shows all results
- Useful when: Tasks are independent, some failures expected

### Resource Monitoring

Track memory and CPU usage per task (requires psutil).

**Automatic when psutil is installed**:
- Tracks peak memory usage (MB)
- Tracks CPU percentage
- Logged to summary CSV
- Displayed in final report

**Without psutil**:
- No resource metrics collected
- Summary shows: "Memory/CPU monitoring: Not available"
- All other features work normally

**Summary Report Example**:
```
Performance Statistics:
- Average Duration: 15.34s
- Maximum Duration: 45.12s
- Minimum Duration: 3.21s
- Average Memory Usage: 128.45MB
- Peak Memory Usage: 512.33MB
```

## Process Management

### List Running Workers

```bash
python bin/parallelr.py --list-workers
```

**Output**:
```
Found 2 running parallel-tasker process(es):

PID      Status     Start Time           Log File                       Summary File
----------------------------------------------------------------------------------------------------
12345    running    2025-09-29 14:30:15  tasker_12345.log              summary_12345_29Sep25_143015.csv
12346    running    2025-09-29 14:32:01  tasker_12346.log              summary_12346_29Sep25_143201.csv
```

### Kill Processes

**Kill specific process**:
```bash
python bin/parallelr.py -k 12345
```

**Kill all processes** (requires confirmation):
```bash
python bin/parallelr.py -k
# Prompts: Are you sure? Type 'yes' to confirm:
```

**How It Works**:
1. Sends SIGTERM (graceful shutdown)
2. Waits 3 seconds
3. Sends SIGKILL if still running
4. Cleans up PID file

## Logging and Output

### Log Files

Located in `~/parallelr/logs/`:

All log files use a consistent naming pattern with timestamps to prevent PID reuse conflicts:
- `parallelr_{PID}_{TIMESTAMP}.log` - Main execution log
- `parallelr_{PID}_{TIMESTAMP}_summary.csv` - CSV summary of task results
- `parallelr_{PID}_{TIMESTAMP}_output.txt` - Captured task output

#### 1. Main Log (`parallelr_{PID}_{TIMESTAMP}.log`)
- **Purpose**: Detailed execution log for debugging
- **Format**: Timestamped entries with log levels
- **Rotation**: Rotates at 10MB (configurable)
- **Backups**: Keeps 5 old logs (`.log.1`, `.log.2`, etc.)
- **Content**: Task starts, completions, errors, warnings
- **Example name**: `parallelr_3916638_29Sep25_215848.log`

**Example content**:
```
2025-09-29 14:30:15,123 - P12345 - INFO - [MainThread] - Starting parallel execution
2025-09-29 14:30:15,145 - P12345 - INFO - [ThreadPoolExecutor-0_0] - Worker 1: Starting task ./tasks/task1.sh
2025-09-29 14:30:17,892 - P12345 - INFO - [ThreadPoolExecutor-0_0] - Task completed: ./tasks/task1.sh
```

#### 2. Summary CSV (`parallelr_{PID}_{TIMESTAMP}_summary.csv`)
- **Purpose**: Machine-readable task results
- **Format**: Semicolon-delimited CSV
- **Use**: Analysis, monitoring, reports
- **One row per task**
- **Example name**: `parallelr_3916638_29Sep25_215848_summary.csv`

**Columns**:
```
start_time;end_time;status;process_id;worker_id;task_file;command;exit_code;duration_seconds;memory_mb;cpu_percent;error_message
```

**Example**:
```csv
2025-09-29T14:30:15;2025-09-29T14:30:17;SUCCESS;12345;1;./tasks/task1.sh;bash ./tasks/task1.sh;0;2.75;45.23;12.5;
2025-09-29T14:30:15;2025-09-29T14:30:45;TIMEOUT;12345;2;./tasks/task2.sh;bash ./tasks/task2.sh;;;45.00;128.45;8.3;Timeout after 45s
```

#### 3. Task Output (`parallelr_{PID}_{TIMESTAMP}_output.txt`)
- **Purpose**: Detailed stdout/stderr for each task
- **Enabled**: By default (disable with `--no-task-output-log` flag)
- **Format**: Human-readable with separators
- **Use**: Debugging task failures, verifying output
- **Example name**: `parallelr_3916638_29Sep25_215848_output.txt`

**Example**:
```
================================================================================
Task: ./tasks/task1.sh
Worker: 1
Command: bash ./tasks/task1.sh
Status: SUCCESS
Exit Code: 0
Duration: 2.75s
Memory: 45.23MB
Start: 2025-09-29 14:30:15.123456
End: 2025-09-29 14:30:17.876543

STDOUT:
Processing data...
Complete!

STDERR:

================================================================================
```

### Summary Report

Displayed at end of execution (or in daemon log):

```
Parallel Task Execution Summary
===============================
Total Tasks: 100
Completed Successfully: 92
Failed: 5
Cancelled: 3
Success Rate: 92.0%

Performance Statistics:
- Average Duration: 15.34s
- Maximum Duration: 45.12s
- Minimum Duration: 3.21s
- Average Memory Usage: 128.45MB
- Peak Memory Usage: 512.33MB

Directories:
- Working Dir: /home/user/parallelr/workspace
- Workspace Type: Shared
- Log Dir: /home/user/parallelr/logs

Auto-Stop Protection:
- Stop Limits: Disabled

Log Files:
- Main Log: /home/user/parallelr/logs/parallelr_12345_29Sep25_143015.log (rotating)
- Summary: /home/user/parallelr/logs/parallelr_12345_29Sep25_143015_summary.csv (session-specific)
- Output: /home/user/parallelr/logs/parallelr_12345_29Sep25_143015_output.txt (enabled by default, disable with --no-task-output-log)

Process Info:
- Process ID: 12345
- Workers: 20
```

## Task File Format

Task files can be specified in multiple ways:

1. **Directory**: Discovers all files (non-recursive) in the directory
2. **Specific files**: Using shell glob patterns (e.g., `*.txt`)
3. **Multiple sources**: Combine directories and individual files
4. **Extension filtering**: Use `--file-extension` to filter by type

The framework:
- Accepts files from all specified sources
- Applies extension filters if provided
- Removes duplicates and sorts alphabetically
- Executes each using the command template

**Command Template**:
- Use `@TASK@` as placeholder for task file path
- Replaced with **absolute path** to task file
- Parsed with `shlex.split()` for safe shell argument handling

**Examples**:

```bash
# Execute Python scripts
-C "python3 @TASK@"

# Execute with arguments
-C "python3 process.py --input @TASK@ --verbose"

# Execute bash scripts
-C "bash @TASK@"

# Execute with custom interpreter
-C "/usr/local/bin/custom_tool --file @TASK@"

# Complex command
-C "timeout 120 /app/processor.sh --data @TASK@ --output /tmp/results"
```

**Task File Requirements**:
- Must be regular files (not directories)
- Size must not exceed `max_file_size` (default 1MB)
- Filename can be anything

**Task File Examples**:

```bash
# tasks/task001.sh
#!/bin/bash
echo "Processing task 1"
sleep 5
echo "Task 1 complete"

# tasks/data_001.json
{"id": 1, "data": "..."}

# tasks/script.py
print("Hello from Python task")
```

## Troubleshooting

### Common Issues

#### Issue: "No task files found"
**Cause**: TasksDir is empty or doesn't exist
**Solution**:
```bash
ls -la <TasksDir>  # Verify directory exists and has files
```

#### Issue: "Configuration validation failed"
**Cause**: Invalid YAML syntax or values
**Solution**:
```bash
python bin/parallelr.py --validate-config  # See specific errors
python bin/parallelr.py --show-config      # View current config
```

#### Issue: Tasks hang forever
**Cause**: No timeout set or timeout too high
**Solution**: Use `-t` flag or set `timeout_seconds` in config
```bash
python bin/parallelr.py -T ./tasks -C "bash @TASK@" -r -t 300
```

#### Issue: "Memory/CPU monitoring: Not available"
**Cause**: psutil not installed
**Solution**: psutil is in `lib/`, but if missing:
```bash
pip install --target=lib psutil
```

#### Issue: High failure rate
**Cause**: Wrong command, missing dependencies, wrong permissions
**Solution**:
1. Dry-run first: `python bin/parallelr.py -T ./tasks -C "bash @TASK@"`
2. Check logs: `tail -f ~/parallelr/logs/tasker_<PID>.log`
3. Test single task manually: `bash tasks/task1.sh`
4. Check detailed task output: `~/parallelr/logs/TaskResults_<PID>_*.txt` (enabled by default)

#### Issue: Worker stuck after Ctrl+C
**Cause**: Not cleaning up properly
**Solution**:
```bash
python bin/parallelr.py --list-workers  # Find PID
python bin/parallelr.py -k <PID>        # Kill specific worker
```

#### Issue: Permission denied on task files
**Cause**: Task files not executable
**Solution**:
```bash
chmod +x tasks/*.sh  # Make executable
# Or use interpreter: -C "bash @TASK@" instead of -C "@TASK@"
```

### Debug Mode

Enable debug logging for troubleshooting:

**Via Config** (`~/parallelr/cfg/parallelr.yaml`):
```yaml
logging:
  level: "DEBUG"
```

**Via Environment** (editing script temporarily):
```python
self.level = "DEBUG"  # In LoggingConfig class
```

**Debug Output Includes**:
- Configuration loading details
- Task discovery process
- Worker thread lifecycle
- Detailed error messages
- Resource monitoring data

### Getting Help

**View help**:
```bash
python bin/parallelr.py --help
```

**Validate setup**:
```bash
python bin/parallelr.py --check-dependencies  # Check optional modules
python bin/parallelr.py --validate-config     # Validate configuration
python bin/parallelr.py --show-config         # View current config
```

**Test with dry-run**:
```bash
python bin/parallelr.py -T ./tasks -C "bash @TASK@"
```

## Security Considerations

### Input Validation

- **Task files**: Size checked against `max_file_size`
- **Command arguments**: Length checked against `max_argument_length`
- **Command parsing**: Uses `shlex.split()` to prevent injection
- **Path handling**: Absolute paths used to prevent traversal

### Configuration Protection

- **Security section**: Cannot be overridden by user config
- **Limit enforcement**: User values capped at `max_allowed_*` values
- **Type checking**: Config values validated for correct types

### Process Isolation

- **Process groups**: Enabled by default for clean termination
- **Workspace isolation**: Optional per-worker isolation
- **Resource limits**: Future support for memory/CPU caps

### Best Practices

1. **Validate tasks**: Always dry-run first
2. **Use timeouts**: Prevent runaway tasks
3. **Enable auto-stop**: Use `--enable-stop-limits` for production
4. **Monitor logs**: Check logs regularly in daemon mode
5. **Limit workers**: Don't exceed system capacity
6. **Isolate workspaces**: Use when tasks modify files
7. **Review task files**: Ensure tasks are from trusted sources

---

## Quick Reference

### Essential Commands

```bash
# Dry-run (preview)
python bin/parallelr.py -T <dir> -C "<command> @TASK@"

# Execute
python bin/parallelr.py -T <dir> -C "<command> @TASK@" -r

# Custom workers/timeout
python bin/parallelr.py -T <dir> -C "<command> @TASK@" -r -m 10 -t 300

# Daemon mode
python bin/parallelr.py -T <dir> -C "<command> @TASK@" -r -d

# List workers
python bin/parallelr.py --list-workers

# Kill worker
python bin/parallelr.py -k <PID>

# Check dependencies
python bin/parallelr.py --check-dependencies

# View config
python bin/parallelr.py --show-config

# Validate config
python bin/parallelr.py --validate-config
```

### File Locations

```
parallelr/
├── bin/
│   └── parallelr.py          # Main script
├── cfg/
│   └── parallelr.yaml        # Script config
├── lib/                      # Bundled dependencies (psutil, pyyaml)
└── CLAUDE.md                 # Developer guide

~/parallelr/
├── cfg/
│   └── parallelr.yaml        # User config (optional)
├── logs/
│   ├── tasker_{PID}.log      # Main log (rotating)
│   ├── summary_{PID}_{timestamp}.csv
│   └── TaskResults_{PID}_{timestamp}.txt
├── workspace/                # Shared workspace
│   └── pid{PID}_worker{N}/   # Isolated workspaces (if enabled)
└── pids/
    └── parallelr.pids        # Running process tracking
```

---

**Version**: 1.0
**Python Compatibility**: 3.6.8+
**License**: See project documentation
**Author**: See project documentation