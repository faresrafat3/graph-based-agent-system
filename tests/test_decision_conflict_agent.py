from agents.decision_conflict_agent import DECISION_CONFLICT_PERMISSIONS, resolve_conflicts


def test_permissions_matrix():
    assert "agent_disputes" in DECISION_CONFLICT_PERMISSIONS["READ"]
    assert "binding_decisions" in DECISION_CONFLICT_PERMISSIONS["WRITE"]
    assert "violate_constitution" in DECISION_CONFLICT_PERMISSIONS["NEVER"]


def test_resolve_conflict_selects_security_over_speed():
    disputes = [
        {
            "id": "dispute_1",
            "options": [
                {"id": "fast", "category": "speed", "evidence_score": 10},
                {"id": "secure", "category": "security", "evidence_score": 1},
            ],
        }
    ]
    res = resolve_conflicts(disputes, thread_id="conflict_security")
    assert res["success"] is True
    assert res["binding_decisions"][0]["selected_option_id"] == "secure"


def test_resolve_conflict_rejects_constitution_violating_options():
    disputes = [
        {
            "id": "dispute_2",
            "options": [
                {"id": "bad", "category": "security", "violates_constitution": True},
            ],
        }
    ]
    res = resolve_conflicts(disputes, thread_id="conflict_unresolved")
    assert res["success"] is False
    assert res["unresolved_conflicts"]
