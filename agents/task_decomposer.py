"""
Task Decomposer Agent - First of 8 Karpathy Agents
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, List
import json
from datetime import datetime

# Import dependencies
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.llm_integration import call_llm
from memory.custom_memory import memory
from tools.mcp_tools import mcp_tools


# State Definition
class TaskDecomposerState(TypedDict):
    # Input
    requirements: str
    project_context: str
    constraints: str
    
    # Output
    tasks: List[dict]
    metadata: dict
    clarifications_needed: List[str]
    
    # Control
    retry_count: int
    success: bool
    
    # Memory
    similar_past_decompositions: List[dict]
    
    # Validation
    coverage: float
    has_circular: bool
    valid_assignments: bool
    use_cached: bool


# System Prompt
SYSTEM_PROMPT = """You are a Task Decomposer Agent. Your ONLY job is to convert 
natural language requirements into structured tasks in JSON format.

## Core Principles (Karpathy's 4 Principles)

1. Think before decomposing - Analyze requirements thoroughly
2. Simplicity first - Break into minimum necessary tasks
3. Surgical decomposition - Only decompose what's in requirements
4. Goal-driven decomposition - All requirements must be covered

## Output Format (JSON)

{
  "tasks": [
    {
      "id": "task_1",
      "title": "...",
      "description": "...",
      "type": "feature|architecture|requirements|testing|bugfix|refactor",
      "priority": "high|medium|low",
      "dependencies": [],
      "estimated_effort": "small|medium|large|xlarge",
      "assigned_system": "pm|architect|developer|reviewer|tester",
      "acceptance_criteria": ["..."]
    }
  ],
  "metadata": {
    "total_tasks": 5,
    "high_priority": 2,
    "medium_priority": 2,
    "low_priority": 1,
    "estimated_total_effort": "xlarge"
  },
  "clarifications_needed": ["..."]
}

## Examples

### Example 1: Simple
Input: "Build a login page with email/password authentication"
Output:
{
  "tasks": [
    {
      "id": "task_1",
      "title": "Design login page UI",
      "description": "Create UI mockup for login page",
      "type": "architecture",
      "priority": "high",
      "dependencies": [],
      "estimated_effort": "small",
      "assigned_system": "architect",
      "acceptance_criteria": ["UI mockup created", "Email field included", "Password field included"]
    },
    {
      "id": "task_2",
      "title": "Implement login page",
      "description": "Build frontend for login page",
      "type": "feature",
      "priority": "high",
      "dependencies": ["task_1"],
      "estimated_effort": "medium",
      "assigned_system": "developer",
      "acceptance_criteria": ["Login page renders correctly", "Form validation works"]
    },
    {
      "id": "task_3",
      "title": "Implement authentication backend",
      "description": "Build backend API for authentication",
      "type": "feature",
      "priority": "high",
      "dependencies": [],
      "estimated_effort": "medium",
      "assigned_system": "developer",
      "acceptance_criteria": ["API endpoint created", "Authentication works"]
    }
  ],
  "metadata": {
    "total_tasks": 3,
    "high_priority": 3,
    "medium_priority": 0,
    "low_priority": 0,
    "estimated_total_effort": "large"
  },
  "clarifications_needed": []
}

### Example 2: Vague
Input: "Build something cool"
Output:
{
  "tasks": [],
  "metadata": {
    "total_tasks": 0,
    "high_priority": 0,
    "medium_priority": 0,
    "low_priority": 0,
    "estimated_total_effort": "unknown"
  },
  "clarifications_needed": [
    "What type of application?",
    "What features are required?",
    "What is the target audience?"
  ]
}

## Constraints

- MUST output valid JSON
- MUST include all dependencies
- MUST assign to correct system (pm|architect|developer|reviewer|tester)
- MUST provide acceptance criteria for each task
- NEVER make assumptions without clarification
- NEVER create circular dependencies
- NEVER skip required tasks
"""


# Permission Boundaries (Law 2 & Constitution Article I, Section 2)
TASK_DECOMPOSER_PERMISSIONS = {
    "READ": ["requirements", "project_context", "constraints"],
    "WRITE": ["tasks", "metadata", "clarifications_needed"],
    "NEVER": ["code", "architecture_design", "deployment", "credentials"],
    "HUMAN_CHECKPOINT": ["vague_requirements", "ambiguous_scope"]
}


# Karpathy Loop Implementation

def propose(state: TaskDecomposerState) -> dict:
    """Step 1: Propose - Analyze requirements and check memory"""
    
    requirements = state["requirements"]
    
    # Enforce Permission Boundaries Check
    if any(forbidden in requirements.lower() for forbidden in ["deploy to production", "delete production database"]):
        raise PermissionError("Task Decomposer Agent attempted an action listed in NEVER permissions.")
    
    # Check memory for similar past decompositions
    similar = memory.find_similar(requirements, threshold=0.8)
    
    if similar and similar[0]["similarity"] > 0.9:
        # Use past decomposition as reference
        past_data = similar[0]["entry"]["data"]
        past_tasks = past_data.get("tasks", [])
        # Guard against cache poisoning (F5): never reuse an empty/!success
        # decomposition, or the refine loop would retrieve [] forever.
        if past_tasks:
            return {
                "tasks": past_tasks,
                "metadata": past_data.get("metadata", {}),
                "clarifications_needed": past_data.get("clarifications_needed", []),
                "similar_past_decompositions": similar,
                "use_cached": True,
            }
    
    # Use MCP tools to parse requirements
    parsed = mcp_tools.requirements_parser(requirements)
    
    return {
        "parsed_requirements": parsed,
        "similar_past_decompositions": similar,
        "use_cached": False
    }


def execute(state: TaskDecomposerState) -> dict:
    """Step 2: Execute - Create structured tasks using LLM"""
    import re
    
    if state.get("use_cached") and state.get("tasks"):
        return {
            "tasks": state.get("tasks", []),
            "metadata": state.get("metadata", {}),
            "clarifications_needed": state.get("clarifications_needed", [])
        }

    requirements = state["requirements"]
    project_context = state.get("project_context", "")
    constraints = state.get("constraints", "")
    
    # Build prompt
    prompt = f"""Requirements:
{requirements}

Project Context:
{project_context}

Constraints:
{constraints}

Decompose these requirements into structured tasks following the JSON format specified."""
    
    # Call LLM
    response = call_llm(prompt, SYSTEM_PROMPT)
    
    # Robust JSON extraction
    raw_text = response.strip()
    if "```" in raw_text:
        # Strip markdown fences
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.MULTILINE)
        raw_text = re.sub(r"\s*```$", "", raw_text, flags=re.MULTILINE).strip()
        
    json_match = re.search(r"(\{.*\})", raw_text, re.DOTALL)
    if json_match:
        raw_text = json_match.group(1)
        
    # Parse JSON
    try:
        result = json.loads(raw_text)
        tasks = result.get("tasks", [])
        
        # Normalize task attributes for downstream consistency
        normalized_tasks = []
        for task in tasks:
            assigned = str(task.get("assigned_system", "")).lower()
            if "frontend" in assigned or "backend" in assigned or "dev" in assigned:
                assigned = "developer"
            elif "design" in assigned or "arch" in assigned:
                assigned = "architect"
            elif "test" in assigned or "qa" in assigned:
                assigned = "tester"
            elif "pm" in assigned or "product" in assigned:
                assigned = "pm"
            elif assigned not in ["pm", "architect", "developer", "reviewer", "tester"]:
                assigned = "developer"
                
            task["assigned_system"] = assigned
            normalized_tasks.append(task)
            
        result["tasks"] = normalized_tasks
        
        # Use MCP tools to analyze dependencies for circular loops
        if result.get("tasks"):
            dep_analysis = mcp_tools.dependency_analyzer(result["tasks"])
            
            # Check for circular dependencies
            if dep_analysis["circular_dependencies"]:
                if "clarifications_needed" not in result:
                    result["clarifications_needed"] = []
                result["clarifications_needed"].append(
                    f"Circular dependencies detected: {dep_analysis['circular_dependencies']}"
                )
        
        return {
            "tasks": result.get("tasks", []),
            "metadata": result.get("metadata", {}),
            "clarifications_needed": result.get("clarifications_needed", [])
        }
    
    except json.JSONDecodeError:
        return {
            "tasks": [],
            "metadata": {},
            "clarifications_needed": ["Failed to parse JSON output from LLM"]
        }


def evaluate(state: TaskDecomposerState) -> dict:
    """Step 3: Evaluate - Validate tasks"""
    
    tasks = state.get("tasks", [])
    requirements = state["requirements"]
    
    # Check for circular dependencies
    dep_analysis = mcp_tools.dependency_analyzer(tasks)
    has_circular = len(dep_analysis["circular_dependencies"]) > 0
    
    # Check requirements coverage
    requirements_lower = requirements.lower()
    task_descriptions = " ".join([
        (t.get("title", "") + " " + t.get("description", "")).lower() 
        for t in tasks
    ])
    keywords = [k for k in requirements_lower.split() if len(k) > 3]
    covered = sum(1 for k in keywords if k in task_descriptions)
    coverage = covered / len(keywords) if keywords else 1.0
    
    # Check assignments
    valid_systems = ["pm", "architect", "developer", "reviewer", "tester"]
    valid_assignments = all(
        t.get("assigned_system") in valid_systems 
        for t in tasks
    ) if tasks else False
    
    # Check clarifications
    clarifications = state.get("clarifications_needed", [])
    needs_clarification = len(clarifications) > 0
    
    # Determine success
    success = (
        not has_circular and 
        coverage >= 0.6 and 
        valid_assignments and 
        not needs_clarification and
        len(tasks) > 0
    )
    
    return {
        "success": success,
        "coverage": coverage,
        "has_circular": has_circular,
        "valid_assignments": valid_assignments
    }


def commit(state: TaskDecomposerState) -> dict:
    """Step 4: Commit - Save to memory (never cache empty/!success output)."""
    tasks = state.get("tasks", [])
    requirements = state["requirements"]

    # F5: never persist an empty or failed decomposition — doing so would poison
    # the similarity cache and let a later refine loop retrieve [] indefinitely.
    if tasks and state.get("success", False):
        memory.add_to_long_term(
            data={
                "requirements": requirements,
                "tasks": tasks,
                "metadata": state.get("metadata", {}),
                "timestamp": datetime.now().isoformat(),
            },
            metadata={
                "source": "task_decomposer",
                "success": True,
            },
        )

    return {"committed": True}


def refine(state: TaskDecomposerState) -> dict:
    """Step 5: Repeat - If invalid, refine and retry"""
    
    retry_count = state.get("retry_count", 0) + 1
    
    return {
        "retry_count": retry_count,
        "tasks": [],
        "success": False,
        "use_cached": False
    }


def should_continue(state: TaskDecomposerState) -> str:
    """Determine next step in Karpathy Loop"""
    
    success = state.get("success", False)
    retry_count = state.get("retry_count", 0)
    
    if success:
        return "commit"
    elif retry_count >= 3:
        return "escalate"
    else:
        return "refine"


# Build LangGraph Workflow
workflow = StateGraph(TaskDecomposerState)

# Add nodes (Karpathy Loop steps)
workflow.add_node("propose", propose)
workflow.add_node("execute", execute)
workflow.add_node("evaluate", evaluate)
workflow.add_node("commit", commit)
workflow.add_node("refine", refine)

# Set entry point
workflow.set_entry_point("propose")

# Add edges
workflow.add_edge("propose", "execute")
workflow.add_edge("execute", "evaluate")

# Conditional routing
workflow.add_conditional_edges(
    "evaluate",
    should_continue,
    {
        "commit": "commit",
        "refine": "refine",
        "escalate": END
    }
)

# Loop back from refine to propose
workflow.add_edge("refine", "propose")

# End after commit
workflow.add_edge("commit", END)

# Compile with Checkpointer (State Persistence - Article III, Section 1)
checkpointer = MemorySaver()
task_decomposer_graph = workflow.compile(checkpointer=checkpointer)


# Main function
def decompose_requirements(
    requirements: str,
    project_context: str = "",
    constraints: str = "",
    thread_id: str = "default_session"
) -> dict:
    """
    Decompose requirements into structured tasks
    
    Args:
        requirements: Natural language requirements
        project_context: Project context (optional)
        constraints: Constraints (optional)
        thread_id: Session thread ID for state persistence
    
    Returns:
        Dict with tasks, metadata, clarifications_needed
    """
    
    result = task_decomposer_graph.invoke(
        {
            "requirements": requirements,
            "project_context": project_context,
            "constraints": constraints,
            "retry_count": 0,
            "success": False,
            "tasks": [],
            "metadata": {},
            "clarifications_needed": [],
            "similar_past_decompositions": [],
            "coverage": 0.0,
            "has_circular": False,
            "valid_assignments": False,
            "use_cached": False
        },
        config={"configurable": {"thread_id": thread_id}}
    )
    
    return {
        "tasks": result.get("tasks", []),
        "metadata": result.get("metadata", {}),
        "clarifications_needed": result.get("clarifications_needed", []),
        "success": result.get("success", False)
    }


# Test function
def test_task_decomposer():
    """Test Task Decomposer Agent"""
    
    print("Testing Task Decomposer Agent...")
    
    # Test 1: Simple requirements
    print("\n1. Testing simple requirements...")
    result = decompose_requirements(
        requirements="Build a login page with email/password authentication",
        project_context="Web application",
        constraints="Use React and Node.js"
    )
    
    print(f"   Tasks: {len(result['tasks'])}")
    print(f"   Success: {result['success']}")
    print(f"   Clarifications: {result['clarifications_needed']}")
    
    if result["tasks"]:
        for task in result["tasks"][:3]:
            print(f"   - {task.get('title')} ({task.get('type')})")
    
    # Test 2: Complex requirements
    print("\n2. Testing complex requirements...")
    result = decompose_requirements(
        requirements="Build a task management app with user authentication, task creation, task assignment, notifications, and reporting",
        project_context="SaaS application",
        constraints="Must be scalable"
    )
    
    print(f"   Tasks: {len(result['tasks'])}")
    print(f"   Success: {result['success']}")
    
    # Test 3: Vague requirements
    print("\n3. Testing vague requirements...")
    result = decompose_requirements(
        requirements="Build something cool",
        project_context="",
        constraints=""
    )
    
    print(f"   Tasks: {len(result['tasks'])}")
    print(f"   Success: {result['success']}")
    print(f"   Clarifications: {result['clarifications_needed']}")
    
    print("\n✓ Task Decomposer Agent tests completed!")


if __name__ == "__main__":
    test_task_decomposer()
