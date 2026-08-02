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
