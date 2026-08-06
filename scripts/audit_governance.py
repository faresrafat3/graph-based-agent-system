"""Run distributed governance compliance checks."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from system.governance_checks import check_verified_closure, run_governance_checks

# Checks the audit refuses to run without. P2 (CONSTITUTION Article VI) is a HARD
# structural invariant, so unwiring check_verified_closure from run_governance_checks
# must fail the audit rather than quietly shrink it.
REQUIRED_CHECKS = {check_verified_closure("verified_closure_probe" and None).check_name}


def main() -> int:
    result = run_governance_checks()
    executed = {check["check_name"] for check in result["checks"]}
    missing = sorted(REQUIRED_CHECKS - executed)
    if missing:
        print("Distributed governance checks failed:")
        print("[audit_wiring]")
        for check_name in missing:
            print(f"- required check '{check_name}' was not executed by run_governance_checks().")
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
