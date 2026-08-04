import pytest
import os
import tempfile
import shutil
from memory.session_state_merger import SessionStateMerger


@pytest.fixture
def temp_merger():
    temp_dir = tempfile.mkdtemp(prefix="snapshot_test_")
    merger = SessionStateMerger(snapshot_dir=temp_dir)
    yield merger
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_compute_code_hash_and_ast_summary(temp_merger):
    """Verify SHA-256 code hash and AST structural extraction"""
    code = """
def login(username: str) -> bool:
    return True

class AuthModule:
    pass
"""
    chash = temp_merger.compute_code_hash(code)
    assert len(chash) == 64
    
    ast_sum = temp_merger.compute_ast_summary(code)
    assert ast_sum["valid_ast"] is True
    assert "login" in ast_sum["functions"]
    assert "AuthModule" in ast_sum["classes"]


def test_create_and_restore_snapshot(temp_merger):
    """Verify snapshot creation and deterministic restoration"""
    session_id = "sess_1001"
    code = "def authenticate(): return True"
    state = {
        "completed_tasks": ["task_1", "task_2"],
        "code_modules": {"auth.py": code},
        "metadata": {"author": "Karpathy Pipeline"}
    }
    
    snapshot_path = temp_merger.create_snapshot(session_id, state)
    assert os.path.exists(snapshot_path)
    
    # Restore with matching state
    current_state = {
        "completed_tasks": ["task_3"],
        "code_modules": {"auth.py": code}
    }
    
    res = temp_merger.verify_and_merge(snapshot_path, current_state)
    assert res["success"] is True
    assert "task_1" in res["merged_state"]["completed_tasks"]
    assert "task_3" in res["merged_state"]["completed_tasks"]
    assert res["merged_state"]["code_modules"]["auth.py"] == code
    assert res["merged_state"]["restored_from_session"] == session_id


def test_restore_detects_corrupted_state(temp_merger):
    """Verify Law 19 breach is raised if code hash does not match snapshot"""
    session_id = "sess_1002"
    original_code = "def authenticate(): return True"
    corrupted_code = "def authenticate(): return False # Tampered!"
    
    state = {
        "completed_tasks": ["task_1"],
        "code_modules": {"auth.py": original_code}
    }
    snapshot_path = temp_merger.create_snapshot(session_id, state)
    
    current_state = {
        "completed_tasks": ["task_1"],
        "code_modules": {"auth.py": corrupted_code}  # Modified!
    }
    
    res = temp_merger.verify_and_merge(snapshot_path, current_state)
    assert res["success"] is False
    assert "Law 19 Breach" in res["error"]
