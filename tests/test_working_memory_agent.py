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
