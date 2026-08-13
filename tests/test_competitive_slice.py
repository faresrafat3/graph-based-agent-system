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
            "breaches": []
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
            "breaches": []
        }
    
    def fake_ground_truth(code, problem):
        call_count["ground"] += 1
        if call_count["ground"] == 1:
            return {"passed": False, "returncode": 1, "stderr": "assert False"}
        else:
            return {"passed": True, "returncode": 0, "stderr": ""}
    
    def fake_debug(failed_code, test_failure, problem_spec="", past_reflections=None, thread_id=""):
        return {"fixed_code": "def fixed(): return True", "success": True, "breaches": [], "debug_summary": "fixed", "fix_attempts": 1}
    
    def fake_reflection(*args, **kwargs):
        return {"verbal_reflection": "Need to handle edge", "reflection_summary": "handle edge", "success": True, "breaches": []}
    
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


def test_slice_triggers_reflexion_loop(monkeypatch):
    """Verify that when all candidates fail ground-truth, reflexion is triggered to reinforce the next trial"""
    call_count = {"sample": 0, "reflection": 0}
    
    def fake_curated(*args, **kwargs):
        return {"sanitized_prompt": "spec", "success": True, "signal_to_noise_ratio": 1.0, "compacted_summary": ""}
        
    def fake_sample(**kwargs):
        call_count["sample"] += 1
        return {
            "candidates": [{"id": f"c_{call_count['sample']}", "code": "bad code"}],
            "valid_candidates": [{"id": f"c_{call_count['sample']}", "code": "bad code"}],
            "sampling_report": {"total_generated": 1},
            "success": True,
            "breaches": []
        }
        
    def fake_ground_truth(code, problem):
        return {"passed": False, "returncode": 1, "stderr": "assert False"}
        
    def fake_debug(failed_code, test_failure, problem_spec="", past_reflections=None, thread_id=""):
        return {"fixed_code": "def fixed(): return False", "success": True, "breaches": [], "debug_summary": "fixed", "fix_attempts": 1}
        
    def fake_reflection(*args, **kwargs):
        call_count["reflection"] += 1
        return {"verbal_reflection": "My reflection", "reflection_summary": "reflected", "success": True, "breaches": []}
        
    monkeypatch.setattr(slice_module, "curate_context", fake_curated)
    monkeypatch.setattr(slice_module, "sample_candidates", fake_sample)
    monkeypatch.setattr(slice_module, "run_ground_truth", fake_ground_truth)
    monkeypatch.setattr(slice_module, "debug_code", fake_debug)
    monkeypatch.setattr(slice_module, "generate_reflection", fake_reflection)
    monkeypatch.setattr(slice_module, "get_relevant_reflections", lambda *a, **k: [])
    
    res = run_competitive_slice(fake_problem(), n_samples=1, max_debug_retries=1, max_reflexion_trials=1)
    
    assert res["passed"] is False
    assert res["success"] is False
    assert call_count["sample"] == 2  # Trial 0 and Trial 1
    assert call_count["reflection"] == 1  # 1 reflection generated between trials


def test_slice_reflexion_failure(monkeypatch):
    """Verify that when reflexion generation fails, the slice still proceeds and fails safely"""
    def fake_curated(*args, **kwargs):
        return {"sanitized_prompt": "spec", "success": True, "signal_to_noise_ratio": 1.0, "compacted_summary": ""}
        
    def fake_sample(**kwargs):
        return {
            "candidates": [{"id": "c0", "code": "bad code"}],
            "valid_candidates": [{"id": "c0", "code": "bad code"}],
            "sampling_report": {"total_generated": 1},
            "success": True,
            "breaches": []
        }
        
    def fake_ground_truth(code, problem):
        return {"passed": False, "returncode": 1, "stderr": "assert False"}
        
    def fake_debug(failed_code, test_failure, problem_spec="", past_reflections=None, thread_id=""):
        return {"fixed_code": "def fixed(): return False", "success": True, "breaches": [], "debug_summary": "fixed", "fix_attempts": 1}
        
    def fake_reflection_fail(*args, **kwargs):
        return {"success": False, "breaches": ["failed to reflect"]}
        
    monkeypatch.setattr(slice_module, "curate_context", fake_curated)
    monkeypatch.setattr(slice_module, "sample_candidates", fake_sample)
    monkeypatch.setattr(slice_module, "run_ground_truth", fake_ground_truth)
    monkeypatch.setattr(slice_module, "debug_code", fake_debug)
    monkeypatch.setattr(slice_module, "generate_reflection", fake_reflection_fail)
    monkeypatch.setattr(slice_module, "get_relevant_reflections", lambda *a, **k: [])
    
    res = run_competitive_slice(fake_problem(), n_samples=1, max_debug_retries=1, max_reflexion_trials=1)
    
    assert res["passed"] is False
    assert res["success"] is False


def test_run_slice_on_3_failing_problems(monkeypatch):
    import benchmarks.humaneval_harness as harness
    
    # Mock load_problems to return dummy problems matching the failing ids
    def fake_load_problems():
        return [
            {
                "task_id": "HumanEval/76",
                "prompt": "def f():",
                "test": "def check():\n    assert True\n",
                "entry_point": "f"
            },
            {
                "task_id": "HumanEval/116",
                "prompt": "def g():",
                "test": "def check():\n    assert True\n",
                "entry_point": "g"
            },
            {
                "task_id": "HumanEval/145",
                "prompt": "def h():",
                "test": "def check():\n    assert True\n",
                "entry_point": "h"
            }
        ]
        
    monkeypatch.setattr(harness, "load_problems", fake_load_problems)
    
    # Also mock run_competitive_slice itself
    called_problems = []
    
    def fake_run_competitive_slice(prob, **kwargs):
        called_problems.append(prob["task_id"])
        return {"passed": True, "success": True}
        
    monkeypatch.setattr(slice_module, "run_competitive_slice", fake_run_competitive_slice)
    
    results = slice_module.run_slice_on_3_failing_problems()
    
    assert len(results) == 3
    assert set(called_problems) == {"HumanEval/76", "HumanEval/116", "HumanEval/145"}

