"""
Competitive Context Manager - Specialized for HumanEval / LeetCode / Competitive Programming

Part of Phase 2: Specialized Context Managers that work WITH new agents (Debugger, Sampling, Reflexion)
Not a replacement for existing Auth/DB/API/UI managers, but an addition for competitive tasks.

Reuses BaseDomainContextManager and follows same pattern as existing managers.
"""

import re
from typing import Dict, Any

from agents.domain_context_managers import BaseDomainContextManager


class CompetitiveContextManager(BaseDomainContextManager):
    """
    Specialized for competitive programming tasks.
    Filters HumanEval prompts to keep only essential parts: signature, docstring, examples, not noisy story.

    Works with SamplingAgent and DebuggerAgent to provide clean, high-signal context.
    """

    def __init__(self):
        super().__init__(domain_name="competitive", max_domain_budget=1500)

    def filter_competitive_context(self, raw_prompt: str, test_failure: str = "", reflection: str = "") -> Dict[str, Any]:
        """
        Filter competitive programming prompt.

        Args:
            raw_prompt: HumanEval prompt with signature + docstring + examples
            test_failure: Optional failure output to keep relevant
            reflection: Optional past reflection

        Returns:
            Dict with filtered_context, signal_to_noise, etc.
        """
        if not raw_prompt:
            return {"filtered_context": "", "signal_to_noise": 1.0, "original_length": 0, "filtered_length": 0}

        original_len = len(raw_prompt)

        # Step 1: Extract function signature and docstring (most important)
        # Find def line
        def_match = re.search(r"^\s*def\s+\w+\s*\(.*?\):", raw_prompt, re.MULTILINE | re.DOTALL)
        signature = def_match.group(0) if def_match else ""

        # Extract docstring (triple quotes)
        docstring_match = re.search(r'""".*?"""', raw_prompt, re.DOTALL)
        docstring = docstring_match.group(0) if docstring_match else ""
        if not docstring:
            docstring_match = re.search(r"'''.*?'''", raw_prompt, re.DOTALL)
            docstring = docstring_match.group(0) if docstring_match else ""

        # If no docstring found, use first 800 chars as fallback
        if not docstring:
            docstring = raw_prompt[:800]

        # Step 2: Extract examples (lines with >>> or Example)
        example_lines = []
        for line in raw_prompt.split("\n"):
            if ">>>" in line or line.strip().startswith("Example") or "e.g." in line.lower():
                example_lines.append(line)
        examples = "\n".join(example_lines[-5:])  # last 5 examples

        # Step 3: Build filtered context: signature + docstring + examples
        filtered = f"{signature}\n{docstring}\n{examples}".strip()

        # Step 4: If test_failure provided, append relevant snippet
        if test_failure:
            # Keep only assert / expected / got lines
            failure_lines = []
            for line in test_failure.split("\n"):
                if any(k in line.lower() for k in ["assert", "expected", "got", "failed", "error"]):
                    failure_lines.append(line)
            if failure_lines:
                filtered += "\n\n# Previous failure:\n" + "\n".join(failure_lines[-3:])

        # Step 5: If reflection provided, append
        if reflection:
            filtered += f"\n\n# Learning from past: {reflection[:200]}"

        # Use base filter for final sanitization (removes tracebacks etc)
        base_filtered = super().filter_context(filtered, domain_specific_data=raw_prompt)
        
        return {
            "filtered_context": base_filtered["filtered_context"],
            "original_length": original_len,
            "filtered_length": len(base_filtered["filtered_context"]),
            "signal_to_noise": round(len(base_filtered["filtered_context"]) / original_len, 4) if original_len > 0 else 1.0,
            "signature": signature,
            "examples": examples
        }

    def filter_context(self, global_context: str, domain_specific_data: str = "") -> Dict[str, Any]:
        """Override base to use competitive filtering"""
        # If domain_specific_data contains HumanEval-like prompt, use competitive filter
        if domain_specific_data and "def " in domain_specific_data and '"""' in domain_specific_data:
            return self.filter_competitive_context(domain_specific_data)
        # Otherwise fallback to base
        return super().filter_context(global_context, domain_specific_data)
