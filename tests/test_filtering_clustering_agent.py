import sys
sys.path.append('.')

from agents.filtering_clustering_agent import FilteringEngine, FILTERING_CLUSTERING_PERMISSIONS, filter_and_cluster

def test_permissions():
    assert "READ" in FILTERING_CLUSTERING_PERMISSIONS
    assert "WRITE" in FILTERING_CLUSTERING_PERMISSIONS
    assert "filtered_candidates" in FILTERING_CLUSTERING_PERMISSIONS["WRITE"]

def test_filter_by_ast():
    cands = [
        {"code": "def good(): return 1"},
        {"code": "def bad(\n return"},
    ]
    valid = FilteringEngine.filter_by_ast(cands)
    assert len(valid) == 1

def test_cluster_by_hash():
    cands = [
        {"code": "def f(): return 1"},
        {"code": "def f(): return 1"},
        {"code": "def f(): return 2"},
    ]
    clusters = FilteringEngine.cluster_by_hash(cands)
    assert len(clusters) == 2

def test_pick_representatives():
    clusters = {
        "hash1": [{"code": "def f(): return 1", "id": "1"}, {"code": "def f():\n  return 1\n  # longer", "id": "2"}],
        "hash2": [{"code": "def g(): return 2", "id": "3"}]
    }
    reps = FilteringEngine.pick_representatives(clusters)
    assert len(reps) == 2
    # Should pick shortest per cluster
    assert reps[0]["id"] == "1"

def test_filter_and_cluster_success():
    cands = [
        {"code": "def a(): return 1", "id": "1"},
        {"code": "def a(): return 1", "id": "2"},  # duplicate
        {"code": "def b(): return 2", "id": "3"},
    ]
    res = filter_and_cluster(cands, problem_spec="test")
    assert res["success"] is True
    assert "filtering_report" in res
    assert res["filtering_report"]["total_input"] == 3
    assert res["filtering_report"]["representatives"] == 2  # after dedup and pick


def test_filter_and_cluster_input_validations():
    """Verify input validations on empty or excessive candidate lists"""
    import pytest
    with pytest.raises(ValueError, match="candidates required"):
        filter_and_cluster([])
        
    with pytest.raises(ValueError, match="Too many candidates"):
        filter_and_cluster([{"code": "def f(): pass"}] * 101)


def test_cluster_by_execution_output():
    """Verify clustering behavior on execution outputs"""
    cands = [
        {"code": "def f(): return 1", "execution_output": "output_1"},
        {"code": "def f(): return 2", "execution_output": "output_2"},
        {"code": "def f(): return 3", "execution_output": "output_1"}, # same execution output
    ]
    clusters = FilteringEngine.cluster_by_behavior(cands)
    assert len(clusters) == 2


def test_filtering_refine_and_should_continue():
    """Verify refine, should_continue, and evaluate branch decisions in the filtering agent graph"""
    from agents.filtering_clustering_agent import refine, should_continue, evaluate
    
    res = refine({"retry_count": 0})
    assert res["retry_count"] == 1
    assert res["success"] is False
    
    assert should_continue({"success": True}) == "commit"
    assert should_continue({"success": False, "retry_count": 2}) == "escalate"
    assert should_continue({"success": False, "retry_count": 0}) == "refine"
    
    eval_res = evaluate({"representatives": []})
    assert eval_res["success"] is False
    assert any("No representatives" in v for v in eval_res["breaches"])

