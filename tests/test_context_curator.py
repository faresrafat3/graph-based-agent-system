import pytest
from agents.context_curator import curate_context, ContextCuratorEngine, CONTEXT_CURATOR_PERMISSIONS


def test_permissions_matrix():
    assert "READ" in CONTEXT_CURATOR_PERMISSIONS
    assert "WRITE" in CONTEXT_CURATOR_PERMISSIONS
    assert "NEVER" in CONTEXT_CURATOR_PERMISSIONS
    assert "source_code_edit" in CONTEXT_CURATOR_PERMISSIONS["NEVER"]


def test_sanitize_raw_text():
    raw_noisy = """
    User requirements: Build login page.
    Traceback (most recent call last):
      File "main.py", line 42, in <module>
    ValueError: Something broke!
    
    
    Please proceed.
    """
    clean = ContextCuratorEngine.sanitize_raw_text(raw_noisy)
    assert "Traceback Omitted for Noise Control" in clean
    assert "ValueError" not in clean


def test_compact_history_logs():
    logs = [
        {"action": "propose", "status": "success"},
        {"action": "execute", "status": "failed"},
        {"action": "refine", "status": "success"}
    ]
    summary = ContextCuratorEngine.compact_history_logs(logs, max_items=2)
    assert "Action: execute" in summary
    assert "Action: refine" in summary


def test_curate_context_pipeline():
    res = curate_context(
        raw_prompt="Build a clean dashboard interface with user auth",
        history_logs=[{"action": "init", "status": "ok"}],
        max_token_budget=1000
    )
    assert res["success"] is True
    assert len(res["sanitized_prompt"]) > 0
    assert res["signal_to_noise_ratio"] > 0
