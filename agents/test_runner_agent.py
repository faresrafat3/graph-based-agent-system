"""
Test Runner Agent - Physical Execution & Verification Engine.
Executes generated code and pytest test suites in a constrained temporary runtime.
Provides empirical execution ground-truth to the Karpathy Loop.

Important: this is a defensive local execution harness, not a replacement for a
kernel/container sandbox. It blocks common risky patterns, cleans environment
secrets, validates paths, applies timeouts, and uses OS resource limits when
available. Untrusted code should still be isolated at the container/VM layer.
"""

import os
import re
import sys
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Permission Boundaries (Law 2)
TEST_RUNNER_PERMISSIONS = {
    "READ": ["source_code", "test_code", "project_structure"],
    "WRITE": ["test_reports", "execution_logs"],
    "NEVER": ["production_environment", "external_network_call", "credentials_file"],
    "HUMAN_CHECKPOINT": ["destructive_file_operations", "untrusted_binary_execution"]
}


_ALLOWED_FILENAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\.py$")
_ALLOWED_TEST_FILENAME_RE = re.compile(r"^test_[A-Za-z0-9_]+\.py$")
_SECRET_ENV_PATTERNS = (
    "KEY",
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "CREDENTIAL",
    "AUTH",
)
_FORBIDDEN_CODE_PATTERNS = [
    ("external_network", r"\b(?:socket|requests|httpx|aiohttp|urllib|http\.client)\b"),
    ("subprocess_execution", r"\b(?:subprocess|os\.system|pty|pexpect)\b"),
    ("dynamic_execution", r"\b(?:eval|exec|compile|__import__)\s*\("),
    ("environment_access", r"\bos\.(?:environ|getenv|putenv|unsetenv)\b"),
    ("file_system_escape", r"\b(?:open|Path)\s*\(|\b(?:shutil|glob|fnmatch)\b"),
    ("destructive_operations", r"\b(?:unlink|remove|rmdir|rmtree|rename|replace|chmod|chown)\s*\("),
    ("unsafe_modules", r"\b(?:ctypes|pickle|marshal|multiprocessing|threading)\b"),
]


def validate_sandbox_filename(filename: str, *, is_test: bool = False) -> str:
    """
    Validate that a generated filename is a safe single Python module filename.

    Args:
        filename: Candidate filename from generated output.
        is_test: Whether this is expected to be a pytest filename.

    Returns:
        The original filename if valid.

    Raises:
        ValueError: If the filename is empty, absolute, nested, or unsafe.
    """
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("Filename must be a non-empty string.")

    candidate = filename.strip()
    path = Path(candidate)
    if path.is_absolute() or len(path.parts) != 1 or ".." in path.parts:
        raise ValueError(f"Unsafe filename path traversal rejected: {filename!r}")

    pattern = _ALLOWED_TEST_FILENAME_RE if is_test else _ALLOWED_FILENAME_RE
    if not pattern.fullmatch(candidate):
        expected = "test_<name>.py" if is_test else "<module_name>.py"
        raise ValueError(f"Unsafe filename {filename!r}; expected {expected}.")

    return candidate


def _resolve_inside(base_dir: str, filename: str) -> str:
    """Resolve filename under base_dir and guarantee it stays within base_dir."""
    base = Path(base_dir).resolve()
    target = (base / filename).resolve()
    if base not in target.parents and target != base:
        raise ValueError(f"Resolved path escaped sandbox: {filename!r}")
    return str(target)


def scan_code_for_risky_patterns(code: str, label: str = "code") -> list[str]:
    """
    Deterministically reject common risky operations before physical execution.

    The checks intentionally prefer false positives over allowing generated code
    to access network, secrets, host filesystem, subprocesses, or dynamic eval.
    """
    violations = []
    text = code or ""
    for name, pattern in _FORBIDDEN_CODE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            violations.append(f"{label}: forbidden runtime pattern detected: {name}")
    return violations


def _clean_execution_env(temp_dir: str) -> dict:
    """Build a minimal subprocess environment without inherited secrets."""
    env = {
        "PYTHONPATH": temp_dir,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "HOME": temp_dir,
        "TMPDIR": temp_dir,
        "TEMP": temp_dir,
        "TMP": temp_dir,
        "PATH": os.environ.get("PATH", ""),
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
    }

    # Do not copy API keys, tokens, credentials, auth headers, etc.
    return {
        key: value for key, value in env.items()
        if not any(marker in key.upper() for marker in _SECRET_ENV_PATTERNS)
    }


def _resource_limited_preexec(timeout_seconds: int):
    """Return a preexec_fn that applies Linux/Unix resource limits when available."""
    if os.name == "nt":
        return None

    def _apply_limits():
        try:
            import resource

            cpu_limit = max(1, int(timeout_seconds))
            memory_limit = 512 * 1024 * 1024  # 512 MiB
            file_size_limit = 10 * 1024 * 1024  # 10 MiB
            process_limit = 32

            resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit + 1))
            resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
            resource.setrlimit(resource.RLIMIT_FSIZE, (file_size_limit, file_size_limit))
            if hasattr(resource, "RLIMIT_NPROC"):
                resource.setrlimit(resource.RLIMIT_NPROC, (process_limit, process_limit))
        except Exception:
            # Best-effort: subprocess timeout and static preflight still apply.
            pass

    return _apply_limits


def _run_subprocess(cmd: list[str], temp_dir: str, timeout_seconds: int) -> subprocess.CompletedProcess:
    """Run a constrained subprocess in the temporary execution directory."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=temp_dir,
        env=_clean_execution_env(temp_dir),
        timeout=timeout_seconds,
        preexec_fn=_resource_limited_preexec(timeout_seconds),
    )


def _failure(stage: str, error: str, violations: Optional[list[str]] = None, stdout: str = "", stderr: str = "") -> dict:
    """Build a standard Test Runner failure response."""
    return {
        "success": False,
        "stage": stage,
        "error": error,
        "stdout": stdout,
        "stderr": stderr,
        "passed_tests": 0,
        "failed_tests": 0,
        "traceback": stderr or error,
        "violations": violations or [],
    }


def run_code_and_tests(
    filename: str,
    code: str,
    test_filename: str,
    test_code: str,
    timeout_seconds: int = 15
) -> dict:
    """
    Execute Python source code and pytest tests inside a constrained temp dir.

    Args:
        filename: Safe source module filename, e.g. ``calculator.py``.
        code: Source code content.
        test_filename: Safe pytest filename, e.g. ``test_calculator.py``.
        test_code: Pytest test code content.
        timeout_seconds: Max execution timeout.

    Returns:
        Dict with success status, output, pass/fail counts, and violations.
    """
    try:
        safe_filename = validate_sandbox_filename(filename, is_test=False)
        safe_test_filename = ""
        if test_filename or test_code:
            safe_test_filename = validate_sandbox_filename(test_filename, is_test=True)
    except ValueError as exc:
        return _failure("preflight", str(exc), violations=[str(exc)])

    violations = []
    violations.extend(scan_code_for_risky_patterns(code, "source_code"))
    if test_code:
        violations.extend(scan_code_for_risky_patterns(test_code, "test_code"))
    if violations:
        return _failure(
            "preflight",
            "Unsafe generated code rejected before execution",
            violations=violations,
        )

    temp_dir = tempfile.mkdtemp(prefix="agent_sandbox_")

    try:
        source_path = _resolve_inside(temp_dir, safe_filename)
        with open(source_path, "w", encoding="utf-8") as f:
            f.write(code)

        test_path = None
        if safe_test_filename and test_code:
            test_path = _resolve_inside(temp_dir, safe_test_filename)
            with open(test_path, "w", encoding="utf-8") as f:
                f.write(test_code)

        # Stage 1: Syntax & Import Check (python -m py_compile)
        compile_cmd = [sys.executable, "-I", "-m", "py_compile", source_path]
        comp_proc = _run_subprocess(compile_cmd, temp_dir, timeout_seconds)

        if comp_proc.returncode != 0:
            return _failure(
                "compilation",
                "Compilation/Syntax error detected",
                stdout=comp_proc.stdout,
                stderr=comp_proc.stderr,
            )

        # Stage 2: Pytest Execution if test file exists
        if test_path:
            pytest_cmd = [sys.executable, "-I", "-m", "pytest", test_path, "-v", "--tb=short", "-p", "no:cacheprovider"]
            test_proc = _run_subprocess(pytest_cmd, temp_dir, timeout_seconds)

            output = test_proc.stdout + "\n" + test_proc.stderr
            is_success = test_proc.returncode == 0
            passed_count = output.count(" PASSED")
            failed_count = output.count(" FAILED")

            # Law 3: distinguish a genuine test failure from a broken harness.
            # pytest exit codes: 0=all passed, 1=tests failed, 2=interrupted,
            # 3=internal error, 4=usage error, 5=no tests collected.
            # Without this split, a broken sandbox is silently reported as a code
            # defect — the exact class of failure Law 3 exists to prevent.
            if not is_success and failed_count == 0 and test_proc.returncode in (2, 3, 4, 5):
                return _failure(
                    "harness_error",
                    (
                        f"Test harness error (pytest exit code {test_proc.returncode}) — "
                        "not a code defect. Check the sandbox environment."
                    ),
                    stdout=test_proc.stdout,
                    stderr=test_proc.stderr,
                )

            return {
                "success": is_success,
                "stage": "testing",
                "error": None if is_success else "Pytest test suite failures detected",
                "stdout": test_proc.stdout,
                "stderr": test_proc.stderr,
                "passed_tests": passed_count,
                "failed_tests": failed_count,
                "traceback": test_proc.stdout if not is_success else "",
                "violations": [],
            }

        return {
            "success": True,
            "stage": "compilation",
            "error": None,
            "stdout": "Source compiled cleanly",
            "stderr": "",
            "passed_tests": 0,
            "failed_tests": 0,
            "traceback": "",
            "violations": [],
        }

    except subprocess.TimeoutExpired:
        return _failure(
            "timeout",
            f"Execution timed out after {timeout_seconds} seconds",
            stderr="TimeoutExpired",
        )
    except Exception as exc:
        return _failure("runtime_error", f"Test runner failed safely: {exc}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
