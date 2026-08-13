"""
Decision & Conflict Agent - Deterministic governance-based dispute resolver.

Karpathy Meta-Agent #6. Resolves simple conflicts using explicit priority rules
and escalates unresolved disputes. It performs no LLM calls.
"""

from typing import Any, TypedDict

from kernel.karpathy_loop import build_karpathy_loop


DECISION_CONFLICT_PERMISSIONS = {
    "READ": ["agent_disputes", "constitution_rules", "tradeoff_logs"],
    "WRITE": ["conflict_resolutions", "binding_decisions"],
    "NEVER": ["breach_constitution", "grant_unauthorized_permissions"],
    "HUMAN_CHECKPOINT": ["unresolvable_architectural_dispute"],
}


class DecisionConflictState(TypedDict):
    disputes: list[dict]
    binding_decisions: list[dict]
    unresolved_conflicts: list[dict]
    breaches: list[str]
    retry_count: int
    success: bool


class DecisionConflictEngine:
    """Deterministic conflict resolution rules."""

    PRIORITY = {
        "security": 0,
        "privacy": 1,
        "correctness": 2,
        "quality": 3,
        "architecture": 4,
        "performance": 5,
        "cost": 6,
        "speed": 7,
    }

    @classmethod
    def resolve(cls, disputes: list[dict]) -> dict[str, Any]:
        decisions = []
        unresolved = []
        breaches = []

        if not isinstance(disputes, list):
            return {
                "binding_decisions": [],
                "unresolved_conflicts": [],
                "breaches": ["disputes must be a list."],
                "success": False,
            }

        for dispute in disputes or []:
            dispute_id = dispute.get("id", "unknown_dispute")
            options = dispute.get("options", [])
            if not options:
                unresolved.append(dispute)
                breaches.append(f"Dispute '{dispute_id}' has no options to evaluate.")
                continue

            ranked_options = []
            for option in options:
                category = str(option.get("category", "")).lower()
                if option.get("breachs_constitution"):
                    continue
                rank = cls.PRIORITY.get(category, 999)
                evidence_score = int(option.get("evidence_score", 0) or 0)
                ranked_options.append((rank, -evidence_score, option))

            if not ranked_options:
                unresolved.append(dispute)
                breaches.append(f"Dispute '{dispute_id}' has no constitution-compliant options.")
                continue

            ranked_options.sort(key=lambda item: (item[0], item[1], str(item[2].get("id", ""))))
            best = ranked_options[0][2]
            if ranked_options[0][0] == 999:
                unresolved.append(dispute)
                breaches.append(f"Dispute '{dispute_id}' has no known priority category.")
                continue

            decisions.append({
                "dispute_id": dispute_id,
                "selected_option_id": best.get("id"),
                "category": best.get("category"),
                "rationale": f"Selected highest-priority compliant option in category '{best.get('category')}'.",
            })

        return {
            "binding_decisions": decisions,
            "unresolved_conflicts": unresolved,
            "breaches": breaches,
            "success": len(breaches) == 0,
        }


# Karpathy Loop (shared factory; standard nodes)

def execute(state: DecisionConflictState) -> dict:
    return DecisionConflictEngine.resolve(state.get("disputes", []))


decision_conflict_graph = build_karpathy_loop(
    DecisionConflictState,
    execute_fn=execute,
    list_input_keys=("disputes",),
)


def resolve_conflicts(
    disputes: list[dict],
    thread_id: str = "decision_conflict_session",
) -> dict[str, Any]:
    """Resolve disputes using deterministic governance priorities."""
    result = decision_conflict_graph.invoke(
        {
            "disputes": disputes,
            "binding_decisions": [],
            "unresolved_conflicts": [],
            "breaches": [],
            "retry_count": 0,
            "success": False,
        },
        config={"configurable": {"thread_id": thread_id}},
    )
    return {
        "success": result.get("success", False),
        "binding_decisions": result.get("binding_decisions", []),
        "unresolved_conflicts": result.get("unresolved_conflicts", []),
        "breaches": result.get("breaches", []),
    }
