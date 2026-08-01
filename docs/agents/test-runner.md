# Test Runner Agent Lifecycle

## Identity

| Field | Value |
|---|---|
| Module | `agents/test_runner_agent.py` |
| Public Entrypoint | `run_code_and_tests(...)` |
| Status | Implemented |
| Primary Role | Compile and run generated Python code/tests in a constrained temporary environment |

## Responsibility Boundary

The Test Runner executes generated Python only in a defensive local harness. It must not access production environments, credentials, external networks, or arbitrary binaries.

## Permissions

```python
TEST_RUNNER_PERMISSIONS = {
    "READ": ["source_code", "test_code", "project_structure"],
    "WRITE": ["test_reports", "execution_logs"],
    "NEVER": ["production_environment", "external_network_call", "credentials_file"],
    "HUMAN_CHECKPOINT": ["destructive_file_operations", "untrusted_binary_execution"]
}
```

## Input Contract

```python
filename: str
code: str
test_filename: str
test_code: str
timeout_seconds: int = 15
```

## Output Contract

```python
{
  "success": bool,
  "stage": str,
  "error": str | None,
  "stdout": str,
  "stderr": str,
  "passed_tests": int,
  "failed_tests": int,
  "traceback": str,
  "violations": list[str]
}
```

## Full Lifecycle

### Preflight

- Validate filenames.
- Reject path traversal.
- Reject risky runtime patterns.
- Build clean subprocess environment.

### Execute Compile

- Write source/test files inside temp directory.
- Run isolated Python compile command.

### Execute Tests

- Run pytest if test code exists.
- Capture stdout/stderr.
- Count pass/fail markers.

### Evaluate

- Compilation failure fails immediately.
- Pytest failure returns failure report.

### Cleanup

- Remove temp directory in `finally`.

## Security Note

This is not a complete kernel/container sandbox. High-risk generated code should run in Docker, gVisor, Firecracker, nsjail, or another hardened backend.

## Tests

- `tests/test_test_runner_agent.py`

## Usage

```python
from agents.test_runner_agent import run_code_and_tests

result = run_code_and_tests("calc.py", code, "test_calc.py", test_code)
```

## Improvement Plan

- Container backend.
- Network namespace isolation.
- Structured execution result object.
- Import allowlist.
