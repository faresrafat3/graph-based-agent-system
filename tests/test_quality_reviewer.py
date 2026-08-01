from agents.quality_reviewer import QUALITY_REVIEWER_PERMISSIONS, review_quality


def test_permissions_matrix():
    assert "validation_reports" in QUALITY_REVIEWER_PERMISSIONS["READ"]
    assert "approval_status" in QUALITY_REVIEWER_PERMISSIONS["WRITE"]
    assert "bypass_tests" in QUALITY_REVIEWER_PERMISSIONS["NEVER"]


def test_review_quality_approves_clean_evidence():
    res = review_quality(
        validation_reports=[{"success": True, "violations": []}],
        assignment_result={"success": True, "violations": []},
        acceptance_criteria=["Feature works"],
        thread_id="quality_success",
    )
    assert res["approved"] is True
    assert res["quality_score"] == 1.0


def test_review_quality_rejects_failed_execution():
    res = review_quality(
        validation_reports=[{"success": True}],
        assignment_result={"success": True},
        execution_results=[{"success": False, "stage": "testing", "error": "failed"}],
        acceptance_criteria=["Works"],
        thread_id="quality_failed_execution",
    )
    assert res["approved"] is False
    assert any("Execution result" in r for r in res["rejection_reasons"])


def test_review_quality_rejects_critical_security_report():
    res = review_quality(
        validation_reports=[{"success": True}],
        assignment_result={"success": True},
        security_reports=[{"success": True, "severity": "critical", "issue": "secret"}],
        acceptance_criteria=["Works"],
        thread_id="quality_security",
    )
    assert res["approved"] is False
    assert any("Security report" in r for r in res["rejection_reasons"])
