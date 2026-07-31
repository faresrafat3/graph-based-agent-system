import pytest
from llm.llm_integration import call_llm


def test_call_llm_mock_fallback():
    response = call_llm("Build login page", allow_mock=True)
    assert response is not None
    assert "tasks" in response
