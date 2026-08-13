"""
Integration Agent - Deterministic artifact manifest builder.

Karpathy Meta-Agent #5. Builds a unified manifest from validated artifacts and
rejects filename/export conflicts without LLM calls.
"""

from typing import Any, TypedDict

from kernel.karpathy_loop import build_karpathy_loop

from agents.deterministic_validator import (
    DeterministicValidatorEngine,
    apply_verify_verdict,
    record_effect,
    verified_closure_enabled,
)


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

        if not isinstance(artifacts, list):
            return {
                "integration_manifest": {"modules": [], "tests": [], "exports": {}, "artifact_count": 0},
                "conflicts": ["artifacts must be a list."],
                "success": False,
            }

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


# Karpathy Loop (shared factory; standard nodes, failures keyed on ``conflicts``)

def execute(state: IntegrationAgentState) -> dict:
    return IntegrationAgentEngine.build_manifest(state.get("artifacts", []))


integration_agent_graph = build_karpathy_loop(
    IntegrationAgentState,
    execute_fn=execute,
    list_input_keys=("artifacts",),
    evaluate_fail_keys=("conflicts",),
)


def integrate_artifacts(
    artifacts: list[dict],
    thread_id: str = "integration_agent_session",
) -> dict[str, Any]:
    """Build a deterministic integration manifest from artifacts, closed by VERIFY (P2)."""
    # P2: postcondition declared at propose time, before the manifest is written.
    postcondition = {"kind": "non_empty", "path": None}

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
    manifest = result.get("integration_manifest", {})
    output = {
        "success": result.get("success", False),
        "integration_manifest": manifest,
        "conflicts": result.get("conflicts", []),
    }

    # === VERIFY node (P2) === the manifest write is graph-state only, so it is
    # first recorded as a real effect and then checked by the zero-LLM verifier.
    if verified_closure_enabled() and output["success"]:
        postcondition["path"] = record_effect("integration_agent", {
            "artifact_count": manifest.get("artifact_count", 0),
            "modules": manifest.get("modules", []),
            "tests": manifest.get("tests", []),
            "exports": manifest.get("exports", {}),
        })
        verify_breaches = DeterministicValidatorEngine.verify_execution_postcondition(postcondition)
        output = apply_verify_verdict(output, postcondition, verify_breaches)
        if verify_breaches:
            output["conflicts"] = list(output.get("conflicts", [])) + verify_breaches

    return output
