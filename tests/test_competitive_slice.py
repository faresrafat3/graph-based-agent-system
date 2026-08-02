import sys
sys.path.append('.')

from agents.competitive_slice import run_competitive_slice
import agents.competitive_slice as slice_module

def fake_problem():
    return {
        "task_id": "HumanEval/0",
        "prompt": "def has_close_elements(numbers, threshold):\n    \"\"\"Check if...\"\"\"\n",
        "test": "def check():\n    assert has_close_elements([1,2,3], 0.5) == False\n",
        "entry_point": "has_close_elements"
    }

def test_competitive_slice_passes_with_good_code(monkeypatch):
    def fake_curated(raw_prompt, history_logs=None, max_token_budget=4000):
        return {"sanitized_prompt": raw_prompt, "success": True, "signal_to_noise_ratio": 1.0, "compacted_summary": ""}
    
    def fake_sample(problem_spec, n_samples=5, temperature=0.8, project_context="", past_reflections=None, thread_id=""):
        return {
            "candidates": [{"id": "c0", "code": "def has_close_elements(numbers, threshold):\n    return False", "temperature": temperature}],
            "valid_candidates": [{"id": "c0", "code": "def has_close_elements(numbers, threshold):\n    return False"}],
            "sampling_report": {"total_generated": 1, "after_dedup": 1, "valid_after_ast": 1},
            "success": True,
            "violations": []
        }
    
    def fake_ground_truth(code, problem):
        return {"passed": True, "returncode": 0, "stderr": ""}
    
    monkeypatch.setattr(slice_module, "curate_context", fake_curated)
    monkeypatch.setattr(slice_module, "sample_candidates", fake_sample)
    monkeypatch.setattr(slice_module, "run_ground_truth", fake_ground_truth)
    monkeypatch.setattr(slice_module, "get_relevant_reflections", lambda spec, limit=3: [])
    
    res = run_competitive_slice(fake_problem(), n_samples=1)
    assert res["passed"] is True
    assert res["success"] is True

def test_slice_uses_debugger_when_first_fails(monkeypatch):
    call_count = {"sample": 0, "ground": 0}
    
    def fake_curated(*args, **kwargs):
        return {"sanitized_prompt": "spec", "success": True, "signal_to_noise_ratio": 1.0, "compacted_summary": ""}
    
    def fake_sample(**kwargs):
        call_count["sample"] += 1
        return {
            "candidates": [{"id": "c0", "code": "bad code"}],
            "valid_candidates": [{"id": "c0", "code": "bad code"}],
            "sampling_report": {},
            "success": True,
            "violations": []
        }
    
    def fake_ground_truth(code, problem):
        call_count["ground"] += 1
        if call_count["ground"] == 1:
            return {"passed": False, "returncode": 1, "stderr": "assert False"}
        else:
            return {"passed": True, "returncode": 0, "stderr": ""}
    
    def fake_debug(failed_code, test_failure, problem_spec="", past_reflections=None, thread_id=""):
        return {"fixed_code": "def fixed(): return True", "success": True, "violations": [], "debug_summary": "fixed", "fix_attempts": 1}
    
    def fake_reflection(*args, **kwargs):
        return {"verbal_reflection": "Need to handle edge", "reflection_summary": "handle edge", "success": True, "violations": []}
    
    monkeypatch.setattr(slice_module, "curate_context", fake_curated)
    monkeypatch.setattr(slice_module, "sample_candidates", fake_sample)
    monkeypatch.setattr(slice_module, "run_ground_truth", fake_ground_truth)
    monkeypatch.setattr(slice_module, "debug_code", fake_debug)
    monkeypatch.setattr(slice_module, "generate_reflection", fake_reflection)
    monkeypatch.setattr(slice_module, "get_relevant_reflections", lambda *a, **k: [])
    
    res = run_competitive_slice(fake_problem(), n_samples=1, max_debug_retries=1)
    assert res["passed"] is True
    # Should have used debugger
    assert call_count["ground"] == 2
