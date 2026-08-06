"""
Code Execution Agent - Takes decomposed tasks and generates production-grade code.
Implements the Karpathy Loop: Propose → Execute → Evaluate → Commit/Refine.

The LLM is sandboxed as CPU — it generates code.
All validation is deterministic (AST parsing, syntax checks, import verification).
"""

import os
import sys
import ast
import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.llm_integration import call_llm
from tools.json_output_parser import parse_json_object_response
from agents.deterministic_validator import (
    DeterministicValidatorEngine,
    apply_verify_verdict,
    digest,
    record_effect,
    verified_closure_enabled,
)


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
    breaches = []
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
        breaches.append(f"SyntaxError at line {e.lineno}: {e.msg}")
        return {"success": False, "breaches": breaches, "metrics": metrics}
    
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
    security_breaches = []
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
            security_breaches.append(f"Security breach: {name} detected in generated code")
    
    breaches.extend(security_breaches)
    
    # Stage 4: Quality gate
    if metrics["function_count"] == 0 and metrics["class_count"] == 0:
        breaches.append("No functions or classes found — code appears to be incomplete")
    
    return {
        "success": len(breaches) == 0,
        "breaches": breaches,
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
    breaches = []
    source = extracted.get("filename", "")
    test = extracted.get("test_filename", "")

    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*\.py", str(source)):
        breaches.append(f"Unsafe source filename: {source!r}")

    if test and not re.fullmatch(r"test_[A-Za-z0-9_]+\.py", str(test)):
        breaches.append(f"Unsafe test filename: {test!r}")

    return breaches


def _validate_extracted_code_package(extracted: dict) -> tuple:
    """Validate generated code, test code, and filenames as one package."""
    filename_breaches = _validate_generated_filenames(extracted)
    code_validation = validate_python_syntax(extracted.get("code", ""))
    test_code = extracted.get("test_code", "")
    test_validation = {"success": True, "breaches": [], "metrics": {}}
    if test_code:
        test_validation = validate_python_syntax(test_code)

    combined_breaches = []
    combined_breaches.extend(filename_breaches)
    combined_breaches.extend(code_validation["breaches"])
    combined_breaches.extend([f"Test code: {v}" for v in test_validation["breaches"]])

    success = (
        not filename_breaches
        and code_validation["success"]
        and test_validation["success"]
    )
    return success, code_validation, test_validation, combined_breaches


def _write_code_artifacts(output_dir: str, extracted: dict) -> dict:
    """Materialise the generated package on disk — the code executor's write edge.

    Never raises: a failed write leaves the declared postcondition unsatisfied, and
    the VERIFY node downgrades the result. Filenames are already constrained to a
    single safe module name by _validate_generated_filenames.
    """
    paths = {}
    try:
        base = Path(output_dir)
        base.mkdir(parents=True, exist_ok=True)
        source_path = base / Path(extracted.get("filename", "")).name
        source_path.write_text(extracted.get("code", ""), encoding="utf-8")
        paths["source_path"] = str(source_path)
        test_code = extracted.get("test_code", "")
        if extracted.get("test_filename") and test_code:
            test_path = base / Path(extracted["test_filename"]).name
            test_path.write_text(test_code, encoding="utf-8")
            paths["test_path"] = str(test_path)
    except OSError as exc:
        logger.warning("Code artifact write failed under %s: %s", output_dir, exc)
    return paths


def execute_task(task: dict, project_context: str = "", max_retries: int = 3, output_dir: "str | None" = None) -> dict:
    """
    Full Karpathy Loop for code execution:
    Propose → Execute (LLM) → Evaluate (AST) → Commit/Refine → VERIFY (P2)
    
    Args:
        task: Decomposed task dict with title, description, type, acceptance_criteria
        project_context: Project context string
        max_retries: Max surgical refinement attempts
        output_dir: Optional directory to materialise the generated package into.
            When omitted the artifact is recorded as a P2 effect file instead, so the
            write edge always terminates in a checkable postcondition.
        
    Returns:
        Dict with generated code, validation results, postcondition verdict, metadata
    """
    
    # === P2: postcondition declared at PROPOSE time (before any write) ===
    postcondition = {"kind": "non_empty", "path": None}

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
                "breaches": [f"NEVER permission breachd: {forbidden}"]
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
            "breaches": ["JSON extraction failed"]
        }
    
    # === Stage 4: Evaluate package — code, tests, filenames (Zero-LLM) ===
    package_success, validation, test_validation, combined_breaches = _validate_extracted_code_package(extracted)

    # === Stage 5: Surgical Refinement Loop ===
    attempt = 0
    while not package_success and attempt < max_retries:
        attempt += 1

        fix_prompt = (
            "SURGICAL CORRECTION REQUIRED.\n"
            "The following deterministic breaches were found in the generated package:\n"
            + "\n".join(f"- {v}" for v in combined_breaches) +
            f"\n\nOriginal task: {task.get('title')}\n"
            "Fix ONLY the breaches listed above. Preserve unchanged correct code and tests.\n"
            "Output ONLY valid JSON with filename, code, test_filename, test_code, imports_required, and description."
        )

        llm_response = call_llm(fix_prompt, CODE_GENERATION_PROMPT)
        refined = extract_code_from_response(llm_response)

        if refined["success"]:
            extracted = refined
            package_success, validation, test_validation, combined_breaches = _validate_extracted_code_package(extracted)
        else:
            combined_breaches = ["JSON extraction failed during surgical refinement"]

    test_code = extracted.get("test_code", "")

    result = {
        "success": package_success,
        "filename": extracted["filename"],
        "code": extracted.get("code", ""),
        "test_filename": extracted["test_filename"],
        "test_code": test_code,
        "imports_required": extracted["imports_required"],
        "description": extracted["description"],
        "code_metrics": validation["metrics"],
        "code_breaches": validation["breaches"],
        "test_valid": test_validation["success"],
        "test_breaches": test_validation["breaches"],
        "breaches": combined_breaches,
        "refinement_attempts": attempt
    }

    # === Stage 6: WRITE + VERIFY node (P2 — Verified Closure) ===
    # The agent does not get to close on its own report. It writes the artifact
    # (to output_dir when given, otherwise as a recorded effect) and the
    # zero-LLM verifier decides whether the write actually landed.
    if verified_closure_enabled() and package_success:
        code_text = extracted.get("code", "")
        if output_dir:
            written = _write_code_artifacts(output_dir, extracted)
            result["artifact_paths"] = written
            postcondition["path"] = written.get("source_path", str(Path(output_dir) / extracted["filename"]))
        else:
            postcondition["path"] = record_effect("code_executor", {
                "task_title": task.get("title", ""),
                "filename": extracted["filename"],
                "code_sha256": digest(code_text),
                "code_bytes": len(code_text.encode("utf-8")),
                "test_filename": extracted["test_filename"],
                "test_bytes": len(test_code.encode("utf-8")),
            })
        verify_breaches = DeterministicValidatorEngine.verify_execution_postcondition(postcondition)
        result = apply_verify_verdict(result, postcondition, verify_breaches)

    return result
