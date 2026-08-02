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
