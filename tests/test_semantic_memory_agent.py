import sys
sys.path.append('.')

from agents.semantic_memory_agent import SemanticEngine, SEMANTIC_MEMORY_PERMISSIONS, extract_semantic_rule, get_semantic_rules
from memory.custom_memory import memory
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


def test_is_rule_actionable_various_branches():
    """Verify quality gate checks on the semantic rule string"""
    # 1. Empty/too short (Line 101)
    assert SemanticEngine.is_rule_actionable("") is False
    assert SemanticEngine.is_rule_actionable("short rule") is False
    
    # 2. No RULE: prefix, has if but missing actionable words (Line 105-107)
    assert SemanticEngine.is_rule_actionable("This is an rule if you want to check.") is False
    
    # 3. Contains code pattern (Line 111-112)
    assert SemanticEngine.is_rule_actionable("def fix(x):\n    print(x)\n    return True") is False


def test_extract_semantic_rule_validations():
    """Verify input validations on episodic entries count"""
    import pytest
    # 1. Need at least 2 entries (Line 119)
    with pytest.raises(ValueError, match="Need at least 2 episodic entries"):
        extract_semantic_rule([])


def test_extract_semantic_rule_no_repeats():
    """Verify rule outcome when no repeated tags are found"""
    # Pass two episodes with no common tags (Line 131)
    episodes = [
        {"tags": ["tag_a"], "episode_id": "1", "outcome": "FAIL"},
        {"tags": ["tag_b"], "episode_id": "2", "outcome": "FAIL"},
    ]
    res = extract_semantic_rule(episodic_entries=episodes)
    assert res["success"] is True
    assert "No repeated pattern found" in res["semantic_rule"]


def test_extract_semantic_rule_prefix_and_evaluate_fails(monkeypatch):
    """Verify that rule prefix is auto-attached and evaluation failures are flagged"""
    # 1. LLM returns rule without 'RULE:' prefix (Line 148)
    monkeypatch.setattr(semantic_module, "call_llm", lambda *a, **k: "If you find list, always check empty because it fails.")
    episodes = [
        {"tags": ["tag_a"], "episode_id": "1", "outcome": "FAIL"},
        {"tags": ["tag_a"], "episode_id": "2", "outcome": "FAIL"},
    ]
    res1 = extract_semantic_rule(episodic_entries=episodes, thread_id="prefix_session")
    assert res1["success"] is True
    assert res1["semantic_rule"].startswith("RULE: If")
    
    # 2. LLM returns non-actionable rule (Line 162)
    monkeypatch.setattr(semantic_module, "call_llm", lambda *a, **k: "just try again")
    res2 = extract_semantic_rule(episodic_entries=episodes, thread_id="evaluate_fail_session")
    assert res2["success"] is False
    assert any("Rule not actionable" in v for v in res2["breaches"])


def test_semantic_refine_and_should_continue():
    """Verify refine and should_continue branch decisions in semantic memory graph"""
    from agents.semantic_memory_agent import refine, should_continue
    
    res = refine({"retry_count": 0})
    assert res["retry_count"] == 1
    assert res["success"] is False
    
    assert should_continue({"success": True}) == "commit"
    assert should_continue({"success": False, "retry_count": 2}) == "escalate"
    assert should_continue({"success": False, "retry_count": 0}) == "refine"


def test_semantic_auto_retrieval_and_get_rules_exceptions(monkeypatch):
    """Verify auto-retrieval, database exceptions, and safe fallbacks inside semantic memory agent"""
    from memory.custom_memory import memory as global_memory_inst
    import pytest
    
    # Mock normal find_similar/add_to_long_term
    global_memory_inst.clear_long_term()
    global_memory_inst.add_to_long_term(
        data={"type": "episodic", "tags": ["tag_a"], "episode_id": "1", "outcome": "FAIL"},
        metadata={}
    )
    global_memory_inst.add_to_long_term(
        data={"type": "episodic", "tags": ["tag_a"], "episode_id": "2", "outcome": "FAIL"},
        metadata={}
    )
    
    # 1. Test auto-retrieve inside extract_semantic_rule when episodic_entries is None (Line 222-227)
    monkeypatch.setattr(semantic_module, "call_llm", lambda *a, **k: "RULE: If list, always check empty because it fails.")
    res = extract_semantic_rule(episodic_entries=None, thread_id="auto_retrieve_session")
    assert res["success"] is True
    assert "RULE:" in res["semantic_rule"]
    
    # 2. Test auto-retrieve exception (Line 226-227)
    original_get = global_memory_inst.get_from_long_term
    global_memory_inst.get_from_long_term = lambda *a, **k: exec('raise RuntimeError("db lock")')
    with pytest.raises(ValueError, match="Need at least 2 episodic entries"):
        extract_semantic_rule(episodic_entries=None, thread_id="auto_retrieve_error_session")
    
    # 3. Test get_semantic_rules exception (Line 253-259)
    from agents.semantic_memory_agent import get_semantic_rules
    assert get_semantic_rules() == []
    
    # Restore normal memory methods
    global_memory_inst.get_from_long_term = original_get
    
    # 4. Mock commit memory add_to_long_term exception (Line 179-180)
    original_add = global_memory_inst.add_to_long_term
    global_memory_inst.add_to_long_term = lambda *a, **k: exec('raise RuntimeError("db lock")')
    
    episodes = [
        {"tags": ["tag_a"], "episode_id": "1", "outcome": "FAIL"},
        {"tags": ["tag_a"], "episode_id": "2", "outcome": "FAIL"},
    ]
    res_commit_err = extract_semantic_rule(episodic_entries=episodes, thread_id="commit_error_session")
    assert res_commit_err["success"] is True  # Safe commit fallback, doesn't crash agent
    
    global_memory_inst.add_to_long_term = original_add

