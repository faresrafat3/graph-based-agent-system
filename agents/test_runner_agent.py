"""
Test Runner Agent - Physical Execution & Verification Engine.
Executes generated code and pytest test suites in a sandboxed runtime environment.
Provides empirical execution ground-truth to the Karpathy Loop.
"""

import os
import sys
import subprocess
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Permission Boundaries (Law 2)
TEST_RUNNER_PERMISSIONS = {
    "READ": ["source_code", "test_code", "project_structure"],
    "WRITE": ["test_reports", "execution_logs"],
    "NEVER": ["production_environment", "external_network_call", "credentials_file"],
    "HUMAN_CHECKPOINT": ["destructive_file_operations", "untrusted_binary_execution"]
}


def run_code_and_tests(
    filename: str,
    code: str,
    test_filename: str,
    test_code: str,
    timeout_seconds: int = 15
) -> dict:
    """
    Executes Python source code and test code physically inside an isolated temporary directory.
    Uses pytest for zero-LLM empirical verification (Ground Truth).
    
    Args:
        filename: Name of the Python source file (e.g., 'auth.py')
        code: Source code content
        test_filename: Name of the test file (e.g., 'test_auth.py')
        test_code: Pytest test code content
        timeout_seconds: Max execution timeout
        
    Returns:
        Dict with success status, test output, pass count, fail count, and tracebacks
    """
    
    # Create isolated temporary execution directory
    temp_dir = tempfile.mkdtemp(prefix="agent_sandbox_")
    
    try:
        # Write source code file
        source_path = os.path.join(temp_dir, filename)
        with open(source_path, "w", encoding="utf-8") as f:
            f.write(code)
            
        # Write test code file if provided
        test_path = None
        if test_filename and test_code:
            test_path = os.path.join(temp_dir, test_filename)
            with open(test_path, "w", encoding="utf-8") as f:
                f.write(test_code)
                
        # Stage 1: Syntax & Import Check (python -m py_compile)
        compile_cmd = [sys.executable, "-m", "py_compile", source_path]
        comp_proc = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=timeout_seconds)
        
        if comp_proc.returncode != 0:
            return {
                "success": False,
                "stage": "compilation",
                "error": "Compilation/Syntax error detected",
                "stdout": comp_proc.stdout,
                "stderr": comp_proc.stderr,
                "passed_tests": 0,
                "failed_tests": 0,
                "traceback": comp_proc.stderr
            }
            
        # Stage 2: Pytest Execution if test file exists
        if test_path:
            pytest_cmd = [sys.executable, "-m", "pytest", test_path, "-v", "--tb=short"]
            env = os.environ.copy()
            env["PYTHONPATH"] = temp_dir
            
            test_proc = subprocess.run(
                pytest_cmd,
                capture_output=True,
                text=True,
                cwd=temp_dir,
                env=env,
                timeout=timeout_seconds
            )
            
            output = test_proc.stdout + "\n" + test_proc.stderr
            is_success = test_proc.returncode == 0
            
            # Extract pass/fail counts
            passed_count = output.count(" PASSED")
            failed_count = output.count(" FAILED")
            
            return {
                "success": is_success,
                "stage": "testing",
                "error": None if is_success else "Pytest test suite failures detected",
                "stdout": test_proc.stdout,
                "stderr": test_proc.stderr,
                "passed_tests": passed_count,
                "failed_tests": failed_count,
                "traceback": test_proc.stdout if not is_success else ""
            }
        else:
            # Source compiled successfully, no tests provided
            return {
                "success": True,
                "stage": "compilation",
                "error": None,
                "stdout": "Source compiled cleanly",
                "stderr": "",
                "passed_tests": 0,
                "failed_tests": 0,
                "traceback": ""
            }
            
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stage": "timeout",
            "error": f"Execution timed out after {timeout_seconds} seconds",
            "stdout": "",
            "stderr": "TimeoutExpired",
            "passed_tests": 0,
            "failed_tests": 0,
            "traceback": "Execution process hung or infinite loop detected"
        }
    finally:
        # Clean up temporary sandbox directory
        shutil.rmtree(temp_dir, ignore_errors=True)
