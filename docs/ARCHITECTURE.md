# Architecture Documentation

## System Architecture

### Overview

The Software Builder Agents system is a **multi-agent system** that implements Karpathy's Agentic Engineering principles for automated software development.

### Design Principles

1. **Specialization**: Each agent has a single, well-defined responsibility
2. **Loose Coupling**: Agents communicate through well-defined interfaces
3. **Fault Tolerance**: Agents fail gracefully and escalate when needed
4. **Scalability**: System can handle complex requirements by adding more agents
5. **Transparency**: System provides clear visibility into agent decisions

### Architecture Layers
```
┌─────────────────────────────────────────────────────────────┐
│ Presentation Layer                                          │
│ • User Interface (CLI/API)                                  │
│ • Human Escalation Agent                                    │
└─────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────┐
│ Orchestration Layer                                         │
│ • Karpathy Pipeline (agents/karpathy_pipeline.py)           │
│ • LangGraph State Machine                                   │
│ • Conditional Routing                                       │
└─────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────┐
│ Governance Layer (Zero-LLM) [NEW - Laws 11, 12, 13]        │
│ • Context Curator Agent      (Law 12: Context Sanitation)   │
│ • Deterministic Validator    (Law 11: Execution Grounding)  │
│ • Surgical Refiner Agent     (Law 13: Surgical Refinement)  │
└─────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────┐
│ Agent Layer                                                 │
│ • 8 Karpathy Meta-Agents                                    │
│ • 7 Software Domain Agents                                  │
│ • Each agent implements Karpathy Loop                       │
│ • Agents are independent and specialized                    │
└─────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────┐
│ Infrastructure Layer                                        │
│ • LLM Integration (OpenAI/Anthropic) + Mock/Dry-Run Mode    │
│ • Custom Memory (Short-term + Long-term)                    │
│ • MCP Tools (DFS Dependency Analyzer)                       │
│ • MemorySaver Checkpointer                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Agent Architecture

### Karpathy Loop

Each agent implements the **Karpathy Loop** pattern:
```
┌──────────┐
│ Propose  │ ← Generate plan/hypothesis
└────┬─────┘
     ↓
┌──────────┐
│ Execute  │ ← Implement plan
└────┬─────┘
     ↓
┌──────────┐
│ Evaluate │ ← Check if plan worked
└────┬─────┘
     │
     ├──── Success ──→ ┌──────────┐
     │                 │  Commit  │ ← Commit changes
     │                 └──────────┘
     │
     └──── Failure ──→ ┌──────────┐
                       │  Refine  │ ← Refine and retry
                       └────┬─────┘
                            ↓
                     (Back to Propose)
```

### Agent State

Each agent maintains state using LangGraph:

```python
class AgentState(TypedDict):
    # Input
    input: Any
    
    # Output
    output: Any
    
    # Control
    retry_count: int
    success: bool
    
    # Memory
    memory_context: List[dict]
    
    # Validation
    validation_results: dict
```

### Agent Communication
Agents communicate through state passing:

```python
# Task Decomposer → Agent Assigner
workflow.add_edge("task_decomposer", "agent_assigner")

# State is automatically passed between agents
```

---

## Task Decomposer Agent (Detailed)

### State Definition
```python
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
```

### Workflow
```python
workflow = StateGraph(TaskDecomposerState)

# Add nodes
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

# Loop back
workflow.add_edge("refine", "propose")
workflow.add_edge("commit", END)
```

### Propose Step
```python
def propose(state):
    requirements = state["requirements"]
    
    # Check memory for similar past decompositions
    similar = memory.find_similar(requirements, threshold=0.8)
    
    if similar and similar[0]["similarity"] > 0.9:
        # Use past decomposition as reference
        past_tasks = similar[0]["entry"]["data"].get("tasks", [])
        return {"tasks": past_tasks, "similar_past_decompositions": similar}
    
    # Use MCP tools to parse requirements
    parsed = mcp_tools.requirements_parser(requirements)
    
    return {"parsed_requirements": parsed, "similar_past_decompositions": similar}
```

### Execute Step
```python
def execute(state):
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

Decompose these requirements into structured tasks."""
    
    # Call LLM
    response = call_llm(prompt, SYSTEM_PROMPT)
    
    # Parse JSON
    try:
        result = json.loads(response)
        
        # Enhance with MCP tools
        if result.get("tasks"):
            dep_analysis = mcp_tools.dependency_analyzer(result["tasks"])
            
            for task in result["tasks"]:
                task_id = task.get("id")
                if task_id in dep_analysis["dependencies"]:
                    task["dependencies"] = dep_analysis["dependencies"][task_id]
        
        return {
            "tasks": result.get("tasks", []),
            "metadata": result.get("metadata", {}),
            "clarifications_needed": result.get("clarifications_needed", [])
        }
    
    except json.JSONDecodeError:
        return {
            "tasks": [],
            "metadata": {},
            "clarifications_needed": ["Failed to parse JSON"]
        }
```

### Evaluate Step
```python
def evaluate(state):
    tasks = state.get("tasks", [])
    requirements = state["requirements"]
    
    # Check circular dependencies
    dep_analysis = mcp_tools.dependency_analyzer(tasks)
    has_circular = len(dep_analysis["circular_dependencies"]) > 0
    
    # Check coverage
    requirements_lower = requirements.lower()
    task_descriptions = " ".join([t.get("description", "").lower() for t in tasks])
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
    
    success = (
        not has_circular and 
        coverage >= 0.8 and 
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
```

---

## Memory Architecture

### Short-Term Memory
```python
class ShortTermMemory:
    def __init__(self):
        self.data = {}
    
    def add(self, key, value):
        self.data[key] = value
    
    def get(self, key):
        return self.data.get(key)
    
    def clear(self):
        self.data = {}
```
**Use Case**: Current session context

### Long-Term Memory
```python
class LongTermMemory:
    def __init__(self):
        self.entries = []
    
    def add(self, data, metadata=None):
        entry = {
            "data": data,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat()
        }
        self.entries.append(entry)
    
    def find_similar(self, query, threshold=0.8, limit=3):
        similar = []
        query_keywords = set(query.lower().split())
        
        for entry in self.entries:
            data_str = str(entry["data"]).lower()
            entry_keywords = set(data_str.split())
            
            # Jaccard similarity
            overlap = len(query_keywords & entry_keywords)
            total = len(query_keywords | entry_keywords)
            similarity = overlap / total if total > 0 else 0
            
            if similarity >= threshold:
                similar.append({"entry": entry, "similarity": similarity})
        
        similar.sort(key=lambda x: x["similarity"], reverse=True)
        return similar[:limit]
```
**Use Case**: Past decompositions for reference

---

## MCP Tools Architecture

### Requirements Parser
```python
def requirements_parser(document: str) -> dict:
    features = []
    constraints = []
    ambiguities = []
    
    # Keyword-based extraction
    keywords = {
        "authentication": "authentication",
        "database": "database",
        "API": "API",
        "UI": "UI",
        "testing": "testing"
    }
    
    doc_lower = document.lower()
    for keyword, feature in keywords.items():
        if keyword in doc_lower:
            features.append(f"Requires {feature}")
    
    # Ambiguity detection
    ambiguous_phrases = ["something", "thing", "stuff", "etc"]
    for phrase in ambiguous_phrases:
        if phrase in doc_lower:
            ambiguities.append(f"Ambiguous phrase: '{phrase}'")
    
    return {
        "features": features,
        "constraints": constraints,
        "ambiguities": ambiguities
    }
```

### Dependency Analyzer
```python
def dependency_analyzer(tasks: List[dict]) -> dict:
    dependencies = {}
    circular = []
    
    for task in tasks:
        task_id = task.get("id")
        task_type = task.get("type", "")
        
        deps = []
        
        if task_type == "feature":
            arch_tasks = [t["id"] for t in tasks if t.get("type") == "architecture"]
            deps = arch_tasks
        elif task_type == "testing":
            feat_tasks = [t["id"] for t in tasks if t.get("type") == "feature"]
            deps = feat_tasks
        
        dependencies[task_id] = deps
    
    # Circular dependency detection
    # (simplified - real implementation would use DFS)
    
    return {
        "dependencies": dependencies,
        "circular_dependencies": circular
    }
```

---

## Error Handling

### Retry Mechanism
```python
def should_continue(state):
    success = state.get("success", False)
    retry_count = state.get("retry_count", 0)
    
    if success:
        return "commit"
    elif retry_count >= 3:
        return "escalate"  # Escalate to human
    else:
        return "refine"    # Retry
```

### Escalation
When an agent fails after 3 retries, it escalates to the Human Escalation Agent:
```python
workflow.add_conditional_edges(
    "evaluate",
    should_continue,
    {
        "commit": "commit",
        "refine": "refine",
        "escalate": "human_escalation"
    }
)
```

---

## Performance Considerations

### Parallel Execution
Agents can run in parallel when there are no dependencies:
```python
# Parallel execution
workflow.add_edge("agent_assigner", "progress_monitor")
workflow.add_edge("agent_assigner", "quality_reviewer")
workflow.add_edge("agent_assigner", "integration")
```

### Caching
Memory provides caching for similar requests:
```python
similar = memory.find_similar(requirements, threshold=0.9)
if similar:
    # Use cached result
    return similar[0]["entry"]["data"]
```

### Batching
Tasks can be batched for efficiency:
```python
# Batch multiple tasks
for task in tasks:
    kanban.create_task(task)
```

---

## Security Considerations

### Permission Boundaries
Each agent has explicit permissions:
```python
# Task Decomposer Agent
PERMISSIONS = {
    "READ": ["requirements", "project_context"],
    "WRITE": ["tasks", "metadata"],
    "NEVER": ["code", "deployment", "credentials"]
}
```

### Input Validation
All inputs are validated:
```python
def validate_requirements(requirements: str):
    if not requirements or len(requirements) < 10:
        raise ValueError("Requirements too short")
    if len(requirements) > 10000:
        raise ValueError("Requirements too long")
```

### Output Validation
All outputs are validated:
```python
def validate_tasks(tasks: List[dict]):
    for task in tasks:
        if "id" not in task:
            raise ValueError("Task missing id")
        if "title" not in task:
            raise ValueError("Task missing title")
```

---

## Scalability

### Adding New Agents
To add a new agent:
1. Define agent state
2. Implement Karpathy Loop
3. Add to workflow
4. Connect to other agents

```python
# Example: Adding a new agent
class NewAgentState(TypedDict):
    input: Any
    output: Any

def new_agent(state):
    # Implement agent logic
    return {"output": result}

workflow.add_node("new_agent", new_agent)
workflow.add_edge("previous_agent", "new_agent")
```

### Adding New Tools
To add a new tool:
1. Implement tool function
2. Add to MCPTools class
3. Use in agents

```python
class MCPTools:
    def new_tool(self, input):
        # Implement tool logic
        return result
```

---

## Monitoring and Observability

### Logging
All agents log their actions:
```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def propose(state):
    logger.info(f"Proposing for requirements: {state['requirements'][:100]}")
    # ... rest of logic
```

### Metrics
System tracks metrics:
```python
metrics = {
    "tasks_created": 0,
    "success_rate": 0.0,
    "average_retry_count": 0.0,
    "escalation_rate": 0.0
}
```

---

## Future Enhancements

### Planned Features
- **Visualization**: Web UI for monitoring agents
- **Advanced Memory**: Vector embeddings for similarity search
- **More Tools**: Additional MCP tools for different use cases
- **More Agents**: Additional specialized agents
- **Distributed Execution**: Run agents on multiple machines

### Research Directions
- **Reinforcement Learning**: Agents learn from feedback
- **Multi-Modal**: Support for images, audio, video
- **Collaborative Agents**: Agents that can negotiate
- **Self-Improving Agents**: Agents that improve their own prompts

---

## References

1. Karpathy, A. (2024). "Agentic Engineering". Sequoia Capital.
2. LangChain Team. (2024). "LangGraph Documentation".
3. MAAD Framework. (2024). "Multi-Agent Architecture Design".
4. MetaGPT. (2023). "Meta-Programming for Multi-Agent Collaborative Framework".
5. AutoGen. (2024). "Microsoft Research".

---

**Last Updated**: July 31, 2025
