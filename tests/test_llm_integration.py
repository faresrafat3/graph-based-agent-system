import pytest
from llm.llm_integration import call_llm
from agents.task_decomposer import SYSTEM_PROMPT


def test_call_llm_execution():
    """Verify call_llm returns a valid non-empty string from LLM or mock"""
    response = call_llm("Build login page with email auth", system_prompt=SYSTEM_PROMPT, allow_mock=True)
    assert response is not None
    assert len(response) > 0
