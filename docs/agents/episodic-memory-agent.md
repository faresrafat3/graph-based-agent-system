# Episodic Memory Agent

**Category:** memory | **Phase:** 2 Memory System

## Role
Stores full execution episodes (problem + code + failure + reflection + outcome) for future retrieval. Part of Episodic -> Semantic -> Working chain.

## Permissions
READ [execution_history, problem_spec, code, failure, reflection]
WRITE [episodic_entry, memory_index, episode_summary]
NEVER [credentials, deployment]

## Loop
Propose: check problem_spec, privacy check for credentials
Execute: build episode with tags (edge_empty, infra_timeout, etc)
Evaluate: check ID, type, token budget <2000
Commit: add_to_long_term

Tags extracted deterministically: empty, null, boundary, timeout, 429, assert, index, sort, search, outcome_*

## Memory to Context
Feeds into Semantic and Working Memory agents.
