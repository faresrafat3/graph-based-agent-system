"""
Semantic Memory Agent - Summarizes episodic memories into rules

Phase 2: Episodic (raw) -> Semantic (rules) -> Working (budgeted)

Role: Periodically scans episodic memory, extracts repeated patterns, generates semantic rules.
Example: 3 episodes failed on empty list -> Rule: "Always check len==0 early"

This is what turns experience into knowledge.

Law 2,4,11 compliant. Evaluate ZERO-LLM.
"""

import sys
from typing import TypedDict, List, Dict, Any
from collections import Counter

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))))

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from memory.custom_memory import memory as global_memory
from llm.llm_integration import call_llm


SEMANTIC_MEMORY_PERMISSIONS = {
    "READ": ["episodic_entries", "long_term_memory", "tags", "reflections"],
    "WRITE": ["semantic_rule", "rule_summary", "knowledge_base"],
    "NEVER": ["credentials", "raw_code_execution", "deployment"],
    "HUMAN_CHECKPOINT": ["rule_contradiction", "knowledge_base_overflow"]
}

SEMANTIC_SYSTEM_PROMPT = """You are Semantic Memory Agent.

Your ONLY job: Summarize multiple episodic failures into ONE concrete, reusable rule.

Input: Several episodic failures with similar tags
Output: ONE rule, concise, actionable, generalizable.

Rules:
- Think before summarizing - find common root cause
- Be concrete, not vague
- Format: "RULE: If [condition], then [action] because [reason]. Example: ..."
- NEVER output code, ONLY rule text
- 1-2 sentences max
- No credentials

Example Input: 3 episodes all failed on empty list
Example Output: "RULE: If function takes list/array, always check len==0 early and return appropriate default (0, [], False) because empty is valid edge. Example: if not arr: return []"
"""


class SemanticState(TypedDict):
    episodic_entries: List[Dict]
    semantic_rule: str
    rule_summary: str
    supporting_episodes: List[str]
    violations: List[str]
    retry_count: int
    success: bool


class SemanticEngine:
    """Deterministic helpers"""

    @staticmethod
    def find_repeated_patterns(episodes: List[Dict], min_repeats: int = 2) -> Dict[str, List[Dict]]:
        """Group episodes by tags, find repeats (ZERO-LLM)"""
        tag_groups = {}
        for ep in episodes:
            for tag in ep.get("tags", []):
                if tag.startswith("outcome"):
                    continue
                tag_groups.setdefault(tag, []).append(ep)

        # Only keep groups with >= min_repeats
        repeated = {tag: eps for tag, eps in tag_groups.items() if len(eps) >= min_repeats}
        return repeated

    @staticmethod
    def build_summary_prompt(tag: str, episodes: List[Dict]) -> str:
        """Build prompt for rule generation"""
        failures = "\n".join(f"- {ep.get('failure','')[:200]} (reflection: {ep.get('reflection','')[:200]})" for ep in episodes[:5])
        return f"""TAG: {tag}
Failed episodes with this tag ({len(episodes)} times):

{failures}

Summarize into ONE reusable rule.
"""

    @staticmethod
    def is_rule_actionable(rule: str) -> bool:
        """ZERO-LLM quality gate"""
        if not rule or len(rule.strip()) < 20:
            return False
        if len(rule.split()) < 8:
            return False
        # Must start with RULE: and contain If/then or actionable
        if not rule.strip().upper().startswith("RULE:"):
            # Allow without prefix but must have If
            lower = rule.lower()
            if "if" not in lower or ("then" in lower or "should" in lower or "always" in lower) is False:
                return False
        # Must not be code
        if "def " in rule and "return" in rule and len(rule) > 100:
            # Might be code, reject if looks like function
            if rule.count("def ") >= 1 and rule.count("\n") >= 2:
                return False
        return True


def propose(state: SemanticState) -> dict:
    episodes = state.get("episodic_entries", [])
    if len(episodes) < 2:
        raise ValueError("Need at least 2 episodic entries to extract semantic rule")

    return {"semantic_rule": "", "violations": [], "success": False}


def execute(state: SemanticState) -> dict:
    episodes = state.get("episodic_entries", [])

    # Find most repeated tag
    repeated = SemanticEngine.find_repeated_patterns(episodes, min_repeats=2)
    if not repeated:
        # No repeats, take most common outcome type
        return {
            "semantic_rule": "RULE: No repeated pattern found yet, need more episodes to generalize.",
            "rule_summary": "Insufficient data",
            "supporting_episodes": []
        }

    # Pick tag with most episodes
    top_tag = max(repeated.keys(), key=lambda k: len(repeated[k]))
    supporting = repeated[top_tag]

    prompt = SemanticEngine.build_summary_prompt(top_tag, supporting)
    raw = call_llm(prompt, SEMANTIC_SYSTEM_PROMPT, temperature=0.2)

    # Clean
    rule = raw.strip()
    # Ensure starts with RULE:
    if not rule.upper().startswith("RULE:"):
        rule = f"RULE: {rule}"

    summary = rule[:200]  # first 200 chars as summary

    return {
        "semantic_rule": rule,
        "rule_summary": summary,
        "supporting_episodes": [ep.get("episode_id", "") for ep in supporting[:5]]
    }


def evaluate(state: SemanticState) -> dict:
    rule = state.get("semantic_rule", "")
    if not SemanticEngine.is_rule_actionable(rule):
        return {"success": False, "violations": [f"Rule not actionable: {rule[:100]}"]}
    return {"success": True, "violations": []}


def commit(state: SemanticState) -> dict:
    rule = state.get("semantic_rule", "")
    supporting = state.get("supporting_episodes", [])
    try:
        global_memory.add_to_long_term(
            data={
                "type": "semantic",
                "rule": rule,
                "supporting_episodes": supporting,
                "tags": ["semantic_rule"]
            },
            metadata={"agent": "semantic_memory_agent", "rule_count": 1}
        )
    except Exception:
        pass
    return {"committed": True}


def refine(state: SemanticState) -> dict:
    return {"retry_count": state.get("retry_count", 0) + 1, "success": False}


def should_continue(state: SemanticState) -> str:
    if state.get("success"):
        return "commit"
    elif state.get("retry_count", 0) >= 2:
        return "escalate"
    else:
        return "refine"


workflow = StateGraph(SemanticState)
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
semantic_graph = workflow.compile(checkpointer=checkpointer)


def extract_semantic_rule(
    episodic_entries: List[Dict] = None,
    thread_id: str = "semantic_session"
) -> dict:
    """Main entrypoint - extracts rule from episodic entries"""
    if episodic_entries is None:
        # Auto-retrieve recent episodic entries
        try:
            all_long = global_memory.get_from_long_term(limit=20)
            episodic_entries = [e["data"] for e in all_long if e["data"].get("type") == "episodic"]
        except Exception:
            episodic_entries = []

    result = semantic_graph.invoke(
        {
            "episodic_entries": episodic_entries,
            "semantic_rule": "",
            "rule_summary": "",
            "supporting_episodes": [],
            "violations": [],
            "retry_count": 0,
            "success": False
        },
        config={"configurable": {"thread_id": thread_id}}
    )

    return {
        "semantic_rule": result.get("semantic_rule", ""),
        "rule_summary": result.get("rule_summary", ""),
        "supporting_episodes": result.get("supporting_episodes", []),
        "success": result.get("success", False),
        "violations": result.get("violations", [])
    }


def get_semantic_rules(limit: int = 10) -> List[str]:
    """Retrieve existing semantic rules"""
    try:
        all_long = global_memory.get_from_long_term(limit=50)
        rules = [e["data"].get("rule", "") for e in all_long if e["data"].get("type") == "semantic" and e["data"].get("rule")]
        return rules[:limit]
    except Exception:
        return []
