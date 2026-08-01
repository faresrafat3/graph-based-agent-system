import pytest
from agents.karpathy_pipeline import run_karpathy_pipeline


def test_full_pipeline_success():
    """End-to-end pipeline: Curate → Decompose → Validate → Pass"""
    result = run_karpathy_pipeline(
        requirements="Build a login page with email authentication",
        project_context="Web application",
        constraints="Use React"
    )
    assert result["stage"] == "complete"
    assert result["success"] is True
    assert result["quality_score"] == 1.0
    assert len(result["tasks"]) > 0


def test_pipeline_context_signal_to_noise():
    """Verify context sanitation preserves signal"""
    result = run_karpathy_pipeline(
        requirements="Simple dashboard with charts",
    )
    assert result["context_signal_to_noise"] == 1.0  # Clean input = no noise removed


def test_pipeline_with_noisy_input():
    """Verify pipeline handles noisy tracebacks in requirements"""
    noisy = """Build user profile page.
    Traceback (most recent call last):
      File "app.py", line 10
    RuntimeError: crash
    
    Also add settings page."""
    result = run_karpathy_pipeline(requirements=noisy)
    assert result["stage"] == "complete"
    assert result["success"] is True
    assert result["context_signal_to_noise"] < 1.0  # Noise was removed
