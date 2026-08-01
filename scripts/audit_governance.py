"""Run distributed governance compliance checks."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from system.governance_checks import run_governance_checks


def main() -> int:
    result = run_governance_checks()
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
        for violation in check["violations"]:
            print(f"- {violation}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
