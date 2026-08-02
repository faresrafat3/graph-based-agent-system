# Semantic Memory Agent

**Category:** memory | **Phase:** 2

## Role
Summarizes episodic memories into reusable rules. Finds repeated tags, generates RULE.

Example: 3 episodes with edge_empty tag -> RULE: always check len==0.

## Permissions
READ [episodic_entries, long_term_memory]
WRITE [semantic_rule, knowledge_base]
NEVER [credentials, raw_code_execution]

## Loop
Propose: need >=2 episodes
Execute: find repeated patterns by tags, pick top tag, call LLM to generate rule with SEMANTIC_SYSTEM_PROMPT
Evaluate: ZERO-LLM actionable check (must start with RULE:, contain If/then, not code)
Commit: store as type=semantic in long_term

## Relation
Episodic -> Semantic -> Working. Semantic rules are boosted in Working Memory ranking.
