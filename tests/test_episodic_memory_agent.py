import sys
sys.path.append('.')

from agents.episodic_memory_agent import EpisodicEngine, EPISODIC_MEMORY_PERMISSIONS, store_episode, retrieve_episodes
from memory.custom_memory import memory

def test_permissions_matrix():
    assert "READ" in EPISODIC_MEMORY_PERMISSIONS
    assert "WRITE" in EPISODIC_MEMORY_PERMISSIONS
    assert "NEVER" in EPISODIC_MEMORY_PERMISSIONS
    assert "problem_spec" in EPISODIC_MEMORY_PERMISSIONS["READ"]

def test_build_episode():
    ep = EpisodicEngine.build_episode(
        problem_spec="def add(a,b):",
        code="return a+b",
        failure="assert fail",
        reflection="check empty",
        outcome="FAIL",
        duration=1.2,
        metadata={}
    )
    assert "episode_id" in ep
    assert ep["type"] == "episodic"
    assert "tags" in ep
    assert "outcome_FAIL" in ep["tags"] or "outcome_fail" in [t.lower() for t in ep["tags"]]

def test_extract_tags():
    tags = EpisodicEngine.extract_tags("empty list problem", "timeout error", "FAIL")
    assert "edge_empty" in tags
    assert "infra_timeout" in tags

def test_store_and_retrieve(monkeypatch):
    memory.clear_long_term()
    res = store_episode(
        problem_spec="def sort_array(arr): test empty",
        code="return arr",
        failure="empty list failed",
        reflection="check len==0",
        outcome="FAIL",
        duration=0.5
    )
    assert res["success"] is True
    assert "episodic_entry" in res

    retrieved = retrieve_episodes("empty list sort", limit=2)
    assert len(retrieved) >= 1


def test_store_episode_validations_and_never():
    """Verify input validations on empty or security-breaching specifications"""
    import pytest
    with pytest.raises(ValueError, match="problem_spec required"):
        store_episode(problem_spec="", code="", failure="", reflection="")
        
    with pytest.raises(PermissionError, match="blocked by NEVER permission"):
        store_episode(problem_spec="password = 'secret'", code="", failure="", reflection="")


def test_evaluate_edge_cases():
    """Verify validation checks on the episodic entry structure inside evaluate node"""
    from agents.episodic_memory_agent import evaluate
    
    # 1. Episode ID missing
    res1 = evaluate({"episodic_entry": {"type": "episodic"}})
    assert res1["success"] is False
    assert "Episode ID missing" in res1["breaches"]
    
    # 2. Type must be episodic
    res2 = evaluate({"episodic_entry": {"episode_id": "ep1", "type": "other"}})
    assert res2["success"] is False
    assert "Type must be episodic" in res2["breaches"]
    
    # 3. Episode too large
    large_entry = {"episode_id": "ep1", "type": "episodic", "code": "a" * 9000}
    res3 = evaluate({"episodic_entry": large_entry})
    assert res3["success"] is False
    assert any("Episode too large" in v for v in res3["breaches"])


def test_episodic_refine_and_should_continue():
    """Verify refine and should_continue branch decisions in episodic memory graph"""
    from agents.episodic_memory_agent import refine, should_continue
    
    res = refine({"retry_count": 0})
    assert res["retry_count"] == 1
    assert res["success"] is False
    
    assert should_continue({"success": True}) == "commit"
    assert should_continue({"success": False, "retry_count": 2}) == "escalate"
    assert should_continue({"success": False, "retry_count": 0}) == "refine"


def test_episodic_exceptions_and_filtering(monkeypatch):
    from agents.episodic_memory_agent import global_memory
    
    # 1. Mock memory add_to_long_term exception
    original_add = global_memory.add_to_long_term
    def fake_add(*a, **k):
        raise RuntimeError("db lock")
    global_memory.add_to_long_term = fake_add
    
    res = store_episode(
        problem_spec="def add_elements(a, b):",
        code="return a+b",
        failure="assert fail",
        reflection="check empty list",
        outcome="FAIL",
        duration=0.5,
        thread_id="episodic_except_session"
    )
    assert res["success"] is True  # Commit failure is safe, doesn't crash agent
    
    # Restore normal add_to_long_term manually
    global_memory.add_to_long_term = original_add
    
    # Store a normal episode so we can retrieve it
    memory.clear_long_term()
    store_episode(
        problem_spec="def sort_array(arr): test empty",
        code="return arr",
        failure="empty list failed",
        reflection="check len==0",
        outcome="FAIL",
        duration=0.5,
        thread_id="episodic_normal_session"
    )
    
    # 2. Call retrieve_episodes with unpunctuated keywords from the failure string to match above 0.05 threshold (covers line 231)
    retrieved = retrieve_episodes("test list", limit=1)
    assert len(retrieved) == 1
    
    # 3. Call retrieve_episodes with outcome_filter
    filtered = retrieve_episodes("empty list sort", limit=1, outcome_filter="FAIL")
    assert len(filtered) == 1
    
    # 4. Mock retrieve exception
    original_find = global_memory.find_similar
    def fake_find(*a, **k):
        raise RuntimeError("db lock")
    global_memory.find_similar = fake_find
    
    res_empty = retrieve_episodes("empty list sort")
    assert res_empty == []  # Falls back safely to empty list
    
    # Restore normal find_similar
    global_memory.find_similar = original_find


