# parallelr - Parallel Task Executor

## Version 1.0.11

[![CI](https://github.com/bastelbude1/parallelr/actions/workflows/ci.yml/badge.svg)](https://github.com/bastelbude1/parallelr/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/bastelbude1/parallelr/branch/master/graph/badge.svg)](https://codecov.io/gh/bastelbude1/parallelr)

A robust, production-ready Python framework for executing tasks in parallel with comprehensive configuration, monitoring, and error handling capabilities.

[[_TOC_]]

## Overview

**parallelr** is a Python 3.6.8+ compatible parallel task execution framework designed for reliability, flexibility, and production use. It executes multiple tasks concurrently using a configurable worker pool, with built-in timeout handling, resource monitoring, comprehensive logging, and automatic error detection.

**Testing Strategy**: This project uses a **dual Python testing approach** to ensure both backward compatibility and implementation correctness:

- **Local Development & Production**: Python **3.6.8** - The production environment requires Python 3.6.8, and all local testing MUST use this version to verify compatibility
- **GitHub CI/CD**: Python **3.9+** - CI pipeline uses Python 3.9 for modern tooling support (pytest, linters) while maintaining 3.6.8-compatible syntax

**Why this approach?** The code must run on Python 3.6.8 in production, but testing tools (pytest, coverage, linters) work better on modern Python versions. Both environments execute the same test suite to guarantee the code works correctly on both versions.

Perfect for batch processing, data pipelines, test suites, or any scenario where you need to execute multiple independent tasks efficiently.

## Key Features

- ✓ **Parallel Execution**: Execute tasks concurrently with configurable worker pools (1-100 workers)
- ✓ **Flexible Task Selection**: Support for directories, files, glob patterns, and multiple sources
- ✓ **Arguments Mode**: Run same template with different arguments from file with multi-argument support
- ✓ **Environment Variables**: Set task-specific environment variables from arguments file
- ✓ **File Type Filtering**: Filter tasks by extension(s) with `--file-extension`
- ✓ **Flexible Configuration**: Two-tier YAML configuration system with user overrides
- ✓ **Resource Monitoring**: Track memory and CPU usage per task with per-task and worst-case total reporting
- ✓ **JSONL Results**: Machine-readable results in JSON Lines format for analysis
- ✓ **PSR Analysis Tool**: Standalone tool (psr.py) for filtering, reporting, and CSV export
- ✓ **Workspace Management**: Shared or isolated workspace modes
- ✓ **Auto-Stop Protection**: Automatic halt on consecutive failures or high error rates
- ✓ **Daemon Mode**: Background execution with process tracking
- ✓ **Enhanced Output Logging**: Detailed per-task output with command-line parameters and truncation tracking
- ✓ **Comprehensive Logging**: Rotating logs with timestamp-based naming to prevent conflicts
- ✓ **Timeout Management**: Per-task timeout with graceful termination
- ✓ **Security Validation**: Input validation and argument length checking
- ✓ **Graceful Shutdown**: Signal handling for clean termination
- ✓ **Real-time Output Capture**: Non-blocking I/O with precise truncation tracking
- ✓ **TASKER Integration**: Simplified `ptasker` mode with auto-generated project IDs

## Quick Start on JumpHosts

```bash
# 1. Create a directory with task files
mkdir my_tasks
echo "echo 'Task 1 complete'" > my_tasks/task1.sh
echo "echo 'Task 2 complete'" > my_tasks/task2.sh

# 2. Execute tasks with 5 parallel workers (dry-run first)
parallelr -T my_tasks -C "bash @TASK@"

# 3. Run for real
parallelr -T my_tasks -C "bash @TASK@" -r

# 4. Run with custom settings
parallelr -T my_tasks -C "bash @TASK@" -r -m 10 -t 300
```

### Quick Start for TASKER Users (ptasker mode)

The `ptasker` symlink provides a simplified interface specifically for running [TASKER](https://devcloud.ubs.net/ubs/ts/mainframe/mms-midrange-n-datawarehouse-svcs/platforms-access-tls/commons/tasker) test cases:

```bash
# 1. Execute TASKER tests with auto-generated project ID
ptasker -T /path/to/test_cases -r

# 2. Execute only .txt test cases
ptasker -T /path/to/test_cases --file-extension txt -r

# 3. Execute specific test files using glob patterns
ptasker -T /path/to/test_cases/*.txt -r

# 4. Execute with custom project name
python bin/ptasker -T /path/to/test_cases -p myproject -r

# 5. Run as daemon
ptasker -T /path/to/test_cases -p myproject -r -D

# 6. Validate ptasker configuration
ptasker --validate-config
```

**How it works**: ptasker automatically generates the command as `tasker @TASK@ -p <project> -r`. You don't need to specify `-C`. If no project name is provided, one is auto-generated (e.g., `parallelr_1a811c`).

**Custom Configuration**: ptasker can have its own configuration files (`cfg/ptasker.yaml` and `~/ptasker/cfg/ptasker.yaml`). If these don't exist, it automatically falls back to the parallelr configs. This allows you to customize ptasker settings independently while maintaining a common default configuration.

## Requirements

**Python**: 3.6.8 or higher

**Platform**: Linux/Unix

**Standard Library**: pathlib, argparse, threading, subprocess, signal, logging, queue, csv, json, shlex, select, errno, fcntl

### Optional Python Modules

The script works without these modules but provides enhanced functionality when available. Dependencies are bundled in the `lib/` directory and loaded automatically.

**Check module availability**:
```bash
parallelr --check-dependencies
```

**PyYAML** (bundled: 6.0.1):
- **Purpose**: Load YAML configuration files (`cfg/parallelr.yaml`)
- **Without it**: Configuration files are ignored; only hardcoded defaults are used
- **Why use it**: Allows customizing workers, timeouts, logging levels, and all other settings without modifying code
- **Install**: `pip3 install --target=<path to lib> pyyaml`

**psutil** (bundled: 7.1.0):
- **Purpose**: Monitor memory and CPU usage per task during execution
- **Without it**: Memory/CPU metrics show 0.00 (not collected)
- **Why use it**: Essential for performance analysis, debugging resource issues, and capacity planning
- **Install**: `pip3 install --target=<path to lib> psutil`

**Custom library path**: Set `PARALLELR_LIB_PATH` environment variable to use an alternative library location (default: `/app/COOL/lib` if exists)

## Usage

### Command Line Arguments

#### Required Arguments

| Argument | Description |
|----------|-------------|
| `-T, --TasksDir PATHS...` | **[Optional with -A]** Directory, file paths, glob patterns, or template file:<br>• **Without -A**: Directory of task files, specific files, or glob patterns<br>• **With -A**: Single template file (not directory) where `@TASK@` is replaced<br>• **Omit with -A**: Execute commands directly without template (arguments-only mode)<br>• Examples: `-T /path/to/dir`, `-T /path/*.txt`, `-T template.sh -A args.txt` |
| `-C, --Command CMD` | Command template with `@TASK@` placeholder for task file path (file mode) or `@ARG@`/`@ARG_N@` placeholders for arguments (arguments mode) |
| | **Note**: Either `-T` or `-A` is required (or both) |

#### Execution Control

| Argument | Description |
|----------|-------------|
| `-r, --run` | Execute tasks (without this flag, runs in dry-run mode). **Dry-run mode** shows full command with environment variables (e.g., `HOSTNAME=value cmd`). **Execution mode** sets environment variables internally and passes them to subprocesses. |
| `-m, --max N` | Maximum parallel workers (default: 20, max: 100, overrides config) |
| `-t, --timeout N` | Task timeout in seconds (default: 600, max: 3600, overrides config) |
| `-s, --sleep N` | Delay between starting new tasks (0-60 seconds, default: 0.5). Prevents thundering herd. Use `-s 0` to disable |
| `--file-extension EXT` | Filter task files by extension(s). Single: `txt`, Multiple: `txt,log,dat` |
| `-A, --arguments-file FILE` | File containing arguments, one per line. Each line becomes a parallel task |
| `-E, --env-var NAME` | Environment variable name to set with argument value (e.g., HOSTNAME) |

#### Advanced Execution

| Argument | Description |
|----------|-------------|
| `-d, --debug` | Enable debug mode (set log level to DEBUG) |
| `-D, --daemon` | Run as background daemon (detached from session) |
| `--enable-stop-limits` | Enable automatic halt on excessive failures |
| `--no-task-output-log` | Disable detailed stdout/stderr logging to output file (enabled by default) |
| `--no-search, --no-fallback` | Disable automatic fallback search in standard TASKER directories. Files must exist in current directory. Use for strict path validation. |
| `-y, --yes` | Automatically confirm prompts (for automation/CI pipelines). Useful when fallback file resolution is used and you want to skip interactive confirmation. |

> **Note:** Be careful to distinguish between `-d` (lowercase, debug mode) and `-D` (uppercase, daemon mode). These are different flags with different purposes.

#### Process Management

| Argument | Description |
|----------|-------------|
| `--list-workers` | List all running parallelr processes (safe, read-only) |
| `-k, --kill [PID]` | Kill processes: `-k` kills all (requires confirmation), `-k PID` kills specific process |

#### Configuration

| Argument | Description |
|----------|-------------|
| `--check-dependencies` | Check optional Python module availability and exit |
| `--validate-config` | Validate configuration files and exit. Shows which configs are loaded and whether fallback is used |
| `--show-config` | Display current effective configuration and file locations |

### Basic Examples

```bash
# Dry-run to preview commands (safe, no execution)
# NOTE: Dry-run mode displays full commands including environment variable assignments
parallelr -T ./tasks -C "python3 @TASK@"

# Execute Python scripts with 5 workers
# NOTE: In execution mode, environment variables are set internally (not printed to stdout)
parallelr -T ./tasks -C "python3 @TASK@" -r -m 5

# Execute only .txt files from a directory
parallelr -T ./tasks --file-extension txt -C "process @TASK@" -r

# Execute specific files using shell glob patterns
parallelr -T ./tasks/*.py -C "python3 @TASK@" -r

# Execute from multiple sources
parallelr -T ./scripts -T ./tests -T config.json -C "process @TASK@" -r

# Filter multiple extensions
parallelr -T ./data --file-extension "csv,tsv,txt" -C "analyze @TASK@" -r

# Execute bash scripts with 600s timeout
parallelr -T ./scripts -C "bash @TASK@" -r -t 600

# Throttle resource consumption with 2-second delay between task starts
parallelr -T ./tasks -C "curl @TASK@" -r -s 2.0

# Run as daemon with auto-stop protection
parallelr -T ./tasks -C "python3 @TASK@" -r -D --enable-stop-limits

# Execute without detailed output logging (logging is enabled by default)
parallelr -T ./tasks -C "./process.sh @TASK@" -r --no-task-output-log

# Show version
parallelr --version

# List running workers
parallelr --list-workers

# Kill specific worker
parallelr -k 12345

# Kill all workers (requires 'yes' confirmation)
parallelr -k
```

### Arguments Mode (New Feature)

Arguments mode allows you to run the same template file/script with different arguments in parallel. Instead of creating multiple task files, you provide one template and a file containing arguments (one per line).

#### Basic Usage

**1. Environment Variable Mode** - Set an environment variable for each task:
```bash
# Create arguments file (e.g., hostnames.txt)
echo "server1.example.com
server2.example.com
server3.example.com" > hostnames.txt

# Run template.sh for each hostname with HOSTNAME environment variable
parallelr -T template.sh -A hostnames.txt -E HOSTNAME -C "bash @TASK@" -r
# Each task runs: HOSTNAME=<hostname> bash template.sh
```

**2. Command Argument Mode** - Replace @ARG@ in command with each argument:
```bash
# Run script with each hostname as command-line argument
parallelr -T process.py -A hostnames.txt -C "python @TASK@ --host @ARG@" -r
# Each task runs: python process.py --host <hostname>
```

**3. Combined Mode** - Use both environment variable and command argument:
```bash
parallelr -T script.sh -A hosts.txt -E HOSTNAME -C "bash @TASK@ @ARG@" -r
# Each task runs: HOSTNAME=<hostname> bash script.sh <hostname>
```

**4. Multi-Argument Mode** - Process multiple arguments per line with delimiters:
```bash
# Create multi-column arguments file (e.g., servers.txt)
echo "server1.example.com,8080,prod
server2.example.com,8081,dev
server3.example.com,8082,staging" > servers.txt

# Use comma separator with indexed placeholders
parallelr -T deploy.sh -A servers.txt -S comma -C "bash @TASK@ --host @ARG_1@ --port @ARG_2@ --env @ARG_3@" -r
# Each task runs: bash deploy.sh --host server1.example.com --port 8080 --env prod

# With multiple environment variables (comma-separated)
parallelr -T deploy.sh -A servers.txt -S comma -E HOSTNAME,PORT,ENV -C "bash @TASK@" -r
# Each task runs: HOSTNAME=server1.example.com PORT=8080 ENV=prod bash deploy.sh
```

**Supported Delimiters**:
- `space` - One or more space characters (space only, not tabs)
- `whitespace` - One or more whitespace characters (spaces, tabs, etc.)
- `tab` - One or more tabs
- `comma` - Comma (`,`)
- `semicolon` - Semicolon (`;`)
- `pipe` - Pipe (`|`)
- `colon` - Colon (`:`) - Common in config files like `/etc/passwd`

**Placeholders**:
- `@TASK@` - Template file path (File Mode only)
- `@ARG@` - First argument (backward compatibility)
- `@ARG_1@`, `@ARG_2@`, `@ARG_3@`, etc. - Individual arguments by position

**Environment Variable Validation**:
- **Fewer env vars than arguments**: Only available env vars are set, warning logged
- **More env vars than arguments**: Error logged, execution stops

#### Arguments-Only Mode (No Template)

The `-T` (template) argument is now **optional** when using `-A` (arguments file). This allows you to execute commands directly in parallel without needing a template file.

**Use Cases**:
- Execute simple commands for each argument (ping, curl, ssh, etc.)
- Run one-liner operations across multiple targets
- Quick parallel command execution without creating template files

**1. Direct Command Execution** - Use placeholders directly in command:
```bash
# Ping multiple hosts
echo "server1.example.com
server2.example.com
server3.example.com" > hosts.txt

parallelr -A hosts.txt -C "ping -c 1 @ARG@" -r
# Each task runs: ping -c 1 <hostname>
```

**2. Environment Variables Without Template**:
```bash
# SSH to multiple servers using environment variable
parallelr -A hosts.txt -E HOSTNAME -C "ssh $HOSTNAME uptime" -r
# Each task runs: HOSTNAME=<hostname> ssh $HOSTNAME uptime
```

**3. Multiple Arguments Without Template**:
```bash
# Create multi-column file
echo "server1.example.com,8080,prod
server2.example.com,8081,dev
server3.example.com,8082,staging" > servers.csv

# Use indexed placeholders directly
parallelr -A servers.csv -S comma -C "curl http://@ARG_1@:@ARG_2@/health" -r
# Each task runs: curl http://server1.example.com:8080/health

# Or with environment variables
parallelr -A servers.csv -S comma -E HOST,PORT,ENV -C "curl http://$HOST:$PORT/health" -r
# Each task runs: HOST=server1.example.com PORT=8080 ENV=prod curl http://$HOST:$PORT/health
```

**4. Complex One-Liners**:
```bash
# Execute complex commands for each target
parallelr -A databases.txt -E DB -C "mysqldump -h $DB -u backup --password=\$PASS mydb | gzip > backup_$DB.sql.gz" -r
```

**When to Use Template vs Arguments-Only**:
- **Use Template** (`-T file.sh`): When command logic is complex, multi-line, or reusable
- **Use Arguments-Only** (no `-T`): When command is simple, one-liner, or ad-hoc

**Important Notes**:
- When `-T` is used with `-A`, it must be a **single template file** (not a directory)
- Without `-T`, the command template (`-C`) must contain placeholders (`@ARG@`, `@ARG_N@`) or environment variables (`-E`) to use arguments
- All delimiter options (`-S`) work the same with or without template
- Environment variable mode (`-E`) works the same with or without template

#### ptasker Integration

ptasker mode automatically sets HOSTNAME when using arguments file:
```bash
# Automatically sets HOSTNAME environment variable for TASKER
ptasker -T template.txt -A hostnames.txt -p myproject -r
# Equivalent to: HOSTNAME=<hostname> tasker template.txt -p myproject -r
```

#### Arguments File Format

**Single Argument per Line**:
```text
# Comments start with #
server1.example.com
server2.example.com
# Empty lines are skipped

server3.example.com
server4.example.com
```

**Multiple Arguments per Line** (with `-S` delimiter):
```text
# Space-separated (use -S space)
server1.example.com 8080 prod
server2.example.com 8081 dev

# Tab-separated (use -S tab)
# Note: Use actual tab character (\t) between fields
server1.example.com<TAB>8080<TAB>prod
server2.example.com<TAB>8081<TAB>dev

# Comma-separated (use -S comma)
server1.example.com,8080,prod
server2.example.com,8081,dev

# Semicolon-separated (use -S semicolon)
server1.example.com;8080;prod
server2.example.com;8081;dev

# Pipe-separated (use -S pipe)
server1.example.com|8080|prod
server2.example.com|8081|dev

# Colon-separated (use -S colon) - Common in /etc/passwd format
server1.example.com:8080:prod
server2.example.com:8081:dev
```

#### Use Cases

- **Infrastructure Testing**: Test same script across multiple servers
- **Data Processing**: Process multiple data files with same algorithm
- **API Testing**: Test endpoints with different parameters
- **Configuration Deployment**: Apply same template to different environments

## Configuration

### Configuration Hierarchy

parallelr uses a **hierarchical merge** configuration system with automatic fallback for symlinks.

#### How Configuration Merging Works

**IMPORTANT**: Both configs are loaded and merged. The user config does NOT replace the script config - it only overrides specific values you choose to customize.

**Loading Process**:
1. **Start with hardcoded defaults** (built into the code)
2. **Load Script Configuration** - overrides defaults
3. **Load User Configuration** - overrides specific script config values

**What This Means**:
- ✓ User config values override matching script config values
- ✓ Script config provides all values not specified in user config
- ✓ System limits (`max_allowed_*`) always come from script config
- ✓ Security settings always come from script config (cannot be overridden)
- ✓ You only need to specify values you want to change in user config

**Example Merge**:

Script config (`cfg/parallelr.yaml`):
```yaml
limits:
  max_workers: 20
  timeout_seconds: 600
  max_allowed_workers: 100
logging:
  level: "INFO"
```

User config (`~/parallelr/cfg/parallelr.yaml`):
```yaml
limits:
  max_workers: 50
logging:
  level: "DEBUG"
```

**Effective Configuration** (merged result):
- `max_workers: 50` ← from user config (overrides script)
- `timeout_seconds: 600` ← from script config (not overridden)
- `max_allowed_workers: 100` ← from script config (system limit)
- `level: "DEBUG"` ← from user config (overrides script)

#### Configuration Files

1. **Script Configuration** (`cfg/parallelr.yaml`)
   - Ships with the tool
   - Defines system defaults and maximum limits
   - Controls security boundaries
   - Provides base values for all settings
   - Always loaded first

2. **User Configuration** (`~/parallelr/cfg/parallelr.yaml`)
   - Optional user-specific overrides
   - Only specify values you want to customize
   - Subject to validation against script limits
   - Merged on top of script config
   - Allows customization within safe boundaries

#### Symlink Config Fallback

When using symlinks (e.g., `ptasker`), the tool first looks for symlink-specific configs (`ptasker.yaml`), then falls back to the original script's config (`parallelr.yaml`) if not found. This allows:
- Custom configurations per symlink (optional)
- Automatic fallback to default parallelr config
- Clear indication in validation output when fallback is used

**Fallback Example**:
- `ptasker` looks for `cfg/ptasker.yaml` → not found
- Falls back to `cfg/parallelr.yaml` → found and used
- Same for user config: `~/ptasker/cfg/ptasker.yaml` → `~/parallelr/cfg/parallelr.yaml`

#### Checking Your Configuration

Use `--validate-config` to see which configs are loaded and whether fallback is active:
```bash
parallelr --validate-config
```

Use `--show-config` to see the complete effective configuration (after merging):
```bash
parallelr --show-config
```

### Configuration Sections

#### 1. Limits Section

Controls execution limits and safety thresholds.

```yaml
limits:
  # Worker and timeout settings
  max_workers: 20              # Number of parallel workers
  timeout_seconds: 600         # Task timeout (10 minutes)
  wait_time: 0.1               # Polling interval when all workers busy (config file only, 0.01-10.0 seconds)
  task_start_delay: 0.5       # Delay between starting new tasks (0-60 seconds, prevents thundering herd)
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

- **task_start_delay**: Delay in seconds between starting new tasks. **Default: 0.5 seconds** to prevent thundering herd problem. Range: 0-60 seconds.
  - `0`: No delay - tasks start as fast as possible (use `-s 0` to disable default delay)
  - `0.1-1.0`: Light throttling for API rate limits or I/O management (default is 0.5)
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

- **use_process_groups**: Enables process group management for comprehensive cleanup of child processes.
  - `true` (recommended): Tasks and all their child processes are terminated together
    - POSIX: Uses `setsid()` to create new process group, terminates with `killpg()`
    - Windows: Uses `CREATE_NEW_PROCESS_GROUP`, terminates with `CTRL_BREAK_EVENT`
    - Prevents orphaned child processes when tasks timeout or are cancelled
    - Essential for scripts that spawn background jobs or subprocesses
  - `false`: Only the direct task process is terminated
    - Child processes may outlive parent and become orphans
    - Use only if tasks are guaranteed not to spawn children

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

**Remember**: You only need to specify values you want to change. All other settings will come from the script config.

Create `~/parallelr/cfg/parallelr.yaml`:

```yaml
# User overrides for parallelr
# Only specify settings you want to customize
# All other values will come from script config (cfg/parallelr.yaml)

limits:
  max_workers: 50              # Override default of 20 (capped at max_allowed_workers: 100)
  timeout_seconds: 1800        # Override default of 600 (capped at max_allowed_timeout: 3600)
  # Note: timeout_seconds not specified, so script default (600) will be used
  # Note: max_allowed_workers always comes from script config (100)

execution:
  workspace_isolation: true    # Override default (false) - use isolated workspaces

logging:
  level: "DEBUG"               # Override default (INFO) - more verbose logging
  max_log_size_mb: 50          # Override default (10) - larger logs before rotation
  # Note: Other logging settings come from script config
```

**What Happens**:
- Settings you specify in user config override script config
- Settings you DON'T specify come from script config
- System limits (`max_allowed_*`) always enforced from script config
- Security settings always come from script config (cannot be overridden)

**Validation Rules**:
- User cannot override `security` section
- `max_workers`, `timeout_seconds`, `max_output_capture` are capped at `max_allowed_*` values
- Invalid values cause warnings and fall back to script defaults
- Type mismatches are automatically converted if possible

**Minimal Example** (only override what you need):
```yaml
# Just increase workers - everything else from script config
limits:
  max_workers: 50
```

### Validating Configuration

Use `--validate-config` to check configuration status and see which files are loaded:

```bash
parallelr --validate-config
# or
ptasker --validate-config
```

**Example Output (configs loaded)**:
```text
✓ Configuration is valid
✓ Script config: /app/COOL/parallelr/cfg/parallelr.yaml
✓ User config: /home/<TNR>/parallelr/cfg/parallelr.yaml
✓ Working dir: /home/<TNR>/parallelr/workspace
✓ Log dir: /home/<TNR>/parallelr/logs
✓ Workspace mode: Shared
✓ Workers: 20 (max allowed: 100)
✓ Timeout: 600s (max allowed: 3600s)
✓ Max Output Capture: 1000 (max allowed: 10000)
```

**Example Output (with fallback)**:
```text
✓ Configuration is valid
✓ Script config: /app/COOL/parallelr/cfg/parallelr.yaml (fallback from ptasker.yaml)
✓ User config: /home/<TNR>/parallelr/cfg/parallelr.yaml (fallback from ptasker.yaml)
✓ Working dir: /home/<TNR>/ptasker/workspace
✓ Log dir: /home/<TNR>/ptasker/logs
✓ Workspace mode: Shared
✓ Workers: 20 (max allowed: 100)
✓ Timeout: 600s (max allowed: 3600s)
✓ Max Output Capture: 1000 (max allowed: 10000)
```

**Example Output (no configs)**:
```text
✓ Configuration is valid
  Script config: Not found (using defaults)
  User config: Not found (using defaults)
✓ Working dir: /home/<TNR>/parallelr/workspace
✓ Log dir: /home/<TNR>/parallelr/logs
✓ Workspace mode: Shared
✓ Workers: 20 (max allowed: 100)
✓ Timeout: 600s (max allowed: 3600s)
✓ Max Output Capture: 1000 (max allowed: 10000)
```

**Status Indicators**:
- `✓` = Config file loaded successfully
- `  ` (no checkmark) = Config file not found, using defaults
- `(fallback from X.yaml)` = Looked for X.yaml, fell back to parallelr.yaml

## Advanced Features

### Daemon Mode

Run parallelr as a background daemon, detached from your terminal session.

```bash
# Start as daemon
parallelr -T ./tasks -C "bash @TASK@" -r -D

# Check running daemons
parallelr --list-workers

# View daemon logs
tail -f ~/parallelr/logs/parallelr_<PID>_*.log

# Kill daemon
parallelr -k <PID>
```

**How It Works**:
- Uses Unix double-fork technique
- Detaches from terminal (can close SSH session)
- Redirects stdout/stderr to `/dev/null`
- All output goes to log files
- Process ID tracked in `~/parallelr/pids/parallelr.pids`

**Limitations**:
- Linux/Unix only
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
parallelr -T ./tasks -C "python @TASK@" -r --enable-stop-limits
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
```text
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
parallelr --list-workers
```

**Output**:
```text
Found 2 running parallel-tasker process(es):

PID      Status     Start Time           Log File                                    Summary File
------------------------------------------------------------------------------------------------------------
12345    running    2025-09-29 14:30:15  parallelr_12345_29Sep25_143015.log         parallelr_12345_29Sep25_143015_summary.csv
12346    running    2025-09-29 14:32:01  parallelr_12346_29Sep25_143201.log         parallelr_12346_29Sep25_143201_summary.csv
```

### Kill Processes

**Kill specific process**:
```bash
parallelr -k 12345
```

**Kill all processes** (requires confirmation):
```bash
parallelr -k
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
```text
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
```csv
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
```text
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

```text
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
- Working Dir: /home/<TNR>/parallelr/workspace
- Workspace Type: Shared
- Log Dir: /home/<TNR>/parallelr/logs

Auto-Stop Protection:
- Stop Limits: Disabled

Log Files:
- Main Log: /home/<TNR>/parallelr/logs/parallelr_12345_29Sep25_143015.log (rotating)
- Summary: /home/<TNR>/parallelr/logs/parallelr_12345_29Sep25_143015_summary.csv (session-specific)
- Output: /home/<TNR>/parallelr/logs/parallelr_12345_29Sep25_143015_output.txt (enabled by default, disable with --no-task-output-log)

Process Info:
- Process ID: 12345
- Workers: 20
```

### JSONL Results Format

Starting with version 1.0.0, parallelr generates results in **JSONL (JSON Lines)** format instead of CSV for better flexibility and data richness.

**Location**: `~/parallelr/logs/parallelr_{PID}_{TIMESTAMP}_results.jsonl`

**Format**: One JSON object per line
- **Session metadata** (first line): Configuration, hostname, user
- **Task results** (subsequent lines): Detailed execution data for each task

**Example**:
```jsonl
{"type":"session","session_id":"parallelr_12345_29Sep25_143015","hostname":"server1","user":"username","command_template":"bash @TASK@","max_workers":5}
{"type":"task","start_time":"2025-09-29T14:30:15","end_time":"2025-09-29T14:30:17","status":"SUCCESS","process_id":"12345","worker_id":1,"task_file":"./tasks/task1.sh","command_executed":"bash ./tasks/task1.sh","exit_code":0,"duration_seconds":2.75,"memory_mb":45.23,"cpu_percent":12.5,"error_message":""}
```

### PSR - Parallelr Summary Report Tool

**psr.py** is a standalone tool for analyzing JSONL results and generating custom CSV reports with filtering and column selection.

**Location**: `bin/psr.py`

#### Basic Usage

**1. Display all results as CSV** (default columns):
```bash
python bin/psr.py ~/parallelr/logs/parallelr_12345_29Sep25_143015_results.jsonl
```

**Default columns**:
```
START_TIME, END_TIME, STATUS, PROCESS_ID, WORKER_ID, COMMAND_EXECUTED, EXIT_CODE, DURATION_SECONDS, MEMORY_MB, CPU_PERCENT, ERROR_MESSAGE
```

**2. Custom columns** (including nested fields):
```bash
# Basic columns
python bin/psr.py results.jsonl --columns start_time,status,exit_code,duration_seconds

# Access nested fields (e.g., environment variables)
python bin/psr.py results.jsonl --columns start_time,env_vars.HOSTNAME,env_vars.TASK_ID,status
```

**3. Filter results**:
```bash
# Show only failed tasks
python bin/psr.py results.jsonl --filter status=FAILED

# Show successful tasks
python bin/psr.py results.jsonl --filter status=SUCCESS

# Exclude successful tasks
python bin/psr.py results.jsonl --filter status!=SUCCESS
```

**4. Save to CSV file**:
```bash
python bin/psr.py results.jsonl --output report.csv
```

**5. Show execution statistics**:
```bash
python bin/psr.py results.jsonl --stats
```

**Example output**:
```text
============================================================
EXECUTION STATISTICS
============================================================

Session ID: parallelr_12345_29Sep25_143015
Hostname: server1
User: username
Command Template: bash @TASK@

Total Tasks: 100

By Status:
  FAILED: 5 (5.0%)
  SUCCESS: 92 (92.0%)
  TIMEOUT: 3 (3.0%)

Total Duration: 1534.50s
Average Duration: 15.35s per task
============================================================
```

#### Advanced Examples

**Combine filtering and custom columns**:
```bash
# Failed tasks with specific details
python bin/psr.py results.jsonl \
  --filter status=FAILED \
  --columns task_file,exit_code,duration_seconds,error_message \
  --output failed_tasks.csv
```

**Extract environment variable data**:
```bash
# Tasks with specific environment variables
python bin/psr.py results.jsonl \
  --columns start_time,env_vars.HOSTNAME,env_vars.PORT,env_vars.ENV,status \
  --output deployment_report.csv
```

**Performance analysis**:
```bash
# Top memory consumers
python bin/psr.py results.jsonl \
  --columns task_file,memory_mb,duration_seconds,cpu_percent \
  | sort -t',' -k2 -nr \
  | head -20
```

#### Nested Field Access

Use dot notation to access nested JSON fields:

**Available nested fields**:
- `env_vars.VARIABLE_NAME` - Environment variables set for the task
- `arguments.0`, `arguments.1`, etc. - Individual arguments (if using -A mode)

**Example**:
```bash
# Show tasks with their environment variables
python bin/psr.py results.jsonl \
  --columns worker_id,env_vars.SERVER,env_vars.TASK_ID,status,duration_seconds
```

#### Integration with Analysis Tools

**Import into Excel/Google Sheets**:
```bash
python bin/psr.py results.jsonl --output report.csv
# Open report.csv in Excel/Google Sheets
```

**Import into pandas (Python)**:
```python
import pandas as pd
df = pd.read_csv('report.csv')
```

**Import into R**:
```r
library(readr)
data <- read_csv('report.csv')
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
parallelr --help
```

**Validate setup**:
```bash
parallelr --check-dependencies  # Check optional modules
parallelr --validate-config     # Validate configuration
parallelr --show-config         # View current config
```

**Test with dry-run**:
```bash
parallelr -T ./tasks -C "bash @TASK@"
```

## Security Considerations

### Template/Arguments File Path Resolution

parallelr uses a multi-tier file resolution system with security protections:

#### Resolution Order

When you specify a template (`-T`) or arguments file (`-A`):

1. **Check explicit path**: If file exists at specified location (including relative paths like `../template.sh`), use it
2. **Fallback search** (if not found and `--no-search` not set): Search in standard TASKER directories:
   - `~/tasker/test_cases/`
   - `~/TASKER/test_cases/`
   - `~/tasker/test_cases/functional/`
   - `~/TASKER/test_cases/functional/`

#### Security Model

**Explicit Paths** (user-provided):
- Trust user intent - user has shell access anyway
- Allow any valid path including `../sibling_dir/file.txt`
- Rely on filesystem permissions for access control
- Fail if file doesn't exist or isn't readable

**Fallback Paths** (automatic search):
- Strict containment validation
- Prevent path traversal attacks
- Verify resolved path stays within base directory
- User confirmation required before using fallback files (unless `--yes` flag)

#### Fallback Behavior

When fallback finds a file:
1. **INFO messages** show resolved path and fallback location
2. **Interactive prompt** asks for confirmation (unless `--yes` flag)
3. **User can decline** to use the fallback file

**Example output**:
```bash
$ ptasker -T hello.txt -A hosts.txt -r
2025-10-30 08:00:00 - INFO - Template file 'hello.txt' found via fallback search at: /home/user/tasker/test_cases/hello.txt
2025-10-30 08:00:00 - INFO - Fallback location: /home/user/tasker/test_cases

============================================================
WARNING: File found via fallback search
============================================================
Requested file:  hello.txt
Found at:        /home/user/tasker/test_cases/hello.txt
Search location: /home/user/tasker/test_cases
============================================================
Continue with this file? [y/N]:
```

#### Controlling Fallback Behavior

**Disable fallback search** (strict mode):
```bash
parallelr -T template.txt -A args.txt --no-search -r
# Fails if files not in current directory
```

**Auto-confirm fallback** (automation/CI):
```bash
parallelr -T template.txt -A args.txt --yes -r
# No prompts, automatically uses fallback files
```

**Use explicit paths** (bypass fallback):
```bash
parallelr -T /absolute/path/template.txt -A ../args.txt -r
# No fallback search, uses exact paths specified
```

#### Why This Design?

- **Usability**: Automatic fallback search for convenience
- **Transparency**: INFO messages show which files are being used
- **Security**: User awareness and consent before using unexpected files
- **Flexibility**: Options for strict mode (`--no-search`) or automation (`--yes`)

### Input Validation

- **Task files**: Size checked against `max_file_size`
- **Command arguments**: Length checked against `max_argument_length`
- **Command parsing**: Uses `shlex.split()` to prevent injection
- **Path handling**: Absolute paths resolved, filesystem permissions enforced

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

## Testing

The project includes a comprehensive test suite covering functionality, edge cases, and security.

### Dual Python Testing Strategy

**CRITICAL**: This project uses different Python versions for local and CI testing:

| Environment | Python Version | Purpose | Requirement |
|------------|----------------|---------|-------------|
| **Local Development** | **3.6.8 ONLY** | Verify production compatibility | **MANDATORY** - Must test with exact production version |
| **GitHub CI/CD** | **3.9+** | Modern tooling (pytest, linters, coverage) | Uses 3.6.8-compatible syntax |

**Why?** The production environment runs Python 3.6.8, so all code must be compatible. However, modern testing tools work better on Python 3.9+. The same test suite runs on both versions to ensure correctness.

### Local Testing (Python 3.6.8)

```bash
# CRITICAL: Verify you have exactly Python 3.6.8
python -V  # Must show: Python 3.6.8
python --version  # If different, find python3.6 interpreter

# Install test dependencies (Python 3.6.8 compatible versions)
pip install -r tests/requirements-test-py36.txt

# Run all tests
pytest tests/ -v

# Run specific test categories
pytest tests/unit/ -v          # Unit tests
pytest tests/integration/ -v   # Integration tests
pytest tests/security/ -v      # Security tests

# Run with coverage
pytest tests/ --cov=bin/parallelr.py --cov-report=html
```

### CI Testing (Python 3.9+)

GitHub Actions automatically runs tests on **Python 3.9** with:
- Full pytest suite
- Code coverage reporting
- Linting (pylint, flake8)
- Legacy bash test suites

**Both local (3.6.8) and CI (3.9) tests must pass before merging.**

### Test Categories

- **Unit Tests (42)**: Placeholder replacement, input validation, exception handling
- **Integration Tests (47)**: File mode, arguments mode, daemon mode, workspace management, signal handling
- **Security Tests (20)**: Command injection prevention, path traversal validation

### Python Compatibility Notes

**All code must work on Python 3.6.8:**
- ✅ Use `stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True`
- ❌ Never use `capture_output=True` or `text=True` (Python 3.7+)
- ✅ Use `typing.List[str]` for type hints
- ❌ Never use `list[str]` (Python 3.9+)

For detailed testing documentation, see [tests/README.md](tests/README.md).

---

## Quick Reference

### Essential Commands

```bash
# Dry-run (preview)
parallelr -T <dir> -C "<command> @TASK@"

# Execute
parallelr -T <dir> -C "<command> @TASK@" -r

# Custom workers/timeout
parallelr -T <dir> -C "<command> @TASK@" -r -m 10 -t 300

# Daemon mode
parallelr -T <dir> -C "<command> @TASK@" -r -D

# List workers
parallelr --list-workers

# Kill worker
parallelr -k <PID>

# Check dependencies
parallelr --check-dependencies

# View config
parallelr --show-config

# Validate config
parallelr --validate-config
```