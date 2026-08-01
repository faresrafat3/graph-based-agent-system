import pytest
from agents.domain_squads import (
    AuthSquadAgent,
    DatabaseSquadAgent,
    APISquadAgent,
    UISquadAgent,
    SQUAD_PERMISSIONS
)


def test_squad_permissions_matrix():
    """Verify Law 20 permission boundaries matrix"""
    assert "jwt" in SQUAD_PERMISSIONS["auth_squad"]["ALLOWED_TYPES"]
    assert "css" in SQUAD_PERMISSIONS["auth_squad"]["FORBIDDEN_KEYWORDS"]
    assert "schema" in SQUAD_PERMISSIONS["db_squad"]["ALLOWED_TYPES"]
    assert "react component" in SQUAD_PERMISSIONS["db_squad"]["FORBIDDEN_KEYWORDS"]


def test_auth_squad_out_of_scope_raises():
    """Verify Law 20 violation raises PermissionError if Auth Squad receives out-of-scope UI task"""
    agent = AuthSquadAgent()
    task = {
        "id": "task_99",
        "title": "Design CSS layout and jsx component",
        "description": "Add CSS styling to page",
        "type": "ui"
    }
    
    with pytest.raises(PermissionError) as exc_info:
        agent.execute_auth_task(task)
        
    assert "Law 20 Violation" in str(exc_info.value)


def test_db_squad_out_of_scope_raises():
    """Verify Law 20 violation raises PermissionError if DB Squad receives out-of-scope React task"""
    agent = DatabaseSquadAgent()
    task = {
        "id": "task_100",
        "title": "Create react component for header",
        "description": "Build header react component",
        "type": "ui"
    }
    
    with pytest.raises(PermissionError) as exc_info:
        agent.execute_db_task(task)
        
    assert "Law 20 Violation" in str(exc_info.value)


def test_auth_squad_valid_execution():
    """Valid auth task executes and returns squad metadata"""
    agent = AuthSquadAgent()
    task = {
        "id": "task_1",
        "title": "Implement JWT login authentication",
        "description": "Create login endpoint with password hashing",
        "type": "auth"
    }
    res = agent.execute_auth_task(task, global_context="Web app auth")
    
    assert res["success"] is True
    assert res["squad"] == "auth"
    assert res["task_id"] == "task_1"
    assert res["response"] is not None
