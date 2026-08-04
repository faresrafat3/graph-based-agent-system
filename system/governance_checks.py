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
    breaches: list[str]
    detail: dict[str, Any] | None = None


def module_path(module_name: str) -> Path:
    """Convert a dotted module path to a Python source path."""
    return Path(*module_name.split(".")).with_suffix(".py")


def check_registry_shape(registry: list[dict] | None = None) -> GovernanceCheckResult:
    """Verify that registry entries expose required catalog fields."""
    registry = AGENT_REGISTRY if registry is None else registry
    breaches = []
    if not isinstance(registry, list):
        return GovernanceCheckResult("registry_shape", False, ["registry must be a list."])

    seen_names = set()
    for entry in registry:
        name = entry.get("name", "<unknown>") if isinstance(entry, dict) else "<invalid>"
        if not isinstance(entry, dict):
            breaches.append("registry entries must be dictionaries.")
            continue
        missing = sorted(REQUIRED_REGISTRY_KEYS - set(entry))
        if missing:
            breaches.append(f"Registry entry '{name}' missing keys: {missing}.")
        if name in seen_names:
            breaches.append(f"Duplicate registry entry name: '{name}'.")
        seen_names.add(name)

    return GovernanceCheckResult("registry_shape", not breaches, breaches)


def check_lifecycle_artifacts(registry: list[dict] | None = None) -> GovernanceCheckResult:
    """Verify lifecycle docs and test files exist for registered items."""
    registry = AGENT_REGISTRY if registry is None else registry
    breaches = []
    for entry in registry:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name", "<unknown>")
        lifecycle_doc = Path(entry.get("lifecycle_doc", ""))
        test_file = Path(entry.get("test_file", ""))
        if not lifecycle_doc.exists():
            breaches.append(f"{name} missing lifecycle doc: {lifecycle_doc}.")
        if not test_file.exists():
            breaches.append(f"{name} missing test file: {test_file}.")
    return GovernanceCheckResult("lifecycle_artifacts", not breaches, breaches)


def check_entrypoints(registry: list[dict] | None = None) -> GovernanceCheckResult:
    """Verify modules import and public entrypoints exist."""
    registry = AGENT_REGISTRY if registry is None else registry
    breaches = []
    for entry in registry:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name", "<unknown>")
        try:
            module = importlib.import_module(entry.get("module", ""))
        except Exception as exc:
            breaches.append(f"{name} module import failed: {exc}.")
            continue
        entrypoint = entry.get("entrypoint")
        if entrypoint and not hasattr(module, entrypoint):
            breaches.append(f"{name} missing entrypoint: {entrypoint}.")
        elif entrypoint and not callable(getattr(module, entrypoint)):
            breaches.append(f"{name} entrypoint is not callable: {entrypoint}.")
    return GovernanceCheckResult("entrypoints", not breaches, breaches)


def check_permission_matrices(registry: list[dict] | None = None) -> GovernanceCheckResult:
    """Verify standard permission matrices have expected shape."""
    registry = AGENT_REGISTRY if registry is None else registry
    breaches = []
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
            breaches.append(f"{name} module import failed while checking permissions: {exc}.")
            continue
        if not hasattr(module, symbol):
            breaches.append(f"{name} missing permission symbol {symbol}.")
            continue
        matrix = getattr(module, symbol)
        if entry.get("standard_permissions"):
            if not isinstance(matrix, dict):
                breaches.append(f"{name} permission matrix must be a dict.")
                continue
            missing = sorted(REQUIRED_PERMISSION_KEYS - set(matrix))
            if missing:
                breaches.append(f"{name} permission matrix missing keys: {missing}.")
            non_lists = [key for key in REQUIRED_PERMISSION_KEYS if key in matrix and not isinstance(matrix.get(key), list)]
            if non_lists:
                breaches.append(f"{name} permission matrix keys must contain lists: {non_lists}.")
    return GovernanceCheckResult("permission_matrices", not breaches, breaches)


def check_no_llm_in_evaluate(registry: list[dict] | None = None) -> GovernanceCheckResult:
    """Verify functions named evaluate do not call call_llm."""
    registry = AGENT_REGISTRY if registry is None else registry
    breaches = []
    checked_paths = set()
    for entry in registry:
        if not isinstance(entry, dict):
            continue
        source_path = module_path(entry.get("module", ""))
        if source_path in checked_paths:
            continue
        checked_paths.add(source_path)
        if not source_path.exists():
            breaches.append(f"Source path does not exist: {source_path}.")
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
                        breaches.append(f"{source_path}: evaluate() must not call call_llm.")
    return GovernanceCheckResult("no_llm_in_evaluate", not breaches, breaches)


def check_no_silent_except(main_registry: list[dict] | None = None) -> GovernanceCheckResult:
    """Verify agent modules do not swallow errors with bare 'except Exception:'.

    A bare ``except Exception:`` with no binding and no logging silently discards
    failures, which breachs Law 3 (Fail Loudly) and Law 11 (no hidden failures).
    This check walks the AST of every registered module and flags any handler that
    catches ``Exception`` (or a broader builtin) without binding the exception to a
    name via ``as``.
    """
    registry = AGENT_REGISTRY if main_registry is None else main_registry
    breaches = []
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
            breaches.append(f"{source_path}: could not parse ({exc}).")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            # Bare 'except:' (no type) is always silent.
            if node.type is None:
                breaches.append(f"{source_path}:{node.lineno}: bare 'except:' swallows all errors silently.")
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
                breaches.append(
                    f"{source_path}:{node.lineno}: 'except Exception:' without 'as' binding swallows failures silently."
                )
    return GovernanceCheckResult("no_silent_except", not breaches, breaches)


# Live production entrypoint (main.py -> agents.karpathy_pipeline.run_karpathy_pipeline).
LIVE_ENTRYPOINT = "run_karpathy_pipeline"

# Registered agents that are intentionally NOT wired into the live call graph.
# Silence about dead agents is forbidden (Law 3): every such agent must be
# explicitly declared here with a reason, so the gap is visible and reviewed.
EXTERNAL_ALLOWED = {
    # entrypoint name -> reason it is intentionally unreachable from the live pipeline
    "run_competitive_slice": "Invoked only by benchmarks/humaneval_harness.py (AlphaCode/competitive eval).",
    "CompetitiveContextManager": "Competitive-slice support class; reached via run_competitive_slice only.",
    "BaseDomainContextManager": "Base class for domain context managers; subclassed, not directly invoked.",
    "monitor_progress": "Progress monitor; optional observability, not on the default execution path.",
    "debug_code": "Debugger agent; invoked on-demand, not in the happy-path pipeline.",
    "sample_candidates": "AlphaCode sampling; reached only via competitive/experimental flows.",
    "filter_and_cluster": "AlphaCode filtering; reached only via competitive/experimental flows.",
    "generate_reflection": "Reflexion memory; reached via surgical_refiner's internal loop only.",
    "store_episode": "Episodic memory write; invoked by other agents' commit steps, not the pipeline head.",
    "extract_semantic_rule": "Semantic memory write; invoked by other agents' commit steps, not the pipeline head.",
    "assemble_working_memory": "Working memory assembly; invoked by other agents, not the pipeline head.",
    "resolve_conflicts": "Decision & Conflict agent; governance escalation, optional, not default-wired.",
    "handle_escalation": "Human escalation; terminal checkpoint, optional, not default-wired.",
    "prioritize_resources": "Resource & Priority agent; governance, optional, not default-wired.",
    "integrate_artifacts": "Integration agent; reached via orchestrate_graph path / governance, optional.",
    "AuthSquadAgent": "Domain squad entry class; reached via dispatch_domain_tasks only.",
}


def _transitive_reachable(entrypoint: str, entry_names: set[str]) -> set[str]:
    """Return the set of registered entrypoint names reachable from `entrypoint`.

    Pure static AST walk: for each agent module we collect the names it references
    that match a registered entrypoint, then close transitively. The two optional
    pipeline flags (dispatch_domains, orchestrate_graph) are treated as enabled so
    their subtrees count as reachable.
    """
    agents_dir = Path(__file__).resolve().parent.parent / "agents"
    refs: dict[str, set[str]] = {ep: set() for ep in entry_names}
    for py in agents_dir.rglob("*.py"):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        names_in_file = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names_in_file.add(node.id)
            elif isinstance(node, ast.Attribute):
                names_in_file.add(node.attr)
        matched = names_in_file & entry_names
        for ep in matched:
            refs[ep] |= matched - {ep}
    # seed: enable optional-flag entrypoints so their subtrees are reachable
    seeds = {entrypoint, "dispatch_domain_tasks", "orchestrate_graph_execution"}
    seen: set[str] = set()
    stack = [s for s in seeds if s in refs]
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        for m in refs.get(n, ()):
            if m not in seen:
                stack.append(m)
    return seen


def check_entrypoints_reachable(main_registry: list[dict] | None = None) -> GovernanceCheckResult:
    """Every registered agent must be reachable from the live path OR declared external.

    The registry advertises N production agents, but the live call graph
    (main.py -> run_karpathy_pipeline) actually exercises a subset. A registered
    agent that is neither reachable nor explicitly listed in EXTERNAL_ALLOWED is a
    silent dead registration (this is what hid the dead DispatchKernel path and the
    misprioritized live-task-drop). This check makes the gap a hard, reviewed invariant.
    """
    registry = AGENT_REGISTRY if main_registry is None else main_registry
    entry_names = {e["entrypoint"] for e in registry}
    reachable = _transitive_reachable(LIVE_ENTRYPOINT, entry_names)
    breaches = []
    unreachable_but_allowed = []
    for e in registry:
        ep = e["entrypoint"]
        if ep in reachable or ep == LIVE_ENTRYPOINT:
            continue
        if ep in EXTERNAL_ALLOWED:
            unreachable_but_allowed.append(f"{e['name']} ({ep}) — {EXTERNAL_ALLOWED[ep]}")
        else:
            breaches.append(
                f"{e['name']} (entrypoint '{ep}') is registered but NOT reachable from "
                f"'{LIVE_ENTRYPOINT}' and is not in EXTERNAL_ALLOWED. Either wire it into "
                f"the live pipeline or declare it intentionally external in EXTERNAL_ALLOWED."
            )
    detail = {
        "live_entrypoint": LIVE_ENTRYPOINT,
        "reachable_count": len(reachable & entry_names),
        "total_registered": len(registry),
        "externally_allowed": unreachable_but_allowed,
    }
    return GovernanceCheckResult(
        "entrypoints_reachable",
        not breaches,
        breaches,
        detail=detail,
    )


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
        check_entrypoints_reachable,
    ]
    results = [check(registry) for check in checks]
    breaches = [breach for result in results for breach in result.breaches]
    return {
        "success": not breaches,
        "registered_items": len(registry or []),
        "checks": [
            {
                "check_name": result.check_name,
                "success": result.success,
                "breaches": result.breaches,
                **({"detail": result.detail} if hasattr(result, "detail") and result.detail else {}),
            }
            for result in results
        ],
        "breaches": breaches,
    }
