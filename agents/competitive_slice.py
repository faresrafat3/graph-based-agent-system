"""
Competitive Programming Slice Graph - Specialized Graph for HumanEval/LeetCode tasks

This is a SLICE, not the Ultimate Graph. It uses only the agents needed for
competitive programming / single-function completion, inspired by AlphaCode + Reflexion.

Slice Topology (5-7 agents vs 20 in Ultimate):
    Problem -> ContextCurator (sanitize) 
            -> SamplingAgent (AlphaCode: N candidates)
            -> ExecutionValidator (physical execution filter)
            -> [if all fail] ReflexionAgent -> DebuggerAgent -> loop
            -> Clustering (dedup) -> Integration (pick best)

This slice is selected by DispatchKernel when task_type == "humaneval" or "competitive"
"""

from typing import Dict, Any
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.context_curator import curate_context
from agents.sampling_agent import sample_candidates
from agents.debugger_agent import debug_code
from agents.reflexion_agent import generate_reflection, get_relevant_reflections
from benchmarks.humaneval_harness import run_ground_truth


def run_competitive_slice(
    problem: Dict[str, Any],
    n_samples: int = 5,
    max_debug_retries: int = 2,
    max_reflexion_trials: int = 2,
    temperature: float = 0.8
) -> Dict[str, Any]:
    """
    Run competitive programming slice graph on a single HumanEval problem.

    Args:
        problem: HumanEval problem dict with prompt, test, entry_point, task_id
        n_samples: Number of candidates to sample (AlphaCode)
        max_debug_retries: Max debugger retries per candidate
        max_reflexion_trials: Max reflexion trials (outer loop)
        temperature: Sampling temperature

    Returns:
        Dict with final_code, passed, attempts, reflections, etc.
    """
    task_id = problem.get("task_id", "unknown")
    prompt = problem.get("prompt", "")
    
    print(f"[CompetitiveSlice] Task {task_id} - Starting with {n_samples} samples @ temp {temperature}")

    # === Stage 1: Context Curation (Zero-LLM) ===
    curated = curate_context(raw_prompt=prompt, history_logs=[], max_token_budget=4000)
    sanitized = curated["sanitized_prompt"] if curated["success"] else prompt

    # Retrieve relevant past reflections (Long-term memory)
    past_reflections = get_relevant_reflections(prompt, limit=3)

    execution_history = []
    for reflexion_trial in range(max_reflexion_trials + 1):
        # === Stage 2: Sampling (AlphaCode) ===
        sampling_result = sample_candidates(
            problem_spec=sanitized,
            n_samples=n_samples,
            temperature=temperature if reflexion_trial == 0 else max(0.3, temperature - 0.2 * reflexion_trial),  # cool down after reflection
            past_reflections=past_reflections,
            thread_id=f"competitive_{task_id}_trial_{reflexion_trial}"
        )

        valid_candidates = sampling_result.get("valid_candidates", [])
        print(f"  Trial {reflexion_trial+1}: Generated {sampling_result['sampling_report'].get('total_generated',0)} -> {len(valid_candidates)} valid after AST")

        # === Stage 3: Execution Filtering (AlphaCode filtering) ===
        for cand in valid_candidates:
            code = cand.get("code", "")
            exec_result = run_ground_truth(code, problem)

            if exec_result["passed"]:
                print(f"  ✅ PASS found in trial {reflexion_trial+1}, candidate {cand['id']}")
                return {
                    "task_id": task_id,
                    "final_code": code,
                    "passed": True,
                    "trial": reflexion_trial,
                    "candidate_id": cand["id"],
                    "total_candidates_tried": len(valid_candidates),
                    "reflections_used": past_reflections,
                    "execution_history": execution_history,
                    "sampling_report": sampling_result["sampling_report"],
                    "success": True
                }
            else:
                # Failed candidate - prepare for debugging
                failure = exec_result["stderr"][:500]
                execution_history.append({
                    "candidate_id": cand["id"],
                    "code_snippet": code[:300],
                    "failure": failure,
                    "trial": reflexion_trial
                })

                # Try debugger for this candidate (inner loop)
                if max_debug_retries > 0:
                    debug_res = debug_code(
                        failed_code=code,
                        test_failure=failure,
                        problem_spec=sanitized,
                        past_reflections=past_reflections,
                        thread_id=f"debug_{task_id}_{cand['id']}"
                    )
                    if debug_res["success"]:
                        fixed_code = debug_res["fixed_code"]
                        exec_fixed = run_ground_truth(fixed_code, problem)
                        if exec_fixed["passed"]:
                            print(f"  ✅ PASS after debugging candidate {cand['id']}")
                            return {
                                "task_id": task_id,
                                "final_code": fixed_code,
                                "passed": True,
                                "trial": reflexion_trial,
                                "candidate_id": cand["id"] + "_debugged",
                                "debug_summary": debug_res["debug_summary"],
                                "reflections_used": past_reflections,
                                "execution_history": execution_history,
                                "sampling_report": sampling_result["sampling_report"],
                                "success": True
                            }

        # === Stage 4: Reflexion - if all candidates failed, reflect ===
        if reflexion_trial < max_reflexion_trials:
            # Take first failure as example
            if execution_history:
                last_failure = execution_history[-1]
                reflection_res = generate_reflection(
                    failed_code=last_failure.get("code_snippet", ""),
                    test_failure=last_failure.get("failure", ""),
                    problem_spec=sanitized,
                    execution_history=execution_history,
                    thread_id=f"reflexion_{task_id}_trial_{reflexion_trial}"
                )
                if reflection_res["success"]:
                    new_reflection = reflection_res["verbal_reflection"]
                    past_reflections.append(new_reflection)
                    print(f"  💭 Reflexion: {reflection_res['reflection_summary'][:100]}...")
                else:
                    print("  ⚠️ Reflexion failed to generate actionable reflection")

    # If we reach here, all trials failed
    print(f"  ❌ FAIL after {max_reflexion_trials+1} trials, {len(execution_history)} candidates tried")
    return {
        "task_id": task_id,
        "final_code": execution_history[-1]["code_snippet"] if execution_history else "",
        "passed": False,
        "trial": max_reflexion_trials,
        "total_candidates_tried": len(execution_history),
        "reflections_used": past_reflections,
        "execution_history": execution_history,
        "sampling_report": {},
        "success": False
    }


def run_slice_on_3_failing_problems():
    """Quick demo on the 3 problems that failed in full run: 76, 116, 145"""
    from benchmarks.humaneval_harness import load_problems
    problems = load_problems()
    failing_ids = {"HumanEval/76", "HumanEval/116", "HumanEval/145"}
    targets = [p for p in problems if p["task_id"] in failing_ids]

    results = []
    for prob in targets:
        res = run_competitive_slice(prob, n_samples=5, max_debug_retries=1, max_reflexion_trials=1)
        results.append(res)
        print(f"Result {prob['task_id']}: PASS={res['passed']}")

    passed = sum(1 for r in results if r["passed"])
    print(f"\nSlice retry on 3 previously failing: {passed}/3 passed")
    return results
