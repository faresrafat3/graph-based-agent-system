import sys
sys.path.append('.')

from agents.competitive_context_manager import CompetitiveContextManager

def test_filter_competitive_basic():
    mgr = CompetitiveContextManager()
    prompt = '''def has_close_elements(numbers, threshold):
    """Check if in given list of numbers, are any two numbers closer than given threshold.
    >>> has_close_elements([1.0, 2.0, 3.0], 0.5)
    False
    """
    return False
'''
    res = mgr.filter_competitive_context(prompt)
    assert "has_close_elements" in res["filtered_context"] or "def" in res["filtered_context"]
    assert res["signal_to_noise"] > 0

def test_filter_with_failure():
    mgr = CompetitiveContextManager()
    prompt = "def add(a,b):\n    \"\"\"Add two numbers\"\"\"\n    return a+b"
    failure = "assert add(2,2)==4 failed, expected 4 got 2"
    res = mgr.filter_competitive_context(prompt, test_failure=failure)
    assert "assert" in res["filtered_context"].lower() or "failed" in res["filtered_context"].lower()

def test_filter_with_reflection():
    mgr = CompetitiveContextManager()
    prompt = "def sort(arr): ..."
    reflection = "Need to handle empty list"
    res = mgr.filter_competitive_context(prompt, reflection=reflection)
    assert "empty" in res["filtered_context"].lower() or "Learning" in res["filtered_context"]

def test_base_filter_fallback():
    mgr = CompetitiveContextManager()
    res = mgr.filter_context(global_context="some global", domain_specific_data="not humaneval, just generic")
    # Should fallback to base
    assert "filtered_context" in res


def test_filter_competitive_empty():
    mgr = CompetitiveContextManager()
    res = mgr.filter_competitive_context("")
    assert res["filtered_context"] == ""
    assert res["signal_to_noise"] == 1.0


def test_filter_context_override_branch():
    mgr = CompetitiveContextManager()
    res = mgr.filter_context(
        global_context="global",
        domain_specific_data='def my_func():\n    """docstring"""\n    pass'
    )
    assert "my_func" in res["filtered_context"]

