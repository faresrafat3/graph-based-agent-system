import sys
sys.path.append('.')

from agents.debugger_agent import DebuggerEngine, DEBUGGER_PERMISSIONS, debug_code
import agents.debugger_agent as debugger_module

def test_permissions_matrix():
    assert "READ" in DEBUGGER_PERMISSIONS
    assert "WRITE" in DEBUGGER_PERMISSIONS
    assert "NEVER" in DEBUGGER_PERMISSIONS
    assert "HUMAN_CHECKPOINT" in DEBUGGER_PERMISSIONS
    assert "failed_code" in DEBUGGER_PERMISSIONS["READ"]

def test_sanitize_failure():
    raw = "Traceback\n"*10 + "assert False"*5000
    sanitized = DebuggerEngine.sanitize_failure_output(raw)
    assert len(sanitized) <= 2000
    assert "assert" in sanitized

def test_build_fix_prompt():
    prompt = DebuggerEngine.build_fix_prompt(
        failed_code="def add(a,b): return a-b",
        test_failure="assert add(2,2)==4 failed",
        problem_spec="def add(a,b): add two numbers",
        past_reflections=["Check empty list"]
    )
    assert "FAILED CODE" in prompt
    assert "PAST REFLECTIONS" in prompt
    assert "Check empty list" in prompt

def test_build_summary():
    summary = DebuggerEngine.build_summary("short", "longer code here", "assert failed")
    assert "Fixed code" in summary
    assert "delta" in summary.lower() or "chars" in summary.lower()

def test_debug_code_success(monkeypatch):
    def fake_llm(prompt, system_prompt="", **kwargs):
        return "def add(a,b):\n    return a+b"
    
    monkeypatch.setattr(debugger_module, "call_llm", fake_llm)
    
    res = debug_code(
        failed_code="def add(a,b): return a-b",
        test_failure="assert add(2,2)==4",
        problem_spec="add two numbers"
    )
    assert res["success"] is True
    assert "return a+b" in res["fixed_code"]
    assert res["fix_attempts"] >= 1

def test_debug_code_empty_fails(monkeypatch):
    def fake_empty(prompt, system_prompt="", **kwargs):
        return ""
    
    monkeypatch.setattr(debugger_module, "call_llm", fake_empty)
    
    res = debug_code(
        failed_code="bad code",
        test_failure="fail",
        problem_spec="spec"
    )
    # Should fail validation because empty
    assert res["success"] is False
