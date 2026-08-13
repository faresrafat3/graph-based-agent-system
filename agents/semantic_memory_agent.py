"""
Semantic Memory Agent - Summarizes episodic memories into rules

Phase 2: Episodic (raw) -> Semantic (rules) -> Working (budgeted)

Role: Periodically scans episodic memory, extracts repeated patterns, generates semantic rules.
Example: 3 episodes failed on empty list -> Rule: "Always check len==0 early"

This is what turns experience into knowledge.

Law 2,4,11 compliant. Evaluate ZERO-LLM.
"""

import sys
import logging
from typing import TypedDict, List, Dict

logger = logging.getLogger(__name__)

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))))

from kernel.karpathy_loop import build_karpathy_loop, standard_refine, standard_should_continue

from memory.custom_memory import memory as global_memory
from llm.llm_integration import call_llm
from agents.deterministic_validator import (
    DeterministicValidatorEngine,
    apply_verify_verdict,
    record_effect,
    verified_closure_enabled,
)


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
    breaches: List[str]
    retry_count: int
    success: bool
    memory_write_error: str


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

    return {"semantic_rule": "", "breaches": [], "success": False}


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
        return {"success": False, "breaches": [f"Rule not actionable: {rule[:100]}"]}
    return {"success": True, "breaches": []}


def commit(state: SemanticState) -> dict:
    rule = state.get("semantic_rule", "")
    supporting = state.get("supporting_episodes", [])
    write_error = ""
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
    except Exception as exc:  # Memory failure shouldn't break commit, but MUST be loud
        logger.warning("Semantic commit to long-term memory failed: %s", exc)
        # P2: the entrypoint converts this into a breach instead of self-reporting done.
        write_error = f"Semantic long-term write failed: {exc}"
    return {"committed": True, "memory_write_error": write_error}


def refine(state: SemanticState) -> dict:
    return standard_refine(state)


def should_continue(state: SemanticState) -> str:
    return standard_should_continue(state, retry_cap=2)


semantic_graph = build_karpathy_loop(
    SemanticState,
    execute_fn=execute,
    propose_fn=propose,
    evaluate_fn=evaluate,
    commit_fn=commit,
    retry_cap=2,
)


def extract_semantic_rule(
    episodic_entries: List[Dict] = None,
    thread_id: str = "semantic_session"
) -> dict:
    """Main entrypoint - extracts rule from episodic entries, closed by VERIFY (P2)."""
    # P2: postcondition declared at propose time, before the knowledge-base write.
    postcondition = {"kind": "non_empty", "path": None}

    if episodic_entries is None:
        # Auto-retrieve recent episodic entries
        try:
            all_long = global_memory.get_from_long_term(limit=20)
            episodic_entries = [e["data"] for e in all_long if e["data"].get("type") == "episodic"]
        except Exception as exc:
            logger.warning("Semantic auto-retrieval failed, using empty: %s", exc)
            episodic_entries = []

    result = semantic_graph.invoke(
        {
            "episodic_entries": episodic_entries,
            "semantic_rule": "",
            "rule_summary": "",
            "supporting_episodes": [],
            "breaches": [],
            "retry_count": 0,
            "success": False,
            "memory_write_error": ""
        },
        config={"configurable": {"thread_id": thread_id}}
    )

    rule = result.get("semantic_rule", "")
    output = {
        "semantic_rule": rule,
        "rule_summary": result.get("rule_summary", ""),
        "supporting_episodes": result.get("supporting_episodes", []),
        "success": result.get("success", False),
        "breaches": result.get("breaches", [])
    }

    # === VERIFY node (P2) === the rule write lands in long-term memory; the effect is
    # recorded as a real file and that file is the postcondition declared at propose time.
    # A swallowed add_to_long_term failure is surfaced as `memory_write_error` (Law 3)
    # rather than staying invisible; it is not part of the postcondition verdict.
    if verified_closure_enabled() and output["success"]:
        write_error = result.get("memory_write_error", "")
        output["memory_write_error"] = write_error
        postcondition["path"] = record_effect("semantic_memory_agent", {
            "rule": rule[:500],
            "supporting_episodes": output["supporting_episodes"],
            "memory_write_error": write_error,
        })
        verify_breaches = DeterministicValidatorEngine.verify_execution_postcondition(postcondition)
        output = apply_verify_verdict(output, postcondition, verify_breaches)

    return output


def get_semantic_rules(limit: int = 10) -> List[str]:
    """Retrieve existing semantic rules"""
    try:
        all_long = global_memory.get_from_long_term(limit=50)
        rules = [e["data"].get("rule", "") for e in all_long if e["data"].get("type") == "semantic" and e["data"].get("rule")]
        return rules[:limit]
    except Exception as exc:
        logger.warning("Semantic rules retrieval failed, returning empty: %s", exc)
        return []
