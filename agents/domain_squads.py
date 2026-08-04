"""
Domain Squad Agents - Hyper-Specialized Subsystem Squads (Law 20).
Implements rigid, non-overlapping domain methodologies for Auth, DB, API, and UI subsystems.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.llm_integration import call_llm
from agents.domain_context_managers import AuthContextManager, DBContextManager, APIContextManager, UIContextManager


# Squad Permission Matrix (Law 20)
SQUAD_PERMISSIONS = {
    "auth_squad": {
        "ALLOWED_TYPES": ["auth", "authentication", "security", "jwt", "login", "oauth", "password"],
        "FORBIDDEN_KEYWORDS": ["css", "jsx", "react component", "database migration", "raw sql index", "alembic"]
    },
    "db_squad": {
        "ALLOWED_TYPES": ["database", "schema", "migration", "model", "sql", "table", "index", "postgres"],
        "FORBIDDEN_KEYWORDS": ["react component", "jsx", "css", "jwt token", "http router", "route handler"]
    },
    "api_squad": {
        "ALLOWED_TYPES": ["api", "route", "endpoint", "controller", "rest", "http", "pydantic"],
        "FORBIDDEN_KEYWORDS": ["database migration", "alembic", "css styling", "react component", "bcrypt hashing"]
    },
    "ui_squad": {
        "ALLOWED_TYPES": ["ui", "frontend", "component", "layout", "view", "react", "css", "html"],
        "FORBIDDEN_KEYWORDS": ["alembic migration", "raw sql", "bcrypt hashing", "jwt token", "database index"]
    }
}


def _task_text(task: dict) -> str:
    """Return normalized task text used for deterministic boundary checks."""
    return " ".join(
        str(task.get(key, "")) for key in ("id", "title", "description", "type")
    ).lower()


def _enforce_squad_boundary(squad_key: str, task: dict, agent_name: str) -> None:
    """
    Enforce Law 20 before prompt assembly or LLM execution.

    The check scans title, description, and type to prevent hidden cross-domain
    instructions from bypassing a title-only guard.
    """
    permissions = SQUAD_PERMISSIONS[squad_key]
    combined = _task_text(task)

    for keyword in permissions["FORBIDDEN_KEYWORDS"]:
        if keyword in combined:
            raise PermissionError(
                f"Law 20 Breach: {agent_name} received forbidden cross-domain keyword "
                f"'{keyword}' in task: '{task.get('title')}'"
            )

    if not any(keyword in combined for keyword in permissions["ALLOWED_TYPES"]):
        raise PermissionError(
            f"Law 20 Breach: {agent_name} received out-of-scope task: "
            f"'{task.get('title')}'"
        )


class AuthSquadAgent:
    """Hyper-specialized agent for authentication, JWT, and security logic."""

    def __init__(self):
        self.context_mgr = AuthContextManager()

    def execute_auth_task(self, task: dict, global_context: str = "") -> dict:
        """Executes authentication task enforcing security best practices."""
        _enforce_squad_boundary("auth_squad", task, "AuthSquadAgent")

        filtered = self.context_mgr.filter_auth_context(global_context, schemas=task.get("description", ""))

        system_prompt = """You are an Auth Squad Agent. Your ONLY job is to write secure authentication code (JWT, OAuth, bcrypt hashing).
Outputs MUST include:
1. Zero hardcoded secrets/passwords
2. Type-hinted functions
3. Rate-limiting annotations
Output ONLY valid JSON: {"filename": "auth.py", "code": "...", "test_filename": "test_auth.py", "test_code": "..."}"""

        prompt = f"Task: {task.get('title')}\nDescription: {task.get('description')}\nContext: {filtered['filtered_context']}"

        raw_response = call_llm(prompt, system_prompt)
        return {
            "squad": "auth",
            "task_id": task.get("id"),
            "response": raw_response,
            "success": True
        }


class DatabaseSquadAgent:
    """Hyper-specialized agent for database modeling, 3NF schemas, and migrations."""

    def __init__(self):
        self.context_mgr = DBContextManager()

    def execute_db_task(self, task: dict, global_context: str = "") -> dict:
        """Executes database schema or migration task."""
        _enforce_squad_boundary("db_squad", task, "DatabaseSquadAgent")

        filtered = self.context_mgr.filter_db_context(global_context, db_specs=task.get("description", ""))

        system_prompt = """You are a Database Squad Agent. Your ONLY job is to write SQLAlchemy models or Alembic migrations.
Outputs MUST follow 3NF normalization and explicit indexing strategies.
Output ONLY valid JSON: {"filename": "models.py", "code": "...", "test_filename": "test_models.py", "test_code": "..."}"""

        prompt = f"Task: {task.get('title')}\nDescription: {task.get('description')}\nContext: {filtered['filtered_context']}"

        raw_response = call_llm(prompt, system_prompt)
        return {
            "squad": "database",
            "task_id": task.get("id"),
            "response": raw_response,
            "success": True
        }


class APISquadAgent:
    """Hyper-specialized agent for REST API route implementation and Pydantic validation."""

    def __init__(self):
        self.context_mgr = APIContextManager()

    def execute_api_task(self, task: dict, global_context: str = "") -> dict:
        """Executes REST API endpoint task."""
        _enforce_squad_boundary("api_squad", task, "APISquadAgent")

        filtered = self.context_mgr.filter_context(global_context, domain_specific_data=task.get("description", ""))

        system_prompt = """You are an API Squad Agent. Your ONLY job is to write REST API routes with Pydantic payload validation.
Output ONLY valid JSON: {"filename": "routes.py", "code": "...", "test_filename": "test_routes.py", "test_code": "..."}"""

        prompt = f"Task: {task.get('title')}\nDescription: {task.get('description')}\nContext: {filtered['filtered_context']}"

        raw_response = call_llm(prompt, system_prompt)
        return {
            "squad": "api",
            "task_id": task.get("id"),
            "response": raw_response,
            "success": True
        }


class UISquadAgent:
    """Hyper-specialized agent for UI layout and component implementation."""

    def __init__(self):
        self.context_mgr = UIContextManager()

    def execute_ui_task(self, task: dict, global_context: str = "") -> dict:
        """Executes frontend UI component task."""
        _enforce_squad_boundary("ui_squad", task, "UISquadAgent")

        filtered = self.context_mgr.filter_context(global_context, domain_specific_data=task.get("description", ""))

        system_prompt = """You are a UI Squad Agent. Your ONLY job is to write responsive HTML/CSS/JS or React components.
Output ONLY valid JSON: {"filename": "component.jsx", "code": "...", "test_filename": "test_component.js", "test_code": "..."}"""

        prompt = f"Task: {task.get('title')}\nDescription: {task.get('description')}\nContext: {filtered['filtered_context']}"

        raw_response = call_llm(prompt, system_prompt)
        return {
            "squad": "ui",
            "task_id": task.get("id"),
            "response": raw_response,
            "success": True
        }
