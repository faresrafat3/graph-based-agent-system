# Working Memory Agent - Memory to Context Bridge

**Category:** memory | **Phase:** 2

## Role
Takes long-term memory (episodic + semantic + reflexion), ranks by relevance (Jaccard + recency + outcome + semantic boost), assembles within token budget (4000) and sends to context managers.

This is the Memory to Context system.

## Permissions
READ [long_term_memory, problem_spec, current_context, token_budget]
WRITE [working_memory, assembled_context, budget_report]

## Deterministic Logic (ZERO-LLM)
- Ranking: Jaccard similarity + 0.1 recency + 0.2 fail boost + 0.3 semantic boost
- Assembly: iterate ranked entries, estimate tokens (chars/4), include while budget_remaining >0
- Report: budget_total, used, remaining, included, skipped

## Loop
Propose: check problem_spec, budget >=500
Execute: auto-retrieve from global memory if not provided, rank, assemble
Evaluate: check budget not exceeded
Commit: success always (empty memory is valid)

## Example
Long-term 20 entries, Working includes 3 most relevant within 4000 tokens.
