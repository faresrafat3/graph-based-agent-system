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
