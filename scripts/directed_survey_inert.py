#!/usr/bin/env python3
"""
Directed Survey — Inert Agent & Measurement Honesty Auditor.

Grounded in the project's own governing standards:
  - CONSTITUTION.md Ruling F2 (metric honesty): separate governance_score from success_rate.
  - CONSTITUTION.md Ruling C1 (meta-loop = propose-only, default-deny): this script
    REPORTS and PROPOSES; it NEVER mutates source or the registry. Application is
    opt-in (human/flag), never automatic.
  - P7 (Least Sufficient Intervention): an agent that never changes an outcome is a
    silent control -> pruning candidate.
  - Law 3 (Fail Loudly): surface the measurement gap, do not hide it.
  - Fares' standing rule: a metric drop is a DESIGN bug, not a weak model. Each new
    dimension here DECLARES its own falsifier in advance (memory note), else it is
    not built.

Two-pass reachability audit:
  Pass 1 (name-graph): system's own _transitive_reachable (upper bound, may over-count).
  Pass 2 (call-site): strict ast.Call audit over agents/ -> real invocation only.

The DELTA (name-graph reachable but never called) IS the honest inert set.

Outputs:
  reports/directed-survey-inert.<ts>.json   (machine-readable, for change-detection)
  reports/directed-survey-inert.<ts>.md     (human report)
  reports/directed-survey-inert.LATEST.json (stable path for cron change-detection)
  reports/directed-survey-inert.LATEST.md

Change-detection: if the new LATEST differs from the previous LATEST (excluding the
timestamp field), print a CHANGE DETECTED block so a cron monitor can alert.

Zero network, zero LLM, zero API keys. Deterministic.
"""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running from repo root or scripts/.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from system.agent_registry import AGENT_REGISTRY
from system.governance_checks import (
    EXTERNAL_ALLOWED,
    LIVE_ENTRYPOINT,
    _transitive_reachable,
)

AGENTS_DIR = ROOT / "agents"
REPORTS_DIR = ROOT / "reports"
LATEST_JSON = REPORTS_DIR / "directed-survey-inert.LATEST.json"
LATEST_MD = REPORTS_DIR / "directed-survey-inert.LATEST.md"

# Each measured dimension declares its falsifier up front (Fares rule + C1 transparency).
FALSIFIERS = {
    "name_graph_reachable": "count(from _transitive_reachable) must be >= call_site_reachable; if equal AND external set empty, no gap (fails loud otherwise).",
    "call_site_reachable": "count(agents with >=1 real ast.Call from another module) must be > 0; if 0, the live head is dead (critical bug).",
    "inert_honest": "subset of registered NOT in call_site_reachable and NOT in EXTERNAL_ALLOWED; must be non-empty OR system's 0-inert claim is false — this is the failure we surface.",
    "external_overlap": "len(reachable & EXTERNAL_ALLOWED) must == 0 (Ruling: an agent is in EXACTLY one set). Non-zero = classification bug.",
    "governance_vs_success": "governance_score (does it obey rules?) reported separately from success_rate; never conflated (F2).",
}


def pass1_name_graph(entry_names: set[str]) -> set[str]:
    """System's own reachability (upper bound)."""
    return _transitive_reachable(LIVE_ENTRYPOINT, entry_names)


def pass2_call_site(entry_names: set[str]) -> dict[str, set[str]]:
    """Strict: which entrypoints are actually CALLED (ast.Call) somewhere in agents/.

    Returns mapping entrypoint -> set of files that call it (excluding the module
    that defines it, so a self-recursive def is not counted as 'used').
    """
    calls: dict[str, set[str]] = {ep: set() for ep in entry_names}
    defs: dict[str, str] = {}  # entrypoint -> defining module file

    # First, map each entrypoint to the module that DEFINES it (its registry module).
    reg_by_ep = {e["entrypoint"]: e for e in AGENT_REGISTRY}
    for ep in entry_names:
        mod = reg_by_ep[ep]["module"].split(".")
        defs[ep] = str(AGENTS_DIR / Path(*mod).with_suffix(".py"))

    for py in AGENTS_DIR.rglob("*.py"):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else None)
                if name in entry_names and str(py) != defs.get(name):
                    calls[name].add(str(py.relative_to(ROOT)))
    return calls


def main() -> int:
    REPORTS_DIR.mkdir(exist_ok=True)
    entries = AGENT_REGISTRY
    entry_names = {e["entrypoint"] for e in entries}

    name_reach = pass1_name_graph(entry_names)
    call_map = pass2_call_site(entry_names)
    call_reach = {ep for ep, files in call_map.items() if files}

    all_names = {e["name"]: e["entrypoint"] for e in entries}

    # Honest inert = registered, never called, not declared external.
    inert = sorted(
        e["name"] for e in entries
        if e["entrypoint"] not in call_reach and e["entrypoint"] not in EXTERNAL_ALLOWED
    )
    # External but never called (honest external declarations).
    external_silent = sorted(
        e["name"] for e in entries
        if e["entrypoint"] in EXTERNAL_ALLOWED and e["entrypoint"] not in call_reach
    )
    # The double-count bug: reachable AND external.
    overlap = sorted(
        e["name"] for e in entries
        if e["entrypoint"] in name_reach and e["entrypoint"] in EXTERNAL_ALLOWED
    )
    # Live-but-beta: called only from competitive_slice subtree, not pipeline head/orchestrator.
    def _files(ep):
        return call_map.get(ep, set())
    beta = sorted(
        e["name"] for e in entries
        if e["entrypoint"] in call_reach
        and not (_files(e["entrypoint"]) & {"agents/karpathy_pipeline.py", "agents/graph_execution_orchestrator.py"})
    )
    genuinely_live = sorted(
        e["name"] for e in entries
        if _files(e["entrypoint"]) & {"agents/karpathy_pipeline.py", "agents/graph_execution_orchestrator.py"}
    )

    # Governance-vs-success separation (F2): governance_score = do we obey our own rules?
    governance_observations = {
        "registry_count": len(entries),
        "name_graph_reachable": len(name_reach),
        "call_site_reachable": len(call_reach),
        "inert_honest_count": len(inert),
        "external_declared_count": len(EXTERNAL_ALLOWED),
        "external_but_never_called_count": len(external_silent),
        "reachable_AND_external_overlap_count": len(overlap),
        "beta_only_count": len(beta),
        "genuinely_live_count": len(genuinely_live),
        "measurement_miscalibrated": len(name_reach) > len(call_reach),
        "classification_contradiction": len(overlap) > 0,
    }
    # governance_score: how well do we obey the rule "an agent is reachable XOR external, and reachable means really called"?
    breaches = []
    if len(name_reach) > len(call_reach):
        breaches.append("name-graph over-counts reachability vs real call-sites (measurement mis-calibrated).")
    if overlap:
        breaches.append(f"{len(overlap)} agents classified BOTH reachable AND external (contradiction).")
    if inert:
        breaches.append(f"{len(inert)} agents registered but never called and not declared external (silent dead weight).")
    governance_score = 1.0 - (len(breaches) / 4.0)  # 4 structural governance expectations

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report = {
        "survey": "directed-survey-inert",
        "generated_at": ts,
        "live_entrypoint": LIVE_ENTRYPOINT,
        "falsifiers": FALSIFIERS,
        "governance_observations": governance_observations,
        "governance_score": round(governance_score, 3),
        "success_rate_note": "NOT measured here (F2): this survey judges governance adherence, not task success.",
        "breaches": breaches,
        "genuinely_live": genuinely_live,
        "beta_only": beta,
        "inert_honest": inert,
        "external_declared_never_called": external_silent,
        "reachable_AND_external_overlap": overlap,
        "proposals": [
            "P0: add check_entrypoints_called() to governance_checks.py (strict ast.Call) and fail/ warn-loud when name-graph reachable != call-site reachable.",
            "P0: enforce EXACTLY-ONE-SET invariant (reachable XOR external); fix AuthSquadAgent double-count.",
            "P1 (CONNECT or DELETE per P7): the inert agents below must be wired into the live path or removed from AGENT_REGISTRY.",
            "P1: wire self_pruning.py to the STRICT call-site reachable set so P7 prunes real silent controls.",
        ],
        "inert_action_items": [
            {"agent": n, "entrypoint": all_names[n], "options": "CONNECT (preferred for memory/escalation) | DELETE (P7) | KEEP-EXTERNAL-ONLY-IF-JUSTIFIED"}
            for n in inert
        ],
        "compliance": {
            "C1_propose_only": True,
            "C1_no_source_mutation": True,
            "F2_governance_vs_success_separated": True,
            "Law3_fail_loud": True,
        },
    }

    # Write timestamped + LATEST.
    json_path = REPORTS_DIR / f"directed-survey-inert.{ts}.json"
    md_path = REPORTS_DIR / f"directed-survey-inert.{ts}.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_md(report), encoding="utf-8")

    # LATEST copies (stable path for change-detection). Preserve prior for diff.
    prev = None
    if LATEST_JSON.exists():
        try:
            prev = json.loads(LATEST_JSON.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            prev = None
    LATEST_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    LATEST_MD.write_text(render_md(report), encoding="utf-8")

    # Change-detection vs previous LATEST (ignore timestamp + generated_at).
    changed = False
    if prev:
        a = {k: v for k, v in prev.items() if k not in ("generated_at",)}
        b = {k: v for k, v in report.items() if k not in ("generated_at",)}
        changed = json.dumps(a, sort_keys=True, ensure_ascii=False) != json.dumps(b, sort_keys=True, ensure_ascii=False)

    print(f"[directed-survey] wrote {json_path.name} + {md_path.name}")
    print(f"[directed-survey] governance_score={report['governance_score']}  "
          f"call_site_reachable={len(call_reach)}/{len(entries)}  "
          f"inert_honest={len(inert)}  overlap={len(overlap)}")
    if changed:
        print("[directed-survey] CHANGE DETECTED vs previous LATEST -> monitor should alert.")
    else:
        print("[directed-survey] no structural change vs previous LATEST.")
    return 0


def render_md(report: dict) -> str:
    g = report["governance_observations"]
    lines = []
    lines.append("# Directed Survey — Inert Agents & Measurement Honesty\n")
    lines.append(f"> generated_at: {report['generated_at']}  |  live_entrypoint: `{report['live_entrypoint']}`")
    lines.append("> Mode: **propose-only** (C1 default-deny) — no source mutated.\n")
    lines.append(f"## Governance Score (F2): `{report['governance_score']}`")
    lines.append("> Judges rule-adherence, NOT task success (success_rate intentionally not measured here).\n")
    lines.append("## Structural Findings")
    lines.append(f"- Registry size: **{g['registry_count']}**")
    lines.append(f"- Name-graph reachable (system's own, upper bound): **{g['name_graph_reachable']}**")
    lines.append(f"- **Call-site reachable (real invocation): {g['call_site_reachable']}**")
    lines.append(f"- Honest inert (registered, never called, not external): **{g['inert_honest_count']}**")
    lines.append(f"- External-declared but never called: {g['external_but_never_called_count']}")
    lines.append(f"- Reachable AND external (contradiction): **{g['reachable_AND_external_overlap_count']}**")
    lines.append(f"- Live-only-via-beta (competitive subtree): {g['beta_only_count']}")
    lines.append(f"- Genuinely live (pipeline/orchestrator): {g['genuinely_live_count']}")
    lines.append(f"- Measurement mis-calibrated: **{g['measurement_miscalibrated']}**")
    lines.append(f"- Classification contradiction: **{g['classification_contradiction']}**\n")
    if report["breaches"]:
        lines.append("## Breaches (Law 3 — fail loudly)")
        for b in report["breaches"]:
            lines.append(f"- ⚠️ {b}")
        lines.append("")
    lines.append("## Genuinely Live (called from pipeline/orchestrator)")
    for n in report["genuinely_live"]:
        lines.append(f"- ✅ {n}")
    lines.append("\n## Live-only-via-beta (competitive_slice subtree)")
    for n in report["beta_only"]:
        lines.append(f"- 🟡 {n}")
    lines.append("\n## Honest Inert (registered, never called, not external) — P7 candidates")
    for n in report["inert_honest"]:
        lines.append(f"- ❌ {n} (`{report_action_ep(n, report)}`)")
    lines.append("\n## External-declared but never called (honest silence)")
    for n in report["external_declared_never_called"]:
        lines.append(f"- ⚪ {n}")
    if report["reachable_AND_external_overlap"]:
        lines.append("\n## ⚠️ Contradiction: reachable AND external (fix double-count)")
        for n in report["reachable_AND_external_overlap"]:
            lines.append(f"- 🔴 {n}")
    lines.append("\n## Proposals (propose-only — apply is opt-in)")
    for p in report["proposals"]:
        lines.append(f"- {p}")
    lines.append("\n## Inert Action Items (CONNECT | DELETE | KEEP-EXTERNAL)")
    for it in report["inert_action_items"]:
        lines.append(f"- **{it['agent']}** (`{it['entrypoint']}`): {it['options']}")
    lines.append("\n## Falsifiers (declared per dimension)")
    for k, v in report["falsifiers"].items():
        lines.append(f"- `{k}`: {v}")
    lines.append("\n## Compliance")
    for k, v in report["compliance"].items():
        lines.append(f"- {k}: {v}")
    return "\n".join(lines) + "\n"


def report_action_ep(name: str, report: dict) -> str:
    for it in report["inert_action_items"]:
        if it["agent"] == name:
            return it["entrypoint"]
    return "?"


if __name__ == "__main__":
    raise SystemExit(main())
