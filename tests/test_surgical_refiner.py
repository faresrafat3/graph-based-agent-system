import pytest
from agents.surgical_refiner import (
    generate_refinement_feedback,
    SurgicalRefinerEngine,
    SURGICAL_REFINER_PERMISSIONS
)


def test_permissions_matrix():
    assert "READ" in SURGICAL_REFINER_PERMISSIONS
    assert "WRITE" in SURGICAL_REFINER_PERMISSIONS
    assert "NEVER" in SURGICAL_REFINER_PERMISSIONS
    assert "regenerate_entire_system" in SURGICAL_REFINER_PERMISSIONS["NEVER"]


def test_extract_target_keys():
    violations = ["Missing mandatory schema key: 'metadata'", "Task 2 missing 'id'."]
    keys = SurgicalRefinerEngine.extract_target_keys(violations)
    assert "metadata" in keys
    assert "id" in keys


def test_generate_surgical_instructions():
    violations = ["Task 1 has invalid type 'xyz'."]
    feedback = SurgicalRefinerEngine.generate_surgical_instructions(violations, ["type"])
    assert "SURGICAL CORRECTION REQUIRED" in feedback
    assert "Task 1 has invalid type 'xyz'" in feedback


def test_generate_refinement_feedback_pipeline():
    violations = ["Missing mandatory schema key: 'metadata'"]
    res = generate_refinement_feedback(violations)
    assert res["success"] is True
    assert "metadata" in res["target_keys_to_fix"]
    assert "SURGICAL CORRECTION REQUIRED" in res["surgical_feedback"]


def test_generate_surgical_instructions_empty():
    """Verify fallback message when no violations are provided"""
    feedback = SurgicalRefinerEngine.generate_surgical_instructions([], [])
    assert feedback == "No surgical corrections required."


def test_generate_refinement_feedback_empty_violations():
    """Verify pipeline output when no violations are detected"""
    res = generate_refinement_feedback([])
    assert res["success"] is False
    assert "No violations detected" in res["surgical_feedback"] or "surgical corrections" in res["surgical_feedback"]


def test_surgical_refiner_refine_and_should_continue():
    """Verify refine and should_continue branch decisions in Karpathy loop"""
    from agents.surgical_refiner import refine, should_continue
    
    # Test refine node
    ref_res = refine({"retry_count": 1})
    assert ref_res["retry_count"] == 2
    assert ref_res["success"] is False
    
    # Test should_continue commit branch
    assert should_continue({"success": True}) == "commit"
    
    # Test should_continue escalate branch
    assert should_continue({"success": False, "retry_count": 3}) == "escalate"
    
    # Test should_continue refine branch
    assert should_continue({"success": False, "retry_count": 1}) == "refine"

