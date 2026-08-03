"""
Slice Router - Dual-Mode Kernel Router

Detects task type deterministically (ZERO-LLM) and builds appropriate slice graph.

This is Phase 3: Kernel Dual-Mode Routing
- Ultimate Graph for complex software projects (E-commerce, Fintech)
- Competitive Slice for HumanEval / LeetCode
- Sampling + Filtering Slice for diverse generation tasks

Constitution: Law 11 Evaluate never calls LLM, Law 2 Permission checked.
"""

from typing import Dict

SLICE_REGISTRY = {
    "humaneval": {
        "description": "HumanEval / MBPP - single function completion",
        "agents": ["context_curator", "competitive_context_manager", "sampling_agent", "filtering_clustering_agent", "debugger_agent", "reflexion_agent"],
        "topology": "curator -> competitive_context -> sampling (5) -> filtering_clustering -> execution_validator -> debugger_loop -> reflexion -> done",
        "n_agents": 6,
        "estimated_llm_calls": 7,  # 5 samples + 1 debugger + 1 reflexion
        "use_case": "HumanEval, LeetCode, single function"
    },
    "competitive": {
        "description": "Competitive programming - high sampling, clustering",
        "agents": ["context_curator", "competitive_context_manager", "sampling_agent", "filtering_clustering_agent", "debugger_agent", "reflexion_agent"],
        "topology": "AlphaCode: sample 20 -> filter -> cluster -> pick reps -> debug each -> reflexion",
        "n_agents": 6,
        "estimated_llm_calls": 25,
        "use_case": "Codeforces, AtCoder, high diversity needed"
    },
    "ecommerce": {
        "description": "E-commerce microservices backend",
        "agents": ["context_curator", "task_decomposer", "deterministic_validator", "agent_assigner", "graph_execution_orchestrator", "domain_dispatcher", "integration_agent", "quality_reviewer"],
        "topology": "curator -> decomposer -> validator -> assigner -> orchestrator -> dispatcher (Auth/DB/API/UI) -> integration -> quality",
        "n_agents": 8,
        "estimated_llm_calls": 8,
        "use_case": "E-commerce, microservices, DDD"
    },
    "fintech": {
        "description": "Fintech auth with compliance",
        "agents": ["context_curator", "task_decomposer", "deterministic_validator", "agent_assigner", "domain_dispatcher", "quality_reviewer", "human_escalation"],
        "topology": "curator -> decomposer -> validator -> assigner -> auth_squad -> security_validator -> quality -> human_checkpoint",
        "n_agents": 7,
        "estimated_llm_calls": 6,
        "use_case": "Fintech, OAuth, MFA, SOC2"
    },
    "default": {
        "description": "Default Ultimate Graph - full 22 agents",
        "agents": ["context_curator", "task_decomposer", "deterministic_validator", "surgical_refiner", "agent_assigner", "graph_execution_orchestrator", "domain_dispatcher", "progress_monitor", "quality_reviewer", "integration_agent", "decision_conflict_agent", "resource_priority_agent", "human_escalation", "code_executor", "test_runner", "episodic_memory_agent", "semantic_memory_agent", "working_memory_agent"],
        "topology": "Ultimate: all layers, memory system included",
        "n_agents": 18,
        "estimated_llm_calls": 10,
        "use_case": "Generic complex software project"
    }
}


def detect_task_type(requirements: str, project_context: str = "") -> str:
    """
    Deterministic task type detection - ZERO LLM.

    Uses keyword matching and structural heuristics.
    Must be deterministic per Law 11.
    """
    if not requirements:
        return "default"

    text = (requirements + " " + project_context).lower()

    # HumanEval / MBPP detection: has def + test + assert, short, python function
    if "humaneval" in text or "mbpp" in text:
        return "humaneval"
    
    # Competitive programming: leetcode, codeforces, atcoder, or single function with examples
    if any(k in text for k in ["leetcode", "codeforces", "atcoder", "competitive programming"]):
        return "competitive"

    # Heuristic: if requirements contains def + docstring + assert/exampe and length < 2000 chars -> likely humaneval-like
    if "def " in requirements and ('"""' in requirements or "'''" in requirements) and ">>>" in requirements and len(requirements) < 3000:
        return "humaneval"

    # E-commerce
    if any(k in text for k in ["e-commerce", "ecommerce", "microservices", "product catalog", "cart", "stripe", "inventory"]):
        return "ecommerce"

    # Fintech
    if any(k in text for k in ["fintech", "oauth", "oidc", "mfa", "totp", "jwt token rotation", "pci-dss", "soc2"]):
        return "fintech"

    # Default
    return "default"


def build_slice_graph(task_type: str) -> Dict:
    """Build slice graph config for given task type"""
    return SLICE_REGISTRY.get(task_type, SLICE_REGISTRY["default"])


def get_slice_for_requirements(requirements: str, project_context: str = "") -> Dict:
    """Main entrypoint - detect and build slice"""
    task_type = detect_task_type(requirements, project_context)
    slice_config = build_slice_graph(task_type)
    return {
        "task_type": task_type,
        "slice": slice_config,
        "detected_by": "keyword_matching_zero_llm"
    }
