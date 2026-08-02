# Sampling Agent - AlphaCode-Inspired Diverse Generation

**Category:** generation | **Layer:** 2 Execution | **Inspired by:** AlphaCode Sampling + Filtering

## Role

Generates N diverse code candidates with high temperature instead of 1 perfect attempt. Turns single-point failure into population search.

AlphaCode insight: Brute force diversity + execution filtering beats single clever generation.

- Original AlphaCode: 1M samples, massive filtering/clustering on TPU pods
- Our Lite: 5-20 samples, AST validation as filter, SHA256 dedup as clustering (lite)

## Permission Matrix

```python
READ: [problem_spec, project_context, past_reflections, constraints]
WRITE: [candidates, valid_candidates, sampling_report]
NEVER: [credentials, deployment, production_config]
HUMAN_CHECKPOINT: [excessive_sampling_cost >20, prompt_injection_detected]
```

## Karpathy Loop

- Propose: Check problem_spec non-empty, check NEVER (delete production injection)
- Execute: For i in n_samples: build prompt with diversity hint + past reflection, call_llm(temp), strip fences, collect candidate
- Evaluate: Deduplicate by SHA256 hash, filter by AST validation, compute report
- Commit: Success if at least 1 valid candidate

## Diversity Strategy

Prompts cycled:
- "Try iterative approach"
- "Try recursive approach"
- "Try different data structures"
- "Try optimizing edge cases first"
- etc.

Plus past reflections from Reflexion Agent are injected after trial 0 with cooled temperature.

## Outputs

- candidates: All generated (including failed)
- valid_candidates: After dedup + AST filter
- sampling_report: {total_generated, after_dedup, valid_after_ast, diversity_ratio, valid_rate}

## Example Report

```
total_generated: 5, after_dedup: 4 (diversity 0.8), valid_after_ast: 3 (60% valid)
```

## Governance

- Cost control: n_samples >20 requires human checkpoint
- Law 3: Per-candidate failure doesn't kill batch, logs and continues
- Law 12: Sanitization via deduplication

## Relation to Graphs

- Ultimate Graph: Could be used in Code Executor for hard tasks where diversity matters
- Competitive Slice: Stage 2 - Generates population that ExecutionValidator filters. If all fail, triggers Reflexion.

## AlphaCode vs Ours

| AlphaCode | Ours |
|---|---|
| 1M samples, 8 TPU | 5-20 samples, 1 GPU/CPU |
| Full test suite filtering | AST filtering + physical execution in slice |
| Clustering by output behavior on generated inputs | SHA256 dedup (lite) |
| Massive compute | Affordable, fits in Stepfun quota |

## Tests

`tests/test_sampling_agent.py`
