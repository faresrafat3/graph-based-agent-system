"""Run distributed governance compliance checks.

Two modes:

* default            — breaches fail the audit; tracked WARNINGS are printed but tolerated.
* ``--strict``       — WARNINGS also fail the audit.  This is the mode CI runs, so a
                       tracked gap cannot sit in the tree indefinitely without a
                       deliberate, visible decision to keep it.

Rationale (Fares review, 2026-08-07): the governance layer had zero `raise`
statements and `success = not breaches`, which excluded warnings from the pass/fail
decision entirely.  Four known structural gaps (forge wiring + 3x P2 VERIFY) therefore
reported as "passed".  ``--strict`` closes that loophole without silently breaking
existing local workflows.
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from system.governance_checks import check_verified_closure, run_governance_checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Distributed governance audit")
    parser.add_argument(
        "--strict", action="store_true",
        help="Treat tracked WARNINGS as failures (the mode CI uses).",
    )
    args = parser.parse_args(argv)

    # P2 (CONSTITUTION Article VI) is a HARD structural invariant: every WRITE agent
    # must terminate in a VERIFY node. Call it explicitly and refuse to pass the audit
    # if it is not part of the aggregated suite, so it cannot be quietly unwired.
    p2 = check_verified_closure()
    result = run_governance_checks()
    executed = {check["check_name"] for check in result["checks"]}

    if p2.check_name not in executed:
        print("Distributed governance checks failed:")
        print("[audit_wiring]")
        print(
            f"- required check '{p2.check_name}' is not wired into run_governance_checks(); "
            "P2 Verified Closure would go unenforced."
        )
        return 1

    warnings = result.get("warnings", [])
    for warning in warnings:
        print(f"WARNING: {warning}")

    if not result["success"]:
        print("Distributed governance checks failed:")
        for check in result["checks"]:
            if check["success"]:
                continue
            print(f"[{check['check_name']}]")
            for breach in check["breaches"]:
                print(f"- {breach}")
        return 1

    if args.strict and warnings:
        print(
            f"\nSTRICT MODE: {len(warnings)} tracked warning(s) treated as failures. "
            "Wire the gap or remove the tracking entry — a warning is not a pass."
        )
        return 1

    suffix = " (strict: no warnings)" if args.strict else ""
    print(
        "Distributed governance checks passed "
        f"for {result.get('registered_items', 0)} registered items{suffix}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
