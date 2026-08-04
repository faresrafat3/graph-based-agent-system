import pytest
from agents.test_runner_agent import (
    run_code_and_tests,
    validate_sandbox_filename,
    scan_code_for_risky_patterns,
    TEST_RUNNER_PERMISSIONS,
)


def test_permissions_matrix():
    """Verify Test Runner permissions matrix"""
    assert "source_code" in TEST_RUNNER_PERMISSIONS["READ"]
    assert "test_reports" in TEST_RUNNER_PERMISSIONS["WRITE"]
    assert "production_environment" in TEST_RUNNER_PERMISSIONS["NEVER"]


def test_run_valid_code_and_passing_tests():
    """Valid Python code with passing pytest suite passes cleanly"""
    source_code = '''
def calculate_total(prices: list[float], discount: float = 0.0) -> float:
    """Calculate total price after discount."""
    if discount < 0 or discount > 1.0:
        raise ValueError("Invalid discount")
    total = sum(prices)
    return total * (1.0 - discount)
'''
    test_code = '''
import pytest
from calculator import calculate_total

def test_calculate_total_basic():
    assert calculate_total([10.0, 20.0]) == 30.0

def test_calculate_total_discount():
    assert calculate_total([100.0], discount=0.2) == 80.0

def test_calculate_total_invalid_discount():
    with pytest.raises(ValueError):
        calculate_total([10.0], discount=1.5)
'''

    res = run_code_and_tests(
        filename="calculator.py",
        code=source_code,
        test_filename="test_calculator.py",
        test_code=test_code
    )

    assert res["success"] is True
    assert res["passed_tests"] == 3
    assert res["failed_tests"] == 0
    assert res["error"] is None


def test_run_code_with_failing_tests():
    """Failing pytest test suite is caught empirically"""
    source_code = '''
def add(a: int, b: int) -> int:
    return a - b  # Intentional bug!
'''
    test_code = '''
from math_op import add

def test_add():
    assert add(2, 2) == 4
'''

    res = run_code_and_tests(
        filename="math_op.py",
        code=source_code,
        test_filename="test_math_op.py",
        test_code=test_code
    )

    assert res["success"] is False
    assert res["failed_tests"] == 1
    assert "Pytest test suite failures" in res["error"]


def test_run_invalid_syntax_code():
    """Syntax error in source code fails at compilation stage"""
    source_code = "def broken(:\n    pass"
    res = run_code_and_tests(
        filename="broken.py",
        code=source_code,
        test_filename="",
        test_code=""
    )

    assert res["success"] is False
    assert res["stage"] == "compilation"
    assert "Syntax" in res["error"]


def test_reject_path_traversal_filename():
    """Generated filenames cannot escape the sandbox directory."""
    res = run_code_and_tests(
        filename="../escape.py",
        code="def safe() -> bool:\n    return True\n",
        test_filename="",
        test_code="",
    )

    assert res["success"] is False
    assert res["stage"] == "preflight"
    assert "path traversal" in res["error"].lower()


def test_reject_unsafe_runtime_patterns():
    """Generated code that tries to read environment secrets is blocked pre-execution."""
    source_code = '''
import os

def leak() -> str:
    """Attempt to read environment."""
    return os.environ.get("STEPFUN_API_KEY", "")
'''
    breaches = scan_code_for_risky_patterns(source_code, "source_code")
    assert any("environment_access" in v for v in breaches)

    res = run_code_and_tests(
        filename="leaker.py",
        code=source_code,
        test_filename="test_leaker.py",
        test_code="from leaker import leak\n\ndef test_leak():\n    assert leak() == ''\n",
    )

    assert res["success"] is False
    assert res["stage"] == "preflight"
    assert any("environment_access" in v for v in res["breaches"])


def test_validate_sandbox_filename_accepts_safe_names():
    assert validate_sandbox_filename("calculator.py") == "calculator.py"
    assert validate_sandbox_filename("test_calculator.py", is_test=True) == "test_calculator.py"


def test_validate_sandbox_filename_invalid_inputs():
    with pytest.raises(ValueError, match="Filename must be a non-empty string."):
        validate_sandbox_filename(None)
    with pytest.raises(ValueError, match="Filename must be a non-empty string."):
        validate_sandbox_filename("")
    with pytest.raises(ValueError, match="Unsafe filename path traversal rejected"):
        validate_sandbox_filename("/absolute/path.py")
    with pytest.raises(ValueError, match="Unsafe filename path traversal rejected"):
        validate_sandbox_filename("../escape.py")
    with pytest.raises(ValueError, match="Unsafe filename path traversal rejected"):
        validate_sandbox_filename("nested/path.py")
    with pytest.raises(ValueError, match="Unsafe filename 'calculator'; expected"):
        validate_sandbox_filename("calculator")
    with pytest.raises(ValueError, match="Unsafe filename 'calculator.py'; expected test_"):
        validate_sandbox_filename("calculator.py", is_test=True)


def test_resolve_inside_escapes_sandbox():
    from agents.test_runner_agent import _resolve_inside
    with pytest.raises(ValueError, match="Resolved path escaped sandbox"):
        _resolve_inside("/tmp/sandbox", "../escaped.py")


def test_run_code_with_timeout():
    source_code = "import time\ndef infinite():\n    while True:\n        time.sleep(0.01)\n"
    res = run_code_and_tests(
        filename="infinite.py",
        code=source_code,
        test_filename="test_infinite.py",
        test_code="from infinite import infinite\ndef test_inf():\n    infinite()\n",
        timeout_seconds=1
    )
    assert res["success"] is False
    assert res["stage"] == "timeout"
    assert "timed out" in res["error"]


def test_run_code_with_generic_exception(monkeypatch):
    import tempfile
    def fake_mkdtemp(*a, **k):
        raise OSError("mock os error")
    monkeypatch.setattr(tempfile, "mkdtemp", fake_mkdtemp)
    res = run_code_and_tests(
        filename="calculator.py",
        code="def add(a, b): return a + b",
        test_filename="",
        test_code=""
    )
    assert res["success"] is False
    assert res["stage"] == "runtime_error"
    assert "mock os error" in res["error"]

