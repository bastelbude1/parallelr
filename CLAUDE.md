# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**parallelr** is a Python 3.6.8-compatible parallel task execution framework. It executes tasks from a directory in parallel using a configurable number of workers, with robust error handling, resource monitoring, and workspace management.

## ⚠️ CRITICAL: Python 3.6.8 Compatibility Requirement

**MANDATORY**: All code, including tests, MUST be compatible with Python 3.6.8.

### Dual Python Testing Strategy

This project uses **different Python versions for local vs CI testing**:

| Environment | Python Version | Purpose | When to Use |
|------------|----------------|---------|-------------|
| **Local Development** | **3.6.8 ONLY** | Verify production compatibility | **ALWAYS** - Test with exact production version before committing |
| **GitHub CI/CD** | **3.9+** | Modern tooling (pytest 7.x, linters, coverage) | **Automatic** - Runs on every push |

**Why this dual approach?**

1. **Production Requirement**: The target production environment uses Python 3.6.8 exclusively
2. **Tool Compatibility**: Modern testing tools (pytest 7.x, pytest-cov 4.x, pylint 3.x) require Python 3.8+, while CI runs on 3.9+
3. **Safety**: Testing on both ensures code works on 3.6.8 while leveraging modern tooling
4. **Same Test Suite**: Both environments run identical tests - only the interpreter version differs

**CRITICAL RULES:**

- ✅ **ALWAYS** test locally with Python 3.6.8 before pushing
- ✅ **ALL** code must use Python 3.6.8-compatible syntax
- ✅ **BOTH** local (3.6.8) and CI (3.9) tests must pass
- ❌ **NEVER** use Python 3.7+ features, even if CI tests pass

### Python 3.6.8 Compatibility Rules

**FORBIDDEN** (Python 3.7+):
- ❌ `subprocess.run(capture_output=True)` - Use `stdout=subprocess.PIPE, stderr=subprocess.PIPE` instead
- ❌ `subprocess.run(text=True)` - Use `universal_newlines=True` instead
- ❌ `from __future__ import annotations` - Not available in 3.6
- ❌ Dataclass `field(default_factory=...)` with mutable defaults - Limited support

**FORBIDDEN** (Python 3.8+):
- ❌ Walrus operator `:=`
- ❌ Positional-only parameters `/` in function definitions
- ❌ `functools.cached_property`

**FORBIDDEN** (Python 3.9+):
- ❌ `dict | dict` syntax (use `{**dict1, **dict2}`)
- ❌ `list[str]` type hints without `from typing import List` (use `List[str]`)
- ❌ `str.removeprefix()` / `str.removesuffix()`

**ALLOWED** (Python 3.6+):
- ✅ f-strings (introduced in 3.6.0)
- ✅ Type hints from `typing` module (`List`, `Dict`, `Optional`, etc.)
- ✅ `async`/`await`
- ✅ Underscores in numeric literals (1_000_000)

### Testing Compatibility Examples

**subprocess.run - CRITICAL for tests:**

```python
# ❌ WRONG (Python 3.7+) - Tests will FAIL on Python 3.6.8
result = subprocess.run(['cmd'], capture_output=True, text=True)

# ✅ CORRECT (Python 3.6.8+) - Works everywhere
result = subprocess.run(
    ['cmd'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    universal_newlines=True
)
```

**Type hints:**

```python
# ❌ WRONG (Python 3.9+)
def process_items(items: list[str]) -> dict[str, int]:
    pass

# ✅ CORRECT (Python 3.6+)
from typing import List, Dict

def process_items(items: List[str]) -> Dict[str, int]:
    pass
```

**Dictionary merging:**

```python
# ❌ WRONG (Python 3.9+)
merged = dict1 | dict2

# ✅ CORRECT (Python 3.6+)
merged = {**dict1, **dict2}
```

### Local Testing Workflow (Python 3.6.8)

**Before every commit:**

```bash
# 1. VERIFY Python version
python -V  # Must show: Python 3.6.8
# If not 3.6.8, find it: which python3.6

# 2. Install Python 3.6.8 compatible dependencies
pip install -r tests/requirements-test-py36.txt

# 3. Run all tests
pytest tests/ -v

# 4. Verify syntax compatibility
python -m py_compile bin/parallelr.py
python -m py_compile tests/**/*.py

# 5. Run specific test suites
pytest tests/unit/ -v           # Unit tests
pytest tests/integration/ -v    # Integration tests
pytest tests/security/ -v       # Security tests

# 6. Test with coverage
pytest tests/ --cov=bin/parallelr.py --cov-report=html
```

### CI Testing (GitHub Actions with Python 3.9)

**Automatic on every push:**

```yaml
# .github/workflows/test.yml uses Python 3.9
- uses: actions/setup-python@v5
  with:
    python-version: '3.9'
```

**CI runs:**
- Full pytest suite (same tests as local)
- Code coverage (codecov upload)
- Linting (pylint, flake8)
- Legacy bash test suites

**CI uses modern tool versions:**
CI runs with Python 3.9+ and uses modern testing tools for better performance and features. However, test dependencies are pinned for compatibility - see `tests/requirements-test.txt` for exact versions:
- pytest 7.x (Python 3.8+ compatible)
- pytest-cov 4.x for coverage reporting
- pylint 3.x for code quality checks

**IMPORTANT**: CI may run newer tool versions, but all production code in `bin/parallelr.py` must remain compatible with Python 3.6.8 as specified in the requirements files!

### Verification Checklist

Before pushing any code:

- [ ] Tested locally with Python **3.6.8** (not 3.7, 3.8, 3.9, etc.)
- [ ] No `capture_output=True` or `text=True` in subprocess calls
- [ ] All type hints use `typing` module imports (`List`, `Dict`, not `list`, `dict`)
- [ ] No walrus operators (`:=`)
- [ ] No dictionary union operators (`|`)
- [ ] All tests pass with `pytest tests/ -v`
- [ ] Code compiles with `python -m py_compile`

### Common Pitfalls

**Pitfall 1**: Testing with wrong Python version
```bash
# ❌ WRONG - Using system Python (might be 3.9+)
python -V  # Shows Python 3.9.2
pytest tests/ -v  # Tests pass

# ✅ CORRECT - Verify 3.6.8 first
python3.6 -V  # Shows Python 3.6.8
python3.6 -m pytest tests/ -v  # Tests must pass
```

**Pitfall 2**: Using Python 3.7+ features because CI passes
```python
# CI with Python 3.9 will pass this, but production will FAIL
result = subprocess.run(['cmd'], capture_output=True)  # ❌ Python 3.7+

# Must use Python 3.6 compatible syntax
result = subprocess.run(['cmd'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # ✅
```

**Pitfall 3**: Assuming newer pytest syntax works on 3.6.8
```python
# Some pytest features require newer Python
# Always test with Python 3.6.8 locally to catch these
```

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

### PID Management

**PID Lifecycle:**
- PIDs are registered in `~/parallelr/pids/parallelr.pids` when a process starts (parallelr.py:421-439)
- PIDs are unregistered when execution completes normally or via explicit kill command
- **Guaranteed cleanup**: try-finally ensures PID unregistration even on exceptions (parallelr.py:1774-1776)
- **Automatic stale PID cleanup**: Dead PIDs are removed on every startup (parallelr.py:492-552, called at 1055)

**PID File Behavior:**
- Multiple parallelr instances can run simultaneously, all tracked in the same PID file
- Duplicate PIDs are automatically prevented via set-based deduplication
- Stale PIDs (from crashed/killed processes) are cleaned up automatically when a new instance starts
- File is removed entirely when last process completes
- `--list-workers` and `-k` commands only operate on validated running processes

**Implementation Details:**
- `cleanup_stale_pids()`: Validates each PID using `psutil.pid_exists()` or `os.kill(pid, 0)`
- Runs automatically during `ParallelTaskManager` initialization
- Logs info message when stale PIDs are removed
- Preserves PIDs of actually running processes

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
- **Logs**: `~/parallelr/logs/parallelr_{date}_{unique_id}.log` (e.g., `parallelr_04Nov25_k8m2p5.log`)
- **Summary**: `~/parallelr/logs/parallelr_{date}_{unique_id}_summary.csv`
- **Task output**: `~/parallelr/logs/parallelr_{date}_{unique_id}_output.txt`
- **PID tracking**: `~/parallelr/pids/parallelr.pids`
- **Workspace**: `~/parallelr/workspace/` or `~/parallelr/workspace/pid{PID}_worker{N}/`

**Note**: Log files use a simplified naming format with date (DDmmmYY) and a 6-character unique identifier instead of PID and full timestamp. All log files are session-specific with unique names.

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
- Path resolution with security protections (see below)

### Template/Arguments File Path Resolution
The tool uses a multi-tier file resolution system:

**Resolution Order:**
1. Check if file exists at explicit path (including relative paths like `../template.sh`)
2. If not found and `--no-search` not set, search fallback locations:
   - `~/tasker/test_cases/`
   - `~/TASKER/test_cases/`
   - `~/tasker/test_cases/functional/`
   - `~/TASKER/test_cases/functional/`

**Security Model:**
- **Explicit paths**: Trust user intent, rely on filesystem permissions
- **Fallback paths**: Strict containment validation using `Path.resolve()` + `Path.relative_to()`
- **Fallback requires confirmation**: Interactive prompt unless `--yes` flag is set
- **INFO messages**: Show resolved path and fallback location when fallback is used

**New Flags:**
- `--no-search` / `--no-fallback`: Disable fallback search (strict mode)
- `-y` / `--yes`: Auto-confirm fallback usage (for automation/CI)

**Implementation:** See `_resolve_template_path()` (parallelr.py:~1087-1184) and `_prompt_fallback_confirmation()` (parallelr.py:~1186-1219)

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

### ⛔ CRITICAL: Never Merge Pull Requests

**ABSOLUTE RULE**: Claude Code must NEVER merge pull requests to master. This must ALWAYS be done manually by the human developer.

**What Claude CAN do:**
- ✅ Create feature branches
- ✅ Commit changes to feature branches
- ✅ Push to feature branches
- ✅ Create pull requests
- ✅ Review pull requests
- ✅ Provide merge recommendations

**What Claude CANNOT do:**
- ❌ **NEVER** run `gh pr merge`
- ❌ **NEVER** run `git merge` to master
- ❌ **NEVER** merge PRs via any method (web, CLI, API)
- ❌ **NEVER** assume a PR should be auto-merged even if CI passes

**Why manual merging is required:**
- Human review ensures quality control
- Allows final verification before master integration
- Prevents accidental breaking changes
- Maintains clear audit trail of who approved changes

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

### Pull Request Guidelines

**Before Creating a PR:**
1. Ensure all tests pass locally
2. Update documentation (README.md, docstrings)
3. Add test coverage for new features
4. Follow existing code style and conventions

**PR Process:**
1. **Create PR** from your feature branch to `master`
2. **Code Review** is required before merging
   - Address review comments promptly
   - Update PR based on feedback
3. **Merge Strategy**: Squash and merge preferred
   - Keeps commit history clean
   - Single commit per feature/fix on master
   - PR description becomes commit message
4. **After Merge**: Delete the feature branch

### Commit Message Guidelines

Use clear, descriptive commit messages:
- **Format**: `<type>: <short description>`
- **Types**: feat, fix, docs, test, refactor, chore
- **Examples**:
  - `feat: Add multi-argument support with delimiter options`
  - `fix: Prevent IndexError in environment variable validation`
  - `docs: Update README with multi-argument examples`
  - `test: Add comprehensive delimiter test suite`

### Code Review Expectations

**As a Contributor:**
- Respond to review comments within 48 hours
- Be open to suggestions and constructive feedback
- Explain your design decisions when asked
- Update PR based on feedback

**As a Reviewer:**
- Focus on correctness, security, and maintainability
- Provide specific, actionable feedback
- Approve if minor issues can be addressed in follow-up
- Be respectful and constructive