# Finding: The Inert Registry — reasoning is built, then never connected

**Date:** 2026-08-08
**Measured by:** orchestrator (Hermes), verified directly against source at HEAD
**Status:** VERIFIED — reproducible by the script in §4

---

## 0. Why this file exists

Fares's diagnosis, which this measurement was built to test:

> "we are not yet capturing the good reasoning and the strong parts, connecting them,
> carrying them forward, growing and widening them"

He rejected the framing "either the architecture was never the bottleneck, or the generator
is the ceiling" as a false dilemma. This document reports what was found when the repo was
measured for **transport of reasoning** instead of resolve rate.

---

## 1. Headline

**11 of 28 registered agents (39%) are never reached on the main pipeline.** They are registered in
`system/agent_registry.py`, they have lifecycle docs, they have passing tests, they are
counted by governance conformance checks — and nothing on a real execution path calls them.

Two distinct kinds, and the difference matters:

**(a) DIRECTLY INERT — 8 agents.** The declared `entrypoint` has zero real call sites.

| Module | Declared entrypoint |
|---|---|
| `decision_conflict_agent` | `resolve_conflicts()` |
| `human_escalation` | `handle_escalation()` |
| `domain_squads` | `AuthSquadAgent()` |
| `competitive_slice` | `run_competitive_slice()` |
| `episodic_memory_agent` | `store_episode()` |
| `semantic_memory_agent` | `extract_semantic_rule()` |
| `working_memory_agent` | `assemble_working_memory()` |
| `competitive_context_manager` | `CompetitiveContextManager()` |

**(b) TRANSITIVELY INERT — 3 more agents.** These *are* called — but **only from inside a
directly-inert module**, so the call never actually happens. Whole dead chains, not dead nodes.

| Module | Called from | Which is itself |
|---|---|---|
| `domain_context_managers` (+6 subclasses) | `domain_squads.py:71,101,128,154` | INERT |
| `debugger_agent` | `competitive_slice` | INERT |
| `sampling_agent` | `competitive_slice` | INERT |

**`reflexion_agent` is NOT inert — correction, see §3c.** An earlier revision of this file
listed it here. It is reachable from the benchmark harness
(`benchmarks/swebench_harness.py:834`, imported under an alias) and is the one dimension the
project already measured as firing.

The finding that survives verification:

- **All three memory agents are inert.** A system whose declared purpose includes carrying
  knowledge forward has its entire memory tier disconnected from the main pipeline. This is
  the single most consequential item in this document.

`domain_context_managers` shows why chain analysis is required: it has 6 subclasses and 4 real
call sites, so any per-node check calls it healthy. Every one of those calls originates in
`domain_squads`, which nothing invokes.

---

## 2. The mechanism — why this was invisible

The registry stores agents as **metadata strings**, not callable references
(`system/agent_registry.py:236-246`):

```python
{
    "name": "Semantic Memory Agent",
    "module": "agents.semantic_memory_agent",   # a STRING
    "entrypoint": "extract_semantic_rule",      # a STRING
    "lifecycle_doc": "docs/agents/semantic-memory-agent.md",
    "test_file": "tests/test_semantic_memory_agent.py",
}
```

The only code that resolves those strings is `system/governance_checks.py:88,143`, which
calls `importlib.import_module(...)` **to confirm the module and symbol exist** — a
conformance check, not an invocation.

So the agent is simultaneously:
- **present** to the registry,
- **valid** to governance,
- **covered** by a test,
- and **absent** from every run.

Every accounting surface reports health while nothing flows. This is the precise sense in
which "wiring is not flowing."

---

## 3. Why this matters more than the 1/8 resolve rate

The arms all measured *output quality* of one path. This measures *whether the other paths
exist at runtime at all*. Consequences:

1. **The 1/8 ceiling was never a fair test of the architecture**, because a third of the
   architecture was not participating. Neither "the graph works" nor "the model is the
   ceiling" was actually tested.
2. **Adding dimensions could not have helped.** New agents were added to a structure whose
   existing agents were already disconnected — growth by registration, not by connection.
   This is the mechanical explanation for applicability rising (3→4→5→7) while resolve rate
   stayed flat: work was added to the path that runs, and reasoning kept being stranded on
   the paths that do not.
3. **Test coverage actively concealed it.** 3 modules have tests and zero production callers
   (`prime_agent_adapter` 327 LOC / 6 test refs; `cynefin_classifier` 134 / 2;
   `intelligence_forge_demo` 89 / 1). A green suite was evidence of nothing.

---

## 3b. Method correction — the first pass was itself defective

The first version of this document reported 9/28 from a `grep` scan. That pass was wrong in
both directions, and the corrections are recorded here because the project rule is to measure
the apparatus before trusting its output.

| Defect in the grep pass | Effect |
|---|---|
| Matched `entrypoint(` textually, so a class entrypoint invoked via its **subclasses** looked uncalled | **False positive:** `domain_context_managers` was reported inert; it has 6 subclasses with 4 real call sites |
| Never asked whether a caller is *itself* reached | **False negatives:** 4 agents (`debugger_agent`, `sampling_agent`, `reflexion_agent`, `domain_context_managers`) were counted LIVE while their only callers are inert |

The AST pass resolves classes to their transitive subclasses and then propagates inertness
through the call chain. Net effect: 9 → **12**, and the qualitative finding got worse, not
better — `reflexion_agent` only shows up as unreachable once chains are followed.

A subagent was independently instrumenting the same 28 entrypoints with runtime counters while
this was written; its early output (`domain_context_managers` concrete classes invoked 4×) is
what exposed the grep defect. Two independent instruments disagreeing is what caught this.
Neither static pass is authoritative on its own — the runtime table in
`INVOCATION-TABLE.md` supersedes both where they conflict.

## 3c. Runtime evidence — and a second defect in my own analysis

All 28 entrypoints were wrapped with runtime counters (`tools/invocation_counter/`,
`wrapped_count=28`, `failed_to_wrap={}`) and observed in two conditions.

| Condition | Entrypoints that fired | What it proves |
|---|---|---|
| **Under the test suite** | **28 / 28** | Nothing is broken or unimportable. Every agent works when called. |
| **On a real pipeline run** | **3 / 28** | `task_decomposer`, `context_curator`, `karpathy_pipeline` — the pipeline entered, then died. |

Two things must not be read out of this table:

**(1) The real run is not evidence about the other 25.** It aborted on its *first* LLM call —
three consecutive Stepfun read timeouts, then `StepfunAPIError`, total log length 5 lines. The
run never reached the stages where the remaining agents would be called. This is an
**infra failure, not a capability failure**, and per the project's measurement discipline it
must not be counted as one. The real-run column needs a successful run to mean anything.

**(2) 28/28 under tests does not refute the inert finding — it is the finding.** The tests call
these entrypoints *directly*. That is precisely what "registered, conformant, covered, and
never actually invoked" means: the only thing exercising them is the accounting layer. Verified
per module — for `semantic_memory_agent`, `working_memory_agent`, `episodic_memory_agent`,
`human_escalation`, the complete set of non-test referrers is
`system/agent_registry.py` (metadata) and `system/governance_checks.py` (importlib existence
check). No caller on any production path.

**Defect found in my AST pass:** `reflexion_agent` is imported in
`benchmarks/swebench_harness.py:834` as `from agents.reflexion_agent import generate_reflection
as _gr`. Name-based AST matching cannot see through the **alias rebind**, so I wrongly counted
it transitively inert. Corrected: 12 → **11**. Any future pass must resolve import aliases;
the counter harness already tracks this (`alias_rebinds`), which is why it disagreed with me.

Score of my own instruments across this investigation: the grep pass was wrong in two ways,
the AST pass in one more. Every correction was produced by an *independent* instrument
disagreeing, never by re-reading my own output.

## 4. Reproduction

```python
# AST pass: resolves class entrypoints to subclasses, then propagates inertness
# through call chains. Run from the repo root.
import ast, os, re
ROOT = "/home/fares/Projects/graph-based-agent-system"
os.chdir(ROOT)
reg = open("system/agent_registry.py", encoding="utf-8").read()
entries = re.findall(r'"module":\s*"agents\.(\w+)".*?"entrypoint":\s*"(\w+)"', reg, re.S)

trees = {}
for d, _, fs in os.walk("."):
    if "__pycache__" in d or "/.git" in d or "/.venv" in d:
        continue
    for f in fs:
        if f.endswith(".py"):
            p = os.path.join(d, f)
            try:
                trees[p] = ast.parse(open(p, encoding="utf-8", errors="replace").read())
            except Exception:
                pass

# accounting surfaces: registration/conformance/tests are NOT execution
EXCL = ("system/agent_registry.py", "system/governance_checks.py", "system/self_pruning.py",
        "agents/context_system_view.py", "agents/agent_forge.py")
acct = lambda p: p.startswith("./tests/") or any(e in p for e in EXCL)

def names_for(mod, ep):
    """A class entrypoint is 'called' via any transitive subclass."""
    t = trees.get(f"./agents/{mod}.py")
    if not t or not any(isinstance(n, ast.ClassDef) and n.name == ep for n in ast.walk(t)):
        return {ep}
    subs, changed = {ep}, True
    while changed:
        changed = False
        for tt in trees.values():
            for n in ast.walk(tt):
                if isinstance(n, ast.ClassDef):
                    for b in n.bases:
                        bn = getattr(b, "id", None) or getattr(b, "attr", None)
                        if bn in subs and n.name not in subs:
                            subs.add(n.name); changed = True
    return subs

prod = {}
for mod, ep in entries:
    names, hits = names_for(mod, ep), []
    for p, t in trees.items():
        if p == f"./agents/{mod}.py" or acct(p):
            continue
        for n in ast.walk(t):
            if isinstance(n, ast.Call):
                fn = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
                if fn in names:
                    hits.append(p)
    prod[mod] = hits

inert = {m for m, h in prod.items() if not h}
while True:  # a caller that is itself inert does not count as a caller
    grew = {m for m, h in prod.items() if m not in inert and h and
            {c.replace("./agents/", "").replace(".py", "") for c in h if c.startswith("./agents/")}
            and {c.replace("./agents/", "").replace(".py", "") for c in h
                 if c.startswith("./agents/")} <= inert}
    if not grew:
        break
    inert |= grew

print(f"not reached at runtime: {len(inert)}/{len(entries)}")
for m in sorted(inert):
    print("  ", m, "(direct)" if not prod[m] else "(transitive)")
```

---

## 5. Correction to a subagent's report

`P7-AGENT-AUDIT.md` (written by a delegated subagent) lists 10 "removal candidates"
including the memory agents. **Independent re-measurement does not support removal as the
conclusion.** Only 3 modules have zero callers of any kind; the memory agents are *reachable*
through the registry but *inert* at runtime.

The distinction changes the remedy completely:

- unreachable ⇒ delete it
- **inert ⇒ CONNECT it** — the capability was built and then stranded

Deleting the memory tier would destroy exactly the machinery needed to carry reasoning
forward. That subagent report must not be actioned as written. (Recorded per the standing
rule that a subagent summary is a self-report, not evidence.)

---

## 6. What this does NOT prove

- Not proven that connecting these agents raises any score. That needs a runtime measurement.
- Static call-graph analysis only; a dynamic dispatch path could exist that grep cannot see
  (none found beyond the governance conformance import).
- Says nothing about whether each inert agent is individually *worth* connecting.

**Next instrument (per the amended growth rule, falsifier declared in advance):** add
per-agent invocation counters, run the existing suites, and publish an invocation table.
Falsifier: if the inert agents show non-zero invocations at runtime, this finding is wrong
and must be retracted.
