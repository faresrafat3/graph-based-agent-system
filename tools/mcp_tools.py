"""
Custom MCP Tools Implementation
"""

from typing import List, Dict, Any


class MCPTools:
    """Custom MCP tools for agents"""
    
    @staticmethod
    def requirements_parser(document: str) -> Dict[str, Any]:
        """
        Parse requirements document
        
        Args:
            document: Requirements text
        
        Returns:
            Parsed requirements with features, constraints, ambiguities
        """
        features = []
        constraints = []
        ambiguities = []
        
        # Simple keyword-based extraction
        keywords = {
            "authentication": "authentication",
            "database": "database",
            "API": "API",
            "UI": "UI",
            "testing": "testing",
            "notification": "notification",
            "payment": "payment",
            "search": "search",
            "upload": "upload",
            "export": "export"
        }
        
        doc_lower = document.lower()
        for keyword, feature in keywords.items():
            if keyword in doc_lower:
                features.append(f"Requires {feature}")
        
        # Check for ambiguities
        ambiguous_phrases = [
            "something",
            "thing",
            "stuff",
            "etc",
            "and so on",
            "maybe",
            "possibly"
        ]
        
        for phrase in ambiguous_phrases:
            if phrase in doc_lower:
                ambiguities.append(f"Ambiguous phrase: '{phrase}'")
        
        return {
            "features": features,
            "constraints": constraints,
            "ambiguities": ambiguities
        }
    
    @staticmethod
    def dependency_analyzer(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze dependencies between tasks
        
        Args:
            tasks: List of tasks
        
        Returns:
            Dependencies and circular dependencies
        """
        dependencies = {}
        circular = []
        
        # Build dependency graph from explicit task dependencies
        for task in tasks:
            task_id = task.get("id")
            if task_id:
                # Respect dependencies provided in the task specification
                dependencies[task_id] = task.get("dependencies", [])
        
        # Check for circular dependencies using DFS graph cycle detection
        circular = []
        visited = {}  # 0: unvisited, 1: visiting (in current DFS stack), 2: visited
        
        def dfs(node, path):
            visited[node] = 1
            path.append(node)
            
            for neighbor in dependencies.get(node, []):
                if visited.get(neighbor, 0) == 1:
                    cycle_start = path.index(neighbor)
                    circular.append(path[cycle_start:] + [neighbor])
                elif visited.get(neighbor, 0) == 0:
                    dfs(neighbor, path)
            
            path.pop()
            visited[node] = 2

        for task_id in dependencies:
            if visited.get(task_id, 0) == 0:
                dfs(task_id, [])
        
        return {
            "dependencies": dependencies,
            "circular_dependencies": circular
        }
    
    @staticmethod
    def effort_estimator(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Estimate effort for tasks
        
        Args:
            tasks: List of tasks
        
        Returns:
            Effort estimates
        """
        estimates = {}
        
        for task in tasks:
            task_id = task.get("id")
            task_type = task.get("type", "")
            
            if not task_id:
                continue
            
            # Simple heuristics
            if task_type == "architecture":
                estimates[task_id] = "medium"
            elif task_type == "feature":
                estimates[task_id] = "large"
            elif task_type == "testing":
                estimates[task_id] = "medium"
            elif task_type == "requirements":
                estimates[task_id] = "medium"
            elif task_type == "bugfix":
                estimates[task_id] = "small"
            elif task_type == "refactor":
                estimates[task_id] = "medium"
            else:
                estimates[task_id] = "small"
        
        return {"estimates": estimates}
    
    @staticmethod
    def system_assigner(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Assign tasks to systems
        
        Args:
            tasks: List of tasks
        
        Returns:
            System assignments
        """
        assignments = {}
        
        for task in tasks:
            task_id = task.get("id")
            task_type = task.get("type", "")
            
            if not task_id:
                continue
            
            # Assignment heuristics
            if task_type == "requirements":
                assignments[task_id] = "pm"
            elif task_type == "architecture":
                assignments[task_id] = "architect"
            elif task_type == "feature":
                assignments[task_id] = "developer"
            elif task_type == "testing":
                assignments[task_id] = "tester"
            elif task_type == "bugfix":
                assignments[task_id] = "developer"
            elif task_type == "refactor":
                assignments[task_id] = "developer"
            else:
                assignments[task_id] = "developer"
        
        return {"assignments": assignments}
    
    @staticmethod
    def priority_assigner(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Assign priorities to tasks
        
        Args:
            tasks: List of tasks
        
        Returns:
            Priority assignments
        """
        priorities = {}
        
        for task in tasks:
            task_id = task.get("id")
            task_type = task.get("type", "")
            
            if not task_id:
                continue
            
            # Priority heuristics
            if task_type == "architecture":
                priorities[task_id] = "high"
            elif task_type == "requirements":
                priorities[task_id] = "high"
            elif task_type == "feature":
                priorities[task_id] = "high"
            elif task_type == "testing":
                priorities[task_id] = "medium"
            elif task_type == "bugfix":
                priorities[task_id] = "high"
            elif task_type == "refactor":
                priorities[task_id] = "low"
            else:
                priorities[task_id] = "medium"
        
        return {"priorities": priorities}


# Global tools instance
mcp_tools = MCPTools()


# Test function
def test_mcp_tools():
    """Test MCP tools"""
    
    print("Testing MCP tools...")
    
    # Test requirements parser
    parsed = mcp_tools.requirements_parser(
        "Build a login page with authentication and database"
    )
    assert "features" in parsed
    assert len(parsed["features"]) > 0
    print(f"✓ Requirements parser: {parsed['features']}")
    
    # Test dependency analyzer
    tasks = [
        {"id": "task_1", "type": "architecture"},
        {"id": "task_2", "type": "feature"},
        {"id": "task_3", "type": "testing"}
    ]
    deps = mcp_tools.dependency_analyzer(tasks)
    assert "dependencies" in deps
    print(f"✓ Dependency analyzer: {deps['dependencies']}")
    
    # Test effort estimator
    efforts = mcp_tools.effort_estimator(tasks)
    assert "estimates" in efforts
    print(f"✓ Effort estimator: {efforts['estimates']}")
    
    # Test system assigner
    assignments = mcp_tools.system_assigner(tasks)
    assert "assignments" in assignments
    print(f"✓ System assigner: {assignments['assignments']}")
    
    # Test priority assigner
    priorities = mcp_tools.priority_assigner(tasks)
    assert "priorities" in priorities
    print(f"✓ Priority assigner: {priorities['priorities']}")
    
    print("✓ All MCP tools tests passed!")


if __name__ == "__main__":
    test_mcp_tools()
