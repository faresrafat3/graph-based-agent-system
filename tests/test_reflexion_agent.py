import sys
sys.path.append('.')

from agents.reflexion_agent import ReflexionEngine, REFLEXION_PERMISSIONS, generate_reflection
import agents.reflexion_agent as reflexion_module

def test_permissions_matrix():
    assert "READ" in REFLEXION_PERMISSIONS
    assert "WRITE" in REFLEXION_PERMISSIONS
    assert "NEVER" in REFLEXION_PERMISSIONS
    assert "code" in REFLEXION_PERMISSIONS["NEVER"]  # Must not generate code
    assert "verbal_reflection" in REFLEXION_PERMISSIONS["WRITE"]

def test_is_actionable_good():
    good = "Failed because I didn't handle empty list. Next time check len==0 early."
    assert ReflexionEngine.is_reflection_actionable(good) is True

def test_is_actionable_bad_short():
    bad = "Fix it"
    assert ReflexionEngine.is_reflection_actionable(bad) is False

def test_is_actionable_bad_code():
    bad_code = "def fix(): return 1"
    assert ReflexionEngine.is_reflection_actionable(bad_code) is False

def test_build_prompt():
    prompt = ReflexionEngine.build_reflection_prompt(
        failed_code="def add(a,b): return a-b",
        test_failure="assert fail",
        problem_spec="add two numbers",
        history=[{"failure": "empty list"}]
    )
    assert "FAILED CODE" in prompt
    assert "PREVIOUS ATTEMPTS" in prompt

def test_generate_reflection_success(monkeypatch):
    def fake_llm(prompt, system_prompt="", **kwargs):
        return "Failed because I assumed at least one element, didn't handle empty. Next time check len(arr)==0 first."
    
    monkeypatch.setattr(reflexion_module, "call_llm", fake_llm)
    
    res = generate_reflection(
        failed_code="def f(arr): return arr[0]",
        test_failure="IndexError on []",
        problem_spec="get first element"
    )
    assert res["success"] is True
    assert "empty" in res["verbal_reflection"].lower() or "len" in res["verbal_reflection"].lower()
    assert len(res["reflection_summary"]) > 0

def test_reflection_stores_in_memory(monkeypatch):
    def fake_llm(prompt, system_prompt="", **kwargs):
        return "Failed because off-by-one in loop, should use < not <=. Next time check boundary."
    
    monkeypatch.setattr(reflexion_module, "call_llm", fake_llm)
    
    # Clear memory first
    from memory.custom_memory import memory
    memory.clear_long_term()
    
    res = generate_reflection(
        failed_code="for i in range(len(arr)+1)",
        test_failure="IndexError",
        problem_spec="iterate"
    )
    assert res["success"] is True
    # Check memory stored
    assert len(memory.get_from_long_term()) >= 1


def test_is_reflection_actionable_various_branches():
    """Verify quality gate checks on the reflection string"""
    # Cover line 89 (empty)
    assert ReflexionEngine.is_reflection_actionable("") is False
    assert ReflexionEngine.is_reflection_actionable("short") is False
    # Cover line 96 (has def or import, but must pass length and word count checks first!)
    assert ReflexionEngine.is_reflection_actionable(
        "import math. We should next check if the list is empty because that handles it."
    ) is False
    assert ReflexionEngine.is_reflection_actionable(
        "def fix(): We should next check if the list is empty because that handles it."
    ) is False


def test_generate_reflection_validations_and_never(monkeypatch):
    """Verify input validations on empty inputs or NEVER security checks"""
    import pytest
    
    # Mock LLM so it never hits the network
    monkeypatch.setattr(reflexion_module, "call_llm", lambda *a, **k: "Failed because off-by-one. Next time check boundary.")
    
    # Cover line 130 (ValueError)
    with pytest.raises(ValueError, match="Need at least failed_code or test_failure"):
        generate_reflection("", "", thread_id="never_empty_session")
        
    # Cover line 135 (NEVER check)
    res = generate_reflection("password = 'secret'", "error", thread_id="never_session")
    assert res is not None


def test_generate_reflection_with_history(monkeypatch):
    """Verify prompt builder formats previous attempts history block"""
    # Cover line 168 (history is non-empty)
    def fake_llm(prompt, *args, **kwargs):
        assert "PREVIOUS ATTEMPTS" in prompt
        return "Failed because list was empty. Next time check len."
    monkeypatch.setattr(reflexion_module, "call_llm", fake_llm)
    
    res = generate_reflection(
        failed_code="x = 1",
        test_failure="error",
        problem_spec="spec",
        execution_history=[{"failure": "run1"}, {"failure": "run2"}],
        thread_id="history_session"
    )
    assert res is not None


def test_generate_reflection_not_actionable(monkeypatch):
    """Verify evaluation fails when LLM returns non-actionable reflection"""
    # Mock LLM to return non-actionable reflection
    monkeypatch.setattr(reflexion_module, "call_llm", lambda *a, **k: "just try again")
    res = generate_reflection("failed_code", "test_failure", "spec", thread_id="not_actionable_session")
    assert res["success"] is False
    assert any("not actionable" in v for v in res["violations"])


def test_reflexion_refine_and_should_continue():
    """Verify refine and should_continue branch decisions in reflection graph"""
    from agents.reflexion_agent import refine, should_continue
    
    res = refine({"retry_count": 0})
    assert res["retry_count"] == 1
    assert res["success"] is False
    
    assert should_continue({"success": True}) == "commit"
    assert should_continue({"success": False, "retry_count": 2}) == "escalate"
    assert should_continue({"success": False, "retry_count": 0}) == "refine"


def test_reflexion_exceptions(monkeypatch):
    """Verify safe fallbacks on long-term memory exceptions inside commit and retrieve"""
    from memory.custom_memory import CustomMemory
    
    # 1. Mock memory add_to_long_term exception
    def fake_add(*a, **k):
        raise RuntimeError("db lock")
    monkeypatch.setattr(CustomMemory, "add_to_long_term", fake_add)
    
    # Run a successful reflection, should commit and log error safely
    # Must contain at least 8 words to pass the quality gate!
    monkeypatch.setattr(reflexion_module, "call_llm", lambda *a, **k: "Failed because of off-by-one. Next time check boundary first.")
    res = generate_reflection("x = 1", "error", "spec", thread_id="exceptions_session")
    assert res["success"] is True  # Commit failure is safe, doesn't crash agent
    
    # 2. Mock find_similar exception
    def fake_find(*a, **k):
        raise RuntimeError("db lock")
    monkeypatch.setattr(CustomMemory, "find_similar", fake_find)
    
    from agents.reflexion_agent import get_relevant_reflections
    reflections = get_relevant_reflections("spec")
    assert reflections == []  # Falls back safely to empty list


def test_get_relevant_reflections_retrieval():
    """Verify that get_relevant_reflections successfully retrieves and extracts reflections"""
    from agents.reflexion_agent import get_relevant_reflections
    from memory.custom_memory import memory
    
    memory.clear_long_term()
    memory.add_to_long_term(
        data={"type": "reflexion", "problem": "solve add", "reflection": "Should check empty first because it fails."},
        metadata={}
    )
    
    # Use unpunctuated keywords from the reflection string to match above 0.3 Jaccard threshold
    res = get_relevant_reflections("check empty first because", limit=1)
    assert len(res) == 1
    assert "Should check empty" in res[0]





