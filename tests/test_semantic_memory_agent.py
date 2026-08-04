import sys
sys.path.append('.')

from agents.semantic_memory_agent import SemanticEngine, SEMANTIC_MEMORY_PERMISSIONS, extract_semantic_rule
import agents.semantic_memory_agent as semantic_module

def test_permissions_matrix():
    assert "READ" in SEMANTIC_MEMORY_PERMISSIONS
    assert "WRITE" in SEMANTIC_MEMORY_PERMISSIONS
    assert "NEVER" in SEMANTIC_MEMORY_PERMISSIONS

def test_find_repeated_patterns():
    episodes = [
        {"tags": ["edge_empty", "outcome_fail"], "failure": "empty", "episode_id": "1"},
        {"tags": ["edge_empty", "outcome_fail"], "failure": "empty again", "episode_id": "2"},
        {"tags": ["infra_timeout"], "failure": "timeout", "episode_id": "3"},
    ]
    repeated = SemanticEngine.find_repeated_patterns(episodes, min_repeats=2)
    assert "edge_empty" in repeated
    assert len(repeated["edge_empty"]) == 2

def test_is_actionable():
    good = "RULE: If list is empty, check len==0 early because empty is valid edge."
    assert SemanticEngine.is_rule_actionable(good) is True

    bad = "Fix it"
    assert SemanticEngine.is_rule_actionable(bad) is False

def test_extract_rule_success(monkeypatch):
    def fake_llm(prompt, system_prompt="", **kwargs):
        return "RULE: If function takes list, always check len==0 early and return default because empty is valid edge case."

    monkeypatch.setattr(semantic_module, "call_llm", fake_llm)
    
    episodes = [
        {"tags": ["edge_empty"], "failure": "empty list", "reflection": "check empty", "episode_id": "1", "outcome": "FAIL"},
        {"tags": ["edge_empty"], "failure": "empty again", "reflection": "early return", "episode_id": "2", "outcome": "FAIL"},
    ]
    
    res = extract_semantic_rule(episodic_entries=episodes)
    assert res["success"] is True
    assert "RULE:" in res["semantic_rule"]
