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
