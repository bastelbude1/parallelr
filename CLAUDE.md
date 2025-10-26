# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**parallelr** is a Python 3.6.8-compatible parallel task execution framework. It executes tasks from a directory in parallel using a configurable number of workers, with robust error handling, resource monitoring, and workspace management.

## Core Architecture

### Main Components

- **ParallelTaskManager** (parallelr.py:673-966): Main execution coordinator that manages the task queue, worker pool, and result tracking
- **SecureTaskExecutor** (parallelr.py:436-672): Executes individual tasks with security validation, timeout handling, and resource monitoring
- **Configuration** (parallelr.py:142-434): Manages layered configuration system with script defaults and user overrides
- **TaskResult** (parallelr.py:63-89): Data class for task execution results with performance metrics

### Configuration System

The tool uses a two-tier configuration hierarchy:
1. **Script config**: `../cfg/parallelr.yaml` - System defaults and maximum limits
2. **User config**: `~/parallelr/cfg/parallelr.yaml` - User overrides validated against limits

User overrides for `max_workers`, `timeout_seconds`, and `max_output_capture` are automatically capped at the `max_allowed_*` values defined in script config.

### Task Execution Flow

1. Tasks are discovered from the specified directory (parallelr.py:771-791)
2. Each task file is queued and executed by a worker thread
3. Command template uses `@TASK@` placeholder replaced with task file path
4. Real-time output capture with non-blocking I/O using select (parallelr.py:543-595)
5. Resource monitoring via psutil (if available) for memory and CPU tracking
6. Results logged to CSV summary file with semicolon delimiter

### Workspace Management

- **Shared mode** (default): All workers use `~/parallelr/workspace`
- **Isolated mode** (`workspace_isolation: true`): Each worker gets `~/parallelr/workspace/pid{PID}_worker{N}`

### Auto-Stop Protection

When `--enable-stop-limits` is set, execution halts if:
- Consecutive failures exceed `max_consecutive_failures` (default: 5)
- Failure rate exceeds `max_failure_rate` (default: 50%) after `min_tasks_for_rate_check` tasks (default: 10)

### Daemon Mode

The tool supports Unix daemon mode for background execution using double-fork technique (parallelr.py:1035-1067). Not supported on Windows.

## Common Commands

### Execute tasks (foreground)
```bash
python bin/parallelr.py -T ./tasks -C "python3 @TASK@" -r
```

### Execute tasks with custom workers/timeout
```bash
python bin/parallelr.py -T ./tasks -C "bash @TASK@" -r -m 10 -t 300
```

### Execute tasks as daemon (background)
```bash
python bin/parallelr.py -T ./tasks -C "python3 @TASK@" -r -d
```

### Disable detailed task output logging (enabled by default)
```bash
python bin/parallelr.py -T ./tasks -C "python3 @TASK@" -r --no-task-output-log
```

### Enable auto-stop on errors
```bash
python bin/parallelr.py -T ./tasks -C "python3 @TASK@" -r --enable-stop-limits
```

### List running workers
```bash
python bin/parallelr.py --list-workers
```

### Kill all running instances (requires confirmation)
```bash
python bin/parallelr.py -k
```

### Kill specific instance
```bash
python bin/parallelr.py -k <PID>
```

### Validate configuration
```bash
python bin/parallelr.py --validate-config
```

### Show current configuration
```bash
python bin/parallelr.py --show-config
```

### Dry run (show commands without executing)
```bash
python bin/parallelr.py -T ./tasks -C "python3 @TASK@"
```

## File Locations

- **Script**: `bin/parallelr.py`
- **Script config**: `cfg/parallelr.yaml`
- **User config**: `~/parallelr/cfg/parallelr.yaml`
- **Logs**: `~/parallelr/logs/tasker_{PID}.log` (rotating, max 10MB, 5 backups)
- **Summary**: `~/parallelr/logs/summary_{PID}_{timestamp}.csv`
- **Task output**: `~/parallelr/logs/TaskResults_{PID}_{timestamp}.txt` (enabled by default, disable with `--no-task-output-log`)
- **PID tracking**: `~/parallelr/pids/parallelr.pids`
- **Workspace**: `~/parallelr/workspace/` or `~/parallelr/workspace/pid{PID}_worker{N}/`

## Key Implementation Details

### Process Termination
Process termination follows a graceful pattern (parallelr.py:656-666):
1. Send SIGTERM to allow graceful shutdown
2. Wait 5 seconds
3. Send SIGKILL if still alive

### Output Capture
Uses non-blocking I/O with `fcntl` and `select` to capture stdout/stderr in real-time without blocking on subprocess I/O (parallelr.py:543-595). This prevents buffer overflow issues.

### Security Validation
- Task files are validated for size (max 1MB by default)
- Command arguments are parsed with `shlex.split()` to prevent injection
- Each argument length is checked against `max_argument_length` (1000 chars)
- Absolute paths are used for task files to prevent path traversal

### Signal Handling
Graceful shutdown on SIGTERM and SIGINT (parallelr.py:879-887). SIGHUP is ignored to allow daemon operation.

### Custom Library Path
Environment variable `PARALLELR_LIB_PATH` (default: `/app/COOL/lib`) can be set to use custom Python libraries (parallelr.py:14-21).

## Dependencies

**Required**: Python 3.6.8+

**Optional**:
- `pyyaml` - For YAML config file support
- `psutil` - For resource monitoring (memory/CPU usage)

Without optional dependencies, the tool falls back gracefully with reduced functionality.

## Development Workflow

### Git Branching Strategy

**IMPORTANT**: Always create a new feature branch before making changes and pushing to GitHub. Never push directly to master.

```bash
# Create and switch to a new feature branch
git checkout -b feature/your-feature-name

# Make your changes, test, and commit
git add .
git commit -m "Description of changes"

# Push to the feature branch
git push origin feature/your-feature-name

# Create a pull request for review before merging to master
```

### Branch Naming Convention
- Feature branches: `feature/descriptive-name`
- Bug fixes: `bugfix/issue-description`
- Hotfixes: `hotfix/critical-issue`