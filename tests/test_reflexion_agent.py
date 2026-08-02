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
