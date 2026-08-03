"""
Distributed governance check suite.

This module is intentionally NOT an agent and NOT a supreme decision maker. It is
an independent set of small deterministic checks used by CI and maintainers to
surface governance drift. Each check owns a narrow invariant and reports facts;
no LLM calls are used and no system-level business decision is delegated here.
"""

import ast
import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from system.agent_registry import AGENT_REGISTRY


REQUIRED_REGISTRY_KEYS = {"name", "module", "entrypoint", "lifecycle_doc", "test_file", "category"}
REQUIRED_PERMISSION_KEYS = {"READ", "WRITE", "NEVER", "HUMAN_CHECKPOINT"}


@dataclass(frozen=True)
class GovernanceCheckResult:
    """Result for one narrow governance check."""

    check_name: str
    success: bool
    violations: list[str]


def module_path(module_name: str) -> Path:
    """Convert a dotted module path to a Python source path."""
    return Path(*module_name.split(".")).with_suffix(".py")


def check_registry_shape(registry: list[dict] | None = None) -> GovernanceCheckResult:
    """Verify that registry entries expose required catalog fields."""
    registry = AGENT_REGISTRY if registry is None else registry
    violations = []
    if not isinstance(registry, list):
        return GovernanceCheckResult("registry_shape", False, ["registry must be a list."])

    seen_names = set()
    for entry in registry:
        name = entry.get("name", "<unknown>") if isinstance(entry, dict) else "<invalid>"
        if not isinstance(entry, dict):
            violations.append("registry entries must be dictionaries.")
            continue
        missing = sorted(REQUIRED_REGISTRY_KEYS - set(entry))
        if missing:
            violations.append(f"Registry entry '{name}' missing keys: {missing}.")
        if name in seen_names:
            violations.append(f"Duplicate registry entry name: '{name}'.")
        seen_names.add(name)

    return GovernanceCheckResult("registry_shape", not violations, violations)


def check_lifecycle_artifacts(registry: list[dict] | None = None) -> GovernanceCheckResult:
    """Verify lifecycle docs and test files exist for registered items."""
    registry = AGENT_REGISTRY if registry is None else registry
    violations = []
    for entry in registry:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name", "<unknown>")
        lifecycle_doc = Path(entry.get("lifecycle_doc", ""))
        test_file = Path(entry.get("test_file", ""))
        if not lifecycle_doc.exists():
            violations.append(f"{name} missing lifecycle doc: {lifecycle_doc}.")
        if not test_file.exists():
            violations.append(f"{name} missing test file: {test_file}.")
    return GovernanceCheckResult("lifecycle_artifacts", not violations, violations)


def check_entrypoints(registry: list[dict] | None = None) -> GovernanceCheckResult:
    """Verify modules import and public entrypoints exist."""
    registry = AGENT_REGISTRY if registry is None else registry
    violations = []
    for entry in registry:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name", "<unknown>")
        try:
            module = importlib.import_module(entry.get("module", ""))
        except Exception as exc:
            violations.append(f"{name} module import failed: {exc}.")
            continue
        entrypoint = entry.get("entrypoint")
        if entrypoint and not hasattr(module, entrypoint):
            violations.append(f"{name} missing entrypoint: {entrypoint}.")
        elif entrypoint and not callable(getattr(module, entrypoint)):
            violations.append(f"{name} entrypoint is not callable: {entrypoint}.")
    return GovernanceCheckResult("entrypoints", not violations, violations)


def check_permission_matrices(registry: list[dict] | None = None) -> GovernanceCheckResult:
    """Verify standard permission matrices have expected shape."""
    registry = AGENT_REGISTRY if registry is None else registry
    violations = []
    for entry in registry:
        if not isinstance(entry, dict):
            continue
        symbol = entry.get("permission_symbol")
        if not symbol:
            continue
        name = entry.get("name", "<unknown>")
        try:
            module = importlib.import_module(entry.get("module", ""))
        except Exception as exc:
            violations.append(f"{name} module import failed while checking permissions: {exc}.")
            continue
        if not hasattr(module, symbol):
            violations.append(f"{name} missing permission symbol {symbol}.")
            continue
        matrix = getattr(module, symbol)
        if entry.get("standard_permissions"):
            if not isinstance(matrix, dict):
                violations.append(f"{name} permission matrix must be a dict.")
                continue
            missing = sorted(REQUIRED_PERMISSION_KEYS - set(matrix))
            if missing:
                violations.append(f"{name} permission matrix missing keys: {missing}.")
            non_lists = [key for key in REQUIRED_PERMISSION_KEYS if key in matrix and not isinstance(matrix.get(key), list)]
            if non_lists:
                violations.append(f"{name} permission matrix keys must contain lists: {non_lists}.")
    return GovernanceCheckResult("permission_matrices", not violations, violations)


def check_no_llm_in_evaluate(registry: list[dict] | None = None) -> GovernanceCheckResult:
    """Verify functions named evaluate do not call call_llm."""
    registry = AGENT_REGISTRY if registry is None else registry
    violations = []
    checked_paths = set()
    for entry in registry:
        if not isinstance(entry, dict):
            continue
        source_path = module_path(entry.get("module", ""))
        if source_path in checked_paths:
            continue
        checked_paths.add(source_path)
        if not source_path.exists():
            violations.append(f"Source path does not exist: {source_path}.")
            continue
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != "evaluate":
                continue
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    func = child.func
                    called_name = ""
                    if isinstance(func, ast.Name):
                        called_name = func.id
                    elif isinstance(func, ast.Attribute):
                        called_name = func.attr
                    if called_name == "call_llm":
                        violations.append(f"{source_path}: evaluate() must not call call_llm.")
    return GovernanceCheckResult("no_llm_in_evaluate", not violations, violations)


def check_no_silent_except(main_registry: list[dict] | None = None) -> GovernanceCheckResult:
    """Verify agent modules do not swallow errors with bare 'except Exception:'.

    A bare ``except Exception:`` with no binding and no logging silently discards
    failures, which violates Law 3 (Fail Loudly) and Law 11 (no hidden failures).
    This check walks the AST of every registered module and flags any handler that
    catches ``Exception`` (or a broader builtin) without binding the exception to a
    name via ``as``.
    """
    registry = AGENT_REGISTRY if main_registry is None else main_registry
    violations = []
    checked_paths = set()
    for entry in registry:
        if not isinstance(entry, dict):
            continue
        source_path = module_path(entry.get("module", ""))
        if source_path in checked_paths:
            continue
        checked_paths.add(source_path)
        if not source_path.exists():
            continue
        try:
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            violations.append(f"{source_path}: could not parse ({exc}).")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            # Bare 'except:' (no type) is always silent.
            if node.type is None:
                violations.append(f"{source_path}:{node.lineno}: bare 'except:' swallows all errors silently.")
                continue
            # 'except Exception' / 'except BaseException' without 'as' binding is silent.
            type_node = node.type
            is_broad = (
                isinstance(type_node, ast.Name) and type_node.id in ("Exception", "BaseException")
            ) or (
                isinstance(type_node, ast.Tuple)
                and any(isinstance(e, ast.Name) and e.id in ("Exception", "BaseException") for e in type_node.elts)
            )
            if is_broad and node.name is None:
                violations.append(
                    f"{source_path}:{node.lineno}: 'except Exception:' without 'as' binding swallows failures silently."
                )
    return GovernanceCheckResult("no_silent_except", not violations, violations)


def run_governance_checks(registry: list[dict] | None = None) -> dict[str, Any]:
    """Run independent governance checks and aggregate their factual reports."""
    registry = AGENT_REGISTRY if registry is None else registry
    checks: list[Callable[[list[dict]], GovernanceCheckResult]] = [
        check_registry_shape,
        check_lifecycle_artifacts,
        check_entrypoints,
        check_permission_matrices,
        check_no_llm_in_evaluate,
        check_no_silent_except,
    ]
    results = [check(registry) for check in checks]
    violations = [violation for result in results for violation in result.violations]
    return {
        "success": not violations,
        "registered_items": len(registry or []),
        "checks": [
            {
                "check_name": result.check_name,
                "success": result.success,
                "violations": result.violations,
            }
            for result in results
        ],
        "violations": violations,
    }
