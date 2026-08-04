from agents.human_escalation import HUMAN_ESCALATION_PERMISSIONS, handle_escalation


def test_permissions_matrix():
    assert "human_decision" in HUMAN_ESCALATION_PERMISSIONS["READ"]
    assert "resume_signal" in HUMAN_ESCALATION_PERMISSIONS["WRITE"]
    assert "auto_approve_checkpoints" in HUMAN_ESCALATION_PERMISSIONS["NEVER"]


def test_escalation_requires_human_without_decision():
    res = handle_escalation(
        "Need approval",
        blocked_state={"task_id": "task_1"},
        available_options=["approve", "reject"],
        thread_id="human_pending",
    )
    assert res["success"] is False
    assert res["requires_human"] is True
    assert res["resume_signal"] is None


def test_escalation_accepts_valid_decision():
    res = handle_escalation(
        "Need approval",
        blocked_state={"task_id": "task_1"},
        available_options=["approve", "reject"],
        human_decision="approve",
        thread_id="human_approved",
    )
    assert res["success"] is True
    assert res["requires_human"] is False
    assert res["resume_signal"]["decision"] == "approve"


def test_escalation_rejects_invalid_decision():
    res = handle_escalation(
        "Need approval",
        available_options=["approve", "reject"],
        human_decision="maybe",
        thread_id="human_invalid",
    )
    assert res["success"] is False
    assert any("not one of the allowed options" in v for v in res["violations"])


def test_escalation_empty_reason_and_options():
    """Verify validation flags missing reason or missing options"""
    res1 = handle_escalation("", thread_id="empty_reason")
    assert any("reason is required" in v for v in res1["violations"])
    
    # Call the engine directly to bypass wrapper's falsy 'or' fallback
    from agents.human_escalation import HumanEscalationEngine
    res2 = HumanEscalationEngine.evaluate_decision("Need approval", {}, [], None)
    assert any("decision option is required" in v for v in res2["violations"])


def test_escalation_refine_node_directly():
    """Verify that the refine node function operates correctly"""
    from agents.human_escalation import refine
    res = refine({"retry_count": 2})
    assert res["retry_count"] == 3

