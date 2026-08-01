"""
Integration Agent - Deterministic artifact manifest builder.

Karpathy Meta-Agent #5. Builds a unified manifest from validated artifacts and
rejects filename/export conflicts without LLM calls.
"""

from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph


INTEGRATION_AGENT_PERMISSIONS = {
    "READ": ["software_agent_artifacts", "module_exports", "test_reports"],
    "WRITE": ["integration_manifest", "conflict_report"],
    "NEVER": ["deploy_untested_bundle", "override_security_blocks"],
    "HUMAN_CHECKPOINT": ["major_integration_conflict"],
}


class IntegrationAgentState(TypedDict):
    artifacts: list[dict]
    integration_manifest: dict
    conflicts: list[str]
    retry_count: int
    success: bool


class IntegrationAgentEngine:
    """Pure deterministic integration-manifest methods."""

    @staticmethod
    def build_manifest(artifacts: list[dict]) -> dict[str, Any]:
        """Build manifest and detect collisions/missing artifact data."""
        conflicts = []
        modules = []
        tests = []
        exports = {}
        seen_files = {}
        seen_exports = {}

        for index, artifact in enumerate(artifacts or [], 1):
            filename = artifact.get("filename")
            code = artifact.get("code")
            test_filename = artifact.get("test_filename")
            test_code = artifact.get("test_code")

            if not filename:
                conflicts.append(f"Artifact {index} missing filename.")
            elif filename in seen_files:
                conflicts.append(f"Duplicate artifact filename '{filename}'.")
            else:
                seen_files[filename] = index
                modules.append(filename)

            if filename and not isinstance(code, str):
                conflicts.append(f"Artifact '{filename}' missing source code string.")

            if test_filename:
                if test_filename in seen_files:
                    conflicts.append(f"Duplicate test filename '{test_filename}'.")
                else:
                    seen_files[test_filename] = index
                    tests.append(test_filename)
                if not isinstance(test_code, str):
                    conflicts.append(f"Artifact '{filename}' has test filename but missing test code string.")

            for export in artifact.get("exports", []) or []:
                if export in seen_exports:
                    conflicts.append(f"Duplicate export '{export}' in '{filename}' and '{seen_exports[export]}'.")
                else:
                    seen_exports[export] = filename
                    exports[export] = filename

        manifest = {
            "modules": modules,
            "tests": tests,
            "exports": exports,
            "artifact_count": len(artifacts or []),
        }
        return {"integration_manifest": manifest, "conflicts": conflicts, "success": len(conflicts) == 0}


# Karpathy Loop

def propose(state: IntegrationAgentState) -> dict:
    if not isinstance(state.get("artifacts", []), list):
        return {"conflicts": ["artifacts must be a list."], "success": False}
    return {"conflicts": [], "success": True}


def execute(state: IntegrationAgentState) -> dict:
    return IntegrationAgentEngine.build_manifest(state.get("artifacts", []))


def evaluate(state: IntegrationAgentState) -> dict:
    return {"success": len(state.get("conflicts", [])) == 0}


def commit(state: IntegrationAgentState) -> dict:
    return {"committed": True}


def refine(state: IntegrationAgentState) -> dict:
    return {"retry_count": state.get("retry_count", 0) + 1, "success": False}


def should_continue(state: IntegrationAgentState) -> str:
    if state.get("success", False):
        return "commit"
    if state.get("retry_count", 0) >= 1:
        return "escalate"
    return "refine"


workflow = StateGraph(IntegrationAgentState)
workflow.add_node("propose", propose)
workflow.add_node("execute", execute)
workflow.add_node("evaluate", evaluate)
workflow.add_node("commit", commit)
workflow.add_node("refine", refine)
workflow.set_entry_point("propose")
workflow.add_edge("propose", "execute")
workflow.add_edge("execute", "evaluate")
workflow.add_conditional_edges("evaluate", should_continue, {"commit": "commit", "refine": "refine", "escalate": END})
workflow.add_edge("refine", "propose")
workflow.add_edge("commit", END)

integration_agent_graph = workflow.compile(checkpointer=MemorySaver())


def integrate_artifacts(
    artifacts: list[dict],
    thread_id: str = "integration_agent_session",
) -> dict[str, Any]:
    """Build a deterministic integration manifest from artifacts."""
    result = integration_agent_graph.invoke(
        {
            "artifacts": artifacts,
            "integration_manifest": {},
            "conflicts": [],
            "retry_count": 0,
            "success": False,
        },
        config={"configurable": {"thread_id": thread_id}},
    )
    return {
        "success": result.get("success", False),
        "integration_manifest": result.get("integration_manifest", {}),
        "conflicts": result.get("conflicts", []),
    }
