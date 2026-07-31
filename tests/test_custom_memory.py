import pytest
from memory.custom_memory import CustomMemory


def test_short_term_memory():
    mem = CustomMemory()
    mem.add_to_short_term("session_key", "session_value")
    assert mem.get_from_short_term("session_key") == "session_value"
    mem.clear_short_term()
    assert mem.get_from_short_term("session_key") is None


def test_long_term_memory_search():
    mem = CustomMemory()
    mem.add_to_long_term(
        data={"requirements": "Build user auth system", "tasks": ["task_1"]},
        metadata={"source": "pytest"}
    )
    entries = mem.get_from_long_term()
    assert len(entries) == 1
    
    results = mem.search("user auth")
    assert len(results) == 1
