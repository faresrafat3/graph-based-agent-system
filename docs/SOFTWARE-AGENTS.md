# Software Agents Documentation

## Overview

The **Software Agents** perform the actual software development work, supervised by the **Karpathy Agents** (meta-agents) that manage the system.

## Architecture
```
┌─────────────────────────────────────────────────────────────┐
│ Karpathy Agents (8 Meta-Agents)                             │
│ Task Decomposer, Agent Assigner, Progress Monitor, etc.     │
└─────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────┐
│ Software Agents (7 Agents)                                  │
│ Product Manager, Architect, Developer, Reviewer, Tester,    │
│ DevOps, Security                                            │
└─────────────────────────────────────────────────────────────┘
```

## The 7 Software Agents

Every agent implements the same Karpathy Loop (`propose` → `execute` → `evaluate` → `commit` → `refine`), carries an explicit `PERMISSIONS` dict, and reaches quality gate `>= 0.8` before commit. Per-agent detail follows.

### 1. Product Manager Agent

**Role:** Manages product requirements and priorities

**Responsibilities:** gather/analyze stakeholder requirements; create and maintain the product backlog; prioritize features by business value; write user stories with acceptance criteria; communicate with stakeholders; make product decisions.

**Karpathy Loop Implementation:**

```python
class ProductManagerAgent:
    def propose(self, state):
        """Analyze requirements and create user stories"""
        requirements = state["requirements"]
        
        # Use LLM to analyze requirements
        user_stories = self.analyze_requirements(requirements)
        
        return {
            "user_stories": user_stories,
            "priorities": self.prioritize(user_stories)
        }
    
    def execute(self, state):
        """Create detailed user stories"""
        user_stories = state["user_stories"]
        
        # Create detailed user stories with acceptance criteria
        detailed_stories = []
        for story in user_stories:
            detailed = self.create_detailed_story(story)
            detailed_stories.append(detailed)
        
        return {"detailed_stories": detailed_stories}
    
    def evaluate(self, state):
        """Evaluate user stories quality"""
        stories = state["detailed_stories"]
        
        # Check if stories meet INVEST criteria
        quality_score = self.evaluate_invest(stories)
        
        return {
            "quality_score": quality_score,
            "success": quality_score >= 0.8
        }
    
    def commit(self, state):
        """Save user stories to backlog"""
        stories = state["detailed_stories"]
        self.save_to_backlog(stories)
        return {"committed": True}
    
    def refine(self, state):
        """Refine user stories based on feedback"""
        return {
            "retry_count": state.get("retry_count", 0) + 1,
            "user_stories": []
        }
```

**Permissions:**

```python
PERMISSIONS = {
    "READ": ["requirements", "stakeholder_feedback", "market_research"],
    "WRITE": ["user_stories", "backlog", "priorities"],
    "NEVER": ["code", "architecture", "deployment"],
    "HUMAN_CHECKPOINT": ["major_product_decisions", "scope_changes"]
}
```

**Tools:** requirements parser, stakeholder communication, market research, backlog management.

**Integration with Karpathy Agents:** receives tasks from Task Decomposer; outputs go to Architect and Agent Assigner.

### 2. Architect Agent

**Role:** Designs system architecture

**Responsibilities:** design architecture from requirements; choose the technology stack; define component interactions; create architecture diagrams; make and document architectural decisions.

**Karpathy Loop Implementation:**

```python
class ArchitectAgent:
    def propose(self, state):
        """Analyze requirements and propose architecture"""
        user_stories = state["user_stories"]
        
        # Use LLM to design architecture
        architecture = self.design_architecture(user_stories)
        
        return {
            "architecture": architecture,
            "tech_stack": self.choose_tech_stack(architecture)
        }
    
    def execute(self, state):
        """Create detailed architecture"""
        architecture = state["architecture"]
        
        # Create detailed architecture with diagrams
        detailed_arch = self.create_detailed_architecture(architecture)
        
        return {"detailed_architecture": detailed_arch}
    
    def evaluate(self, state):
        """Evaluate architecture quality"""
        architecture = state["detailed_architecture"]
        
        # Check if architecture meets quality standards
        quality_score = self.evaluate_architecture(architecture)
        
        return {
            "quality_score": quality_score,
            "success": quality_score >= 0.8
        }
    
    def commit(self, state):
        """Save architecture"""
        architecture = state["detailed_architecture"]
        self.save_architecture(architecture)
        return {"committed": True}
    
    def refine(self, state):
        """Refine architecture based on feedback"""
        return {
            "retry_count": state.get("retry_count", 0) + 1,
            "architecture": None
        }
```

**Permissions:**

```python
PERMISSIONS = {
    "READ": ["user_stories", "requirements", "constraints"],
    "WRITE": ["architecture", "tech_stack", "diagrams"],
    "NEVER": ["code", "deployment", "testing"],
    "HUMAN_CHECKPOINT": ["major_architecture_decisions", "tech_stack_choices"]
}
```

**Tools:** architecture design, diagram creation, technology research, architecture evaluation.

**Integration with Karpathy Agents:** receives user stories from Product Manager; outputs go to Developer and Agent Assigner.

### 3. Developer Agent

**Role:** Writes code

**Responsibilities:** write code from the architecture; implement features; write unit tests; fix bugs; refactor; document code.

**Karpathy Loop Implementation:**

```python
class DeveloperAgent:
    def propose(self, state):
        """Analyze architecture and plan implementation"""
        architecture = state["architecture"]
        user_stories = state["user_stories"]
        
        # Use LLM to plan implementation
        implementation_plan = self.plan_implementation(architecture, user_stories)
        
        return {
            "implementation_plan": implementation_plan,
            "files_to_create": self.identify_files(implementation_plan)
        }
    
    def execute(self, state):
        """Write code"""
        plan = state["implementation_plan"]
        
        # Write code for each file
        code_files = []
        for file in plan["files_to_create"]:
            code = self.write_code(file)
            code_files.append(code)
        
        return {"code_files": code_files}
    
    def evaluate(self, state):
        """Evaluate code quality"""
        code_files = state["code_files"]
        
        # Run tests
        tests_pass = self.run_tests(code_files)
        
        # Check code quality
        quality_score = self.evaluate_code_quality(code_files)
        
        return {
            "tests_pass": tests_pass,
            "quality_score": quality_score,
            "success": tests_pass and quality_score >= 0.8
        }
    
    def commit(self, state):
        """Commit code"""
        code_files = state["code_files"]
        self.commit_code(code_files)
        return {"committed": True}
    
    def refine(self, state):
        """Fix issues and refactor"""
        return {
            "retry_count": state.get("retry_count", 0) + 1,
            "code_files": []
        }
```

**Permissions:**

```python
PERMISSIONS = {
    "READ": ["architecture", "user_stories", "existing_code"],
    "WRITE": ["code", "unit_tests", "documentation"],
    "NEVER": ["architecture", "deployment", "production"],
    "HUMAN_CHECKPOINT": ["major_refactoring", "breaking_changes"]
}
```

**Tools:** code generation, testing, code quality, documentation.

**Integration with Karpathy Agents:** receives architecture from Architect; outputs go to Reviewer, Tester, and Agent Assigner.

### 4. Reviewer Agent

**Role:** Reviews code

**Responsibilities:** review code for quality, bugs, security issues, and best practices; provide feedback; approve or reject code.

**Karpathy Loop Implementation:**

```python
class ReviewerAgent:
    def propose(self, state):
        """Plan code review"""
        code_files = state["code_files"]
        
        # Plan review approach
        review_plan = self.plan_review(code_files)
        
        return {"review_plan": review_plan}
    
    def execute(self, state):
        """Review code"""
        plan = state["review_plan"]
        code_files = state["code_files"]
        
        # Review each file
        reviews = []
        for file in code_files:
            review = self.review_file(file)
            reviews.append(review)
        
        return {"reviews": reviews}
    
    def evaluate(self, state):
        """Evaluate review results"""
        reviews = state["reviews"]
        
        # Check if code meets quality standards
        approved = all(review["approved"] for review in reviews)
        
        return {
            "approved": approved,
            "success": approved
        }
    
    def commit(self, state):
        """Approve code"""
        self.approve_code(state["reviews"])
        return {"committed": True}
    
    def refine(self, state):
        """Request changes"""
        return {
            "retry_count": state.get("retry_count", 0) + 1,
            "reviews": []
        }
```

**Permissions:**

```python
PERMISSIONS = {
    "READ": ["code", "architecture", "user_stories", "tests"],
    "WRITE": ["reviews", "feedback"],
    "NEVER": ["code", "architecture", "deployment"],
    "HUMAN_CHECKPOINT": ["major_issues", "security_vulnerabilities"]
}
```

**Tools:** code review, static analysis, security scanning, best-practices checkers.

**Integration with Karpathy Agents:** receives code from Developer; outputs go to Developer (for fixes) or Quality Reviewer.

### 5. Tester Agent

**Role:** Tests code

**Responsibilities:** write integration and end-to-end tests; run tests; report bugs; verify fixes; ensure test coverage.

**Karpathy Loop Implementation:**

```python
class TesterAgent:
    def propose(self, state):
        """Plan testing"""
        code_files = state["code_files"]
        user_stories = state["user_stories"]
        
        # Plan tests
        test_plan = self.plan_tests(code_files, user_stories)
        
        return {"test_plan": test_plan}
    
    def execute(self, state):
        """Write and run tests"""
        plan = state["test_plan"]
        
        # Write tests
        tests = []
        for test_case in plan["test_cases"]:
            test = self.write_test(test_case)
            tests.append(test)
        
        # Run tests
        test_results = self.run_tests(tests)
        
        return {
            "tests": tests,
            "test_results": test_results
        }
    
    def evaluate(self, state):
        """Evaluate test results"""
        test_results = state["test_results"]
        
        # Check if all tests pass
        all_pass = all(result["passed"] for result in test_results)
        
        # Check test coverage
        coverage = self.calculate_coverage(test_results)
        
        return {
            "all_pass": all_pass,
            "coverage": coverage,
            "success": all_pass and coverage >= 0.8
        }
    
    def commit(self, state):
        """Commit tests"""
        tests = state["tests"]
        self.commit_tests(tests)
        return {"committed": True}
    
    def refine(self, state):
        """Fix failing tests"""
        return {
            "retry_count": state.get("retry_count", 0) + 1,
            "tests": []
        }
```

**Permissions:**

```python
PERMISSIONS = {
    "READ": ["code", "architecture", "user_stories", "existing_tests"],
    "WRITE": ["tests", "test_reports", "bug_reports"],
    "NEVER": ["code", "architecture", "deployment"],
    "HUMAN_CHECKPOINT": ["critical_bugs", "security_issues"]
}
```

**Tools:** test generation, test execution, coverage analysis, bug reporting.

**Integration with Karpathy Agents:** receives code from Developer; outputs go to Developer (for fixes) or Quality Reviewer.

### 6. DevOps Agent

**Role:** Manages deployment

**Responsibilities:** set up CI/CD pipelines; manage deployment; monitor systems; handle infrastructure; ensure availability; manage scaling.

**Karpathy Loop Implementation:**

```python
class DevOpsAgent:
    def propose(self, state):
        """Plan deployment"""
        code_files = state["code_files"]
        architecture = state["architecture"]
        
        # Plan deployment
        deployment_plan = self.plan_deployment(code_files, architecture)
        
        return {"deployment_plan": deployment_plan}
    
    def execute(self, state):
        """Deploy code"""
        plan = state["deployment_plan"]
        
        # Set up CI/CD
        self.setup_cicd(plan)
        
        # Deploy
        deployment_result = self.deploy(plan)
        
        return {"deployment_result": deployment_result}
    
    def evaluate(self, state):
        """Evaluate deployment"""
        result = state["deployment_result"]
        
        # Check if deployment succeeded
        deployed = result["success"]
        
        # Check if system is healthy
        healthy = self.check_health()
        
        return {
            "deployed": deployed,
            "healthy": healthy,
            "success": deployed and healthy
        }
    
    def commit(self, state):
        """Confirm deployment"""
        self.confirm_deployment()
        return {"committed": True}
    
    def refine(self, state):
        """Fix deployment issues"""
        return {
            "retry_count": state.get("retry_count", 0) + 1,
            "deployment_plan": None
        }
```

**Permissions:**

```python
PERMISSIONS = {
    "READ": ["code", "architecture", "deployment_config"],
    "WRITE": ["cicd_config", "deployment_scripts", "monitoring_config"],
    "NEVER": ["code", "architecture", "user_data"],
    "HUMAN_CHECKPOINT": ["production_deployment", "infrastructure_changes"]
}
```

**Tools:** CI/CD, deployment, monitoring, infrastructure management.

**Integration with Karpathy Agents:** receives approved code from Reviewer; outputs go to Progress Monitor.

### 7. Security Agent

**Role:** Ensures system security

**Responsibilities:** perform security audits; identify vulnerabilities; implement security measures; monitor for security issues; respond to incidents; ensure compliance.

**Karpathy Loop Implementation:**

```python
class SecurityAgent:
    def propose(self, state):
        """Plan security audit"""
        code_files = state["code_files"]
        architecture = state["architecture"]
        
        # Plan security audit
        security_plan = self.plan_security_audit(code_files, architecture)
        
        return {"security_plan": security_plan}
    
    def execute(self, state):
        """Perform security audit"""
        plan = state["security_plan"]
        
        # Scan for vulnerabilities
        vulnerabilities = self.scan_vulnerabilities(plan)
        
        # Implement security measures
        security_measures = self.implement_security(plan)
        
        return {
            "vulnerabilities": vulnerabilities,
            "security_measures": security_measures
        }
    
    def evaluate(self, state):
        """Evaluate security"""
        vulnerabilities = state["vulnerabilities"]
        
        # Check if critical vulnerabilities exist
        critical_vulns = [v for v in vulnerabilities if v["severity"] == "critical"]
        
        return {
            "critical_vulnerabilities": len(critical_vulns),
            "success": len(critical_vulns) == 0
        }
    
    def commit(self, state):
        """Commit security measures"""
        measures = state["security_measures"]
        self.commit_security(measures)
        return {"committed": True}
    
    def refine(self, state):
        """Fix vulnerabilities"""
        return {
            "retry_count": state.get("retry_count", 0) + 1,
            "security_plan": None
        }
```

**Permissions:**

```python
PERMISSIONS = {
    "READ": ["code", "architecture", "deployment_config", "logs"],
    "WRITE": ["security_config", "security_measures", "security_reports"],
    "NEVER": ["user_data", "credentials", "production_secrets"],
    "HUMAN_CHECKPOINT": ["critical_vulnerabilities", "security_incidents"]
}
```

**Tools:** security scanning, vulnerability assessment, security implementation, monitoring.

**Integration with Karpathy Agents:** receives code from Developer and Reviewer; outputs go to Developer (for fixes) or DevOps (for deployment).

## Integration with Karpathy Agents

### Workflow

```
Task Decomposer (Karpathy)
    ↓
Product Manager (Software)
    ↓
Architect (Software)
    ↓
Developer (Software)
    ↓
Reviewer (Software) ←→ Tester (Software)
    ↓
Security (Software)
    ↓
DevOps (Software)
    ↓
Agent Assigner (Karpathy)
    ↓
Progress Monitor (Karpathy)
    ↓
Quality Reviewer (Karpathy)
    ↓
Integration (Karpathy)
```

### Communication

Software agents communicate through state passing:

```python
# Product Manager → Architect
workflow.add_edge("product_manager", "architect")

# Architect → Developer
workflow.add_edge("architect", "developer")

# Developer → Reviewer
workflow.add_edge("developer", "reviewer")

# Reviewer → Tester
workflow.add_edge("reviewer", "tester")

# Tester → Developer (for fixes)
workflow.add_conditional_edges(
    "tester",
    should_fix,
    {
        "fix": "developer",
        "approve": "security"
    }
)
```

### Testing

Each Software Agent has tests covering propose/execute/evaluate:

```python
def test_product_manager():
    agent = ProductManagerAgent()
    
    # Test propose
    state = {"requirements": "Build a login page"}
    result = agent.propose(state)
    assert "user_stories" in result
    
    # Test execute
    result = agent.execute({"user_stories": [...]})
    assert "detailed_stories" in result
    
    # Test evaluate
    result = agent.evaluate({"detailed_stories": [...]})
    assert "quality_score" in result

def test_architect():
    agent = ArchitectAgent()
    
    # Test propose
    state = {"user_stories": [...]}
    result = agent.propose(state)
    assert "architecture" in result
    
    # Test execute
    result = agent.execute({"architecture": {...}})
    assert "detailed_architecture" in result
    
    # Test evaluate
    result = agent.evaluate({"detailed_architecture": {...}})
    assert "quality_score" in result

# Similar tests for Developer, Reviewer, Tester, DevOps, Security
```

## Summary

The 7 Software Agents perform the actual development, under supervision of the 8 Karpathy Agents that manage the system:

- **Product Manager** - Manages requirements
- **Architect** - Designs architecture
- **Developer** - Writes code
- **Reviewer** - Reviews code
- **Tester** - Tests code
- **DevOps** - Deploys code
- **Security** - Ensures security

**Last Updated**: July 31, 2025
