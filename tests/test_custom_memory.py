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


def test_long_term_memory_similarity_and_clear():
    mem = CustomMemory()
    mem.add_to_long_term(
        data={"requirements": "Build user auth system", "tasks": ["task_1"]},
        metadata={"source": "pytest"}
    )
    
    # Test similar search
    similar = mem.find_similar("user auth system", threshold=0.1)
    assert len(similar) == 1
    assert similar[0]["similarity"] > 0.0
    
    # Test zero total keywords for Jaccard
    empty_similar = mem.find_similar("   ", threshold=0.0)
    assert len(empty_similar) == 1
    
    # Test search with limit
    mem.add_to_long_term(data={"requirements": "Build user profile"}, metadata={})
    results = mem.search("user", limit=1)
    assert len(results) == 1
    
    # Test stats
    stats = mem.get_stats()
    assert stats["short_term_size"] == 0
    assert stats["long_term_size"] == 2
    
    # Test clear
    mem.clear_long_term()
    assert len(mem.get_from_long_term()) == 0


def test_internal_memory_test_function():
    from memory.custom_memory import test_memory
    # This executes the inner test_memory function to ensure it always runs and stays verified.
    test_memory()

