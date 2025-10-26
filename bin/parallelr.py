#!/usr/bin/env python3
"""
Parallel Task Executor - Python 3.6.8 Compatible

A robust parallel task execution framework with simplified configuration
and practical security measures.
"""

import os
import sys
from pathlib import Path

# Add custom library path if configured
def add_custom_lib_path():
    """Add custom library path if configured."""
    # Add project lib path first
    script_dir = Path(__file__).resolve().parent
    project_lib = script_dir.parent / 'lib'
    if project_lib.exists() and str(project_lib) not in sys.path:
        sys.path.insert(0, str(project_lib))

    # Then add custom path from environment variable
    custom_path = os.getenv('PARALLELR_LIB_PATH', '/app/COOL/lib')
    if custom_path and Path(custom_path).exists():
        if custom_path not in sys.path:
            sys.path.insert(0, custom_path)

add_custom_lib_path()

import argparse
import time
import logging
import signal
import threading
import subprocess
import queue
import csv
import json
import shlex
import select
import errno
import fcntl
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from enum import Enum

# Optional imports with fallbacks
try:
    import yaml # type: ignore
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

try:
    import psutil # type: ignore
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

class TaskStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"

class TaskResult:
    """Data class for task execution results."""
    def __init__(self, task_file, command, start_time, end_time=None, status=None, 
                 exit_code=None, stdout="", stderr="", error_message="", duration=0.0,
                 worker_id=0, memory_usage=0.0, cpu_usage=0.0):
        self.task_file = task_file
        self.command = command
        self.start_time = start_time
        self.end_time = end_time
        self.status = status
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.error_message = error_message
        self.duration = duration
        self.worker_id = worker_id
        self.memory_usage = memory_usage
        self.cpu_usage = cpu_usage

    def to_log_line(self):
        """Convert task result to CSV log line with process info."""
        end_time_str = self.end_time.isoformat() if self.end_time else ''
        exit_code_str = self.exit_code if self.exit_code is not None else ''
        error_msg_str = self.error_message.replace(';', '|') if self.error_message else ''
        
        return f"{self.start_time.isoformat()};{end_time_str};{self.status.value};{os.getpid()};{self.worker_id};{self.task_file};{self.command};{exit_code_str};{self.duration:.2f};{self.memory_usage:.2f};{self.cpu_usage:.2f};{error_msg_str}"

class ParallelTaskExecutorError(Exception):
    pass

class SecurityError(ParallelTaskExecutorError):
    pass

class ConfigurationError(ParallelTaskExecutorError):
    pass

class LimitsConfig:
    """Core execution limits with user override protection."""
    def __init__(self):
        self.max_workers = 20
        self.timeout_seconds = 600
        self.wait_time = 0.1
        self.task_start_delay = 0.0  # Delay between starting new tasks (seconds)
        self.max_output_capture = 1000
        self.max_allowed_workers = 100
        self.max_allowed_timeout = 3600
        self.max_allowed_output = 10000
        self.stop_limits_enabled = False
        self.max_consecutive_failures = 5
        self.max_failure_rate = 0.5
        self.min_tasks_for_rate_check = 10

class SecurityConfig:
    """Basic security settings."""
    def __init__(self):
        self.max_argument_length = 1000

class ExecutionConfig:
    """Task execution settings."""
    def __init__(self):
        self.workspace_isolation = False
        self.use_process_groups = True

class LoggingConfig:
    """Logging configuration."""
    def __init__(self):
        self.level = "INFO"
        self.console_format = "%(asctime)s - %(levelname)s - %(message)s"
        self.file_format = "%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s"
        self.custom_date_format = "%d%b%y_%H%M%S"
        self.max_log_size_mb = 10
        self.backup_count = 5

class AdvancedConfig:
    """Optional advanced settings."""
    def __init__(self):
        self.max_file_size = 1048576
        self.memory_limit_mb = None
        self.retry_failed_tasks = False

class Configuration:
    """Configuration manager with script defaults and optional user overrides."""

    def __init__(self, script_path):
        self.script_name = Path(script_path).stem
        self.original_script_name = self._get_original_script_name(script_path)

        # Track what was actually loaded (initialize before calling path methods)
        self.script_config_loaded = False
        self.script_config_is_fallback = False
        self.user_config_loaded = False
        self.user_config_is_fallback = False

        # Get config paths (may set fallback flags)
        self.script_config_path = self._get_script_config_path(script_path)
        self.user_config_path = self._get_user_config_path()

        # Initialize with defaults
        self.limits = LimitsConfig()
        self.security = SecurityConfig()
        self.execution = ExecutionConfig()
        self.logging = LoggingConfig()
        self.advanced = AdvancedConfig()

        # Load script config first, then user config
        self._load_script_config()
        self._load_user_config()

    def _get_original_script_name(self, script_path):
        """Get the original script name by resolving symlinks."""
        resolved_path = Path(script_path).resolve()
        return resolved_path.stem

    def _get_script_config_path(self, script_path):
        """Get script config path with fallback to original script config."""
        script_dir = Path(script_path).resolve().parent
        cfg_dir = script_dir.parent / 'cfg'

        # First try the symlink/current name config
        primary_config = cfg_dir / f"{self.script_name}.yaml"

        # If it doesn't exist and we're using a symlink, fall back to original
        if not primary_config.exists() and self.script_name != self.original_script_name:
            fallback_config = cfg_dir / f"{self.original_script_name}.yaml"
            if fallback_config.exists():
                self.script_config_is_fallback = True
                return fallback_config

        return primary_config

    def _get_user_config_path(self):
        """Get user config path with fallback to original script config."""
        home_dir = Path.home()

        # First try the symlink/current name config
        primary_config = home_dir / self.script_name / 'cfg' / f"{self.script_name}.yaml"

        # If it doesn't exist and we're using a symlink, fall back to original
        if not primary_config.exists() and self.script_name != self.original_script_name:
            fallback_config = home_dir / self.original_script_name / 'cfg' / f"{self.original_script_name}.yaml"
            if fallback_config.exists():
                self.user_config_is_fallback = True
                return fallback_config

        return primary_config

    def _load_script_config(self):
        """Load script configuration with system limits."""
        try:
            if not self.script_config_path.exists():
                return

            with open(str(self.script_config_path), 'r') as f:
                if self.script_config_path.suffix in ['.yaml', '.yml']:
                    if not HAS_YAML:
                        return
                    config_data = yaml.safe_load(f)
                else:
                    return

            self._apply_config(config_data or {})
            self.script_config_loaded = True

        except (FileNotFoundError, PermissionError) as e:
            print(f"Warning: Cannot access script config: {e}")
        except Exception as e:
            print(f"Warning: Script config load failed, using defaults: {e}")

    def _load_user_config(self):
        """Load user configuration with validation against limits."""
        try:
            if not self.user_config_path.exists():
                return

            with open(str(self.user_config_path), 'r') as f:
                if self.user_config_path.suffix in ['.yaml', '.yml']:
                    if not HAS_YAML:
                        return
                    user_config = yaml.safe_load(f)
                else:
                    return

            self._apply_user_config(user_config or {})
            self.user_config_loaded = True

        except (FileNotFoundError, PermissionError) as e:
            print(f"Warning: Cannot access user config: {e}")
        except Exception as e:
            print(f"Warning: User config load failed, using script defaults: {e}")

    def _apply_config(self, config_data):
        """Apply configuration data to instances."""
        sections = {
            'limits': self.limits,
            'security': self.security,
            'execution': self.execution,
            'logging': self.logging,
            'advanced': self.advanced
        }

        for section_name, section_instance in sections.items():
            if section_name in config_data:
                self._update_instance(section_instance, config_data[section_name])

    def _apply_user_config(self, config_data):
        """Apply user configuration with limits validation."""
        allowed_sections = {
            'limits': self.limits,
            'execution': self.execution,
            'logging': self.logging,
            'advanced': self.advanced
        }

        for section_name, section_instance in allowed_sections.items():
            if section_name in config_data:
                if section_name == 'limits':
                    self._update_limits_with_validation(section_instance, config_data[section_name])
                else:
                    self._update_instance(section_instance, config_data[section_name])

    def _update_instance(self, instance, data):
        """Update instance with dictionary data."""
        for key, value in data.items():
            if hasattr(instance, key):
                current_value = getattr(instance, key)
                if current_value is not None:
                    expected_type = type(current_value)
                    if not isinstance(value, expected_type):
                        try:
                            if expected_type == bool and isinstance(value, str):
                                value = value.lower() in ('true', '1', 'yes', 'on')
                            else:
                                value = expected_type(value)
                        except (ValueError, TypeError):
                            raise ConfigurationError(f"Invalid type for {key}: expected {expected_type.__name__}, got {type(value).__name__}")
                setattr(instance, key, value)

    def _update_limits_with_validation(self, limits_instance, data):
        """Update limits with validation against maximum allowed values."""
        for key, value in data.items():
            if hasattr(limits_instance, key) and not key.startswith('max_allowed_'):
                # Validate against max_allowed_* values
                if key == 'max_workers' and value > limits_instance.max_allowed_workers:
                    print(f"Warning: User max_workers ({value}) exceeds limit ({limits_instance.max_allowed_workers}), using limit")
                    value = limits_instance.max_allowed_workers
                elif key == 'timeout_seconds' and value > limits_instance.max_allowed_timeout:
                    print(f"Warning: User timeout_seconds ({value}) exceeds limit ({limits_instance.max_allowed_timeout}), using limit")
                    value = limits_instance.max_allowed_timeout
                elif key == 'max_output_capture' and value > limits_instance.max_allowed_output:
                    print(f"Warning: User max_output_capture ({value}) exceeds limit ({limits_instance.max_allowed_output}), using limit")
                    value = limits_instance.max_allowed_output
                
                setattr(limits_instance, key, value)

    def validate(self):
        """Validate configuration settings."""
        errors = []
        
        if self.limits.max_workers <= 0:
            errors.append("max_workers must be positive")
        if self.limits.timeout_seconds <= 0:
            errors.append("timeout_seconds must be positive")
        # Wait time must be between 0.01 (10ms) and 10.0 (10 seconds)
        if self.limits.wait_time < 0.01:
            errors.append("wait_time must be at least 0.01 seconds (10ms)")
        if self.limits.wait_time > 10.0:
            errors.append("wait_time cannot exceed 10.0 seconds")

        # Task start delay must be between 0 and 60 seconds
        if self.limits.task_start_delay < 0:
            errors.append("task_start_delay cannot be negative")
        if self.limits.task_start_delay > 60.0:
            errors.append("task_start_delay cannot exceed 60.0 seconds")

        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.logging.level.upper() not in valid_levels:
            errors.append(f"Invalid log level: {self.logging.level}")
        
        if self.advanced.max_file_size <= 0:
            errors.append("max_file_size must be positive")
        
        try:
            self.get_custom_timestamp()
        except Exception:
            errors.append("custom_date_format is invalid")
        
        if errors:
            error_list = "\n".join(f"  - {error}" for error in errors)
            raise ConfigurationError(f"Configuration validation failed:\n{error_list}")

    def get_working_directory(self, worker_id=None, process_id=None):
        """Get working directory - shared or isolated based on config."""
        home_dir = Path.home()
        base_workspace = home_dir / self.script_name / "workspace"
        
        if self.execution.workspace_isolation and worker_id is not None and process_id is not None:
            worker_workspace = base_workspace / f"pid{process_id}_worker{worker_id}"
            worker_workspace.mkdir(parents=True, exist_ok=True)
            return worker_workspace
        else:
            base_workspace.mkdir(parents=True, exist_ok=True)
            return base_workspace

    def get_worker_workspace(self, worker_id, process_id):
        """Get workspace for specific worker."""
        return self.get_working_directory(worker_id, process_id)

    def get_log_directory(self):
        """Get log directory in user's home: ~/<script_name>/logs"""
        home_dir = Path.home()
        log_dir = home_dir / self.script_name / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir

    def get_pidfile_path(self):
        """Get path for PID file."""
        home_dir = Path.home()
        pid_dir = home_dir / self.script_name / "pids"
        pid_dir.mkdir(parents=True, exist_ok=True)
        return pid_dir / f"{self.script_name}.pids"

    def register_process(self, process_id):
        """Register this process in the PID file."""
        pidfile = self.get_pidfile_path()
        try:
            existing_pids = set()
            if pidfile.exists():
                with open(str(pidfile), 'r') as f:
                    for line in f:
                        pid = line.strip()
                        if pid.isdigit():
                            existing_pids.add(int(pid))
            
            existing_pids.add(process_id)
            
            with open(str(pidfile), 'w') as f:
                for pid in sorted(existing_pids):
                    f.write(f"{pid}\n")
                    
        except Exception as e:
            print(f"Warning: Could not register process: {e}")

    def unregister_process(self, process_id):
        """Remove this process from the PID file."""
        pidfile = self.get_pidfile_path()
        try:
            if not pidfile.exists():
                return
                
            existing_pids = set()
            with open(str(pidfile), 'r') as f:
                for line in f:
                    pid = line.strip()
                    if pid.isdigit():
                        existing_pids.add(int(pid))
            
            existing_pids.discard(process_id)
            
            if existing_pids:
                with open(str(pidfile), 'w') as f:
                    for pid in sorted(existing_pids):
                        f.write(f"{pid}\n")
            else:
                pidfile.unlink()
                
        except Exception as e:
            print(f"Warning: Could not unregister process: {e}")

    def get_running_processes(self):
        """Get list of registered running processes."""
        pidfile = self.get_pidfile_path()
        if not pidfile.exists():
            return []
            
        try:
            pids = []
            with open(str(pidfile), 'r') as f:
                for line in f:
                    pid = line.strip()
                    if pid.isdigit():
                        try:
                            if HAS_PSUTIL:
                                if psutil.pid_exists(int(pid)):
                                    pids.append(int(pid))
                            else:
                                os.kill(int(pid), 0)
                                pids.append(int(pid))
                        except (OSError, ProcessLookupError):
                            pass
            return pids
        except Exception:
            return []

    def get_custom_timestamp(self):
        """Get custom formatted timestamp."""
        return datetime.now().strftime(self.logging.custom_date_format)

    def get_process_log_prefix(self, process_id):
        """Get simplified log file prefix."""
        return f"parallelr_{process_id}"

    @classmethod
    def from_script(cls, script_path):
        """Create configuration for given script."""
        return cls(script_path)

    def __str__(self):
        """String representation of configuration."""
        workspace_type = "isolated per worker" if self.execution.workspace_isolation else "shared"

        # Indicate if using fallback configs
        script_config_desc = f"{self.script_config_path} (exists: {self.script_config_path.exists()})"
        if self.script_name != self.original_script_name and self.script_config_path.name == f"{self.original_script_name}.yaml":
            script_config_desc += " [fallback from original script]"

        user_config_desc = f"{self.user_config_path} (exists: {self.user_config_path.exists()})"
        if self.script_name != self.original_script_name and self.user_config_path.parts[-1] == f"{self.original_script_name}.yaml":
            user_config_desc += " [fallback from original script]"

        return f"""Configuration for {self.script_name}:
  Workers: {self.limits.max_workers} (max allowed: {self.limits.max_allowed_workers})
  Timeout: {self.limits.timeout_seconds}s (max allowed: {self.limits.max_allowed_timeout}s)
  Log Level: {self.logging.level}
  Workspace: {workspace_type}
  Working Dir: {self.get_working_directory()}
  Log Dir: {self.get_log_directory()}
  Stop Limits: {"Enabled" if self.limits.stop_limits_enabled else "Disabled"}
  Script Config: {script_config_desc}
  User Config: {user_config_desc}"""

class SecureTaskExecutor:
    """Simplified task executor with basic security validation."""
    
    def __init__(self, task_file, command_template, timeout, worker_id, logger, config,
                 extra_env=None, task_argument=None):
        self.task_file = task_file
        self.command_template = command_template
        self.timeout = timeout
        self.worker_id = worker_id
        self.logger = logger
        self.config = config
        self.extra_env = extra_env or {}
        self.task_argument = task_argument
        self._process = None
        self._cancelled = False

    def _validate_task_file_security(self, task_file):
        """Basic security validation for task file."""
        try:
            if os.path.getsize(task_file) > self.config.advanced.max_file_size:
                raise SecurityError(f"Task file too large: {task_file}")
        except OSError as e:
            raise SecurityError(f"Cannot access task file: {task_file}") from e

    def _build_secure_command(self, task_file):
        """Build command arguments with basic security validation."""
        abs_task_file = str(Path(task_file).resolve())
        command_str = self.command_template.replace("@TASK@", abs_task_file)

        # Replace @ARG@ if we have a task argument (use is not None to handle "0" and other falsy values)
        if self.task_argument is not None:
            command_str = command_str.replace("@ARG@", shlex.quote(self.task_argument))

        try:
            args = shlex.split(command_str)
        except ValueError as e:
            raise SecurityError(f"Invalid command syntax: {e}") from e

        if not args:
            raise SecurityError("Empty command after parsing")

        for arg in args:
            if len(arg) > self.config.security.max_argument_length:
                raise SecurityError(f"Argument too long: {len(arg)} characters")

        return args

    def _monitor_process(self):
        """Monitor process resource usage."""
        if not HAS_PSUTIL:
            return 0.0, 0.0

        if not self._process:
            return 0.0, 0.0

        try:
            process = psutil.Process(self._process.pid)
            memory_mb = process.memory_info().rss / 1024 / 1024
            cpu_percent = process.cpu_percent(interval=0)  # Non-blocking
            return memory_mb, cpu_percent
        except (psutil.NoSuchProcess, psutil.AccessDenied, ProcessLookupError):
            # Process ended or no permission
            return 0.0, 0.0
        except Exception:
            # Unexpected error - log at debug level only
            return 0.0, 0.0

    def execute(self):
        """Execute task with basic security and monitoring."""
        start_time = datetime.now()
        
        result = TaskResult(
            task_file=self.task_file,
            command="",
            start_time=start_time,
            end_time=None,
            status=TaskStatus.PENDING,
            exit_code=None,
            stdout="",
            stderr="",
            error_message="",
            duration=0.0,
            worker_id=self.worker_id,
            memory_usage=0.0,
            cpu_usage=0.0
        )

        # fix buffer issue 
        stdout_lines = []
        stderr_lines = []
         
        try:
            self._validate_task_file_security(self.task_file)
            command_args = self._build_secure_command(self.task_file)
            result.command = ' '.join(command_args)
            
            self.logger.info(f"Worker {self.worker_id}: Starting task {self.task_file}")
            result.status = TaskStatus.RUNNING
            
            if self._cancelled:
                result.status = TaskStatus.CANCELLED
                result.error_message = "Task cancelled"
                return result
            
            if self.config.execution.workspace_isolation:
                work_dir = self.config.get_worker_workspace(self.worker_id, os.getpid())
            else:
                work_dir = self.config.get_working_directory()

            # Prepare environment with any extra variables
            env = os.environ.copy()
            if self.extra_env:
                env.update(self.extra_env)

            # Prepare process group configuration
            popen_kwargs = {
                'shell': False,
                'stdout': subprocess.PIPE,
                'stderr': subprocess.PIPE,
                'universal_newlines': True,
                'bufsize': 0,  # Unbuffered
                'cwd': str(work_dir),
                'env': env
            }

            # Apply process group settings if enabled
            if self.config.execution.use_process_groups:
                if os.name == 'posix':
                    # POSIX: Use setsid to create new process group
                    popen_kwargs['preexec_fn'] = os.setsid
                else:
                    # Windows: Use CREATE_NEW_PROCESS_GROUP flag
                    popen_kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP

            self._process = subprocess.Popen(command_args, **popen_kwargs)
            
            try:
                # Real-time output capture with timeout handling
                stdout_fd = self._process.stdout.fileno()
                stderr_fd = self._process.stderr.fileno()

                # Make file descriptors non-blocking
                fl = fcntl.fcntl(stdout_fd, fcntl.F_GETFL)
                fcntl.fcntl(stdout_fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
                fl = fcntl.fcntl(stderr_fd, fcntl.F_GETFL)
                fcntl.fcntl(stderr_fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
                timeout_time = time.time() + self.timeout

                while self._process.poll() is None:
                    if time.time() > timeout_time:
                        raise subprocess.TimeoutExpired(command_args, self.timeout)

                    # Monitor resource usage during execution
                    current_memory, current_cpu = self._monitor_process()
                    if current_memory > result.memory_usage:
                        result.memory_usage = current_memory
                    if current_cpu > result.cpu_usage:
                        result.cpu_usage = current_cpu

                    # Check for available data
                    ready, _, _ = select.select([stdout_fd, stderr_fd], [], [], 0.1)

                    for fd in ready:
                        try:
                            if fd == stdout_fd:
                                data = os.read(fd, 4096).decode('utf-8', errors='replace')
                                if data:
                                    stdout_lines.append(data)
                            elif fd == stderr_fd:
                                data = os.read(fd, 4096).decode('utf-8', errors='replace')
                                if data:
                                    stderr_lines.append(data)
                        except OSError as e:
                            if e.errno != errno.EAGAIN:
                                break

                # Read any remaining output
                try:
                    remaining_stdout = self._process.stdout.read()
                    if remaining_stdout:
                        stdout_lines.append(remaining_stdout)
                except:
                    pass

                try:
                    remaining_stderr = self._process.stderr.read()
                    if remaining_stderr:
                        stderr_lines.append(remaining_stderr)
                except:
                    pass

                # Get final resource usage (keep max values)
                memory_usage, cpu_usage = self._monitor_process()
                if memory_usage > result.memory_usage:
                    result.memory_usage = memory_usage
                if cpu_usage > result.cpu_usage:
                    result.cpu_usage = cpu_usage

                # Wait for process completion
                self._process.wait()
                result.exit_code = self._process.returncode

                # Combine captured output - capture LAST N chars (errors appear at end)
                stdout = ''.join(stdout_lines)
                stderr = ''.join(stderr_lines)
                max_capture = self.config.limits.max_output_capture
                result.stdout = stdout[-max_capture:] if stdout else ""
                result.stderr = stderr[-max_capture:] if stderr else ""
                if result.exit_code == 0:
                    result.status = TaskStatus.SUCCESS
                    self.logger.info("Worker {}: Task completed successfully".format(self.worker_id))
                else:
                    result.status = TaskStatus.FAILED
                    result.error_message = "Exit code {}".format(result.exit_code)

            except subprocess.TimeoutExpired:
                result.status = TaskStatus.TIMEOUT
                result.error_message = "Timeout after {}s".format(self.timeout)

                # Capture any output before terminating - capture LAST N chars
                stdout = ''.join(stdout_lines)
                stderr = ''.join(stderr_lines)
                max_capture = self.config.limits.max_output_capture
                result.stdout = stdout[-max_capture:] if stdout else ""
                result.stderr = stderr[-max_capture:] if stderr else ""
                self._terminate_process()
        
        except SecurityError as e:
            result.status = TaskStatus.ERROR
            result.error_message = f"Security error: {e}"
        except Exception as e:
            result.status = TaskStatus.ERROR
            result.error_message = f"Error: {e}"
            # Capture any partial output - capture LAST N chars (errors at end)
            stdout = ''.join(stdout_lines)
            stderr = ''.join(stderr_lines)
            max_capture = self.config.limits.max_output_capture
            result.stdout = stdout[-max_capture:] if stdout else ""
            result.stderr = stderr[-max_capture:] if stderr else ""
        
        finally:
            result.end_time = datetime.now()
            result.duration = (result.end_time - result.start_time).total_seconds()
            self._process = None
        
        return result

    def _terminate_process(self):
        """Safely terminate the running process and its children."""
        if not self._process:
            return

        try:
            pid = self._process.pid

            # Terminate process group if enabled, otherwise just the process
            if self.config.execution.use_process_groups:
                if os.name == 'posix':
                    # POSIX: Terminate entire process group
                    try:
                        pgid = os.getpgid(pid)
                        self.logger.debug(f"Terminating process group {pgid}")
                        os.killpg(pgid, signal.SIGTERM)
                    except (OSError, ProcessLookupError) as e:
                        self.logger.debug(f"Process group termination failed, falling back to process: {e}")
                        # Fallback to single process termination
                        self._process.terminate()
                else:
                    # Windows: Send CTRL_BREAK_EVENT to process group
                    try:
                        self.logger.debug(f"Sending CTRL_BREAK to process group {pid}")
                        self._process.send_signal(signal.CTRL_BREAK_EVENT)
                    except (OSError, AttributeError) as e:
                        self.logger.debug(f"Process group signal failed, falling back to terminate: {e}")
                        # Fallback to single process termination
                        self._process.terminate()
            else:
                # Process groups disabled - terminate single process
                self._process.terminate()

            # Wait for graceful termination
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Forceful kill if graceful termination failed
                if self.config.execution.use_process_groups and os.name == 'posix':
                    try:
                        pgid = os.getpgid(pid)
                        self.logger.debug(f"Force killing process group {pgid}")
                        os.killpg(pgid, signal.SIGKILL)
                    except (OSError, ProcessLookupError) as e:
                        self.logger.debug(f"Process group kill failed, falling back to process: {e}")
                        self._process.kill()
                else:
                    self._process.kill()

        except Exception as e:
            self.logger.debug(f"Error during process termination: {e}")
            # Last resort - try basic kill
            try:
                self._process.kill()
            except:
                pass

    def cancel(self):
        """Cancel the running task."""
        self._cancelled = True
        self._terminate_process()

class ParallelTaskManager:
    """Main parallel task execution manager."""
    
    def __init__(self, max_workers, timeout, task_start_delay, tasks_paths, command_template,
                 script_path, dry_run=False, enable_stop_limits=False, log_task_output=True,
                 file_extension=None, arguments_file=None, env_var=None):

        self.config = Configuration.from_script(script_path)
        self.config.validate()

        if max_workers is not None:
            self.config.limits.max_workers = max_workers
        if timeout is not None:
            self.config.limits.timeout_seconds = timeout
        if task_start_delay is not None:
            self.config.limits.task_start_delay = task_start_delay

        if enable_stop_limits:
            self.config.limits.stop_limits_enabled = True

        self.max_workers = self.config.limits.max_workers
        self.timeout = self.config.limits.timeout_seconds
        self.wait_time = self.config.limits.wait_time  # Always from config
        self.task_start_delay = self.config.limits.task_start_delay
        # Handle both single path (string) and multiple paths (list)
        if isinstance(tasks_paths, str):
            self.tasks_paths = [tasks_paths]
        else:
            self.tasks_paths = tasks_paths if tasks_paths else []
        self.file_extension = file_extension
        self.command_template = command_template
        self.dry_run = dry_run
        self.arguments_file = arguments_file
        self.env_var = env_var

        self.log_dir = self.config.get_log_directory()
        self.process_id = os.getpid()
        
        self.config.register_process(self.process_id)
        
        self.consecutive_failures = 0
        self.total_completed = 0

        # Change to task_entries to support both files and arguments
        self.task_entries = []  # Will contain dicts with task info
        self.task_files = []  # Legacy support
        self.completed_tasks = []
        self.failed_tasks = []
        self.running_tasks = {}
        self.executor = None
        self.futures = {}
        self.shutdown_requested = False

        # Create timestamp for this session (used across all log files)
        self.timestamp = self.config.get_custom_timestamp()

        self.logger = self._setup_logging()

        self.summary_log_file = self.log_dir / f"parallelr_{self.process_id}_{self.timestamp}_summary.csv"
        self._log_lock = threading.Lock()
        self._init_summary_log()

        self.log_task_output = log_task_output
        self.task_results_file = self.log_dir / f"parallelr_{self.process_id}_{self.timestamp}_output.txt"

    def _setup_logging(self):
        """Set up logging with size-based rotation."""
        import logging.handlers

        logger = logging.getLogger(f'parallelr_{self.process_id}_{self.timestamp}')
        logger.setLevel(getattr(logging, self.config.logging.level.upper()))
        logger.handlers.clear()

        log_filename = f'parallelr_{self.process_id}_{self.timestamp}.log'
        max_bytes = self.config.logging.max_log_size_mb * 1024 * 1024
        
        file_handler = logging.handlers.RotatingFileHandler(
            str(self.log_dir / log_filename),
            maxBytes=max_bytes,
            backupCount=self.config.logging.backup_count
        )
        
        enhanced_format = f"%(asctime)s - P{self.process_id} - %(levelname)s - [%(threadName)s] - %(message)s"
        file_handler.setFormatter(logging.Formatter(enhanced_format))
        logger.addHandler(file_handler)
        
        # Console handler only if not daemon
        if os.getppid() != 1:
            console_format = f"%(asctime)s - P{self.process_id} - %(levelname)s - %(message)s"
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(logging.Formatter(console_format))
            logger.addHandler(console_handler)
        
        return logger

    def _init_summary_log(self):
        """Initialize the summary CSV log file."""
        if not self.dry_run:
            try:
                with self._log_lock:
                    with open(str(self.summary_log_file), 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f, delimiter=';')
                        writer.writerow([
                            'start_time', 'end_time', 'status', 'process_id', 'worker_id',
                            'task_file', 'command', 'exit_code', 'duration_seconds',
                            'memory_mb', 'cpu_percent', 'error_message'
                        ])
            except Exception as e:
                raise ParallelTaskExecutorError(f"Failed to init summary log: {e}") from e

    def _discover_tasks(self):
        """Discover task files from directories and/or explicit file paths, or create tasks from arguments."""
        task_entries = []

        # Check if we're in arguments mode
        if self.arguments_file:
            # Arguments mode: Read arguments from file and create tasks
            if not self.tasks_paths or len(self.tasks_paths) != 1:
                raise ParallelTaskExecutorError("Arguments mode requires exactly one template file with -T")

            template_file = Path(self.tasks_paths[0])
            if not template_file.is_file():
                raise ParallelTaskExecutorError(f"Template file not found: {template_file}")

            args_file = Path(self.arguments_file)
            if not args_file.is_file():
                raise ParallelTaskExecutorError(f"Arguments file not found: {args_file}")

            # Read arguments from file
            try:
                with open(args_file, 'r') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        # Skip empty lines and comments
                        if not line or line.startswith('#'):
                            continue
                        # Create a task entry for each argument
                        task_entries.append({
                            'type': 'argument',
                            'template': str(template_file),
                            'argument': line,
                            'line_num': line_num
                        })
            except Exception as e:
                raise ParallelTaskExecutorError(f"Failed to read arguments file: {e}") from e

            self.logger.info(f"Created {len(task_entries)} tasks from arguments file")
            return task_entries

        # Regular mode: Discover task files from paths
        task_files = []

        # Parse file extensions if provided
        allowed_extensions = set()
        if self.file_extension:
            # Support both "txt" and "txt,log,dat" formats
            for ext in self.file_extension.split(','):
                ext = ext.strip()
                if not ext.startswith('.'):
                    ext = '.' + ext
                allowed_extensions.add(ext.lower())

        try:
            if not self.tasks_paths:
                raise ParallelTaskExecutorError("No task paths specified")

            for task_path in self.tasks_paths:
                path = Path(task_path)

                if path.is_file():
                    # It's a file - add it directly
                    # Check extension filter if provided
                    if allowed_extensions:
                        if path.suffix.lower() not in allowed_extensions:
                            self.logger.debug(f"Skipping {path} - extension not in filter")
                            continue
                    task_files.append(str(path))

                elif path.is_dir():
                    # It's a directory - discover files within
                    for file_path in path.iterdir():
                        if file_path.is_file():
                            # Check extension filter if provided
                            if allowed_extensions:
                                if file_path.suffix.lower() not in allowed_extensions:
                                    continue
                            task_files.append(str(file_path))

                else:
                    # Path doesn't exist - could be a glob pattern that shell didn't expand
                    # Try glob expansion
                    import glob
                    matched_files = glob.glob(str(path))
                    if matched_files:
                        for file_path in matched_files:
                            file_path = Path(file_path)
                            if file_path.is_file():
                                # Check extension filter if provided
                                if allowed_extensions:
                                    if file_path.suffix.lower() not in allowed_extensions:
                                        continue
                                task_files.append(str(file_path))
                    else:
                        raise ParallelTaskExecutorError(f"Path does not exist: {path}")

            if not task_files:
                if allowed_extensions:
                    ext_list = ', '.join(allowed_extensions)
                    raise ParallelTaskExecutorError(f"No task files found matching extensions: {ext_list}")
                else:
                    raise ParallelTaskExecutorError(f"No task files found in specified paths")

            # Remove duplicates and sort
            task_files = sorted(list(set(task_files)))

            # Convert to task entries for consistency
            for task_file in task_files:
                task_entries.append({
                    'type': 'file',
                    'file': task_file
                })

            if allowed_extensions:
                ext_list = ', '.join(allowed_extensions)
                self.logger.info(f"Discovered {len(task_entries)} task files with extensions: {ext_list}")
            else:
                self.logger.info(f"Discovered {len(task_entries)} task files")

            return task_entries

        except Exception as e:
            raise ParallelTaskExecutorError(f"Failed to discover task files: {e}") from e

    def _check_error_limits(self):
        """Check if error limits are exceeded."""
        if not self.config.limits.stop_limits_enabled:
            return False
        
        if self.consecutive_failures >= self.config.limits.max_consecutive_failures:
            self.logger.error(f"Auto-stop: {self.consecutive_failures} consecutive failures (limit: {self.config.limits.max_consecutive_failures})")
            return True
        
        if self.total_completed >= self.config.limits.min_tasks_for_rate_check:
            failure_rate = len(self.failed_tasks) / self.total_completed
            if failure_rate > self.config.limits.max_failure_rate:
                self.logger.error(f"Auto-stop: {failure_rate:.1%} failure rate exceeds limit ({self.config.limits.max_failure_rate:.0%})")
                return True
        
        return False

    def _handle_completed_task(self, future):
        """Handle completion of a task with error tracking."""
        try:
            result = future.result()
            task_file = result.task_file
            self._log_task_result(result)
            self.total_completed += 1

            if result.status == TaskStatus.SUCCESS:
                self.completed_tasks.append(result)
                self.consecutive_failures = 0
                self.logger.info(f"Task completed: {task_file}")
            else:
                self.failed_tasks.append(result)
                if self.config.limits.stop_limits_enabled:
                    self.consecutive_failures += 1

                if result.status == TaskStatus.TIMEOUT:
                    self.logger.warning(f"Task timed out after {self.timeout}s: {task_file}")
                else:
                    self.logger.warning(f"Task failed: {task_file} - {result.error_message}")

                if self.config.limits.stop_limits_enabled and self._check_error_limits():
                    self.shutdown_requested = True

            # Clean up future-based tracking
            if future in self.running_tasks:
                del self.running_tasks[future]
            if future in self.futures:
                del self.futures[future]

        except Exception as e:
            self.logger.error(f"Error handling task: {e}")
            if self.config.limits.stop_limits_enabled:
                self.consecutive_failures += 1
            # Clean up on error too
            if future in self.running_tasks:
                del self.running_tasks[future]
            if future in self.futures:
                del self.futures[future]

    def _log_task_result(self, result):
        """Log task result to summary file."""
        if not self.dry_run:
            try:
                with self._log_lock:
                    with open(str(self.summary_log_file), 'a', newline='', encoding='utf-8') as f:
                        f.write(result.to_log_line() + '\n')
            except Exception as e:
                self.logger.error(f"Log write failed: {e}")

        if self.log_task_output and not self.dry_run:
            try:
                timestamp = self.config.get_custom_timestamp()
                #task_results_file = self.log_dir / f"TaskResults_{self.process_id}_{timestamp}.txt"
                with self._log_lock:
                    with open(str(self.task_results_file), 'a', encoding='utf-8') as f:
                        f.write(f"\n{'='*80}\n")
                        f.write(f"Task: {result.task_file}\n")
                        f.write(f"Worker: {result.worker_id}\n")
                        f.write(f"Command: {result.command}\n")
                        f.write(f"Status: {result.status.value}\n")
                        f.write(f"Exit Code: {result.exit_code}\n")
                        f.write(f"Duration: {result.duration:.2f}s\n")
                        f.write(f"Memory: {result.memory_usage:.2f}MB\n")
                        f.write(f"Start: {result.start_time}\n")
                        f.write(f"End: {result.end_time}\n")
                        if result.stdout:
                            f.write(f"\nSTDOUT:\n{result.stdout}\n")
                        if result.stderr:
                            f.write(f"\nSTDERR:\n{result.stderr}\n")
                        if result.error_message:
                            f.write(f"\nERROR: {result.error_message}\n")
            except Exception as e:
                self.logger.error(f"Output log write failed: {e}")

    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.shutdown_requested = True
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGHUP, signal.SIG_IGN)

    def execute_tasks(self):
        """Execute all tasks."""
        self.logger.info("Starting parallel execution")

        try:
            self.task_entries = self._discover_tasks()
            total_tasks = len(self.task_entries)

            # For backward compatibility, also populate task_files if in file mode
            self.task_files = [entry.get('file', entry.get('template')) for entry in self.task_entries]

            self.logger.info(f"Executing {total_tasks} tasks with {self.max_workers} workers")
            if self.task_start_delay > 0:
                self.logger.info(f"Task start delay: {self.task_start_delay} seconds between new tasks")

            if self.dry_run:
                self.logger.info("DRY RUN MODE")
                for i, task_entry in enumerate(self.task_entries, 1):
                    if task_entry['type'] == 'argument':
                        # Build command with absolute path and proper quoting
                        abs_task_file = str(Path(task_entry['template']).resolve())
                        command_str = self.command_template.replace("@TASK@", abs_task_file)
                        command_str = command_str.replace("@ARG@", shlex.quote(task_entry['argument']))
                        if self.env_var:
                            env_prefix = f"{self.env_var}={shlex.quote(task_entry['argument'])} "
                            command_str = env_prefix + command_str
                    else:
                        abs_task_file = str(Path(task_entry['file']).resolve())
                        command_str = self.command_template.replace("@TASK@", abs_task_file)
                    self.logger.info(f"[{i}/{total_tasks}]: {command_str}")
                return {'total': total_tasks, 'completed': 0, 'failed': 0, 'cancelled': 0}

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                task_queue = queue.Queue()
                for task_entry in self.task_entries:
                    task_queue.put(task_entry)
                
                worker_counter = 0
                tasks_started = 0  # Track number of tasks started for delay

                while not task_queue.empty() or self.futures:
                    if self.shutdown_requested:
                        if self.config.limits.stop_limits_enabled:
                            self.logger.info("Auto-stop triggered due to error limits")
                        else:
                            self.logger.info("Shutdown requested")
                        break

                    while len(self.futures) < self.max_workers and not task_queue.empty():
                        if self.shutdown_requested:
                            break

                        # Apply task start delay (except for first task)
                        if self.task_start_delay > 0 and tasks_started > 0:
                            time.sleep(self.task_start_delay)

                        task_entry = task_queue.get()
                        worker_counter += 1
                        tasks_started += 1

                        # Prepare task file and extra environment based on task type
                        if task_entry['type'] == 'argument':
                            task_file = task_entry['template']
                            extra_env = {self.env_var: task_entry['argument']} if self.env_var else {}
                            task_argument = task_entry['argument']
                        else:
                            task_file = task_entry['file']
                            extra_env = {}
                            task_argument = None

                        task_executor = SecureTaskExecutor(
                            task_file, self.command_template, self.timeout,
                            worker_counter, self.logger, self.config,
                            extra_env=extra_env, task_argument=task_argument
                        )

                        future = executor.submit(task_executor.execute)
                        # Use future as key to avoid collisions when same template is used multiple times
                        self.futures[future] = task_file  # Keep for reference
                        self.running_tasks[future] = task_executor  # Key by future, not task_file
                    
                    if self.futures:
                        try:
                            for future in as_completed(self.futures.keys(), timeout=self.wait_time):
                                self._handle_completed_task(future)
                                break
                        except:
                            time.sleep(self.wait_time)
                
                if self.shutdown_requested:
                    self.logger.info("Cancelling remaining tasks...")
                    for task_executor in self.running_tasks.values():
                        task_executor.cancel()

            self.config.unregister_process(self.process_id)
            
            stats = {
                'total': total_tasks,
                'completed': len(self.completed_tasks),
                'failed': len(self.failed_tasks),
                'cancelled': total_tasks - len(self.completed_tasks) - len(self.failed_tasks)
            }
            
            self.logger.info(f"Execution completed: {stats}")
            return stats
            
        except Exception as e:
            self.logger.error(f"Fatal error during task execution: {e}")
            raise

    def get_summary_report(self):
        """Generate a summary report of the execution."""
        total = len(self.task_files) if self.task_files else 0
        completed = len(self.completed_tasks)
        failed = len(self.failed_tasks)
        
        if not self.completed_tasks and not self.failed_tasks:
            return "No tasks were executed."
        
        if self.completed_tasks:
            durations = [task.duration for task in self.completed_tasks]
            avg_duration = sum(durations) / len(durations)
            max_duration = max(durations)
            min_duration = min(durations)
            
            memory_usage = [task.memory_usage for task in self.completed_tasks]
            avg_memory = sum(memory_usage) / len(memory_usage)
            max_memory = max(memory_usage)
        else:
            avg_duration = max_duration = min_duration = 0
            avg_memory = max_memory = 0
        
        success_rate = (completed / total * 100) if total > 0 else 0

        workspace_type = "Isolated per worker" if self.config.execution.workspace_isolation else "Shared"
        stop_enabled = "Enabled" if self.config.limits.stop_limits_enabled else "Disabled"

        stop_details = ""
        if self.config.limits.stop_limits_enabled:
            stop_details = f"\n- Max Consecutive Failures: {self.config.limits.max_consecutive_failures}"
            stop_details += f"\n- Max Failure Rate: {self.config.limits.max_failure_rate:.0%}"

        # Resource monitoring info
        resource_info = ""
        if HAS_PSUTIL:
            resource_info = f"""- Average Memory Usage: {avg_memory:.2f}MB
- Peak Memory Usage: {max_memory:.2f}MB"""
        else:
            resource_info = "- Memory/CPU monitoring: Not available (psutil not installed)"

        report = f"""
Parallel Task Execution Summary
===============================
Total Tasks: {total}
Completed Successfully: {completed}
Failed: {failed}
Cancelled: {total - completed - failed}
Success Rate: {success_rate:.1f}%

Performance Statistics:
- Average Duration: {avg_duration:.2f}s
- Maximum Duration: {max_duration:.2f}s
- Minimum Duration: {min_duration:.2f}s
{resource_info}

Directories:
- Working Dir: {self.config.get_working_directory()}
- Workspace Type: {workspace_type}
- Log Dir: {self.log_dir}

Auto-Stop Protection:
- Stop Limits: {stop_enabled}{stop_details}

Log Files:
- Main Log: {self.log_dir / f'parallelr_{self.process_id}_{self.timestamp}.log'} (rotating)
- Summary: {self.summary_log_file} (session-specific)
- Output: {self.task_results_file} (disable with --no-task-output-log)

Process Info:
- Process ID: {self.process_id}
- Workers: {self.max_workers}
"""
        return report

# Helper functions for daemon mode
def daemonize():
    """Daemonize the current process using double-fork technique."""
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError as e:
        print(f"Fork #1 failed: {e}", file=sys.stderr)
        sys.exit(1)

    os.chdir('/')
    os.setsid()
    os.umask(0)

    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError as e:
        print(f"Fork #2 failed: {e}", file=sys.stderr)
        sys.exit(1)

    sys.stdout.flush()
    sys.stderr.flush()
    
    with open(os.devnull, 'r') as dev_null_r:
        os.dup2(dev_null_r.fileno(), sys.stdin.fileno())
    
    with open(os.devnull, 'w') as dev_null_w:
        os.dup2(dev_null_w.fileno(), sys.stdout.fileno())
        os.dup2(dev_null_w.fileno(), sys.stderr.fileno())

    return True

def is_daemon_supported():
    """Check if daemon mode is supported."""
    return hasattr(os, 'fork') and os.name != 'nt'

def start_daemon_process(script_path, args):
    """Start the parallel tasker as a daemon process."""
    script_name = Path(script_path).name

    if not is_daemon_supported():
        print("Error: Daemon mode not supported on this platform (Windows)", file=sys.stderr)
        return 1

    print(f"Starting {script_name} as daemon...")
    # Handle both single string and list of strings
    if args.TasksDir:
        if isinstance(args.TasksDir, list):
            task_paths_str = ', '.join(str(p) for p in args.TasksDir)
        else:
            task_paths_str = str(args.TasksDir)
        print(f"Task paths: {task_paths_str}")
    else:
        print(f"Task paths: None")
    if args.file_extension:
        print(f"File extension filter: {args.file_extension}")
    print(f"Command template: {args.Command}")
    print(f"Workers: {args.max or 'default'}")
    print(f"Timeout: {args.timeout or 'default'}")
    print(f"Stop limits: {'enabled' if args.enable_stop_limits else 'disabled'}")
    
    config = Configuration.from_script(script_path)
    log_dir = config.get_log_directory()
    pid_file = config.get_pidfile_path()
    
    print(f"Logs will be written to: {log_dir}")
    print(f"PID tracking: {pid_file}")
    print()
    print("Daemonizing...")
    
    if daemonize():
        return None
    
    return 1

def list_workers(script_path):
    """List running worker processes."""
    script_name = Path(script_path).name
    config = Configuration.from_script(script_path)
    running_pids = config.get_running_processes()

    if not running_pids:
        print(f"No running {script_name} processes found.")
        return

    print(f"Found {len(running_pids)} running {script_name} process(es):")
    print()
    print(f"{'PID':<8} {'Status':<10} {'Start Time':<20} {'Log File':<30} {'Summary File'}")
    print("-" * 100)
    
    for pid in running_pids:
        try:
            if HAS_PSUTIL:
                try:
                    proc = psutil.Process(pid)
                    status = proc.status()
                    start_time = datetime.fromtimestamp(proc.create_time()).strftime("%Y-%m-%d %H:%M:%S")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    status = "unknown"
                    start_time = "unknown"
            else:
                try:
                    os.kill(pid, 0)
                    status = "running"
                    start_time = "unknown"
                except OSError:
                    status = "dead"
                    start_time = "unknown"
            
            log_dir = config.get_log_directory()

            # Find most recent log file for this PID
            log_pattern = f"parallelr_{pid}_*.log"
            log_files = list(log_dir.glob(log_pattern))
            if log_files:
                log_file = max(log_files, key=lambda f: f.stat().st_mtime).name
            else:
                log_file = "no log found"

            # Find most recent summary file for this PID
            summary_pattern = f"parallelr_{pid}_*_summary.csv"
            summary_files = list(log_dir.glob(summary_pattern))
            if summary_files:
                summary_file = max(summary_files, key=lambda f: f.stat().st_mtime).name
            else:
                summary_file = "no summary found"

            print(f"{pid:<8} {status:<10} {start_time:<20} {log_file:<30} {summary_file}")
            
        except Exception as e:
            print(f"{pid:<8} {'error':<10} {'unknown':<20} {'error reading info':<30} {str(e)}")
    
    print()
    print("Commands:")
    print(f"  View logs:        tail -f {config.get_log_directory()}/parallelr_<PID>_*.log")
    print(f"  View progress:    tail -f {config.get_log_directory()}/parallelr_<PID>_*_summary.csv")
    print(f"  Kill specific:    python {script_name} -k <PID>")
    print(f"  Kill all:         python {script_name} -k")

def kill_processes(script_path, target_pid=None):
    """Kill worker processes - DANGEROUS OPERATION."""
    script_name = Path(script_path).name
    config = Configuration.from_script(script_path)
    running_pids = config.get_running_processes()

    if not running_pids:
        print(f"No running {script_name} processes found to kill.")
        return

    if target_pid is None:
        print(f"⚠️  WARNING: This will kill ALL {len(running_pids)} running {script_name} processes!")
        print(f"PIDs to be killed: {running_pids}")
        response = input("Are you sure? Type 'yes' to confirm: ")
        if response.lower() != 'yes':
            print("Kill operation cancelled.")
            return
    
    if target_pid:
        if target_pid in running_pids:
            try:
                os.kill(target_pid, signal.SIGTERM)
                print(f"✓ Sent termination signal to process {target_pid}")
                
                time.sleep(2)
                try:
                    os.kill(target_pid, 0)
                    os.kill(target_pid, signal.SIGKILL)
                    print(f"✓ Force killed process {target_pid}")
                except OSError:
                    print(f"✓ Process {target_pid} terminated gracefully")
                    
                config.unregister_process(target_pid)
                    
            except OSError as e:
                print(f"✗ Failed to kill process {target_pid}: {e}")
        else:
            print(f"✗ Process {target_pid} not found in running processes.")
            print(f"Use --list-workers to see current processes: {running_pids}")
    else:
        print(f"Killing {len(running_pids)} processes...")
        killed_count = 0
        
        for pid in running_pids:
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"✓ Sent termination signal to process {pid}")
                killed_count += 1
            except OSError as e:
                print(f"✗ Failed to signal process {pid}: {e}")
        
        if killed_count > 0:
            print("Waiting 3 seconds for graceful shutdown...")
            time.sleep(3)
            
            for pid in running_pids:
                try:
                    os.kill(pid, 0)
                    os.kill(pid, signal.SIGKILL)
                    print(f"✓ Force killed process {pid}")
                except OSError:
                    pass
            
            pidfile = config.get_pidfile_path()
            if pidfile.exists():
                pidfile.unlink()
                print("✓ Cleaned up PID file")
        
        print(f"✓ Kill operation completed for {killed_count} processes")

def is_ptasker_mode():
    """Check if script is running in ptasker mode (symlink)."""
    script_name = Path(sys.argv[0]).name
    return script_name.startswith('ptasker')

def generate_project_id():
    """Generate unique project ID for ptasker mode."""
    import secrets
    unique_id = secrets.token_hex(3)  # 6 hex chars
    return f"parallelr_{unique_id}"

def parse_arguments():
    """Parse and validate command line arguments."""
    ptasker_mode = is_ptasker_mode()

    if ptasker_mode:
        description = "Parallel Task Executor for TASKER - Simplified Interface"
        epilog = """
Examples:
  # Execute TASKER tasks with auto-generated project
  %(prog)s -T ./test_cases -r

  # Execute specific file types only
  %(prog)s -T ./test_cases --file-extension txt -r

  # Execute specific files (shell expansion)
  %(prog)s -T ./test_cases/*.txt -r

  # Execute with custom project name
  %(prog)s -T ./test_cases -p myproject -r

  # Execute as daemon
  %(prog)s -T ./test_cases -p myproject -r -d

  # List running workers
  %(prog)s --list-workers

Note: In ptasker mode, command is automatically set to:
      tasker @TASK@ -p <project_name> -r
        """
    else:
        description = "Parallel Task Executor - Python 3.6.8 Compatible"
        epilog = """
Examples:
  # Execute all tasks in directory (foreground)
  %(prog)s -T ./tasks -C "python3 @TASK@" -r

  # Execute specific file types only
  %(prog)s -T ./tasks --file-extension py -C "python3 @TASK@" -r

  # Execute specific files (shell expansion)
  %(prog)s -T ./tasks/*.txt -C "cat @TASK@" -r

  # Execute from multiple sources
  %(prog)s -T ./dir1 -T ./dir2 -T ./file.txt -C "process @TASK@" -r

  # Execute tasks (background/detached)
  %(prog)s -T ./tasks -C "python3 @TASK@" -r -d

  # List running workers (safe)
  %(prog)s --list-workers

  # Kill all running instances (dangerous)
  %(prog)s -k
        """

    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog
    )
    
    parser.add_argument('-m', '--max', type=int, default=None,
                       help='Maximum parallel tasks (overrides config)')
    
    parser.add_argument('-t', '--timeout', type=int, default=None,
                       help='Task timeout in seconds (overrides config)')

    parser.add_argument('-s', '--sleep', type=float, default=None,
                       help='Delay between starting new tasks (0-60 seconds, default: 0). Use to throttle resource consumption')

    parser.add_argument('-T', '--TasksDir', nargs='+', action='append',
                       help='Directory containing task files or specific file paths (can be used multiple times)')

    parser.add_argument('--file-extension',
                       help='Filter task files by extension(s), e.g., "txt" or "txt,log,dat"')

    parser.add_argument('-A', '--arguments-file',
                       help='File containing arguments, one per line. Each line becomes a parallel task')

    parser.add_argument('-E', '--env-var',
                       help='Environment variable name to set with argument value (e.g., HOSTNAME)')

    if ptasker_mode:
        # In ptasker mode, -C is auto-generated from -p
        parser.add_argument('-C', '--Command',
                           help='(Ignored in ptasker mode - auto-generated from project)')
        parser.add_argument('-p', '--project',
                           help='Project name for TASKER (auto-generated if not provided)')
    else:
        # Normal mode
        parser.add_argument('-C', '--Command',
                           help='Command template with @TASK@ pattern to execute')
        parser.add_argument('-p', '--project',
                           help='Project name for summary logging')

    parser.add_argument('-r', '--run', action='store_true',
                       help='Execute tasks (default is dry-run)')

    parser.add_argument('-d', '--daemon', action='store_true',
                       help='Run as background daemon (detached from user session)')

    parser.add_argument('--enable-stop-limits', action='store_true',
                       help='Enable auto-stop on consecutive failures or high failure rate')

    parser.add_argument('--list-workers', action='store_true',
                       help='List running worker processes (safe)')

    parser.add_argument('-k', '--kill', nargs='?', const='all', metavar='PID',
                       help='Kill processes: -k (all) or -k PID (specific) - DANGEROUS!')

    parser.add_argument('--validate-config', action='store_true',
                       help='Validate configuration file and exit')

    parser.add_argument('--show-config', action='store_true',
                       help='Show current configuration and recommended location')

    parser.add_argument('--check-dependencies', action='store_true',
                       help='Check optional Python module availability and exit')

    parser.add_argument('--no-task-output-log', action='store_true',
                       help='Disable detailed task output logging to output file')

    args = parser.parse_args()

    # Special handling for ptasker mode
    if ptasker_mode and not (args.list_workers or args.kill is not None or
                             args.validate_config or args.show_config or args.check_dependencies):
        # Generate or use provided project name
        if not args.project:
            args.project = generate_project_id()
            print(f"Auto-generated project: {args.project}")

        # Auto-generate command for TASKER
        args.Command = f"tasker @TASK@ -p {args.project} -r"
        print(f"Using command: {args.Command}")

        # If arguments file is provided, automatically set HOSTNAME as env var
        if args.arguments_file and not args.env_var:
            args.env_var = 'HOSTNAME'
            print("Auto-setting environment variable: HOSTNAME")

    if args.list_workers or args.kill is not None:
        return args

    if not args.validate_config and not args.show_config and not args.check_dependencies:
        missing_args = []
        if not args.TasksDir:
            missing_args.append("--TasksDir")
        if not args.Command:
            if ptasker_mode:
                # In ptasker mode, Command should have been auto-generated
                parser.error("Internal error: Command not generated in ptasker mode")
            else:
                missing_args.append("--Command")
        if missing_args:
            parser.error(f"The following arguments are required: {', '.join(missing_args)}")

    return args

def get_default_config_content():
    """Get default script configuration file content."""
    return """# Parallel Task Executor Configuration - Script Defaults
# This file defines system limits and defaults for all users

# Core execution limits with maximum allowed values
limits:
  max_workers: 20              # Default number of parallel workers
  timeout_seconds: 600         # Default task timeout in seconds (10 minutes)
  wait_time: 0.1              # Polling interval in seconds (system responsiveness)
  task_start_delay: 0.0       # Delay between starting new tasks (0-60 seconds)
  max_output_capture: 1000    # Maximum characters of output to capture (last N chars)
  
  # Maximum values users are allowed to override
  max_allowed_workers: 100     # Users cannot exceed this worker count
  max_allowed_timeout: 3600    # Users cannot exceed 1 hour timeout
  max_allowed_output: 10000    # Users cannot exceed this output capture
  
  # Auto-stop protection (disabled by default - must be explicitly enabled)
  stop_limits_enabled: false     # Enable with --enable-stop-limits or config
  max_consecutive_failures: 5    # Stop after N consecutive task failures
  max_failure_rate: 0.5          # Stop if >50% of tasks fail
  min_tasks_for_rate_check: 10   # Need at least N tasks before checking failure rate

# Task execution settings
execution:
  workspace_isolation: false  # Default: shared workspace, true: isolated per worker
  use_process_groups: true    # Enable process group management

# Logging configuration
logging:
  level: "INFO"               # Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
  console_format: "%(asctime)s - %(levelname)s - %(message)s"
  file_format: "%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s"
  custom_date_format: "%d%b%y_%H%M%S"  # Format: 17Jun25_181623
  max_log_size_mb: 10         # Log file size before rotation (MB)
  backup_count: 5             # Number of backup log files to keep

# Advanced settings (optional)
# advanced:
#   max_file_size: 1048576      # Maximum task file size (1MB)
#   memory_limit_mb: 1024       # Memory limit per worker (MB)
#   retry_failed_tasks: false   # Whether to retry failed tasks
"""

def show_configuration(script_path):
    """Show current configuration and recommended locations."""
    config = Configuration.from_script(script_path)

    print("=" * 60)
    print("PARALLEL TASK EXECUTOR CONFIGURATION")
    print("=" * 60)
    print()
    print(config)
    print()

    # Check if both configs point to the same file
    same_config = config.script_config_path == config.user_config_path

    if same_config and config.script_config_path.exists():
        # Both configs are the same file - show only once
        print("CONFIGURATION FILE (Script and User):")
        print("-" * 40)
        print(f"Location: {config.script_config_path}")
        if config.script_config_is_fallback or config.user_config_is_fallback:
            print(f"Note: Using fallback from {config.original_script_name}.yaml (no {config.script_name}.yaml found)")
        try:
            with open(str(config.script_config_path), 'r') as f:
                print(f.read())
        except Exception as e:
            print(f"Error reading: {e}")
    else:
        # Different configs - show separately
        print("SCRIPT CONFIGURATION:")
        print("-" * 40)
        if config.script_config_path.exists():
            print(f"Location: {config.script_config_path}")
            if config.script_config_is_fallback:
                print(f"Note: Fallback from {config.script_name}.yaml")
            try:
                with open(str(config.script_config_path), 'r') as f:
                    content = f.read()
                    print(content)
            except Exception as e:
                print(f"Error reading: {e}")
        else:
            print(f"No script config at: {config.script_config_path}")
            print("To create script config:")
            print(get_default_config_content()[:300] + "...")

        print()
        print("USER CONFIGURATION:")
        print("-" * 40)
        if config.user_config_path.exists():
            print(f"Location: {config.user_config_path}")
            if config.user_config_is_fallback:
                print(f"Note: Fallback from {config.script_name}.yaml")
            try:
                with open(str(config.user_config_path), 'r') as f:
                    print(f.read())
            except Exception as e:
                print(f"Error reading: {e}")
        else:
            print(f"No user config found at: {config.user_config_path}")

def check_dependencies():
    """Check optional Python module availability."""
    print("=" * 60)
    print("OPTIONAL PYTHON MODULES")
    print("=" * 60)
    print()

    # Check PyYAML
    print("PyYAML:")
    if HAS_YAML:
        print(f"  ✓ Available (version {yaml.__version__})")
        print(f"  Location: {yaml.__file__}")
        print("  Purpose: Load YAML configuration files")
        print("  Impact: Without it, only hardcoded defaults are used")
    else:
        print("  ✗ Not available")
        print("  Purpose: Load YAML configuration files")
        print("  Impact: Configuration files will be ignored, using hardcoded defaults")
        print("  Install: pip install --target=lib pyyaml")
    print()

    # Check psutil
    print("psutil:")
    if HAS_PSUTIL:
        print(f"  ✓ Available (version {psutil.__version__})")
        print(f"  Location: {psutil.__file__}")
        print("  Purpose: Monitor memory and CPU usage per task")
        print("  Impact: Resource metrics collected and reported")
    else:
        print("  ✗ Not available")
        print("  Purpose: Monitor memory and CPU usage per task")
        print("  Impact: Memory/CPU metrics will show 0.00 (not collected)")
        print("  Install: pip install --target=lib psutil")
    print()

    # Summary
    total = 2
    available = sum([HAS_YAML, HAS_PSUTIL])
    print(f"Summary: {available}/{total} optional modules available")
    print()

    if available == total:
        print("✓ All optional modules are available - full functionality enabled!")
        return True
    elif available > 0:
        print("⚠ Some optional modules missing - reduced functionality")
        return True
    else:
        print("⚠ No optional modules available - basic functionality only")
        return True

def validate_configuration(script_path):
    """Validate configuration files."""
    try:
        config = Configuration.from_script(script_path)
        config.validate()

        print("✓ Configuration is valid")

        # Script config status
        if config.script_config_loaded:
            if config.script_config_is_fallback:
                fallback_note = f" (fallback from {config.script_name}.yaml)"
            else:
                fallback_note = ""
            print(f"✓ Script config: {config.script_config_path}{fallback_note}")
        else:
            print(f"  Script config: Not found (using defaults)")

        # User config status
        if config.user_config_loaded:
            if config.user_config_is_fallback:
                fallback_note = f" (fallback from {config.script_name}.yaml)"
            else:
                fallback_note = ""
            print(f"✓ User config: {config.user_config_path}{fallback_note}")
        else:
            print(f"  User config: Not found (using defaults)")

        print(f"✓ Working dir: {config.get_working_directory()}")
        print(f"✓ Log dir: {config.get_log_directory()}")
        print(f"✓ Workspace mode: {'Isolated' if config.execution.workspace_isolation else 'Shared'}")
        print(f"✓ Workers: {config.limits.max_workers} (max allowed: {config.limits.max_allowed_workers})")
        print(f"✓ Timeout: {config.limits.timeout_seconds}s (max allowed: {config.limits.max_allowed_timeout}s)")
        print(f"✓ Custom timestamp: {config.get_custom_timestamp()}")
        return True

    except ConfigurationError as e:
        print(f"✗ Configuration validation failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error validating configuration: {e}")
        return False

def main():
    """Main function with daemon support and kill handling."""
    script_path = __file__
    
    try:
        args = parse_arguments()

        # Flatten TasksDir if it's a list of lists (from nargs='+' and action='append')
        if args.TasksDir and isinstance(args.TasksDir[0], list):
            flattened = []
            for sublist in args.TasksDir:
                flattened.extend(sublist)
            args.TasksDir = flattened

        if args.list_workers:
            list_workers(script_path)
            sys.exit(0)

        if args.kill is not None:
            if args.kill == 'all':
                kill_processes(script_path)
            else:
                try:
                    target_pid = int(args.kill)
                    kill_processes(script_path, target_pid)
                except ValueError:
                    print(f"✗ Invalid PID: {args.kill}")
                    sys.exit(1)
            sys.exit(0)

        if args.check_dependencies:
            check_dependencies()
            sys.exit(0)

        if args.show_config:
            show_configuration(script_path)
            sys.exit(0)

        if args.validate_config:
            if validate_configuration(script_path):
                sys.exit(0)
            else:
                sys.exit(1)

        if args.daemon:
            daemon_result = start_daemon_process(script_path, args)
            if daemon_result is not None:
                sys.exit(daemon_result)

        if args.timeout and args.timeout <= 0:
            raise ParallelTaskExecutorError("Timeout must be positive")

        if args.sleep:
            if args.sleep < 0:
                raise ParallelTaskExecutorError("Task start delay cannot be negative")
            if args.sleep > 60.0:
                raise ParallelTaskExecutorError("Task start delay cannot exceed 60 seconds")

        manager = ParallelTaskManager(
            max_workers=args.max,
            timeout=args.timeout,
            task_start_delay=args.sleep,
            tasks_paths=args.TasksDir,  # Now a list from action='append'
            command_template=args.Command,
            script_path=script_path,
            dry_run=not args.run,
            enable_stop_limits=args.enable_stop_limits,
            log_task_output=not args.no_task_output_log,
            file_extension=args.file_extension,
            arguments_file=args.arguments_file,
            env_var=args.env_var
        )
        
        if args.daemon:
            manager.logger.info(f"Daemon started successfully - PID: {os.getpid()}")
            # Handle both single string and list of strings
            if args.TasksDir:
                if isinstance(args.TasksDir, list):
                    task_paths_str = ', '.join(str(p) for p in args.TasksDir)
                else:
                    task_paths_str = str(args.TasksDir)
                manager.logger.info(f"Task paths: {task_paths_str}")
            else:
                manager.logger.info(f"Task paths: None")
            if args.file_extension:
                manager.logger.info(f"File extension filter: {args.file_extension}")
            manager.logger.info(f"Command template: {args.Command}")
            manager.logger.info(f"Workers: {manager.max_workers}, Timeout: {manager.timeout}s")
            manager.logger.info(f"Stop limits: {'enabled' if args.enable_stop_limits else 'disabled'}")
        
        manager._setup_signal_handlers()
        stats = manager.execute_tasks()
        
        summary = manager.get_summary_report()
        if args.daemon:
            manager.logger.info(f"Execution completed:\n{summary}")
        else:
            print(f"\n{summary}")
        
        if stats['failed'] > 0:
            sys.exit(1)
        
    except ParallelTaskExecutorError as e:
        if 'args' in locals() and args.daemon:
            logging.getLogger().error(f"Task Executor Error: {e}")
        else:
            print(f"Task Executor Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    except SecurityError as e:
        if 'args' in locals() and args.daemon:
            logging.getLogger().error(f"Security Error: {e}")
        else:
            print(f"Security Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    except ConfigurationError as e:
        if 'args' in locals() and args.daemon:
            logging.getLogger().error(f"Configuration Error: {e}")
        else:
            print(f"Configuration Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    except KeyboardInterrupt:
        if not ('args' in locals() and args.daemon):
            print("\nExecution interrupted by user", file=sys.stderr)
        sys.exit(130)
    
    except Exception as e:
        if 'args' in locals() and args.daemon:
            logging.getLogger().error(f"Unexpected error: {e}")
        else:
            print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

