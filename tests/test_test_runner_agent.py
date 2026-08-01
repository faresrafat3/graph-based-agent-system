import pytest
from agents.test_runner_agent import run_code_and_tests, TEST_RUNNER_PERMISSIONS


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
