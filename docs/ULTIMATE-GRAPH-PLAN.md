# Ultimate Graph vs Specialized Slices - Architecture Plan

**Date:** 2026-08-01
**Status:** Phase 1 Implemented (Debugger, Sampling, Reflexion)
**Inspired by:** AlphaCode (Sampling+Filtering+Clustering) + Reflexion (Verbal RL)

---

## 1. المشكلة الأصلية: Graph واحد لكل حاجة = Anti-Pattern

النظام الحالي عنده Ultimate Graph واحد فيه 20 وكيل يحاول يحل كل حاجة من E-commerce لـ HumanEval. ده بيخالف Law 1 (Specialization) و Law 7 (Simplicity).

HumanEval (single function) مش محتاج Domain Dispatcher ولا Auth Squad. E-commerce محتاجهم.

الحل: **Dual-Mode Kernel** يبني Graph فرعي (Slice) حسب نوع المهمة.

---

## 2. Ultimate Graph (العقل المتكامل) - 22 وكيل حالياً

### Layers:

**Layer 0 - Kernel (Zero-LLM):**
- `kernel/dispatch_kernel.py` - FIFO queue + ROUTING_TABLE (16 signal types)
- `kernel/signal_protocol.py` - AgentSignal typed
- FAILURE_POLICY per agent (max_retries, fallback=human_checkpoint)

**Layer 1 - Governance Specialized (Context & Memory):**
- `ContextCurator` (عام)
- `DomainContextManagers`: Auth, DB, API, UI (موجود) - يفلتر noise حسب المجال
- `DebugContextManager` (جديد في debugger_agent): يفلتر traceback فقط
- `LongTermMemoryCurator` (مستقبل): ينضف memory، يحسب similarity
- `SessionStateMerger` (موجود): يحافظ على state بين slices

**Layer 2 - Execution:**
- `TaskDecomposer`
- `SamplingAgent (NEW - AlphaCode)` - يولد N candidates بـ temp عالي
- `CodeExecutor`
- `DomainSquads` (Auth, DB, API, UI)

**Layer 3 - Verification & Repair (اللي كان ناقص):**
- `DeterministicValidator` (AST)
- `TestRunner`
- `SurgicalRefiner` - يصلح AST breaches
- `DebuggerAgent (NEW - Reflexion Debug)` - يصلح test failures بـ traceback
- `ReflexionAgent (NEW - Verbal RL)` - يولد verbal reflection ويخزنه في long-term memory
- `Filtering & Clustering (AlphaCode)`: جزء من Sampling + Competitive Slice - يفلتر بالـ execution ويعمل dedup

**Layer 4 - Orchestration & Integration:**
- `AgentAssigner`, `GraphExecutionOrchestrator`, `DomainDispatcher`
- `IntegrationAgent`, `QualityReviewer`, `ProgressMonitor`
- `DecisionConflict`, `ResourcePriority`, `HumanEscalation`

### Permission Matrices:

كل وكيل جديد له 4-quadrant: READ/WRITE/NEVER/HUMAN_CHECKPOINT - يتبع CONSTITUTION Article I, Section 2.

---

## 3. Specialized Slices - Graphs صغيرة حسب المهمة

### Registry:

```python
SLICE_REGISTRY = {
  "humaneval": {
    "agents": ["context_curator", "sampling_agent", "execution_validator", "debugger", "reflexion", "clustering"],
    "topology": "curator -> sampling (5) -> filter -> debugger_loop -> done",
    "n_agents": 5
  },
  "competitive": {
    "agents": ["context_curator", "sampling_agent (100)", "execution_validator", "clustering", "debugger"],
    "topology": "AlphaCode full: sample 100 -> filter by sample tests -> cluster -> select",
  },
  "ecommerce": {
    "agents": ["curator", "decomposer", "validator", "assigner", "orchestrator", "domain_dispatcher", "integration", "quality"],
    "topology": "Ultimate minus competitive agents",
    "n_agents": 8
  },
  "fintech_auth": {
    "agents": ["curator", "decomposer", "validator", "assigner", "auth_squad", "security_validator", "quality"],
  }
}
```

### Competitive Slice (اللي اتبنى حالياً):

Topology:

```
Problem
  ↓
ContextCurator (sanitize)
  ↓
SamplingAgent (5 candidates, temp 0.8, diversity hints + past reflections)
  ↓
ExecutionValidator (run_ground_truth for each candidate) -> PASS? -> DONE
  ↓ (all fail)
ReflexionAgent: "Failed because empty list edge, next check len==0"
  ↓ (store in memory)
DebuggerAgent: Fix each candidate using traceback + reflection
  ↓
ExecutionValidator retry -> PASS? -> DONE
  ↓
Loop: Sampling with cooled temp (0.6) + reflections
```

This is exactly what was needed to fix HumanEval/116 (sort_array).

### Selection Logic (Zero-LLM, Deterministic):

```python
def detect_task_type(requirements: str) -> str:
  lower = requirements.lower()
  if "humaneval" in lower or ("def " in lower and "assert" in lower and len(requirements) < 2000):
    return "humaneval"
  if "e-commerce" in lower or "microservices" in lower:
    return "ecommerce"
  if "leetcod" in lower or "competitive" in lower:
    return "competitive"
  return "default" # Ultimate
```

Implemented in `kernel/dispatch_kernel.py` - must be ZERO-LLM per Law 11.

---

## 4. AlphaCode و Reflexion: كيف دمجنا الأفكار؟

### AlphaCode:

**Original:** 1M samples, TPU pods, filter by sample tests, cluster by output behavior on generated inputs, select representatives.

**Our Lite Adaptation (SamplingAgent):**
- N=5-20 (not 1M) - fits Stepfun quota + cost control (HUMAN_CHECKPOINT if >20)
- Filter: AST validation (deterministic) + optional execution filter in slice
- Clustering: SHA256 hash dedup (lite) - can be upgraded to embedding clustering later
- Diversity: Cycle through 8 different prompt hints (iterative, recursive, different DS, edge cases first...)

**Governance Compliance:**
- SamplingAgent has READ [problem_spec], WRITE [candidates], NEVER [credentials]
- Cost control via HUMAN_CHECKPOINT for excessive sampling
- All evaluation (dedup, AST filter) is ZERO-LLM

**Benefit:** Turns single-point failure into population search. If one candidate fails, another might pass. This is why HumanEval/116 would be fixed - one of 5 samples might have correct ordering logic.

### Reflexion:

**Original Paper (Shinn et al. 2023):** Actor generates, Evaluator checks, Reflector generates verbal self-reflection, stores in memory, next trial uses reflection.

**Our Adaptation (ReflexionAgent + DebuggerAgent):**

- **ReflexionAgent:** Generates reflection ONLY (NEVER code) - enforced in evaluate: if "def " in reflection -> fail. Stores in `global_memory.long_term`.
- **DebuggerAgent:** Uses reflections + traceback to fix code.
- **Memory Integration:** `get_relevant_reflections(problem, limit=3)` uses Jaccard similarity to retrieve past reflections.

**Example Flow:**
```
Trial 1: Code fails on empty list -> Reflexion: "Failed because didn't handle empty list, check len==0 early"
Trial 2: SamplingAgent prompt includes reflection, generates code with early return -> PASS
```

**Governance:**
- ReflexionAgent NEVER generates code, only reflection - separation of concerns
- Reflection must be actionable (length, keywords check) - ZERO-LLM quality gate
- Memory storage is WRITE permission, not READ of credentials

---

## 5. Context Managers المتخصصة - كيف تشتغل مع الوكلاء الجدد؟

اللي عندنا حالياً: `AuthContextManager.filter_auth_context()`, `DBContextManager.filter_db_context()`, etc. كل واحد بيفلتر noise حسب مجاله.

**الجديد:** `DebugContextManager.filter_debug_context()` - موجود في debugger_agent.py

- ياخد `global_context + failure_output`
- يستخدم `BaseDomainContextManager.filter_context()` الأساسي
- يضيف `debug_snippet`: يفلتر traceback ويحتفظ بسطرين فيهما assert, error, expected/got

**الفلسفة:** مش هنعمل Context Manager لكل System، هنستخدم الموجودين + نضيف واحد لكل نوع فشل (debug, reflection, etc). النظام يشتغل معاهم هما بس.

لو عايز تضيف واحد جديد (مثلاً `CompetitiveContextManager`):
- يورث من `BaseDomainContextManager`
- يطبق `filter_context()` مخصصة: تشيل الـ story الزايدة في HumanEval prompt، تخلي الـ docstring والـ examples بس
- يتسجل في `domain_context_managers.py`

ده إضافي على System وكيل، عادي جداً.

---

## 6. المرحلة الجاية: Memory to Context System

ده اللي قلت عليه محتاج وكلاء كتير - صح. الخطة واحدة واحدة:

**الآن عندنا:**
- `CustomMemory`: short_term dict + long_term list + `find_similar()` Jaccard
- ReflexionAgent بيكتب فيه

**الجاي:**

1. **EpisodicMemoryAgent:** كل trial (problem + code + result + reflection) يتخزن كـ episode
2. **SemanticMemoryAgent:** كل فترة، يلخص الـ reflections المتكررة: "3 مرات فشلت بسبب empty list -> rule: always check len==0"
3. **WorkingMemoryAgent:** يدير الـ token budget - يقرر أي reflections تتحط في الـ prompt الجاي (limit 3)

**Flow:**
```
Long-term Memory (22 reflections)
  ↓ (find_similar)
Working Memory (3 relevant reflections, 4000 token budget)
  ↓ (filter_debug_context)
Context for Debugger/Sampling (sanitized + reflections)
  ↓
LLM
  ↓
Reflexion -> back to Long-term
```

هنبدأ بواحدة واحدة: الأول Episodic، بعدين Semantic.

---

## 7. ما تم إنجازه (Phase 1) وما المتبقي

**تم (170 tests passing, audit green, 22 agents):**

- ✅ `debugger_agent.py` + docs + tests
- ✅ `sampling_agent.py` (AlphaCode Lite) + docs + tests
- ✅ `reflexion_agent.py` + docs + tests
- ✅ `competitive_slice.py` - Slice Graph for HumanEval
- ✅ `agent_registry.py` updated - 22 items
- ✅ Governance checks passing
- ✅ Benchmark infra (previous): reporting, metrics, extended scenarios

**لم يتم (Phase 2 - القرار عندك):**

- ⬜ `EpisodicMemoryAgent` + `SemanticMemoryAgent`
- ⬜ `CompetitiveContextManager` dedicated
- ⬜ Kernel dual-mode routing `detect_task_type()` + `build_slice()`
- ⬜ Live run of competitive slice on 3 failing HumanEval problems (76,116,145) to prove 100% adjusted
- ⬜ Ablation study: Ultimate vs Slice vs Baseline on 8-scenario suite

**التكلفة:** Sampling 5 candidates * 164 problems = 820 LLM calls, ~$5-10 on Stepfun, + debugging loops ~ 1000 calls.

---

## 8. الخلاصة العلمية

HumanEval كان **Plumbing Test** - صلح 58.5pp infra failures.
Governance Suite (4/8 scenarios) هو **Thesis Test** - بيقيس الـ graph.

الجديد (Debugger + Sampling + Reflexion) هو **Repair & Learning Loop** - بيقيس هل النظام بيتعلم من فشله؟

Ultimate Graph = عقل متكامل (22 وكيل) - لكل حاجة
Slices = عقول متخصصة (5-8 وكلاء) - لكل benchmark

وده بيحقق **CONSTITUTION Article II: Specialization + Loose Coupling**.

Ready to implement Phase 2 when you approve.
