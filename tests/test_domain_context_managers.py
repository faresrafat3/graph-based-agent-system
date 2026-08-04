import pytest
from agents.domain_context_managers import (
    BaseDomainContextManager,
    AuthContextManager,
    DBContextManager,
    APIContextManager,
    UIContextManager
)


def test_base_domain_context_manager():
    """Verify base domain context manager sanitizes and computes SNR"""
    mgr = BaseDomainContextManager(domain_name="test_domain", max_domain_budget=100)
    raw = "Build test feature. Traceback (most recent call last):\n RuntimeError: crash"
    res = mgr.filter_context(raw, domain_specific_data="test schema")
    
    assert res["success"] is True
    assert res["domain"] == "test_domain"
    assert "RuntimeError: crash" not in res["filtered_context"]
    assert "test schema" in res["filtered_context"]


def test_auth_context_manager_filters_ui_noise():
    """Verify AuthContextManager strips HTML/CSS noise"""
    mgr = AuthContextManager()
    raw = "Implement JWT authentication. <style>.btn { color: red; }</style> className='flex row'"
    res = mgr.filter_auth_context(raw)
    
    assert res["success"] is True
    assert "style" not in res["filtered_context"].lower()
    assert "className" not in res["filtered_context"]
    assert "JWT authentication" in res["filtered_context"]


def test_db_context_manager():
    """Verify DBContextManager retains database model concepts"""
    mgr = DBContextManager()
    raw = "Design PostgreSQL database for users table"
    res = mgr.filter_db_context(raw)
    
    assert res["success"] is True
    assert "database" in res["filtered_context"].lower()


def test_base_domain_context_manager_truncation():
    """Verify context truncation works when budget is exceeded"""
    mgr = BaseDomainContextManager(domain_name="test_domain", max_domain_budget=5)
    raw = "Short prompt"
    res = mgr.filter_context(raw, domain_specific_data="This is a very long schema that will definitely exceed the 20 character budget limit.")
    assert "Truncated" in res["filtered_context"]

