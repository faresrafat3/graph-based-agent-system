"""
Code Execution Agent - Takes decomposed tasks and generates production-grade code.
Implements the Karpathy Loop: Propose → Execute → Evaluate → Commit/Refine.

The LLM is sandboxed as CPU — it generates code.
All validation is deterministic (AST parsing, syntax checks, import verification).
"""

import os
import sys
import ast
import json
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.llm_integration import call_llm
from tools.json_output_parser import parse_json_object_response


# Permission Boundaries (Law 2)
CODE_EXECUTOR_PERMISSIONS = {
    "READ": ["task_specification", "project_context", "file_structure"],
    "WRITE": ["source_code", "test_code", "file_structure"],
    "NEVER": ["credentials", "deployment", "database_migrations", "production_config"],
    "HUMAN_CHECKPOINT": ["security_critical_code", "payment_logic", "auth_bypass"]
}


# System Prompt for Code Generation
CODE_GENERATION_PROMPT = """You are a Code Execution Agent. Your ONLY job is to generate 
production-grade Python code for a given task specification.

## Core Principles (Karpathy Engineering)

1. Write COMPLETE, RUNNABLE code — never leave TODOs or placeholders
2. Include proper error handling and type hints
3. Follow PEP 8 and Python best practices
4. Include docstrings for all public functions and classes
5. Generate corresponding unit tests

## Output Format (JSON)

{
  "filename": "module_name.py",
  "code": "full Python source code here",
  "test_filename": "test_module_name.py",
  "test_code": "full pytest test code here",
  "imports_required": ["package1", "package2"],
  "description": "Brief description of what this code does"
}

## Constraints

- Output ONLY valid JSON
- Code MUST be syntactically valid Python
- Code MUST include type hints
- Code MUST include docstrings
- Tests MUST use pytest
- NEVER include credentials, secrets, or hardcoded passwords
- NEVER include deployment or infrastructure code
"""


def validate_python_syntax(code: str) -> dict:
    """
    Deterministic AST-based Python syntax validator (Zero-LLM).
    
    Returns:
        Dict with success, errors list, and metrics
    """
    violations = []
    metrics = {
        "has_docstrings": False,
        "has_type_hints": False,
        "has_error_handling": False,
        "function_count": 0,
        "class_count": 0
    }
    
    # Stage 1: AST Parse — is it valid Python?
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        violations.append(f"SyntaxError at line {e.lineno}: {e.msg}")
        return {"success": False, "violations": violations, "metrics": metrics}
    
    # Stage 2: Structural analysis
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            metrics["function_count"] += 1
            
            # Check docstring
            if (node.body and isinstance(node.body[0], ast.Expr) and 
                isinstance(node.body[0].value, ast.Constant)):
                metrics["has_docstrings"] = True
            
            # Check type hints (return annotation)
            if node.returns is not None:
                metrics["has_type_hints"] = True
                
        elif isinstance(node, ast.ClassDef):
            metrics["class_count"] += 1
            
            # Check class docstring
            if (node.body and isinstance(node.body[0], ast.Expr) and 
                isinstance(node.body[0].value, ast.Constant)):
                metrics["has_docstrings"] = True
                
        elif isinstance(node, (ast.Try, ast.ExceptHandler)):
            metrics["has_error_handling"] = True
    
    # Stage 3: Security boundary checks (NEVER permissions)
    security_violations = []
    forbidden_patterns = [
        ("password", r'password\s*=\s*["\'][^"\']+["\']'),
        ("secret_key", r'secret[_]?key\s*=\s*["\'][^"\']+["\']'),
        ("api_key_hardcoded", r'api[_]?key\s*=\s*["\'](?!your-|placeholder)[^"\']+["\']'),
        ("os.system", r'os\.system\s*\('),
        ("subprocess_shell", r'subprocess\.\w+\(.*shell\s*=\s*True'),
        ("eval_exec", r'\b(?:eval|exec)\s*\('),
    ]
    
    for name, pattern in forbidden_patterns:
        if re.search(pattern, code, re.IGNORECASE):
            security_violations.append(f"Security violation: {name} detected in generated code")
    
    violations.extend(security_violations)
    
    # Stage 4: Quality gate
    if metrics["function_count"] == 0 and metrics["class_count"] == 0:
        violations.append("No functions or classes found — code appears to be incomplete")
    
    return {
        "success": len(violations) == 0,
        "violations": violations,
        "metrics": metrics
    }


def extract_code_from_response(llm_response: str) -> dict:
    """
    Deterministic JSON/code extraction from LLM response (Zero-LLM).
    Handles markdown fences, raw JSON, and partial responses.
    """
    raw = llm_response.strip()
    
    parsed = parse_json_object_response(raw)
    if parsed["success"]:
        result = parsed["data"]
        return {
            "success": True,
            "filename": result.get("filename", "generated_module.py"),
            "code": result.get("code", ""),
            "test_filename": result.get("test_filename", "test_generated_module.py"),
            "test_code": result.get("test_code", ""),
            "imports_required": result.get("imports_required", []),
            "description": result.get("description", "")
        }

    return {
        "success": False,
        "filename": "",
        "code": "",
        "test_filename": "",
        "test_code": "",
        "imports_required": [],
        "description": "Failed to parse LLM code generation response"
    }


def _validate_generated_filenames(extracted: dict) -> list:
    """Validate generated filenames before downstream file writes or execution."""
    violations = []
    source = extracted.get("filename", "")
    test = extracted.get("test_filename", "")

    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*\.py", str(source)):
        violations.append(f"Unsafe source filename: {source!r}")

    if test and not re.fullmatch(r"test_[A-Za-z0-9_]+\.py", str(test)):
        violations.append(f"Unsafe test filename: {test!r}")

    return violations


def _validate_extracted_code_package(extracted: dict) -> tuple:
    """Validate generated code, test code, and filenames as one package."""
    filename_violations = _validate_generated_filenames(extracted)
    code_validation = validate_python_syntax(extracted.get("code", ""))
    test_code = extracted.get("test_code", "")
    test_validation = {"success": True, "violations": [], "metrics": {}}
    if test_code:
        test_validation = validate_python_syntax(test_code)

    combined_violations = []
    combined_violations.extend(filename_violations)
    combined_violations.extend(code_validation["violations"])
    combined_violations.extend([f"Test code: {v}" for v in test_validation["violations"]])

    success = (
        not filename_violations
        and code_validation["success"]
        and test_validation["success"]
    )
    return success, code_validation, test_validation, combined_violations


def execute_task(task: dict, project_context: str = "", max_retries: int = 3) -> dict:
    """
    Full Karpathy Loop for code execution:
    Propose → Execute (LLM) → Evaluate (AST) → Commit/Refine
    
    Args:
        task: Decomposed task dict with title, description, type, acceptance_criteria
        project_context: Project context string
        max_retries: Max surgical refinement attempts
        
    Returns:
        Dict with generated code, validation results, and metadata
    """
    
    # === Permission Boundary Check ===
    task_title = task.get("title", "").lower()
    task_desc = task.get("description", "").lower()
    task_type = task.get("type", "").lower()
    combined = f"{task_title} {task_desc} {task_type}"
    
    for forbidden in CODE_EXECUTOR_PERMISSIONS["NEVER"]:
        forbidden_clean = forbidden.replace("_", " ")
        if forbidden_clean in combined or forbidden in combined:
            return {
                "success": False,
                "error": f"PermissionError: Task touches NEVER boundary '{forbidden}'",
                "code": "",
                "test_code": "",
                "violations": [f"NEVER permission violated: {forbidden}"]
            }
    
    # === Stage 1: Propose — Build the prompt ===
    acceptance = task.get("acceptance_criteria", [])
    acceptance_str = "\n".join(f"- {c}" for c in acceptance) if acceptance else "- Code works correctly"
    
    prompt = f"""Task: {task.get('title', 'Untitled')}
Description: {task.get('description', 'No description')}
Type: {task.get('type', 'feature')}
Priority: {task.get('priority', 'medium')}

Project Context: {project_context}

Acceptance Criteria:
{acceptance_str}

Generate complete, production-grade Python code for this task. Output ONLY valid JSON."""
    
    # === Stage 2: Execute — Call LLM (sandboxed CPU) ===
    llm_response = call_llm(prompt, CODE_GENERATION_PROMPT)
    
    # === Stage 3: Extract — Deterministic parsing ===
    extracted = extract_code_from_response(llm_response)
    
    if not extracted["success"]:
        return {
            "success": False,
            "error": "Failed to extract valid code from LLM response",
            "code": "",
            "test_code": "",
            "violations": ["JSON extraction failed"]
        }
    
    # === Stage 4: Evaluate package — code, tests, filenames (Zero-LLM) ===
    package_success, validation, test_validation, combined_violations = _validate_extracted_code_package(extracted)

    # === Stage 5: Surgical Refinement Loop ===
    attempt = 0
    while not package_success and attempt < max_retries:
        attempt += 1

        fix_prompt = (
            "SURGICAL CORRECTION REQUIRED.\n"
            "The following deterministic violations were found in the generated package:\n"
            + "\n".join(f"- {v}" for v in combined_violations) +
            f"\n\nOriginal task: {task.get('title')}\n"
            "Fix ONLY the violations listed above. Preserve unchanged correct code and tests.\n"
            "Output ONLY valid JSON with filename, code, test_filename, test_code, imports_required, and description."
        )

        llm_response = call_llm(fix_prompt, CODE_GENERATION_PROMPT)
        refined = extract_code_from_response(llm_response)

        if refined["success"]:
            extracted = refined
            package_success, validation, test_validation, combined_violations = _validate_extracted_code_package(extracted)
        else:
            combined_violations = ["JSON extraction failed during surgical refinement"]

    test_code = extracted.get("test_code", "")

    return {
        "success": package_success,
        "filename": extracted["filename"],
        "code": extracted.get("code", ""),
        "test_filename": extracted["test_filename"],
        "test_code": test_code,
        "imports_required": extracted["imports_required"],
        "description": extracted["description"],
        "code_metrics": validation["metrics"],
        "code_violations": validation["violations"],
        "test_valid": test_validation["success"],
        "test_violations": test_validation["violations"],
        "violations": combined_violations,
        "refinement_attempts": attempt
    }
