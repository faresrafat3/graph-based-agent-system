"""
Filtering & Clustering Agent - AlphaCode Stage 2 & 3

Takes AlphaCode's filtering + clustering stages and makes them explicit agents.

Original AlphaCode:
- Stage: Sample 1M
- Stage: Filter by sample tests (keep 10k)
- Stage: Cluster by output behavior on generated inputs (group similar solutions)
- Stage: Pick 1 per cluster

Our Lite:
- Stage: Filter by AST (already in SamplingAgent) + Execution (run_ground_truth)
- Stage: Cluster by SHA256 dedup + output behavior (if execution results available)

This agent is the second half of AlphaCode after SamplingAgent.

Constitution compliant: Evaluate ZERO-LLM, permission matrix.
"""

import sys
import hashlib
from typing import TypedDict, List, Dict, Any

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))))

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agents.code_executor import validate_python_syntax


FILTERING_CLUSTERING_PERMISSIONS = {
    "READ": ["candidates", "test_suite", "problem_spec"],
    "WRITE": ["filtered_candidates", "clusters", "representatives", "filtering_report"],
    "NEVER": ["credentials", "deployment", "production_config"],
    "HUMAN_CHECKPOINT": ["excessive_filtering_cost"]
}


class FilteringClusteringState(TypedDict):
    candidates: List[Dict[str, Any]]
    test_suite: str
    problem_spec: str
    filtered_candidates: List[Dict[str, Any]]
    clusters: Dict[str, List[Dict]]
    representatives: List[Dict]
    filtering_report: Dict[str, Any]
    violations: List[str]
    retry_count: int
    success: bool


class FilteringEngine:
    """Deterministic helpers"""

    @staticmethod
    def filter_by_ast(candidates: List[Dict]) -> List[Dict]:
        """First filter: AST valid"""
        valid = []
        for cand in candidates:
            code = cand.get("code", "")
            val = validate_python_syntax(code)
            if val["success"]:
                valid.append(cand)
        return valid

    @staticmethod
    def cluster_by_hash(candidates: List[Dict]) -> Dict[str, List[Dict]]:
        """Cluster by code hash (lite clustering)"""
        clusters = {}
        for cand in candidates:
            code = cand.get("code", "")
            h = hashlib.sha256(code.encode()).hexdigest()[:8]
            clusters.setdefault(h, []).append(cand)
        return clusters

    @staticmethod
    def cluster_by_behavior(candidates: List[Dict]) -> Dict[str, List[Dict]]:
        """
        More advanced clustering by output behavior.
        If candidates have 'execution_output' field (from previous run), cluster by that.
        Otherwise fallback to hash clustering.
        """
        # Check if we have execution outputs
        has_outputs = any("execution_output" in c for c in candidates)
        if not has_outputs:
            return FilteringEngine.cluster_by_hash(candidates)

        # Cluster by execution output
        clusters = {}
        for cand in candidates:
            output = cand.get("execution_output", "") or cand.get("code", "")[:50]
            h = hashlib.sha256(str(output).encode()).hexdigest()[:8]
            clusters.setdefault(h, []).append(cand)
        return clusters

    @staticmethod
    def pick_representatives(clusters: Dict[str, List[Dict]]) -> List[Dict]:
        """Pick one per cluster (shortest code wins - usually cleanest)"""
        reps = []
        for cluster_id, members in clusters.items():
            # Pick member with shortest code (often simplest)
            best = min(members, key=lambda m: len(m.get("code", "")))
            best["cluster_id"] = cluster_id
            best["cluster_size"] = len(members)
            reps.append(best)
        return reps


def propose(state: FilteringClusteringState) -> dict:
    candidates = state.get("candidates", [])
    if not candidates:
        raise ValueError("candidates required")
    if len(candidates) > 100:
        raise ValueError("Too many candidates (>100) requires HUMAN_CHECKPOINT")

    return {"filtered_candidates": [], "clusters": {}, "representatives": [], "violations": [], "success": False}


def execute(state: FilteringClusteringState) -> dict:
    candidates = state.get("candidates", [])

    # Stage 1: Filter by AST
    after_ast = FilteringEngine.filter_by_ast(candidates)

    # Stage 2: Cluster
    clusters = FilteringEngine.cluster_by_behavior(after_ast)

    # Stage 3: Pick representatives
    reps = FilteringEngine.pick_representatives(clusters)

    report = {
        "total_input": len(candidates),
        "after_ast_filter": len(after_ast),
        "num_clusters": len(clusters),
        "representatives": len(reps),
        "filter_rate": round((len(candidates) - len(after_ast)) / len(candidates), 3) if candidates else 0,
        "cluster_reduction": round((len(after_ast) - len(reps)) / len(after_ast), 3) if after_ast else 0
    }

    return {
        "filtered_candidates": after_ast,
        "clusters": clusters,
        "representatives": reps,
        "filtering_report": report
    }


def evaluate(state: FilteringClusteringState) -> dict:
    reps = state.get("representatives", [])
    success = len(reps) >= 1
    violations = []
    if not success:
        violations.append("No representatives after clustering")
    return {"success": success, "violations": violations}


def commit(state: FilteringClusteringState) -> dict:
    return {"committed": True}


def refine(state: FilteringClusteringState) -> dict:
    return {"retry_count": state.get("retry_count", 0) + 1, "success": False}


def should_continue(state: FilteringClusteringState) -> str:
    if state.get("success"):
        return "commit"
    elif state.get("retry_count", 0) >= 2:
        return "escalate"
    else:
        return "refine"


workflow = StateGraph(FilteringClusteringState)
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
filtering_graph = workflow.compile(checkpointer=checkpointer)


def filter_and_cluster(
    candidates: List[Dict[str, Any]],
    problem_spec: str = "",
    thread_id: str = "filtering_session"
) -> dict:
    """Main entrypoint - AlphaCode filtering + clustering"""
    result = filtering_graph.invoke(
        {
            "candidates": candidates,
            "problem_spec": problem_spec,
            "test_suite": "",
            "filtered_candidates": [],
            "clusters": {},
            "representatives": [],
            "filtering_report": {},
            "violations": [],
            "retry_count": 0,
            "success": False
        },
        config={"configurable": {"thread_id": thread_id}}
    )

    return {
        "filtered_candidates": result.get("filtered_candidates", []),
        "clusters": result.get("clusters", {}),
        "representatives": result.get("representatives", []),
        "filtering_report": result.get("filtering_report", {}),
        "success": result.get("success", False),
        "violations": result.get("violations", [])
    }
