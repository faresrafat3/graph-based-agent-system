import sys
sys.path.append('.')

from agents.sampling_agent import SamplingEngine, SAMPLING_PERMISSIONS, sample_candidates
import agents.sampling_agent as sampling_module

def test_permissions_matrix():
    assert "READ" in SAMPLING_PERMISSIONS
    assert "WRITE" in SAMPLING_PERMISSIONS
    assert "NEVER" in SAMPLING_PERMISSIONS
    assert "problem_spec" in SAMPLING_PERMISSIONS["READ"]
    assert "candidates" in SAMPLING_PERMISSIONS["WRITE"]

def test_deduplication():
    cands = [
        {"code": "def f(): return 1"},
        {"code": "def f(): return 1"},  # duplicate
        {"code": "def f(): return 2"},
    ]
    deduped = SamplingEngine.deduplicate_candidates(cands)
    assert len(deduped) == 2

def test_validate_and_filter():
    cands = [
        {"code": "def good():\n    return 1", "id": "1"},
        {"code": "def bad(\n    return", "id": "2"},  # syntax error
    ]
    valid = SamplingEngine.validate_and_filter(cands)
    assert len(valid) == 1
    assert valid[0]["id"] == "1"

def test_build_prompt_with_reflection():
    prompt = SamplingEngine.build_sampling_prompt(
        problem_spec="def add(a,b):",
        attempt_idx=1,
        past_reflections=["Remember edge case"]
    )
    assert "Diversity Instruction" in prompt
    assert "Remember edge case" in prompt

def test_sample_candidates_success(monkeypatch):
    def fake_llm(prompt, system_prompt="", temperature=0.8, **kwargs):
        # Return different code based on diversity hint in prompt
        if "iterative" in prompt.lower():
            return "def solve():\n    return 1"
        else:
            return "def solve():\n    return 2"
    
    monkeypatch.setattr(sampling_module, "call_llm", fake_llm)
    
    res = sample_candidates(
        problem_spec="def solve(): implement",
        n_samples=3,
        temperature=0.8
    )
    assert res["success"] is True
    assert len(res["candidates"]) == 3
    assert "sampling_report" in res
    assert res["sampling_report"]["total_generated"] == 3

def test_excessive_samples_raises():
    try:
        sample_candidates(problem_spec="test", n_samples=25)
        assert False, "Should have raised for >20"
    except ValueError as e:
        assert "HUMAN_CHECKPOINT" in str(e)


def test_sample_candidates_empty_or_forbidden():
    """Verify input validations on empty or security-breaching specifications"""
    import pytest
    with pytest.raises(ValueError, match="problem_spec must be non-empty"):
        sample_candidates("")
        
    with pytest.raises(PermissionError, match="detected NEVER permission breach"):
        sample_candidates("delete production database")


def test_sample_candidates_fenced_and_exception(monkeypatch):
    """Verify that fenced markdown is stripped and exceptions on single calls are recorded safely per Law 3"""
    call_count = {"llm": 0}
    
    def fake_llm(*a, **k):
        call_count["llm"] += 1
        if call_count["llm"] == 1:
            return "```python\ndef solve():\n    return 1\n```"
        else:
            raise RuntimeError("LLM offline")
            
    monkeypatch.setattr(sampling_module, "call_llm", fake_llm)
    
    res = sample_candidates(
        problem_spec="def solve():",
        n_samples=2,
    )
    
    assert res["success"] is True
    assert len(res["candidates"]) == 2
    assert res["candidates"][0]["code"] == "def solve():\n    return 1"
    assert res["candidates"][1]["failed"] is True
    assert "LLM offline" in res["candidates"][1]["error"]


def test_sampling_refine_and_should_continue():
    """Verify refine and should_continue decisions in the sampling agent graph"""
    from agents.sampling_agent import refine, should_continue
    
    res = refine({"retry_count": 0})
    assert res["retry_count"] == 1
    assert res["success"] is False
    
    assert should_continue({"success": True}) == "commit"
    assert should_continue({"success": False, "retry_count": 2}) == "escalate"
    assert should_continue({"success": False, "retry_count": 0}) == "refine"


def test_sample_candidates_no_valid_candidates(monkeypatch):
    """Verify evaluation and breaches when all candidates fail AST parsing"""
    monkeypatch.setattr(sampling_module, "call_llm", lambda *a, **k: "def broken_syntax(:")
    
    res = sample_candidates(
        problem_spec="def solve():",
        n_samples=2,
        thread_id="sampling_no_valid_session"
    )
    
    assert res["success"] is False
    assert any("No valid candidates" in v for v in res["breaches"])


