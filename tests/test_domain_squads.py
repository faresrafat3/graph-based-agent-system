import pytest

import agents.domain_squads as domain_squads_module
from agents.domain_squads import (
    AuthSquadAgent,
    DatabaseSquadAgent,
    APISquadAgent,
    UISquadAgent,
    SQUAD_PERMISSIONS,
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
        "type": "ui",
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
        "type": "ui",
    }
    
    with pytest.raises(PermissionError) as exc_info:
        agent.execute_db_task(task)
        
    assert "Law 20 Violation" in str(exc_info.value)


def test_auth_squad_valid_execution(monkeypatch):
    """Valid auth task executes and returns squad metadata."""
    monkeypatch.setattr(
        domain_squads_module,
        "call_llm",
        lambda prompt, system_prompt="", **kwargs: '{"filename": "auth.py", "code": "def login(): pass"}',
    )

    agent = AuthSquadAgent()
    task = {
        "id": "task_1",
        "title": "Implement JWT login authentication",
        "description": "Create login endpoint with password hashing",
        "type": "auth",
    }
    res = agent.execute_auth_task(task, global_context="Web app auth")
    
    assert res["success"] is True
    assert res["squad"] == "auth"
    assert res["task_id"] == "task_1"
    assert res["response"] is not None


def test_api_squad_out_of_scope_raises():
    agent = APISquadAgent()
    task = {
        "id": "task_api_bad",
        "title": "Create database migration",
        "description": "Write alembic database migration for users",
        "type": "database",
    }

    with pytest.raises(PermissionError) as exc_info:
        agent.execute_api_task(task)

    assert "Law 20 Violation" in str(exc_info.value)


def test_ui_squad_out_of_scope_raises():
    agent = UISquadAgent()
    task = {
        "id": "task_ui_bad",
        "title": "Implement JWT token rotation",
        "description": "Security token refresh logic",
        "type": "auth",
    }

    with pytest.raises(PermissionError) as exc_info:
        agent.execute_ui_task(task)

    assert "Law 20 Violation" in str(exc_info.value)


def test_auth_squad_totally_out_of_scope_no_allowed():
    """Verify out-of-scope task without forbidden keywords raises PermissionError"""
    agent = AuthSquadAgent()
    task = {
        "id": "task_out",
        "title": "Clean codebase comments",
        "description": "Just clean up code comments and spacing",
        "type": "refactor",
    }
    with pytest.raises(PermissionError, match="received out-of-scope task"):
        agent.execute_auth_task(task)


def test_db_squad_valid_execution(monkeypatch):
    """Verify DatabaseSquadAgent valid execution path"""
    monkeypatch.setattr(
        domain_squads_module,
        "call_llm",
        lambda prompt, system_prompt="", **kwargs: '{"filename": "models.py", "code": "class User(Base): pass"}',
    )
    agent = DatabaseSquadAgent()
    task = {
        "id": "task_db_ok",
        "title": "Create users database table schema",
        "description": "SQL postgres tables",
        "type": "database",
    }
    res = agent.execute_db_task(task, global_context="DB Context")
    assert res["success"] is True
    assert res["squad"] == "database"
    assert "models.py" in res["response"]


def test_ui_squad_valid_execution(monkeypatch):
    """Verify UISquadAgent valid execution path"""
    monkeypatch.setattr(
        domain_squads_module,
        "call_llm",
        lambda prompt, system_prompt="", **kwargs: '{"filename": "button.jsx", "code": "export default Button"}',
    )
    agent = UISquadAgent()
    task = {
        "id": "task_ui_ok",
        "title": "Build react component UI layout",
        "description": "CSS button styles",
        "type": "ui",
    }
    res = agent.execute_ui_task(task, global_context="UI Context")
    assert res["success"] is True
    assert res["squad"] == "ui"
    assert "button.jsx" in res["response"]

