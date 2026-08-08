#!/usr/bin/env python3
"""Decomposition benchmark — measures the claim SWE-bench cannot isolate.

WHY THIS EXISTS
---------------
SWE-bench scores a single end-to-end number: patch applies and the gold test passes.
When a graph arm loses to a flat arm there, the result cannot say WHICH capability failed
— localization, decomposition, repair, or transport. This suite isolates ONE capability:
given a compound request, does the system break it into the right units, in an order that
respects the dependencies between them?

That is the architectural hypothesis in its purest testable form. If constraints live in
the TOPOLOGY rather than in a prompt, then a task with 8 interdependent units should be
decomposed correctly by a system whose structure encodes ordering — and a flat single-shot
arm should degrade as the dependency depth grows.

GRADING IS PROGRAMMATIC
-----------------------
No LLM judges anything. Each fixture declares:
    required   concepts that MUST appear as separate units (semantic keyword sets)
    ordering   pairs (a, b) where a must be sequenced before b
    forbidden  concepts that must NOT be merged into one unit
Scoring is set arithmetic and index comparison over the produced plan. An LLM-as-judge
here would let the system grade its own homework, which this project already rejected
elsewhere; the same standard applies to a new suite.

METRICS
-------
coverage        fraction of required units present                     [0,1]
order_accuracy  fraction of ordering constraints satisfied             [0,1]
separation      fraction of forbidden merges avoided                   [0,1]
granularity     penalty for dumping everything into one unit, or for
                exploding into trivia (deviation from the fixture's expected count)
composite       mean of the four — the headline number per fixture

DIFFICULTY LADDER
-----------------
Fixtures are tiered by dependency depth (1..4). Reporting per-tier is the point: a flat
arm and a graph arm often tie at depth 1 and separate at depth 3+. A single averaged
number would hide exactly the effect being tested.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from statistics import mean

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

RESULTS = os.path.join(ROOT, "benchmarks", "results")


# ---------------------------------------------------------------------------
# FIXTURES — hand-built, dependency-labelled compound tasks.
# Each `required` entry is a set of synonyms: a unit satisfies it if ANY synonym
# appears. This tolerates wording differences without tolerating missing work.
# ---------------------------------------------------------------------------

FIXTURES: list[dict] = [
    {
        "id": "auth-service",
        "tier": 2,
        "expected_units": 6,
        "request": (
            "Build a user authentication service: users register with email and password, "
            "log in to receive a JWT, and can reset a forgotten password by email. "
            "Passwords must be hashed. Add tests."
        ),
        "required": [
            {"schema", "model", "table", "database", "migration"},
            {"register", "signup", "sign up", "registration"},
            {"hash", "bcrypt", "argon", "password storage"},
            {"login", "sign in", "signin", "authenticate"},
            {"jwt", "token", "session"},
            {"reset", "forgot", "recovery"},
            {"test", "tests", "testing"},
        ],
        "ordering": [
            ({"schema", "model", "table", "migration"}, {"register", "signup", "registration"}),
            ({"register", "signup", "registration"}, {"login", "sign in", "authenticate"}),
            ({"login", "sign in", "authenticate"}, {"jwt", "token"}),
        ],
        "forbidden_merges": [
            ({"register", "signup"}, {"login", "sign in"}),
            ({"hash", "bcrypt"}, {"reset", "forgot"}),
        ],
    },
    {
        "id": "csv-etl",
        "tier": 1,
        "expected_units": 4,
        "request": (
            "Write a script that reads a CSV of sales records, validates that each row has "
            "a positive amount and a valid ISO date, aggregates totals per region, and "
            "writes the result to JSON."
        ),
        "required": [
            {"read", "parse", "load", "ingest"},
            {"validate", "validation", "check"},
            {"aggregate", "group", "sum", "total"},
            {"write", "output", "export", "json"},
        ],
        "ordering": [
            ({"read", "parse", "load"}, {"validate", "validation"}),
            ({"validate", "validation"}, {"aggregate", "group", "sum"}),
            ({"aggregate", "group", "sum"}, {"write", "output", "export"}),
        ],
        "forbidden_merges": [
            ({"validate", "validation"}, {"aggregate", "group"}),
        ],
    },
    {
        "id": "rate-limited-api",
        "tier": 3,
        "expected_units": 7,
        "request": (
            "Add rate limiting to an existing REST API. It must be per-API-key, use a "
            "sliding window, be backed by Redis so it works across multiple server "
            "processes, return HTTP 429 with a Retry-After header when exceeded, be "
            "configurable per endpoint, emit metrics, and degrade gracefully (allow "
            "traffic) if Redis is unavailable. Include tests for the window boundary."
        ),
        "required": [
            {"redis", "store", "backend", "storage"},
            {"sliding window", "window", "algorithm", "counter"},
            {"api key", "api-key", "per-key", "identity", "identify"},
            {"429", "too many requests", "reject", "response"},
            {"retry-after", "retry after", "header"},
            {"config", "configuration", "configurable", "per-endpoint"},
            {"metric", "metrics", "telemetry", "observability"},
            {"degrade", "fallback", "fail open", "unavailable", "graceful"},
            {"test", "tests", "boundary"},
        ],
        "ordering": [
            ({"redis", "store", "backend"}, {"sliding window", "window", "algorithm"}),
            ({"sliding window", "window", "algorithm"}, {"429", "reject", "response"}),
            ({"429", "reject", "response"}, {"retry-after", "header"}),
            ({"sliding window", "window", "algorithm"}, {"test", "tests", "boundary"}),
        ],
        "forbidden_merges": [
            ({"metric", "metrics"}, {"sliding window", "algorithm"}),
            ({"degrade", "fallback", "fail open"}, {"config", "configuration"}),
            ({"429", "reject"}, {"retry-after", "header"}),
        ],
    },
    {
        "id": "migration-zero-downtime",
        "tier": 4,
        "expected_units": 8,
        "request": (
            "Migrate a production users table: split the single `name` column into "
            "`first_name` and `last_name` with zero downtime. The application is running "
            "on multiple instances and cannot all be restarted at once. Provide a "
            "reversible path, backfill 40 million existing rows without locking the table, "
            "keep both schemas readable during rollout, and verify data integrity before "
            "dropping the old column."
        ),
        "required": [
            {"add column", "additive", "new column", "expand"},
            {"dual write", "dual-write", "write both", "backward compatible", "both schemas"},
            {"backfill", "batch", "chunk", "populate"},
            {"lock", "locking", "online", "non-blocking", "without locking"},
            {"verify", "integrity", "reconcile", "validate", "compare"},
            {"read path", "read", "switch reads", "cutover"},
            {"drop", "remove old", "cleanup", "contract"},
            {"rollback", "reversible", "revert", "roll back"},
        ],
        "ordering": [
            ({"add column", "additive", "new column", "expand"},
             {"dual write", "dual-write", "write both", "both schemas"}),
            ({"dual write", "dual-write", "write both"}, {"backfill", "batch", "populate"}),
            ({"backfill", "batch", "populate"}, {"verify", "integrity", "reconcile"}),
            ({"verify", "integrity", "reconcile"}, {"drop", "remove old", "cleanup", "contract"}),
            ({"read path", "switch reads", "cutover"}, {"drop", "remove old", "cleanup"}),
        ],
        "forbidden_merges": [
            ({"backfill", "batch"}, {"drop", "remove old"}),
            ({"add column", "additive"}, {"drop", "remove old"}),
            ({"verify", "integrity"}, {"drop", "remove old"}),
        ],
    },
    {
        "id": "flaky-test-triage",
        "tier": 2,
        "expected_units": 5,
        "request": (
            "Our CI suite has intermittent failures. Find which tests are flaky, determine "
            "why each one is flaky, fix the root causes, and add a guard so newly flaky "
            "tests are caught before merge."
        ),
        "required": [
            {"detect", "identify", "find", "collect", "history", "repeat"},
            {"quantify", "rate", "frequency", "measure", "rank"},
            {"root cause", "diagnose", "why", "categorise", "categorize", "analyse", "analyze"},
            {"fix", "repair", "remediate"},
            {"guard", "prevent", "gate", "ci check", "regression"},
        ],
        "ordering": [
            ({"detect", "identify", "find", "collect"}, {"quantify", "rate", "measure", "rank"}),
            ({"quantify", "rate", "measure"}, {"root cause", "diagnose", "analyse", "analyze"}),
            ({"root cause", "diagnose", "analyse"}, {"fix", "repair", "remediate"}),
            ({"fix", "repair", "remediate"}, {"guard", "prevent", "gate"}),
        ],
        "forbidden_merges": [
            ({"detect", "identify"}, {"fix", "repair"}),
            ({"root cause", "diagnose"}, {"fix", "repair"}),
        ],
    },
    {
        "id": "single-unit-control",
        "tier": 1,
        "expected_units": 1,
        "request": "Fix the off-by-one error in the pagination offset calculation in views.py.",
        "required": [
            {"pagination", "offset", "off-by-one", "fix"},
        ],
        "ordering": [],
        "forbidden_merges": [],
        "note": (
            "CONTROL: an atomic task. A system that over-decomposes this is not 'thorough', "
            "it is miscalibrated — inventing structure where none is warranted. Granularity "
            "catches that; without a control fixture, over-decomposition would look like a win."
        ),
    },
]


# ---------------------------------------------------------------------------
# SCORING — pure functions over the produced plan. Deterministic, no LLM.
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 \-]", " ", text.lower())


def _unit_hits(unit: str, concept: set[str]) -> bool:
    t = _norm(unit)
    return any(syn.lower() in t for syn in concept)


def _first_index(units: list[str], concept: set[str]) -> int | None:
    for i, u in enumerate(units):
        if _unit_hits(u, concept):
            return i
    return None


def _last_index(units: list[str], concept: set[str]) -> int | None:
    for i in range(len(units) - 1, -1, -1):
        if _unit_hits(units[i], concept):
            return i
    return None


def score_plan(units: list[str], fixture: dict) -> dict:
    """Grade a decomposition against one fixture. Returns per-metric detail."""
    units = [u for u in units if u and u.strip()]

    covered, missing = [], []
    for concept in fixture["required"]:
        if _first_index(units, concept) is not None:
            covered.append(sorted(concept)[0])
        else:
            missing.append(sorted(concept)[0])
    coverage = len(covered) / len(fixture["required"]) if fixture["required"] else 1.0

    order_ok, order_bad = 0, []
    for before, after in fixture["ordering"]:
        # Compare the FIRST occurrence of the prerequisite against the LAST occurrence of
        # the dependent step. A correct plan legitimately splits one concept across
        # several units — "create the backfill process" (prepare) can precede dual-write
        # while "run the backfill" (execute) follows it. Comparing first-vs-first read
        # that as an inversion and scored a sound 12-unit migration plan at 0.2 order
        # accuracy. The constraint being tested is "the prerequisite starts before the
        # dependent finishes", not "no keyword ever reappears".
        i, j = _first_index(units, before), _last_index(units, after)
        if i is None or j is None:
            order_bad.append(f"{sorted(before)[0]}->{sorted(after)[0]} (absent)")
            continue
        if i < j:
            order_ok += 1
        else:
            order_bad.append(f"{sorted(before)[0]}->{sorted(after)[0]} (inverted)")
    order_accuracy = order_ok / len(fixture["ordering"]) if fixture["ordering"] else 1.0

    sep_ok, merged = 0, []
    for a, b in fixture["forbidden_merges"]:
        collided = any(_unit_hits(u, a) and _unit_hits(u, b) for u in units)
        if collided:
            merged.append(f"{sorted(a)[0]}+{sorted(b)[0]}")
        else:
            sep_ok += 1
    separation = sep_ok / len(fixture["forbidden_merges"]) if fixture["forbidden_merges"] else 1.0

    expected = fixture["expected_units"]
    n = len(units)
    granularity = max(0.0, 1.0 - abs(n - expected) / max(expected, 1)) if n else 0.0

    composite = mean([coverage, order_accuracy, separation, granularity])
    return {
        "fixture": fixture["id"], "tier": fixture["tier"],
        "n_units": n, "expected_units": expected,
        "coverage": round(coverage, 4), "order_accuracy": round(order_accuracy, 4),
        "separation": round(separation, 4), "granularity": round(granularity, 4),
        "composite": round(composite, 4),
        "missing": missing, "order_violations": order_bad, "merged": merged,
    }


# ---------------------------------------------------------------------------
# ARMS
# ---------------------------------------------------------------------------

def arm_flat(request: str) -> list[str]:
    """Single LLM call: 'list the steps'. No structure, no roles, no feedback."""
    from llm.llm_integration import call_llm

    out = call_llm(
        prompt=(
            "Break this software request into an ordered list of implementation steps.\n"
            "Output ONE step per line, prefixed with its number. No prose, no headings.\n\n"
            f"REQUEST: {request}"
        ),
        system_prompt="You are a senior software engineer planning work.",
        timeout=120, max_retries=2,
    )
    return _parse_steps(out)


def arm_graph(request: str) -> list[str]:
    """The system's own decomposer node — the structural arm under test.

    Unlike arm_flat this is a governed graph: propose -> execute -> evaluate -> refine,
    with coverage and circular-dependency checks and a postcondition declared BEFORE the
    graph runs. Ordering is read from each task's declared dependencies rather than from
    the order the model happened to emit them in; a graph that encodes edges should be
    graded on those edges.
    """
    from agents.task_decomposer import decompose_requirements

    result = decompose_requirements(request, thread_id=f"decomp_bench_{time.time_ns()}")
    tasks = result.get("tasks") or []
    return _order_by_dependencies(tasks)


def _task_text(t) -> str:
    if isinstance(t, dict):
        for key in ("description", "title", "task", "name", "summary"):
            if t.get(key):
                return str(t[key])
        return json.dumps(t)
    return str(t)


def _order_by_dependencies(tasks: list) -> list[str]:
    """Topologically sort declared dependencies; fall back to emission order.

    A cycle or an unresolvable reference must NOT crash the benchmark — the fixture's
    ordering constraints will simply be graded against emission order, which is the
    honest outcome for a plan whose own edges are inconsistent.
    """
    if not tasks or not all(isinstance(t, dict) for t in tasks):
        return [_task_text(t) for t in tasks]

    ids, deps = [], {}
    for i, t in enumerate(tasks):
        tid = str(t.get("id") or t.get("task_id") or i)
        ids.append(tid)
        raw = t.get("dependencies") or t.get("depends_on") or []
        if isinstance(raw, (str, int)):
            raw = [raw]
        deps[tid] = [str(d) for d in raw]

    by_id = dict(zip(ids, tasks))
    ordered, seen, visiting = [], set(), set()

    def visit(tid: str) -> bool:
        if tid in seen:
            return True
        if tid in visiting:
            return False  # cycle
        visiting.add(tid)
        for d in deps.get(tid, []):
            if d in by_id and not visit(d):
                return False
        visiting.discard(tid)
        seen.add(tid)
        ordered.append(tid)
        return True

    for tid in ids:
        if not visit(tid):
            return [_task_text(t) for t in tasks]  # cycle: emission order
    return [_task_text(by_id[t]) for t in ordered]


def _parse_steps(text: str | None) -> list[str]:
    """Split a model's step list into units. Accepts None: call_llm can return it on a
    transport failure, and the benchmark must record an empty plan rather than crash."""
    units = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^[\-\*\u2022]\s*", "", line)
        line = re.sub(r"^(?:step\s*)?\d+[\.\)\:]\s*", "", line, flags=re.I)
        if line and not line.startswith("#"):
            units.append(line)
    return units


ARMS = {"flat": arm_flat, "graph": arm_graph}


def run(arms: list[str], repeats: int, out_path: str) -> dict:
    records = []
    for arm in arms:
        for fx in FIXTURES:
            for rep in range(repeats):
                t0 = time.time()
                try:
                    units = ARMS[arm](fx["request"])
                    row = score_plan(units, fx)
                    row.update(arm=arm, rep=rep, ok=True,
                               seconds=round(time.time() - t0, 1), units=units[:12])
                except Exception as exc:
                    row = {"fixture": fx["id"], "tier": fx["tier"], "arm": arm, "rep": rep,
                           "ok": False, "error": f"{type(exc).__name__}: {exc}"[:200],
                           "composite": None, "seconds": round(time.time() - t0, 1)}
                records.append(row)
                status = f"composite={row['composite']}" if row["ok"] else row["error"][:60]
                print(f"  {arm:6} t{fx['tier']} {fx['id']:26} rep{rep} {status}", flush=True)

    print("\n=== DECOMPOSITION SUMMARY ===")
    summary = {}
    for arm in arms:
        ok = [r for r in records if r["arm"] == arm and r["ok"]]
        failed = [r for r in records if r["arm"] == arm and not r["ok"]]
        if not ok:
            print(f"\n--- {arm} --- all {len(failed)} runs failed")
            summary[arm] = {"runs_ok": 0, "runs_failed": len(failed)}
            continue
        per_tier = {}
        for tier in sorted({r["tier"] for r in ok}):
            rows = [r for r in ok if r["tier"] == tier]
            per_tier[f"tier{tier}"] = round(mean(r["composite"] for r in rows), 4)
        summary[arm] = {
            "runs_ok": len(ok), "runs_failed": len(failed),
            "coverage": round(mean(r["coverage"] for r in ok), 4),
            "order_accuracy": round(mean(r["order_accuracy"] for r in ok), 4),
            "separation": round(mean(r["separation"] for r in ok), 4),
            "granularity": round(mean(r["granularity"] for r in ok), 4),
            "composite": round(mean(r["composite"] for r in ok), 4),
            "per_tier": per_tier,
            "mean_seconds": round(mean(r["seconds"] for r in ok), 1),
        }
        s = summary[arm]
        print(f"\n--- {arm} --- ok={s['runs_ok']} failed={s['runs_failed']}")
        print(f"  coverage       {s['coverage']}")
        print(f"  order accuracy {s['order_accuracy']}")
        print(f"  separation     {s['separation']}")
        print(f"  granularity    {s['granularity']}")
        print(f"  COMPOSITE      {s['composite']}")
        print(f"  per tier       {s['per_tier']}")

    if len(arms) == 2:
        a, b = arms
        if summary.get(a, {}).get("runs_ok") and summary.get(b, {}).get("runs_ok"):
            print(f"\n=== PAIRED BY FIXTURE: {a} vs {b} ===")
            deltas = []
            for fx in FIXTURES:
                ra = [r["composite"] for r in records if r["arm"] == a and r["fixture"] == fx["id"] and r["ok"]]
                rb = [r["composite"] for r in records if r["arm"] == b and r["fixture"] == fx["id"] and r["ok"]]
                if ra and rb:
                    d = mean(rb) - mean(ra)
                    deltas.append(d)
                    print(f"  t{fx['tier']} {fx['id']:26} {mean(ra):.3f} -> {mean(rb):.3f}  ({d:+.3f})")
            if deltas:
                wins = sum(1 for d in deltas if d > 0.01)
                losses = sum(1 for d in deltas if d < -0.01)
                print(f"\n  mean delta {mean(deltas):+.4f}   {b} wins {wins}, loses {losses}, "
                      f"ties {len(deltas)-wins-losses} of {len(deltas)} fixtures")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    payload = {"records": records, "summary": summary,
               "n_fixtures": len(FIXTURES), "repeats": repeats}
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1)
    print(f"\nsaved -> {out_path}")
    return payload


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Decomposition benchmark")
    ap.add_argument("--arms", default="flat,graph")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--out", default=os.path.join(RESULTS, "decomposition_bench.json"))
    ns = ap.parse_args(argv)
    arms = [a.strip() for a in ns.arms.split(",") if a.strip()]
    bad = [a for a in arms if a not in ARMS]
    if bad:
        print(f"Unknown arm(s): {bad}. Available: {sorted(ARMS)}", file=sys.stderr)
        return 1
    run(arms, ns.repeats, ns.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
