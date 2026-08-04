# Laws - Graph-Based Agent System

## Overview

These Laws govern the implementation and operation of the Graph-Based Agent System. All code, documentation, and operations **MUST** comply with these Laws. Breaches **MUST** be corrected immediately.

---

## Law 1: The Law of Specialization

### Statement
**Every agent MUST have a single, well-defined responsibility.**

### Rationale
Specialized agents are easier to understand, test, and maintain. Agents with multiple responsibilities are harder to debug and more prone to errors.

### Requirements
1. Each agent MUST do only one thing
2. Each agent MUST have a clear name that reflects its responsibility
3. Each agent MUST have explicit input and output schemas
4. Each agent MUST NOT perform tasks outside its responsibility

### Implementation
```python
# ✅ Good: Specialized agent
class TaskDecomposerAgent:
    """Decomposes requirements into structured tasks."""
    
    def decompose(self, requirements: str) -> List[Task]:
        # Only decompose requirements
        pass

# ❌ Bad: Agent with multiple responsibilities
class GeneralAgent:
    """Does everything."""
    
    def decompose(self, requirements: str):
        pass
    
    def assign(self, tasks: List[Task]):
        pass
    
    def monitor(self, progress: Progress):
        pass
```

### Validation
- Code reviews MUST check for single responsibility
- Agents with multiple responsibilities MUST be split
- Breaches MUST be corrected before merging

### Penalties
- First breach: Warning and required refactoring
- Second breach: Code review rejection
- Third breach: Temporary suspension from contributing

---

## Law 2: The Law of Permission Boundaries

### Statement
**Every agent MUST have explicit permission boundaries.**

### Rationale
Explicit permission boundaries prevent agents from acting outside their scope, reducing errors and security risks.

### Requirements
1. Each agent MUST declare READ permissions
2. Each agent MUST declare WRITE permissions
3. Each agent MUST declare NEVER permissions
4. Each agent MUST declare HUMAN_CHECKPOINT permissions
5. Agents MUST NOT breach their permission boundaries

### Implementation
```python
# ✅ Good: Explicit permission boundaries
class TaskDecomposerAgent:
    PERMISSIONS = {
        "READ": ["requirements", "project_context"],
        "WRITE": ["tasks", "metadata"],
        "NEVER": ["code", "deployment", "credentials"],
        "HUMAN_CHECKPOINT": ["ambiguous_requirements"]
    }
    
    def decompose(self, requirements: str):
        # Check permissions before acting
        if "code" in requirements:
            raise PermissionError("Cannot READ code")
        pass

# ❌ Bad: No permission boundaries
class TaskDecomposerAgent:
    def decompose(self, requirements: str):
        # No permission checks
        pass
```

### Validation
- Code reviews MUST check for permission boundaries
- Agents without permission boundaries MUST add them
- Agents that breach boundaries MUST be stopped

### Penalties
- First breach: Warning and required fix
- Second breach: Code review rejection
- Third breach: Agent disabled

---

## Law 3: The Law of Failure Handling

### Statement
**Every agent MUST handle failures properly.**

### Rationale
Proper failure handling prevents silent errors and ensures system reliability.

### Requirements
1. Agents MUST fail loudly, not silently
2. Agents MUST surface errors to humans when outside their scope
3. Agents MUST NEVER assume, always validate
4. Agents MUST implement retry logic with exponential backoff
5. Agents MUST escalate after 3 failed retries

### Implementation
```python
# ✅ Good: Proper failure handling
class TaskDecomposerAgent:
    def decompose(self, requirements: str):
        try:
            # Try to decompose
            result = self._decompose_impl(requirements)
            return result
        except ValueError as e:
            # Fail loudly
            logger.error(f"Failed to decompose: {e}")
            raise
        except Exception as e:
            # Surface to human
            logger.error(f"Unexpected error: {e}")
            raise HumanEscalationRequired(e)

# ❌ Bad: Silent failure
class TaskDecomposerAgent:
    def decompose(self, requirements: str):
        try:
            result = self._decompose_impl(requirements)
            return result
        except:
            # Silent failure
            return []
```

### Validation
- Code reviews MUST check for failure handling
- Agents with silent failures MUST be fixed
- Agents that fail to escalate MUST be corrected

### Penalties
- First breach: Warning and required fix
- Second breach: Code review rejection
- Third breach: Agent disabled

---

## Law 4: The Law of the Karpathy Loop

### Statement
**Every agent MUST implement the Karpathy Loop.**

### Rationale
The Karpathy Loop ensures agents work systematically and can recover from failures.

### Requirements
1. Agents MUST implement Propose step
2. Agents MUST implement Execute step
3. Agents MUST implement Evaluate step
4. Agents MUST implement Commit step
5. Agents MUST implement Refine step

### Implementation
```python
# ✅ Good: Karpathy Loop
class TaskDecomposerAgent:
    def run(self, requirements: str):
        # Propose
        plan = self.propose(requirements)
        
        # Execute
        result = self.execute(plan)
        
        # Evaluate
        if self.evaluate(result):
            # Commit
            return self.commit(result)
        else:
            # Refine
            refined = self.refine(plan)
            return self.run(refined)
    
    def propose(self, requirements: str):
        # Generate plan
        pass
    
    def execute(self, plan):
        # Implement plan
        pass
    
    def evaluate(self, result):
        # Check if plan worked
        pass
    
    def commit(self, result):
        # Commit if successful
        pass
    
    def refine(self, plan):
        # Refine if failed
        pass

# ❌ Bad: No Karpathy Loop
class TaskDecomposerAgent:
    def decompose(self, requirements: str):
        # No loop, just execute
        return self._decompose_impl(requirements)
```

### Validation
- Code reviews MUST check for Karpathy Loop
- Agents without Karpathy Loop MUST add it
- Agents with incomplete loops MUST complete them

### Penalties
- First breach: Warning and required implementation
- Second breach: Code review rejection
- Third breach: Agent disabled

---

## Law 5: The Law of Testing

### Statement
**All code MUST be tested.**

### Rationale
Testing ensures code quality and prevents regressions.

### Requirements
1. All functions MUST have unit tests
2. All agents MUST have integration tests
3. All edge cases MUST have tests
4. Test coverage MUST be > 80%
5. All tests MUST pass before merging

### Implementation
```python
# ✅ Good: Comprehensive testing
def test_task_decomposer():
    # Test normal case
    agent = TaskDecomposerAgent()
    result = agent.decompose("Build a login page")
    assert len(result) > 0
    
    # Test edge case
    result = agent.decompose("")
    assert len(result) == 0
    
    # Test error case
    with pytest.raises(ValueError):
        agent.decompose(None)

# ❌ Bad: No testing
# No tests
```

### Validation
- CI/CD MUST run all tests
- Code with failing tests MUST NOT be merged
- Code with low coverage MUST NOT be merged

### Penalties
- First breach: Warning and required tests
- Second breach: Code review rejection
- Third breach: Temporary suspension from contributing

---

## Law 6: The Law of Documentation

### Statement
**All code MUST be documented.**

### Rationale
Documentation ensures code is understandable and maintainable.

### Requirements
1. All modules MUST have module docstrings
2. All classes MUST have class docstrings
3. All functions MUST have function docstrings
4. All complex code MUST have inline comments
5. All APIs MUST have API documentation

### Implementation
```python
# ✅ Good: Comprehensive documentation
"""
Task Decomposer Agent Module

This module implements the Task Decomposer Agent, which decomposes
natural language requirements into structured tasks.
"""

class TaskDecomposerAgent:
    """
    Task Decomposer Agent
    
    This agent decomposes natural language requirements into structured tasks
    using LLM and MCP tools.
    
    Attributes:
        llm: LLM instance for natural language understanding
        memory: Memory instance for storing past decompositions
        tools: MCP tools for requirements parsing
    
    Example:
        >>> agent = TaskDecomposerAgent()
        >>> tasks = agent.decompose("Build a login page")
        >>> print(tasks)
        [Task(id='task_1', title='Design login page', ...)]
    """
    
    def decompose(self, requirements: str) -> List[Task]:
        """
        Decompose requirements into structured tasks.
        
        Args:
            requirements: Natural language requirements
        
        Returns:
            List of structured tasks
        
        Raises:
            ValueError: If requirements are invalid
            HumanEscalationRequired: If requirements are too vague
        
        Example:
            >>> agent = TaskDecomposerAgent()
            >>> tasks = agent.decompose("Build a login page")
        """
        pass

# ❌ Bad: No documentation
class TaskDecomposerAgent:
    def decompose(self, requirements):
        pass
```

### Validation
- Code reviews MUST check for documentation
- Undocumented code MUST NOT be merged
- Incomplete documentation MUST be completed

### Penalties
- First breach: Warning and required documentation
- Second breach: Code review rejection
- Third breach: Temporary suspension from contributing

---

## Law 7: The Law of Simplicity

### Statement
**All code MUST be as simple as possible.**

### Rationale
Simple code is easier to understand, test, and maintain.

### Requirements
1. Code MUST prefer simple solutions over complex ones
2. Code MUST avoid unnecessary abstractions
3. Code MUST avoid premature optimization
4. Code MUST follow YAGNI (You Aren't Gonna Need It)
5. Code MUST follow KISS (Keep It Simple, Stupid)

### Implementation
```python
# ✅ Good: Simple code
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

# ❌ Bad: Overly complex code
def add(a: int, b: int) -> int:
    """Add two numbers using complex abstraction."""
    class Adder:
        def __init__(self, a, b):
            self.a = a
            self.b = b
        
        def add(self):
            return self.a + self.b
    
    adder = Adder(a, b)
    return adder.add()
```

### Validation
- Code reviews MUST check for simplicity
- Overly complex code MUST be simplified
- Unnecessary abstractions MUST be removed

### Penalties
- First breach: Warning and required simplification
- Second breach: Code review rejection
- Third breach: Temporary suspension from contributing

---

## Law 8: The Law of Transparency

### Statement
**All decisions MUST be transparent.**

### Rationale
Transparency ensures accountability and trust.

### Requirements
1. All agent decisions MUST be logged
2. All system decisions MUST be documented
3. All user-facing decisions MUST be explained
4. All logs MUST be accessible
5. All documentation MUST be public

### Implementation
```python
# ✅ Good: Transparent decisions
class TaskDecomposerAgent:
    def decompose(self, requirements: str):
        # Log decision
        logger.info(f"Decomposing requirements: {requirements[:100]}")
        
        # Make decision
        tasks = self._decompose_impl(requirements)
        
        # Log result
        logger.info(f"Decomposed into {len(tasks)} tasks")
        
        return tasks

# ❌ Bad: Opaque decisions
class TaskDecomposerAgent:
    def decompose(self, requirements: str):
        # No logging
        return self._decompose_impl(requirements)
```

### Validation
- Code reviews MUST check for transparency
- Opaque decisions MUST be made transparent
- Inaccessible logs MUST be made accessible

### Penalties
- First breach: Warning and required transparency
- Second breach: Code review rejection
- Third breach: Temporary suspension from contributing

---

## Law 9: The Law of Human Oversight

### Statement
**All critical decisions MUST have human oversight.**

### Rationale
Human oversight ensures accountability and prevents errors.

### Requirements
1. Critical decisions MUST require human approval
2. Agents MUST escalate when unsure
3. System MUST provide human interface
4. Humans MUST be able to override agent decisions
5. All overrides MUST be logged

### Implementation
```python
# ✅ Good: Human oversight
class TaskDecomposerAgent:
    def decompose(self, requirements: str):
        # Check if human approval needed
        if self._needs_human_approval(requirements):
            raise HumanEscalationRequired("Requirements need human approval")
        
        # Decompose
        return self._decompose_impl(requirements)

# ❌ Bad: No human oversight
class TaskDecomposerAgent:
    def decompose(self, requirements: str):
        # No human oversight
        return self._decompose_impl(requirements)
```

### Validation
- Code reviews MUST check for human oversight
- Code without human oversight MUST add it
- Agents that bypass oversight MUST be corrected

### Penalties
- First breach: Warning and required oversight
- Second breach: Code review rejection
- Third breach: Agent disabled

---

## Law 10: The Law of Continuous Improvement

### Statement
**The system MUST continuously improve.**

### Rationale
Continuous improvement ensures the system stays relevant and effective.

### Requirements
1. System MUST collect feedback
2. System MUST analyze feedback
3. System MUST implement improvements
4. System MUST measure improvements
5. System MUST iterate

### Implementation
```python
# ✅ Good: Continuous improvement
class System:
    def __init__(self):
        self.feedback = []
        self.metrics = {}
    
    def collect_feedback(self, feedback):
        self.feedback.append(feedback)
    
    def analyze_feedback(self):
        # Analyze feedback
        pass
    
    def implement_improvements(self):
        # Implement improvements
        pass
    
    def measure_improvements(self):
        # Measure improvements
        pass
    
    def iterate(self):
        self.collect_feedback()
        self.analyze_feedback()
        self.implement_improvements()
        self.measure_improvements()

# ❌ Bad: No continuous improvement
class System:
    def __init__(self):
        # No improvement mechanism
        pass
```

### Validation
- System reviews MUST check for continuous improvement
- Systems without improvement mechanism MUST add it
- Systems that fail to improve MUST be corrected

### Penalties
- First breach: Warning and required improvement mechanism
- Second breach: System review rejection
- Third breach: System deprecated

---

## Enforcement

### Enforcement Authority
The system operators have authority to enforce these Laws.

### Enforcement Process
- **Detection**: Breaches are detected through code reviews, testing, and monitoring
- **Notification**: Offenders are notified of breaches
- **Correction**: Offenders must correct breaches
- **Verification**: Corrections are verified
- **Penalties**: Penalties are applied for repeated breaches

### Appeals
Offenders may appeal penalties to the system operators.

### Amendments
These Laws may be amended through the process defined in the Constitution.

---

## Law 11: The Law of Execution Grounding

### Statement
**No agent output MUST be accepted based on LLM self-assessment. All validation MUST be execution-grounded.**

### Rationale
LLM-as-a-Judge leads to "self-endorsement bias" where the model validates its own hallucinations. Only deterministic, execution-based verification (compilers, linters, AST parsers, pytest, JSON schema checkers) provides Ground Truth.

### Requirements
1. The `evaluate` step in ANY agent MUST NOT call an LLM
2. Validation MUST use deterministic Python code (assertions, schema checks, graph algorithms)
3. Quality scores MUST be mathematically computed, not LLM-estimated
4. The Executor (LLM) and the Grader (Validator) MUST be completely separated
5. Only outputs that pass execution-grounded checks MAY be committed to memory

### Implementation
```python
# ✅ Good: Execution-Grounded Validation (Zero LLM)
def evaluate(state):
    breaches = DeterministicValidatorEngine.validate_schema(
        state["output"], required_keys=["tasks", "metadata"]
    )
    score = DeterministicValidatorEngine.calculate_quality_score(breaches)
    return {"success": len(breaches) == 0 and score >= 0.8}

# ❌ Bad: LLM-as-a-Judge
def evaluate(state):
    response = call_llm("Is this output correct? " + str(state["output"]))
    return {"success": "yes" in response.lower()}
```

### Validation
- Code reviews MUST verify that `evaluate` steps contain zero LLM calls
- Any `evaluate` step that invokes an LLM MUST be immediately refactored

### Penalties
- First breach: Mandatory refactoring to deterministic validation
- Second breach: Agent disabled until fixed
- Third breach: Agent removed from the system

---

## Law 12: The Law of Context Sanitation

### Statement
**Every LLM invocation MUST receive a sanitized, budget-aware context. Failed attempts and noise MUST NEVER pollute the context window.**

### Rationale
Context Rot (silent degradation from accumulated noise in the context window) is the primary cause of LLM behavioral drift. The context window is finite RAM — it must be managed like a precious computational resource.

### Requirements
1. Raw inputs MUST be sanitized before reaching any LLM (strip tracebacks, excess whitespace, stale logs)
2. Failed Karpathy Loop iterations MUST NOT be fed back into the context
3. Only the sanitized prompt + clean state MUST enter the LLM context window
4. Historical logs MUST be compacted to a maximum of 3 recent entries
5. Signal-to-Noise Ratio MUST be computed and monitored for every LLM call
6. Only outputs that passed ALL deterministic gates (Law 11) MAY be stored in long-term memory

### Implementation
```python
# ✅ Good: Context Sanitation before LLM invocation
sanitized = ContextCuratorEngine.sanitize_raw_text(raw_prompt)
compacted = ContextCuratorEngine.compact_history_logs(logs, max_items=3)
stn_ratio = ContextCuratorEngine.calculate_signal_to_noise(raw_prompt, sanitized)

# Only feed sanitized context to LLM
response = call_llm(sanitized, system_prompt)

# ❌ Bad: Dumping everything into LLM context
response = call_llm(raw_prompt + "\n" + full_history + "\n" + error_logs)
```

### Validation
- Code reviews MUST verify that Context Curator Agent precedes all LLM invocations
- Direct LLM calls with unsanitized input MUST be rejected

### Penalties
- First breach: Mandatory Context Curator integration
- Second breach: Code review rejection
- Third breach: Agent disabled until pipeline compliance is verified

---

## Law 13: The Law of Surgical Refinement

### Statement
**When an agent output fails validation, refinement MUST be targeted and surgical. Full regeneration is PROHIBITED.**

### Rationale
Full regeneration wastes tokens, destroys correct partial work, and increases the probability of introducing new errors. Karpathy's "Surgical Changes" principle mandates that only the specific failing component be corrected.

### Requirements
1. The Surgical Refiner MUST extract exact failing keys from the validation report
2. Refinement instructions MUST specify ONLY what to fix, not regenerate the entire output
3. Maximum 3 surgical refinement attempts before escalation to HUMAN_CHECKPOINT
4. Each refinement attempt MUST carry forward the correct parts of the previous output
5. The refinement feedback MUST contain the word "SURGICAL CORRECTION REQUIRED" as a hard invariant

### Implementation
```python
# ✅ Good: Surgical, targeted refinement
feedback = SurgicalRefinerEngine.generate_surgical_instructions(
    breaches=["Missing mandatory schema key: 'metadata'"],
    failing_keys=["metadata"]
)
# Output: "SURGICAL CORRECTION REQUIRED: Fix ONLY 'metadata' key. Do NOT regenerate unchanged parts."

# ❌ Bad: Full regeneration
feedback = "The output was wrong. Please try again from scratch."
```

### Validation
- Code reviews MUST verify that refinement steps are targeted (not full regeneration)
- Refinement prompts without "SURGICAL CORRECTION" invariant MUST be rejected

### Penalties
- First breach: Mandatory refactoring to surgical refinement
- Second breach: Code review rejection
---

## Law 14: The Law of Signal Determinism

### Statement
**All inter-agent control flow MUST be driven by deterministic, typed signals. The control plane (routing, dispatch, retry policy) MUST contain zero LLM calls.**

### Rationale
The `kernel/signal_protocol.py` `AgentSignal` schema is the single contract every agent emits on completion. If routing were delegated to an LLM (e.g. "decide the next agent"), the control plane would become non-deterministic, un-auditable, and impossible to replay. A deterministic signal bus is what makes the system a *graph* rather than a chat.

### Requirements
1. Every agent MUST emit exactly ONE typed `AgentSignal` on completion (success / failure / alert / terminal).
2. The `DispatchKernel` MUST route via a static `ROUTING_TABLE` lookup — `route(signal)` returns the next agent name with no model involvement.
3. Retry budgets (`FAILURE_POLICY`) MUST be evaluated deterministically per agent, never by LLM judgment.
4. Unknown signal types MUST raise `ValueError` at construction time, not fail silently at route time.

### Implementation
```python
# ✅ Good: deterministic routing, zero-LLM
ROUTING_TABLE = {"TASK_DECOMPOSED": "deterministic_validator", ...}
def route(self, signal: AgentSignal) -> str:
    return ROUTING_TABLE.get(signal.signal_type, "human_checkpoint")
```

### Validation
- Code reviews MUST verify `route()` contains no `call_llm`.
- Any dynamic/LLM-based next-step selection MUST be rejected.

### Penalties
- First breach: Mandatory refactor to static `ROUTING_TABLE`.
- Second breach: Code review rejection.
- Third breach: Router disabled until compliant.

---

## Law 15: The Law of Latency Budget

### Statement
**No pipeline stage MAY block indefinitely. Every LLM-bound and IO-bound stage MUST respect a bounded latency budget with global pacing.**

### Rationale
The Stepfun per-account quota admits only ~2-3 concurrent requests before returning 429 for tens of seconds. Unbounded per-call retry (0.5s base) burns its attempts in ~2s and marks instances INFRA-FAIL. A *global* token-bucket limiter (`llm/llm_integration.py::_acquire_rate_token`) is the control that keeps the whole process within quota.

### Requirements
1. LLM calls MUST acquire a global rate token before issuing a request.
2. Retry budgets MUST be global across worker threads, not per-call (per-call budgets multiply latency without a ceiling).
3. The kernel MUST enforce a wall-clock ceiling for the full pipeline run.
4. Timeout values MUST be explicit on every transport boundary (HTTP, subprocess, worktree).

### Implementation
```python
# ✅ Good: global token bucket paces all workers
def _acquire_rate_token():
    while True:
        with _RATE_LIMIT_LOCK:
            # refill lazily, sleep until a token is available
            ...
        time.sleep(min(wait, 1.0))
```

### Validation
- Code reviews MUST verify that no unbounded `while`/`for` loop issues LLM calls without a global limiter.
- Load tests MUST confirm no deadlock under N parallel workers.

### Penalties
- First breach: Mandatory integration with the global limiter.
- Second breach: Code review rejection.

---

## Law 16: The Law of Reproducible Evidence

### Statement
**Every quality claim about the system MUST be backed by physically-executed evidence, never by model self-report.**

### Rationale
LLM-as-a-judge produces self-endorsement bias. A system "graded" by the same model that generated the output is not measured — it is flattered. Ground truth comes only from deterministic execution: `pytest` exit codes, `git apply --check`, AST parsing, JSON-schema assertions.

### Requirements
1. Benchmark scores MUST come from subprocess execution of generated code against real test suites.
2. Failure taxonomy MUST separate `capability` (model error) from `infrastructure` (429/timeout) — never conflate them.
3. Raw and infra-adjusted numbers MUST both be published.
4. Predictions MUST be graded by an external oracle (official SWE-bench harness, official HumanEval tests), not by the system under test.

### Implementation
```python
# ✅ Good: external oracle grades, not the model
score = run_tests_in_worktree(patch, instance)  # pytest FTP/PTP, same signal as the grader
```

### Validation
- Code reviews MUST verify benchmark harnesses invoke a real test runner, not `call_llm("is this correct?")`.
- Any report citing model-stated scores MUST be rejected.

### Penalties
- First breach: Mandatory re-run with physical execution.
- Second breach: Report rejected.

---

## Law 17: The Law of Subsystem Context Isolation

### Statement
**No squad agent MUST receive context from an unrelated subsystem. Cross-domain context MUST be filtered by the Domain Context Manager before prompt assembly.**

### Rationale
Context Rot and token dilution occur when unrelated subsystem details (such as HTML/CSS styling or database indexes) are fed into specialized backend or authentication prompts. Subsystem isolation preserves maximum reasoning capability.

---

## Law 18: The Law of Architectural Blueprint Precedence

### Statement
**No Code Agent MAY generate source code until the Architect Planner and DB Squad have committed verified AST blueprints.**

### Rationale
Generating isolated code modules without an overarching architectural blueprint leads to disjointed code, conflicting function signatures, and integration failures.

---

## Law 19: The Law of Session Handoff Grounding

### Statement
**Session handoffs MUST be validated against physical file checksums and AST hashes on disk. Restoring session state based on unverified LLM summaries is STRICTLY PROHIBITED.**

### Rationale
LLM summaries of past session states introduce cumulative hallucination across long development sessions. Only cryptographic SHA-256 code hashes and AST structural summaries provide empirical Ground Truth.

---

## Law 20: The Law of Squad Specialization

### Statement
**An agent assigned to a domain squad MUST NOT perform tasks belonging to another squad. Cross-domain execution attempts MUST trigger an instant permission exception.**

### Rationale
Strict permission boundaries prevent agent scope creep and enforce single-responsibility governance across the hierarchical architecture.

---

## Enforcement

### Enforcement Authority
The system operators have authority to enforce these Laws.

### Enforcement Process
- **Detection**: Breaches are detected through code reviews, testing, and monitoring
- **Notification**: Offenders are notified of breaches
- **Correction**: Offenders must correct breaches
- **Verification**: Corrections are verified
- **Penalties**: Penalties are applied for repeated breaches

### Appeals
Offenders may appeal penalties to the system operators.

### Amendments
These Laws may be amended through the process defined in the Constitution.

---

**Last Updated**: August 1, 2025

**Version**: 2.0

**Status**: Ratified

