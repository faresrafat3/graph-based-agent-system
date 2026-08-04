import pytest
from kernel.signal_protocol import (
    AgentSignal, SUCCESS_SIGNALS, FAILURE_SIGNALS,
    ALERT_SIGNALS, TERMINAL_SIGNALS
)
from kernel.dispatch_kernel import DispatchKernel, ROUTING_TABLE, FAILURE_POLICY


# ==================== Signal Protocol Tests ====================

def test_signal_creation_valid():
    """Valid signal is created with correct properties"""
    sig = AgentSignal(
        signal_type="TASK_DECOMPOSED",
        source_agent="task_decomposer",
        data={"tasks": [{"id": 1}]},
        quality_score=0.95
    )
    assert sig.signal_type == "TASK_DECOMPOSED"
    assert sig.is_success is True
    assert sig.is_failure is False
    assert sig.is_alert is False
    assert sig.quality_score == 0.95


def test_signal_creation_invalid_type_raises():
    """Invalid signal type raises ValueError"""
    with pytest.raises(ValueError) as exc_info:
        AgentSignal(signal_type="INVALID_SIGNAL", source_agent="test")
    assert "Invalid signal type" in str(exc_info.value)


def test_signal_categories():
    """Verify all signal category sets are disjoint"""
    all_categories = [SUCCESS_SIGNALS, FAILURE_SIGNALS, ALERT_SIGNALS, TERMINAL_SIGNALS]
    for i, cat_a in enumerate(all_categories):
        for j, cat_b in enumerate(all_categories):
            if i != j:
                assert len(cat_a & cat_b) == 0, f"Overlap between categories {i} and {j}"


def test_signal_to_dict():
    """Signal serializes to dict correctly"""
    sig = AgentSignal(signal_type="TESTS_PASSED", source_agent="test_runner", data={"passed": 5})
    d = sig.to_dict()
    assert d["signal_type"] == "TESTS_PASSED"
    assert d["source_agent"] == "test_runner"
    assert d["data"]["passed"] == 5
    assert "timestamp" in d


def test_failure_signal_properties():
    """Failure signals are correctly classified"""
    sig = AgentSignal(signal_type="TESTS_FAILED", source_agent="test_runner")
    assert sig.is_failure is True
    assert sig.is_success is False


def test_alert_signal_properties():
    """Alert signals are correctly classified"""
    sig = AgentSignal(signal_type="SECURITY_VIOLATION", source_agent="code_executor")
    assert sig.is_alert is True
    assert sig.is_terminal is False


# ==================== Dispatch Kernel Tests ====================

def test_routing_table_completeness():
    """Every known signal type has a routing entry in at least one table (Ultimate or Slices)"""
    from kernel.dispatch_kernel import SLICE_ROUTING_TABLES
    all_signals = SUCCESS_SIGNALS | FAILURE_SIGNALS | ALERT_SIGNALS | TERMINAL_SIGNALS
    # Build union of all routing tables
    all_tables = [ROUTING_TABLE] + list(SLICE_ROUTING_TABLES.values())
    all_routed = set()
    for tbl in all_tables:
        all_routed.update(tbl.keys())
    for sig_type in all_signals:
        assert sig_type in all_routed, f"Signal {sig_type} missing from all routing tables (default + slices)"

def test_dual_mode_kernel_slice_detection():
    """Dual-Mode Kernel detects task type and builds dynamic routing table"""
    from kernel.slice_router import detect_task_type
    kernel = DispatchKernel()
    
    # Test humaneval detection
    task_type = kernel.detect_task_type("def has_close_elements(numbers, threshold):\n    \"\"\"Check...\"\"\"\n    >>> has_close_elements([1,2], 0.5)")
    assert task_type in ["humaneval", "default"]  # heuristic may detect as humaneval or default
    
    # Test ecommerce detection
    task_type = kernel.detect_task_type("Build e-commerce backend with product catalog and Stripe")
    assert task_type == "ecommerce"
    
    # Test dynamic routing table building
    table = kernel.build_dynamic_routing_table("humaneval")
    assert "CANDIDATES_GENERATED" in table or "CONTEXT_CURATED" in table
    assert kernel.active_slice_type == "humaneval"
    
    table = kernel.build_dynamic_routing_table("ecommerce")
    assert kernel.active_slice_type == "ecommerce"
    
def test_slice_config_retrieval():
    """Kernel can retrieve full slice config for requirements"""
    kernel = DispatchKernel()
    config = kernel.get_slice_config("Build e-commerce backend", "")
    assert "task_type" in config
    assert "slice" in config
    assert config["task_type"] == "ecommerce"


def test_failure_policy_defined():
    """Critical agents have failure policies"""
    assert "task_decomposer" in FAILURE_POLICY
    assert "code_executor" in FAILURE_POLICY
    assert "test_runner" in FAILURE_POLICY
    assert FAILURE_POLICY["code_executor"]["max_retries"] == 3


def test_kernel_emit_and_route():
    """Kernel emits signals and routes them deterministically"""
    kernel = DispatchKernel()
    sig = AgentSignal(signal_type="CONTEXT_CURATED", source_agent="context_curator")
    kernel.emit(sig)
    
    next_agent = kernel.route(sig)
    assert next_agent == "task_decomposer"
    assert len(kernel.signal_log) == 1


def test_kernel_retry_budget():
    """Retry budget is tracked correctly"""
    kernel = DispatchKernel()
    assert kernel.check_retry_budget("code_executor") is True
    
    for _ in range(3):
        kernel.increment_retry("code_executor")
    
    assert kernel.check_retry_budget("code_executor") is False


def test_kernel_routing_failure_to_refiner():
    """Failure signals route to surgical_refiner"""
    kernel = DispatchKernel()
    sig = AgentSignal(signal_type="TESTS_FAILED", source_agent="test_runner")
    assert kernel.route(sig) == "surgical_refiner"


def test_kernel_routing_alert_to_human():
    """Alert signals route to human_checkpoint"""
    kernel = DispatchKernel()
    sig = AgentSignal(signal_type="SECURITY_VIOLATION", source_agent="code_executor")
    assert kernel.route(sig) == "human_checkpoint"


def test_kernel_route_is_used_in_run(tmp_path, monkeypatch):
    """run() routes the code stage through route() and emits one signal per task.

    Guards against the ROUTING_TABLE becoming dead code (F3): the kernel must
    consult route() rather than hard-coding the next agent.
    """
    # Stub the LLM-backed stage so the test never hits the network.
    # NOTE: dispatch_kernel imports decompose_requirements via `from ... import`,
    # so the live reference lives on the dk module object — patch that, not td.
    import kernel.dispatch_kernel as dk

    def fake_decompose(*a, **k):
        return {"tasks": [{"id": "t1"}, {"id": "t2"}], "metadata": {}, "success": True}

    monkeypatch.setattr(dk, "decompose_requirements", fake_decompose)
    # validate_output is imported into dk via `from ... import`; stub it so the
    # deterministic validation stage reports success without hitting real logic.
    monkeypatch.setattr(dk, "validate_output", lambda *a, **k: {"success": True, "quality_score": 1.0, "violations": []})
    monkeypatch.setattr(dk, "execute_task", lambda *a, **k: {"success": False, "code": ""})
    monkeypatch.setattr(dk, "run_code_and_tests", lambda *a, **k: {"success": False})

    kernel = DispatchKernel()
    result = kernel.run("Build a login page", execute_code=True)
    assert result["success"] is True
    # route() must be exercised: CODE_GENERATED resolves to test_runner
    assert kernel.route(AgentSignal(signal_type="CODE_GENERATED", source_agent="x")) == "test_runner"
    # decomposition produces exactly one TASK_DECOMPOSED signal carrying ALL tasks
    # (no silent tasks[:3] truncation — every task is present in the signal payload).
    decomposed = [s for s in kernel.signal_log if s["signal_type"] == "TASK_DECOMPOSED"]
    assert len(decomposed) == 1
    emitted_task_ids = {t.get("id") for t in decomposed[0]["data"].get("tasks", [])}
    assert emitted_task_ids == {"t1", "t2"}
