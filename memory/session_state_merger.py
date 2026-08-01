"""
Session State Merger - Cross-Session State Handoff & Snapshot Protocol (Law 19).
Deterministically merges state snapshots across execution sessions using AST hashes and physical file checksums.
"""

import os
import sys
import json
import hashlib
import ast
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class SessionStateMerger:
    """
    Deterministically manages session snapshots and cross-session state handoffs.
    Enforces Law 19: All restored session states MUST be validated against physical ground-truth.
    """
    
    def __init__(self, snapshot_dir: str = None):
        if snapshot_dir is None:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            snapshot_dir = os.path.join(project_root, "brain", "snapshots")
        self.snapshot_dir = snapshot_dir
        os.makedirs(self.snapshot_dir, exist_ok=True)

    @staticmethod
    def compute_code_hash(code_str: str) -> str:
        """Computes SHA-256 hash of source code string."""
        return hashlib.sha256(code_str.encode("utf-8")).hexdigest()

    @staticmethod
    def compute_ast_summary(code_str: str) -> dict:
        """Computes AST structural signature for deterministic comparison."""
        try:
            tree = ast.parse(code_str)
            functions = []
            classes = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    functions.append(node.name)
                elif isinstance(node, ast.ClassDef):
                    classes.append(node.name)
            return {
                "valid_ast": True,
                "functions": sorted(functions),
                "classes": sorted(classes)
            }
        except SyntaxError:
            return {
                "valid_ast": False,
                "functions": [],
                "classes": []
            }

    def create_snapshot(self, session_id: str, state: dict) -> str:
        """
        Creates an immutable, ground-truth snapshot of the current session.
        
        Args:
            session_id: Unique session identifier
            state: Pipeline/Agent state dictionary
            
        Returns:
            Absolute filepath to written snapshot JSON
        """
        code_modules = state.get("code_modules", {})
        module_hashes = {}
        ast_summaries = {}
        
        for fname, code in code_modules.items():
            module_hashes[fname] = self.compute_code_hash(code)
            ast_summaries[fname] = self.compute_ast_summary(code)
            
        snapshot = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "completed_tasks": state.get("completed_tasks", []),
            "module_hashes": module_hashes,
            "ast_summaries": ast_summaries,
            "metadata": state.get("metadata", {})
        }
        
        filepath = os.path.join(self.snapshot_dir, f"session_{session_id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)
            
        return filepath

    def verify_and_merge(self, snapshot_path: str, current_state: dict) -> dict:
        """
        Restores and deterministically merges a past session snapshot with current state.
        
        Args:
            snapshot_path: Path to snapshot JSON
            current_state: Current active session state
            
        Returns:
            Merged state dict
        """
        if not os.path.exists(snapshot_path):
            raise FileNotFoundError(f"Snapshot not found at: {snapshot_path}")
            
        with open(snapshot_path, "r", encoding="utf-8") as f:
            snapshot = json.load(f)
            
        # Law 19 Enforcement: Verify integrity of snapshot data
        module_hashes = snapshot.get("module_hashes", {})
        corrupted_modules = []
        
        code_modules = current_state.get("code_modules", {})
        for fname, expected_hash in module_hashes.items():
            if fname in code_modules:
                actual_hash = self.compute_code_hash(code_modules[fname])
                if actual_hash != expected_hash:
                    corrupted_modules.append(fname)
                    
        if corrupted_modules:
            return {
                "success": False,
                "error": f"Law 19 Violation: Session state mismatch detected in modules {corrupted_modules}",
                "merged_state": current_state
            }
            
        # Successful Merge
        merged_completed = list(set(snapshot.get("completed_tasks", []) + current_state.get("completed_tasks", [])))
        merged_modules = {**snapshot.get("code_modules", {}), **current_state.get("code_modules", {})}
        
        merged_state = {
            **current_state,
            "completed_tasks": merged_completed,
            "code_modules": merged_modules,
            "restored_from_session": snapshot["session_id"]
        }
        
        return {
            "success": True,
            "error": None,
            "merged_state": merged_state
        }
