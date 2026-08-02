# Competitive Context Manager

**Category:** context_management | **Phase:** 2

## Role
Specialized for HumanEval/LeetCode. Filters HumanEval prompt to essential parts: signature + docstring + examples. Removes noisy story.

Works WITH new agents (Debugger, Sampling, Reflexion), not replacing existing Auth/DB/API/UI managers.

## Methods
- filter_competitive_context(raw_prompt, test_failure, reflection): extracts def signature, docstring (triple quotes), example lines (>>>), appends failure snippet and reflection
- filter_context(): override base, detects if domain_specific_data contains def + docstring -> competitive filter, else fallback to base

## Signal-to-Noise
Calculates filtered/original ratio.

## Example
Input: 500 chars HumanEval prompt with story
Output: 200 chars signature+docstring+examples, signal 0.4 (but higher quality)

## Governance
Uses BaseDomainContextManager, no LLM in filtering.
