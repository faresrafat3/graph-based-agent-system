"""
Sampling Agent - AlphaCode-Inspired Diverse Candidate Generation

Takes AlphaCode's core insight: instead of 1 perfect generation, generate N diverse
candidates with high temperature, then filter + cluster. This turns a single-point
failure into a population that can be searched.

Implemented under Constitution:
- LLM is sandboxed CPU (generates candidates)
- Evaluate is ZERO-LLM (counts, deduplicates, validates syntax)
- Permission boundaries enforced
- Karpathy Loop

AlphaCode insight adapted:
- Original AlphaCode: 1M samples, massive filtering/clustering
- Our Lite version: 5-20 samples, AST validation as filter, simple dedup as clustering
- Suitable for HumanEval + general code generation where diversity matters
"""

import os
import sys
import re
import hashlib
from typing import TypedDict, List, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from llm.llm_integration import call_llm
from agents.code_executor import validate_python_syntax


SAMPLING_PERMISSIONS = {
    "READ": ["problem_spec", "project_context", "past_reflections", "constraints"],
    "WRITE": ["candidates", "valid_candidates", "sampling_report"],
    "NEVER": ["credentials", "deployment", "production_config"],
    "HUMAN_CHECKPOINT": ["excessive_sampling_cost", "prompt_injection_detected"]
}

SAMPLING_SYSTEM_PROMPT = """You are a Sampling Agent (AlphaCode-inspired) inside a graph-based system.

Your job: Generate ONE complete, correct Python implementation for the given problem.

Rules:
- Think differently each time - diversity matters
- Output ONLY raw Python code, no prose, no markdown fences
- Complete function definition including signature
- Include needed imports at top
- Runnable, complete, no TODO
- Be creative in approach but correct

Output ONLY code.
"""


class SamplingState(TypedDict):
    problem_spec: str
    project_context: str
    constraints: str
    past_reflections: List[str]
    n_samples: int
    temperature: float
    candidates: List[Dict[str, Any]]
    valid_candidates: List[Dict[str, Any]]
    sampling_report: Dict[str, Any]
    violations: List[str]
    retry_count: int
    success: bool


class SamplingEngine:
    """Deterministic helpers"""

    @staticmethod
    def deduplicate_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate by code hash - simple clustering (AlphaCode clustering lite)"""
        seen = {}
        deduped = []
        for cand in candidates:
            code = cand.get("code", "")
            h = hashlib.sha256(code.encode()).hexdigest()[:16]
            if h not in seen:
                seen[h] = True
                deduped.append(cand)
        return deduped

    @staticmethod
    def validate_and_filter(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter by AST validation - first stage filter like AlphaCode"""
        valid = []
        for cand in candidates:
            code = cand.get("code", "")
            validation = validate_python_syntax(code)
            if validation["success"]:
                cand["ast_valid"] = True
                cand["metrics"] = validation["metrics"]
                valid.append(cand)
            else:
                cand["ast_valid"] = False
                cand["violations"] = validation["violations"]
        return valid

    @staticmethod
    def build_sampling_prompt(problem_spec: str, attempt_idx: int, past_reflections: List[str]) -> str:
        """Build prompt with diversity hint + past reflections"""
        diversity_hints = [
            "Try an iterative approach.",
            "Try a recursive approach.",
            "Try using different data structures (set, dict, list comprehension).",
            "Try optimizing for readability.",
            "Try optimizing for edge cases first.",
            "Try a completely different algorithm.",
            "Focus on handling empty inputs and boundary conditions.",
            "Think about time complexity, try O(n log n) approach."
        ]
        hint = diversity_hints[attempt_idx % len(diversity_hints)]

        reflection_block = ""
        if past_reflections and attempt_idx > 0:
            reflection_block = f"\nLearnings from past attempts:\n{past_reflections[-1]}\n"

        return f"""{problem_spec}

Diversity Instruction: {hint}
{reflection_block}
Generate ONE complete Python solution.
"""


def propose(state: SamplingState) -> dict:
    problem_spec = state.get("problem_spec", "")
    if not problem_spec.strip():
        raise ValueError("problem_spec must be non-empty")

    # Check for injection in NEVER
    if "delete production" in problem_spec.lower() or "override credentials" in problem_spec.lower():
        raise PermissionError("SamplingAgent detected NEVER permission violation")

    return {"candidates": [], "valid_candidates": [], "violations": [], "success": False}


def execute(state: SamplingState) -> dict:
    problem_spec = state.get("problem_spec", "")
    n_samples = state.get("n_samples", 5)
    temperature = state.get("temperature", 0.8)
    past_reflections = state.get("past_reflections", [])

    candidates = []

    # Sequential calls for now (could be parallel with ThreadPool)
    for i in range(n_samples):
        prompt = SamplingEngine.build_sampling_prompt(problem_spec, i, past_reflections)
        try:
            raw = call_llm(prompt, SAMPLING_SYSTEM_PROMPT, temperature=temperature)
            # Strip fences
            code = raw.strip()
            fenced = re.findall(r"```(?:python|py)?\s*\n(.*?)```", code, re.DOTALL)
            if fenced:
                code = max(fenced, key=len)
            code = re.sub(r"^```(?:python|py)?\s*", "", code)
            code = re.sub(r"```\s*$", "", code)

            candidates.append({
                "id": f"candidate_{i}",
                "code": code.strip(),
                "temperature": temperature,
                "attempt_idx": i,
                "raw_response_length": len(raw)
            })
        except Exception as e:
            # Law 3: fail loudly but per-candidate, not whole batch
            candidates.append({
                "id": f"candidate_{i}",
                "code": "",
                "error": str(e),
                "failed": True
            })

    deduped = SamplingEngine.deduplicate_candidates([c for c in candidates if c.get("code")])
    valid = SamplingEngine.validate_and_filter(deduped)

    report = {
        "total_generated": len(candidates),
        "after_dedup": len(deduped),
        "valid_after_ast": len(valid),
        "invalid": len(candidates) - len(valid),
        "diversity_ratio": round(len(deduped) / len(candidates), 3) if candidates else 0,
        "valid_rate": round(len(valid) / len(candidates), 3) if candidates else 0
    }

    return {
        "candidates": candidates,
        "valid_candidates": valid,
        "sampling_report": report
    }


def evaluate(state: SamplingState) -> dict:
    valid = state.get("valid_candidates", [])
    report = state.get("sampling_report", {})

    # Success if at least 1 valid candidate
    success = len(valid) >= 1
    violations = []
    if not success:
        violations.append("No valid candidates generated after AST filtering")

    return {"success": success, "violations": violations}


def commit(state: SamplingState) -> dict:
    return {"committed": True}


def refine(state: SamplingState) -> dict:
    return {"retry_count": state.get("retry_count", 0) + 1, "success": False}


def should_continue(state: SamplingState) -> str:
    if state.get("success"):
        return "commit"
    elif state.get("retry_count", 0) >= 2:
        return "escalate"
    else:
        return "refine"


workflow = StateGraph(SamplingState)
workflow.add_node("propose", propose)
workflow.add_node("execute", execute)
workflow.add_node("evaluate", evaluate)
workflow.add_node("commit", commit)
workflow.add_node("refine", refine)

workflow.set_entry_point("propose")
workflow.add_edge("propose", "execute")
workflow.add_edge("execute", "evaluate")
workflow.add_conditional_edges("evaluate", should_continue, {"commit": "commit", "refine": "refine", "escalate": END})
workflow.add_edge("refine", "propose")
workflow.add_edge("commit", END)

checkpointer = MemorySaver()
sampling_graph = workflow.compile(checkpointer=checkpointer)


def sample_candidates(
    problem_spec: str,
    n_samples: int = 5,
    temperature: float = 0.8,
    project_context: str = "",
    past_reflections: List[str] = None,
    thread_id: str = "sampling_session"
) -> dict:
    """
    Main entrypoint - AlphaCode-inspired sampling.

    Args:
        problem_spec: Problem description
        n_samples: Number of candidates to generate (5-20 typical)
        temperature: Diversity temperature (0.7-1.0 for diversity)
        project_context: Optional context
        past_reflections: Past verbal reflections to guide diversity
        thread_id: LangGraph thread id

    Returns:
        Dict with candidates, valid_candidates, sampling_report, success
    """
    if n_samples > 20:
        # Human checkpoint for cost control
        raise ValueError("n_samples > 20 requires HUMAN_CHECKPOINT approval (cost control)")

    result = sampling_graph.invoke(
        {
            "problem_spec": problem_spec,
            "project_context": project_context,
            "constraints": "",
            "past_reflections": past_reflections or [],
            "n_samples": n_samples,
            "temperature": temperature,
            "candidates": [],
            "valid_candidates": [],
            "sampling_report": {},
            "violations": [],
            "retry_count": 0,
            "success": False
        },
        config={"configurable": {"thread_id": thread_id}}
    )

    return {
        "candidates": result.get("candidates", []),
        "valid_candidates": result.get("valid_candidates", []),
        "sampling_report": result.get("sampling_report", {}),
        "success": result.get("success", False),
        "violations": result.get("violations", [])
    }
