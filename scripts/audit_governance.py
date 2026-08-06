"""Run distributed governance compliance checks."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from system.governance_checks import check_verified_closure, run_governance_checks


def main() -> int:
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

    for warning in result.get("warnings", []):
        print(f"WARNING: {warning}")

    if result["success"]:
        print(
            "Distributed governance checks passed "
            f"for {result.get('registered_items', 0)} registered items."
        )
        return 0

    print("Distributed governance checks failed:")
    for check in result["checks"]:
        if check["success"]:
            continue
        print(f"[{check['check_name']}]")
        for breach in check["breaches"]:
            print(f"- {breach}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
