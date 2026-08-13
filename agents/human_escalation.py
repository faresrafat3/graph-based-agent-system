"""
Human Escalation Agent - deterministic human checkpoint model.

Karpathy Meta-Agent #8. Prepares and validates human decisions. It does not
collect UI input directly; callers pass the human decision explicitly.
"""

from typing import Any, TypedDict

from kernel.karpathy_loop import build_karpathy_loop


HUMAN_ESCALATION_PERMISSIONS = {
    "READ": ["escalation_reason", "blocked_state", "available_options", "human_decision"],
    "WRITE": ["human_decision_log", "resume_signal"],
    "NEVER": ["bypass_human_response", "auto_approve_checkpoints"],
    "HUMAN_CHECKPOINT": ["always_active"],
}


class HumanEscalationState(TypedDict):
    escalation_reason: str
    blocked_state: dict
    available_options: list[str]
    human_decision: str | None
    requires_human: bool
    decision: str | None
    resume_signal: dict | None
    breaches: list[str]
    retry_count: int
    success: bool


class HumanEscalationEngine:
    """Deterministic checkpoint preparation and decision validation."""

    @staticmethod
    def evaluate_decision(
        escalation_reason: str,
        blocked_state: dict,
        available_options: list[str],
        human_decision: str | None,
    ) -> dict[str, Any]:
        """Validate optional human decision and prepare resume signal."""
        breaches = []
        options = [option for option in available_options or [] if isinstance(option, str) and option.strip()]

        if not escalation_reason:
            breaches.append("Escalation reason is required.")
        if not options:
            breaches.append("At least one human decision option is required.")

        if human_decision is None:
            return {
                "requires_human": True,
                "decision": None,
                "resume_signal": None,
                "breaches": breaches,
                "success": False,
            }

        if human_decision not in options:
            breaches.append(f"Human decision '{human_decision}' is not one of the allowed options: {options}.")
            return {
                "requires_human": True,
                "decision": human_decision,
                "resume_signal": None,
                "breaches": breaches,
                "success": False,
            }

        resume_signal = {
            "decision": human_decision,
            "reason": escalation_reason,
            "blocked_state_keys": sorted(blocked_state.keys()),
        }
        return {
            "requires_human": False,
            "decision": human_decision,
            "resume_signal": resume_signal,
            "breaches": breaches,
            "success": len(breaches) == 0,
        }


# Karpathy Loop (shared factory; no refine edge — checkpoint either commits or escalates)

def propose(state: HumanEscalationState) -> dict:
    return {"requires_human": True, "breaches": [], "success": False}


def execute(state: HumanEscalationState) -> dict:
    return HumanEscalationEngine.evaluate_decision(
        escalation_reason=state.get("escalation_reason", ""),
        blocked_state=state.get("blocked_state", {}),
        available_options=state.get("available_options", []),
        human_decision=state.get("human_decision"),
    )


def evaluate(state: HumanEscalationState) -> dict:
    return {"success": bool(state.get("success", False)) and not state.get("requires_human", True)}


def should_continue(state: HumanEscalationState) -> str:
    if state.get("success", False) and not state.get("requires_human", True):
        return "commit"
    return "escalate"


human_escalation_graph = build_karpathy_loop(
    HumanEscalationState,
    execute_fn=execute,
    propose_fn=propose,
    evaluate_fn=evaluate,
    should_continue_fn=should_continue,
    include_refine=False,
)


def handle_escalation(
    escalation_reason: str,
    blocked_state: dict | None = None,
    available_options: list[str] | None = None,
    human_decision: str | None = None,
    thread_id: str = "human_escalation_session",
) -> dict[str, Any]:
    """Prepare or resolve a human checkpoint deterministically."""
    result = human_escalation_graph.invoke(
        {
            "escalation_reason": escalation_reason,
            "blocked_state": blocked_state or {},
            "available_options": available_options or ["approve", "reject", "revise"],
            "human_decision": human_decision,
            "requires_human": True,
            "decision": None,
            "resume_signal": None,
            "breaches": [],
            "retry_count": 0,
            "success": False,
        },
        config={"configurable": {"thread_id": thread_id}},
    )
    return {
        "success": result.get("success", False),
        "requires_human": result.get("requires_human", True),
        "decision": result.get("decision"),
        "resume_signal": result.get("resume_signal"),
        "breaches": result.get("breaches", []),
    }
