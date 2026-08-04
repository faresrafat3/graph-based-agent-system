from agents.quality_reviewer import QUALITY_REVIEWER_PERMISSIONS, review_quality


def test_permissions_matrix():
    assert "validation_reports" in QUALITY_REVIEWER_PERMISSIONS["READ"]
    assert "approval_status" in QUALITY_REVIEWER_PERMISSIONS["WRITE"]
    assert "bypass_tests" in QUALITY_REVIEWER_PERMISSIONS["NEVER"]


def test_review_quality_approves_clean_evidence():
    res = review_quality(
        validation_reports=[{"success": True, "breaches": []}],
        assignment_result={"success": True, "breaches": []},
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


def test_review_quality_validation_or_assignment_fails():
    """Verify quality review rejection on validation/assignment failures"""
    res = review_quality(
        validation_reports=[{"success": False, "breaches": ["Schema fail"]}],
        assignment_result={"success": False, "breaches": ["Assignment fail"]},
        acceptance_criteria=["Works"],
        thread_id="quality_fails"
    )
    assert res["approved"] is False
    assert any("Validation report" in r for r in res["rejection_reasons"])
    assert any("Assignment failed" in r for r in res["rejection_reasons"])


def test_review_quality_empty_evidence():
    """Verify quality review fallback when no evidence is provided"""
    from agents.quality_reviewer import QualityReviewerEngine
    res = QualityReviewerEngine.review(
        validation_reports=[],
        assignment_result=None,
        dispatch_result=None,
        execution_results=[],
        acceptance_criteria=None,
        security_reports=[]
    )
    assert res["approved"] is False
    assert any("No quality evidence was provided" in r for r in res["rejection_reasons"])


def test_review_quality_invalid_input_types():
    """Verify state validations on invalid input formats"""
    res = review_quality(
        validation_reports="not a list",
        thread_id="quality_invalid_type"
    )
    assert res["approved"] is False
    assert any("validation_reports must be a list" in r for r in res["rejection_reasons"])

    # Test when execution_results is not a list (covers line 63)
    res2 = review_quality(
        execution_results="not a list",
        thread_id="quality_invalid_type_2"
    )
    assert res2["approved"] is False
    assert any("execution_results must be a list" in r for r in res2["rejection_reasons"])

    # Test when security_reports is not a list (covers line 70)
    res3 = review_quality(
        security_reports="not a list",
        thread_id="quality_invalid_type_3"
    )
    assert res3["approved"] is False
    assert any("security_reports must be a list" in r for r in res3["rejection_reasons"])

    # Test when acceptance_criteria contains empty/invalid values (covers line 115)
    res4 = review_quality(
        acceptance_criteria=["", 123],
        thread_id="quality_invalid_type_4"
    )
    assert res4["approved"] is False
    assert any("Acceptance criteria are missing or empty" in r for r in res4["rejection_reasons"])


