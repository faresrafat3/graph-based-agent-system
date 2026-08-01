"""
Context Curator Agent - Meta-Agent for Context Hygiene, Sanitation, and RAM Management
Implements Karpathy's 2nd Engineering Pillar: Context Engineering & Window Sanitation.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, List, Dict, Any
import re

# Permission Boundaries (Law 2 & Constitution Article I, Section 2)
CONTEXT_CURATOR_PERMISSIONS = {
    "READ": ["raw_state", "history_logs", "memory_entries", "raw_requirements"],
    "WRITE": ["sanitized_context", "context_summary", "signal_to_noise_ratio"],
    "NEVER": ["source_code_edit", "execute_deployment", "credentials_access"],
    "HUMAN_CHECKPOINT": ["context_window_overflow", "unrecoverable_context_rot"]
}


# State Definition
class ContextCuratorState(TypedDict):
    # Inputs
    raw_prompt: str
    history_logs: List[dict]
    max_token_budget: int
    
    # Outputs
    sanitized_prompt: str
    compacted_summary: str
    signal_to_noise_ratio: float
    
    # Control
    retry_count: int
    success: bool


class ContextCuratorEngine:
    """Core deterministic sanitization and context hygiene methods"""
    
    @staticmethod
    def sanitize_raw_text(text: str) -> str:
        """Strips noisy stack traces, repetitive logs, and excess whitespace"""
        if not text:
            return ""
        
        # Remove noisy tracebacks
        clean_text = re.sub(r'Traceback \(most recent call last\):.*?(?=\n\n|\Z)', '[Traceback Omitted for Noise Control]', text, flags=re.DOTALL)
        # Collapse multiple newlines
        clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)
        return clean_text.strip()

    @staticmethod
    def compact_history_logs(logs: List[dict], max_items: int = 3) -> str:
        """Compacts historical execution logs to maintain high signal-to-noise ratio"""
        if not logs:
            return "No historical logs."
        
        recent_logs = logs[-max_items:]
        summaries = []
        for i, log in enumerate(recent_logs, 1):
            action = log.get("action", "Unknown Action")
            status = log.get("status", "Unknown Status")
            summaries.append(f"{i}. Action: {action} | Status: {status}")
        
        return "\n".join(summaries)

    @staticmethod
    def calculate_signal_to_noise(raw_text: str, sanitized_text: str) -> float:
        """Calculates signal retention ratio after sanitation"""
        raw_len = len(raw_text)
        if raw_len == 0:
            return 1.0
        return round(len(sanitized_text) / raw_len, 4)


# Karpathy Loop Implementation

def propose(state: ContextCuratorState) -> dict:
    """Step 1: Propose - Inspect raw input and check permission invariants"""
    raw_prompt = state.get("raw_prompt", "")
    
    # Permission Check
    if "override credentials" in raw_prompt.lower():
        raise PermissionError("Context Curator Agent attempted action in NEVER permissions.")
    
    return {
        "sanitized_prompt": "",
        "compacted_summary": "",
        "signal_to_noise_ratio": 0.0
    }


def execute(state: ContextCuratorState) -> dict:
    """Step 2: Execute - Perform deterministic context sanitation and compaction"""
    raw_prompt = state.get("raw_prompt", "")
    history_logs = state.get("history_logs", [])
    
    sanitized = ContextCuratorEngine.sanitize_raw_text(raw_prompt)
    summary = ContextCuratorEngine.compact_history_logs(history_logs)
    stn_ratio = ContextCuratorEngine.calculate_signal_to_noise(raw_prompt, sanitized)
    
    return {
        "sanitized_prompt": sanitized,
        "compacted_summary": summary,
        "signal_to_noise_ratio": stn_ratio
    }


def evaluate(state: ContextCuratorState) -> dict:
    """Step 3: Evaluate - Validate that sanitized context is within token budget"""
    sanitized = state.get("sanitized_prompt", "")
    max_budget = state.get("max_token_budget", 4000)
    
    # Estimate token count (approx 4 chars per token)
    estimated_tokens = len(sanitized) // 4
    success = estimated_tokens <= max_budget and len(sanitized) > 0
    
    return {"success": success}


def commit(state: ContextCuratorState) -> dict:
    """Step 4: Commit - Confirm sanitized context is ready for next agent invocation"""
    return {"committed": True}


def refine(state: ContextCuratorState) -> dict:
    """Step 5: Refine - Truncate context if budget exceeded"""
    retry_count = state.get("retry_count", 0) + 1
    raw_prompt = state.get("raw_prompt", "")
    # Truncate prompt further
    truncated = raw_prompt[:len(raw_prompt) // 2]
    
    return {
        "raw_prompt": truncated,
        "retry_count": retry_count,
        "success": False
    }


def should_continue(state: ContextCuratorState) -> str:
    """Determine next step in Karpathy Loop"""
    if state.get("success", False):
        return "commit"
    elif state.get("retry_count", 0) >= 3:
        return "escalate"
    else:
        return "refine"


# Build LangGraph Workflow for Context Curator Agent
workflow = StateGraph(ContextCuratorState)

workflow.add_node("propose", propose)
workflow.add_node("execute", execute)
workflow.add_node("evaluate", evaluate)
workflow.add_node("commit", commit)
workflow.add_node("refine", refine)

workflow.set_entry_point("propose")
workflow.add_edge("propose", "execute")
workflow.add_edge("execute", "evaluate")

workflow.add_conditional_edges(
    "evaluate",
    should_continue,
    {
        "commit": "commit",
        "refine": "refine",
        "escalate": END
    }
)

workflow.add_edge("refine", "propose")
workflow.add_edge("commit", END)

checkpointer = MemorySaver()
context_curator_graph = workflow.compile(checkpointer=checkpointer)


def curate_context(
    raw_prompt: str,
    history_logs: List[dict] = None,
    max_token_budget: int = 4000,
    thread_id: str = "curator_session"
) -> dict:
    """
    Curates and sanitizes context payload for downstream agent execution.
    
    Args:
        raw_prompt: Input prompt / payload
        history_logs: Historical log dictionaries
        max_token_budget: Maximum allowable token budget
        thread_id: Session thread ID for LangGraph checkpointer
    
    Returns:
        Dict containing sanitized_prompt, compacted_summary, signal_to_noise_ratio, success
    """
    result = context_curator_graph.invoke(
        {
            "raw_prompt": raw_prompt,
            "history_logs": history_logs or [],
            "max_token_budget": max_token_budget,
            "sanitized_prompt": "",
            "compacted_summary": "",
            "signal_to_noise_ratio": 0.0,
            "retry_count": 0,
            "success": False
        },
        config={"configurable": {"thread_id": thread_id}}
    )
    
    return {
        "sanitized_prompt": result.get("sanitized_prompt", ""),
        "compacted_summary": result.get("compacted_summary", ""),
        "signal_to_noise_ratio": result.get("signal_to_noise_ratio", 1.0),
        "success": result.get("success", False)
    }
