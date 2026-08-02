import sys
sys.path.append('.')

from kernel.slice_router import detect_task_type, build_slice_graph, get_slice_for_requirements, SLICE_REGISTRY

def test_registry_has_all_slices():
    assert "humaneval" in SLICE_REGISTRY
    assert "ecommerce" in SLICE_REGISTRY
    assert "fintech" in SLICE_REGISTRY
    assert "default" in SLICE_REGISTRY
    assert "competitive" in SLICE_REGISTRY

def test_detect_humaneval():
    req = "def has_close_elements(numbers, threshold):\n    \"\"\"Check if...\"\"\"\n    >>> has_close_elements([1,2], 0.5)\n    False"
    assert detect_task_type(req) == "humaneval"

def test_detect_ecommerce():
    req = "Build an e-commerce backend with product catalog, cart management, checkout with Stripe"
    assert detect_task_type(req) == "ecommerce"

def test_detect_fintech():
    req = "Implement OAuth2 + OIDC authentication server with MFA TOTP"
    assert detect_task_type(req) == "fintech"

def test_detect_default():
    req = "Build a task management application with auth and CRUD"
    assert detect_task_type(req) == "default"

def test_build_slice():
    slice_cfg = build_slice_graph("humaneval")
    assert "agents" in slice_cfg
    assert "topology" in slice_cfg
    assert slice_cfg["n_agents"] >= 5

def test_get_slice_for_requirements():
    res = get_slice_for_requirements("HumanEval problem def add(a,b):", "")
    assert res["task_type"] == "humaneval"
    assert "slice" in res
    assert res["detected_by"] == "keyword_matching_zero_llm"
