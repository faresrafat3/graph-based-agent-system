"""Standalone wrapper: run the real CLI entry path with counters active.

Additive and removable — imports main.py and runs it unchanged, with the agent
invocation counter installed first so every registry entrypoint that executes on
the real path is recorded.

Usage (project installed as a package, e.g. ``pip install -e .``):
    AGENT_COUNTER_OUT=/tmp/real.json \
      python tools/invocation_counter/run_real.py -- --requirements "..."
"""

from __future__ import annotations

import sys

from tools.invocation_counter import counter

counter.install()

argv = sys.argv[1:]
if argv and argv[0] == "--":
    argv = argv[1:]

exit_code = None
error = None
try:
    import main  # noqa: E402

    exit_code = main.main(argv)
except BaseException as exc:  # noqa: BLE001 - we report, then dump counts
    error = f"{type(exc).__name__}: {exc}"
finally:
    path = counter.dump()
    print(f"\n[invocation-counter] exit_code={exit_code} error={error}")
    print(f"[invocation-counter] counts written to {path}")
