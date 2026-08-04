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
    assert any("not one of the allowed options" in v for v in res["breaches"])
