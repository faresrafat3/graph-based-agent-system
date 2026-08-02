# Filtering & Clustering Agent - AlphaCode Stage 2 & 3

**Category:** generation | **Phase:** 2 | **Inspired:** AlphaCode Filtering + Clustering

## Role
Second half of AlphaCode after SamplingAgent. Filters candidates by AST + execution, clusters by behavior, picks representatives.

## Permissions
READ [candidates, test_suite, problem_spec]
WRITE [filtered_candidates, clusters, representatives, filtering_report]

## Stages
1. Filter by AST: validate_python_syntax
2. Cluster: by hash (lite) or by execution_output if available (behavioral clustering)
3. Pick representatives: shortest code per cluster wins (simplest)

## Report
total_input, after_ast_filter, num_clusters, representatives, filter_rate, cluster_reduction

## Example
Input 20 candidates, after AST 15, 10 clusters, 10 reps -> filter_rate 0.25, cluster_reduction 0.33

## Relation
SamplingAgent -> FilteringClusteringAgent -> Debugger (if needed)
In Competitive Slice: Sampling generates 5, Filtering clusters to 3 reps, ExecutionValidator filters to 1 PASS.

## Governance
All evaluation ZERO-LLM, deterministic.
