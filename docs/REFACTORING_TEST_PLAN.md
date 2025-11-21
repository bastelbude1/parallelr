# Test Suite Plan for Parallelr v2.0 Refactoring

**Goal:** Ensure complete behavioral parity between the monolithic `parallelr.py` (v1.0.x) and the modularized package (v2.0.0) by establishing a comprehensive "safety net" test suite *before* refactoring begins.

## Current State Assessment

*   **Integration Tests:** Strong (`tests/integration/`). Covers file mode, arguments mode, and output validation.
*   **Unit Tests:** Sparse (`tests/unit/`). Good coverage for some helpers (PID, placeholders), but core classes (`Configuration`, `ParallelTaskManager`) lack isolated tests.
*   **E2E Tests:** Missing (`tests/e2e/` is empty). No black-box CLI verification.
*   **Security Tests:** Good (`tests/security/`). Covers injection and path traversal.

## Required Action Items

### 1. Critical: Implement End-to-End (E2E) Tests

**Why:** To verify the CLI binary behaves exactly as expected for users, independent of internal code structure. Integration tests often use fixtures that might mask environment issues.
**Action:** Populate `tests/e2e/` with tests that invoke `bin/parallelr.py` via `subprocess` as a compiled/executable binary.
**Scenarios:**
  * Basic help and version output (`--help`, `--version`).
  * Invalid argument combinations (exit code 2 or 1).
  * Successful run in file mode.
  * Successful run in arguments mode.
  * Ptasker mode invocation (via symlink simulation or argument).

### 2. Critical: Fill Unit Test Gaps

**Why:** Refactoring involves moving classes to new files. We need to verify each class's logic in isolation to debug import/dependency issues easily.
**Action:** Create the following test files:
  * `tests/unit/test_configuration.py`:
    * Test loading script config vs user config.
    * Test `_update_limits_with_validation` (clamping logic).
    * Test `validate()` method error raises.
  * `tests/unit/test_task_manager.py`:
    * Test `_discover_tasks` logic (file vs argument mode).
    * Test `_check_error_limits` logic (auto-stop).

### 3. High: Audit Daemon & Signal Handling

**Why:** These rely on OS-level behaviors (forking, signals) that are easily broken when code moves.
**Action:**
  * Review `tests/integration/test_daemon_mode.py`. Ensure it verifies PID file creation, log file creation, and process detachment.
  * Review `tests/integration/test_signal_handling.py`. Ensure it verifies graceful shutdown on `SIGTERM`.

### 4. Medium: Coverage Audit

**Why:** Ensure no logic branches are left untested.
**Action:** Run coverage report on `bin/parallelr.py`. Target >90% coverage. Identify any "dead code" or untestable branches before refactoring.

## Execution Strategy

1.  **Implement** the tests listed above on the current `v1.0.x` codebase.
2.  **Verify** all tests pass (Green state).
3.  **Refactor** code to modular structure (v2.0).
4.  **Run** the *same* test suite. It must remain Green without modification (except imports).
