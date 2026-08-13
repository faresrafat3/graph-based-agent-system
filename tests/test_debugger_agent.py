from agents.debugger_agent import DebuggerEngine, DEBUGGER_PERMISSIONS, debug_code, DebuggerState
import agents.debugger_agent as debugger_module
import json

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


def test_debugger_credentials_breach():
    import pytest
    with pytest.raises(PermissionError, match="Debugger attempted to handle credentials in NEVER permission."):
        debug_code(
            failed_code="password = 'secret'\nhardcoded API key",
            test_failure="fail",
            problem_spec="spec"
        )


def test_debug_context_manager():
    from agents.debugger_agent import DebugContextManager
    manager = DebugContextManager(domain_name="testing")
    global_context = "This is some global codebase context with general developer guidelines."
    failure_output = "Traceback (most recent call last):\n  File 'test_main.py', line 12\nAssertionError: expected 4, got 3"
    
    res = manager.filter_debug_context(global_context, failure_output)
    assert "filtered_context" in res
    assert "debug_snippet" in res
    assert "AssertionError" in res["debug_snippet"]


def test_debugger_escalation_on_repeated_failures(monkeypatch):
    # Mock LLM to always return invalid syntax, so it fails evaluation
    def fake_broken_llm(*a, **k):
        return "def broken(:"
        
    monkeypatch.setattr(debugger_module, "call_llm", fake_broken_llm)
    
    res = debug_code(
        failed_code="def broken():",
        test_failure="fail",
        problem_spec="spec",
        thread_id="debugger_escalate_session"
    )
    
    assert res["success"] is False
    assert res["fix_attempts"] >= 3


def test_debugger_fenced_response_and_empty_failure(monkeypatch):
    # Cover line 79
    assert DebuggerEngine.sanitize_failure_output("") == ""
    
    # Cover line 148: LLM returns fenced code
    def fake_fenced_llm(*a, **k):
        return "```python\ndef add(a,b):\n    return a+b\n```"
        
    monkeypatch.setattr(debugger_module, "call_llm", fake_fenced_llm)
    
    res = debug_code(
        failed_code="def add(a,b): return a-b",
        test_failure="fail",
        problem_spec="spec",
        thread_id="debugger_fenced_session"
    )
    
    assert res["success"] is True
    assert "return a+b" in res["fixed_code"]


