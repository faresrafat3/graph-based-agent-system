import pytest
from agents.code_executor import (
    validate_python_syntax,
    extract_code_from_response,
    CODE_EXECUTOR_PERMISSIONS,
    execute_task
)


def test_permissions_matrix():
    """Verify NEVER permissions are defined"""
    assert "credentials" in CODE_EXECUTOR_PERMISSIONS["NEVER"]
    assert "deployment" in CODE_EXECUTOR_PERMISSIONS["NEVER"]
    assert "source_code" in CODE_EXECUTOR_PERMISSIONS["WRITE"]
    assert "test_code" in CODE_EXECUTOR_PERMISSIONS["WRITE"]


def test_validate_python_syntax_valid():
    """Valid Python code passes AST validation"""
    code = '''
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

class Calculator:
    """Simple calculator."""
    
    def multiply(self, a: int, b: int) -> int:
        """Multiply two numbers."""
        try:
            return a * b
        except TypeError:
            raise ValueError("Invalid input")
'''
    result = validate_python_syntax(code)
    assert result["success"] is True
    assert len(result["violations"]) == 0
    assert result["metrics"]["function_count"] >= 2
    assert result["metrics"]["class_count"] == 1
    assert result["metrics"]["has_docstrings"] is True
    assert result["metrics"]["has_type_hints"] is True
    assert result["metrics"]["has_error_handling"] is True


def test_validate_python_syntax_invalid():
    """Invalid Python code fails AST validation"""
    code = "def broken_function(:\n    return"
    result = validate_python_syntax(code)
    assert result["success"] is False
    assert len(result["violations"]) > 0
    assert "SyntaxError" in result["violations"][0]


def test_validate_security_violations():
    """Hardcoded secrets are flagged as security violations"""
    code = '''
def connect():
    """Connect to DB."""
    password = "super_secret_123"
    return password
'''
    result = validate_python_syntax(code)
    assert result["success"] is False
    assert any("password" in v.lower() for v in result["violations"])


def test_validate_empty_code():
    """Empty code with no functions/classes is flagged"""
    code = "x = 1\ny = 2\nz = x + y"
    result = validate_python_syntax(code)
    assert result["success"] is False
    assert any("incomplete" in v.lower() for v in result["violations"])


def test_extract_code_from_response_json():
    """Valid JSON response is extracted correctly"""
    response = '{"filename": "auth.py", "code": "def login(): pass", "test_filename": "test_auth.py", "test_code": "def test_login(): pass", "imports_required": [], "description": "Auth module"}'
    result = extract_code_from_response(response)
    assert result["success"] is True
    assert result["filename"] == "auth.py"
    assert "login" in result["code"]


def test_extract_code_from_response_markdown():
    """JSON wrapped in markdown fences is extracted correctly"""
    response = '```json\n{"filename": "utils.py", "code": "def helper(): pass", "test_filename": "test_utils.py", "test_code": "", "imports_required": [], "description": "Utils"}\n```'
    result = extract_code_from_response(response)
    assert result["success"] is True
    assert result["filename"] == "utils.py"


def test_extract_code_from_response_invalid():
    """Invalid response returns success=False"""
    response = "This is not JSON at all"
    result = extract_code_from_response(response)
    assert result["success"] is False


def test_execute_task_permission_boundary():
    """Tasks touching NEVER permissions are blocked"""
    task = {
        "title": "Deploy to production",
        "description": "Deploy the application to production servers",
        "type": "deployment"
    }
    result = execute_task(task)
    assert result["success"] is False
    assert "PermissionError" in result["error"]


def test_execute_task_credentials_blocked():
    """Tasks involving credentials are blocked"""
    task = {
        "title": "Store database credentials",
        "description": "Save production database credentials to config",
        "type": "feature"
    }
    result = execute_task(task)
    assert result["success"] is False
    assert "credentials" in result["error"].lower()


def test_execute_task_fails_when_test_code_invalid(monkeypatch):
    """Package success requires both generated code and generated tests to validate."""
    import agents.code_executor as code_executor_module

    response = {
        "filename": "calculator.py",
        "code": "def add(a: int, b: int) -> int:\n    \"\"\"Add numbers.\"\"\"\n    return a + b\n",
        "test_filename": "test_calculator.py",
        "test_code": "def broken(:\n    pass",
        "imports_required": [],
        "description": "Calculator module",
    }
    monkeypatch.setattr(code_executor_module, "call_llm", lambda *args, **kwargs: __import__("json").dumps(response))

    task = {
        "title": "Implement add function",
        "description": "Create a safe arithmetic helper",
        "type": "feature",
        "acceptance_criteria": ["Adds two numbers"],
    }

    result = execute_task(task, max_retries=0)
    assert result["success"] is False
    assert result["test_valid"] is False
    assert any("SyntaxError" in v for v in result["test_violations"])


def test_execute_task_rejects_unsafe_filenames(monkeypatch):
    """Generated files must be safe module filenames before execution."""
    import agents.code_executor as code_executor_module

    response = {
        "filename": "../escape.py",
        "code": "def safe() -> bool:\n    \"\"\"Safe function.\"\"\"\n    return True\n",
        "test_filename": "test_escape.py",
        "test_code": "",
        "imports_required": [],
        "description": "Unsafe filename",
    }
    monkeypatch.setattr(code_executor_module, "call_llm", lambda *args, **kwargs: __import__("json").dumps(response))

    task = {
        "title": "Implement safe helper",
        "description": "Create a safe helper",
        "type": "feature",
        "acceptance_criteria": ["Helper exists"],
    }

    result = execute_task(task, max_retries=0)
    assert result["success"] is False
    assert any("Unsafe source filename" in v for v in result["violations"])


def test_execute_task_json_parsing_failed(monkeypatch):
    import agents.code_executor as code_executor_module
    monkeypatch.setattr(code_executor_module, "call_llm", lambda *a, **k: "this is not json")
    
    task = {
        "title": "Implement add function",
        "description": "Create a safe arithmetic helper",
        "type": "feature",
        "acceptance_criteria": ["Adds two numbers"],
    }
    
    result = execute_task(task, max_retries=0)
    assert result["success"] is False
    assert "Failed to extract valid code" in result["error"]


def test_execute_task_surgical_refinement_loop(monkeypatch):
    import agents.code_executor as code_executor_module
    import json
    
    # First response has syntax error, second response is valid
    call_count = {"llm": 0}
    
    def fake_llm(*args, **kwargs):
        call_count["llm"] += 1
        if call_count["llm"] == 1:
            return json.dumps({
                "filename": "calculator.py",
                "code": "def broken(:\n    pass",
                "test_filename": "test_calculator.py",
                "test_code": "",
                "imports_required": [],
                "description": "Broken"
            })
        else:
            return json.dumps({
                "filename": "calculator.py",
                "code": "def add(a: int, b: int) -> int:\n    \"\"\"Add numbers.\"\"\"\n    return a + b\n",
                "test_filename": "test_calculator.py",
                "test_code": "def test_add():\n    \"\"\"Test add.\"\"\"\n    assert 1 == 1\n",
                "imports_required": [],
                "description": "Fixed"
            })
            
    monkeypatch.setattr(code_executor_module, "call_llm", fake_llm)
    
    task = {
        "title": "Implement add function",
        "description": "Create a safe arithmetic helper",
        "type": "feature",
        "acceptance_criteria": ["Adds two numbers"],
    }
    
    result = execute_task(task, max_retries=2)
    assert result["success"] is True
    assert call_count["llm"] == 2
    assert "add" in result["code"]
    assert result["refinement_attempts"] == 1


def test_execute_task_rejects_unsafe_test_filenames(monkeypatch):
    import agents.code_executor as code_executor_module
    import json

    response = {
        "filename": "calculator.py",
        "code": "def add(a: int, b: int) -> int:\n    \"\"\"Add numbers.\"\"\"\n    return a + b\n",
        "test_filename": "../test_calculator.py", # Unsafe test filename
        "test_code": "def test_add(): pass",
        "imports_required": [],
        "description": "Calculator module",
    }
    monkeypatch.setattr(code_executor_module, "call_llm", lambda *args, **kwargs: json.dumps(response))

    task = {
        "title": "Implement add function",
        "description": "Create a safe arithmetic helper",
        "type": "feature",
        "acceptance_criteria": ["Adds two numbers"],
    }

    result = execute_task(task, max_retries=0)
    assert result["success"] is False
    assert any("Unsafe test filename" in v for v in result["violations"])


def test_execute_task_refinement_extraction_failed(monkeypatch):
    import agents.code_executor as code_executor_module
    import json
    
    # First response has syntax error, second response has invalid JSON
    call_count = {"llm": 0}
    
    def fake_llm(*args, **kwargs):
        call_count["llm"] += 1
        if call_count["llm"] == 1:
            return json.dumps({
                "filename": "calculator.py",
                "code": "def broken(:\n    pass",
                "test_filename": "test_calculator.py",
                "test_code": "",
                "imports_required": [],
                "description": "Broken"
            })
        else:
            return "completely invalid JSON response"
            
    monkeypatch.setattr(code_executor_module, "call_llm", fake_llm)
    
    task = {
        "title": "Implement add function",
        "description": "Create a safe arithmetic helper",
        "type": "feature",
        "acceptance_criteria": ["Adds two numbers"],
    }
    
    result = execute_task(task, max_retries=1)
    assert result["success"] is False
    assert "JSON extraction failed during surgical refinement" in result["violations"][0]


