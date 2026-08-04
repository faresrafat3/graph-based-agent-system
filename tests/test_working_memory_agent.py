import sys
sys.path.append('.')

from agents.working_memory_agent import WorkingEngine, WORKING_MEMORY_PERMISSIONS, assemble_working_memory
from memory.custom_memory import memory

def test_permissions_matrix():
    assert "READ" in WORKING_MEMORY_PERMISSIONS
    assert "WRITE" in WORKING_MEMORY_PERMISSIONS
    assert "working_memory" in WORKING_MEMORY_PERMISSIONS["WRITE"]

def test_estimate_tokens():
    assert WorkingEngine.estimate_tokens("1234") == 1
    assert WorkingEngine.estimate_tokens("a"*400) == 100

def test_rank_by_relevance():
    entries = [
        {"data": {"type": "episodic", "failure": "empty list", "outcome": "FAIL"}, "metadata": {}},
        {"data": {"type": "semantic", "rule": "check empty", "outcome": ""}, "metadata": {}},
        {"data": {"type": "episodic", "failure": "timeout", "outcome": "PASS"}, "metadata": {}},
    ]
    ranked = WorkingEngine.rank_by_relevance(entries, "empty list problem")
    # First should be empty list FAIL (higher boost) or semantic rule
    assert len(ranked) == 3

def test_assemble_within_budget():
    entries = [
        {"data": {"type": "episodic", "failure": "fail1", "reflection": "ref1", "outcome": "FAIL"}},
        {"data": {"type": "semantic", "rule": "RULE: check empty"}},
    ]
    ranked = WorkingEngine.rank_by_relevance(entries, "test problem")
    assembled, included, report = WorkingEngine.assemble_within_budget(ranked, "problem spec", "current context", 4000)
    assert "budget_total" in report
    assert report["budget_total"] == 4000
    assert len(included) >= 1

def test_assemble_working_memory():
    memory.clear_long_term()
    # Add some episodes
    memory.add_to_long_term(data={"type": "episodic", "failure": "empty", "reflection": "check len", "outcome": "FAIL"}, metadata={})
    memory.add_to_long_term(data={"type": "semantic", "rule": "RULE: check empty"}, metadata={})

    res = assemble_working_memory(problem_spec="empty list handling", token_budget=4000)
    assert res["success"] is True
    assert "budget_report" in res


def test_assemble_within_budget_various_types_and_break():
    """Verify memory snippet formatting for reflexion/generic types and budget-exhausted breaks"""
    entries = [
        {"data": {"type": "reflexion", "reflection": "Reflection details here."}},
        {"data": {"type": "other", "content": "generic content"}},
        {"data": {"type": "semantic", "rule": "A very long semantic rule description to exceed budget quickly."}},
    ]
    # Small budget to force break
    assembled, included, report = WorkingEngine.assemble_within_budget(entries, "problem", "short context", 15)
    assert len(included) < 3  # Should have stopped/broken due to token budget of 15
    assert "Reflection:" in assembled or "generic" in assembled


def test_assemble_working_memory_validations_and_exceptions(monkeypatch):
    """Verify input validations and fallback on database retrieval exceptions"""
    import pytest
    from agents.working_memory_agent import assemble_working_memory, global_memory
    
    # 1. empty problem_spec
    with pytest.raises(ValueError, match="problem_spec required"):
        assemble_working_memory("")
        
    # 2. token_budget < 500
    with pytest.raises(ValueError, match="token_budget too small"):
        assemble_working_memory("spec", token_budget=100)
        
    # 3. mock get_from_long_term exception on global_memory instance directly
    original_get = global_memory.get_from_long_term
    global_memory.get_from_long_term = lambda *a, **k: exec('raise RuntimeError("db crash")')
    
    res = assemble_working_memory("spec")
    assert res["success"] is True  # Falls back safely to empty memory
    
    # Restore normal method
    global_memory.get_from_long_term = original_get


def test_assemble_working_memory_budget_exceeded():
    """Verify that exceeding token budget flags a violation"""
    # 2500 chars is approx 625 tokens, which exceeds a 500 token budget
    res = assemble_working_memory("spec", current_context="a" * 2500, token_budget=500)
    assert any("Budget exceeded" in v for v in res["violations"])


def test_working_memory_refine_and_should_continue():
    """Verify refine and should_continue branch decisions in working memory graph"""
    from agents.working_memory_agent import refine, should_continue
    
    res = refine({"retry_count": 0})
    assert res["retry_count"] == 1
    assert res["success"] is False
    
    assert should_continue({"success": True}) == "commit"
    assert should_continue({"success": False, "retry_count": 2}) == "escalate"
    assert should_continue({"success": False, "retry_count": 0}) == "refine"

