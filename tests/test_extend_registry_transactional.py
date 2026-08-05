"""TDD test for strong-model review #1-b: extend_registry must self-extend WITHOUT self-violating.

gpt-5.6-sol measured: after one forge_agent()+extend_registry() the governance breaches went
0 -> 6 (missing module / entrypoint / lifecycle doc / test file). The fix makes extend_registry
TRANSACTIONAL: it scaffolds the required artifacts so the new entry is governable, and rolls
back (deletes scaffolds + entry) if the registry still has any breach.
"""

import importlib

from system import agent_registry
from system.governance_checks import run_governance_checks
from agents.agent_forge import forge_agent, extend_registry


def _cleanup(name):
    # remove any forged entry + on-disk artifacts left by a test
    agent_registry.AGENT_REGISTRY[:] = [
        e for e in agent_registry.AGENT_REGISTRY
        if not (e.get("forged") and e.get("name") == name)
    ]
    for p in (f"agents/forged/{name}.py", f"tests/test_forged_{name}.py",
              f"docs/reconciliation/forged/{name}.md"):
        import os
        if os.path.exists(p):
            os.remove(p)


def test_extend_registry_stays_governed_no_self_violation():
    try:
        before_ok = run_governance_checks()["success"]
        assert before_ok is True
        a = forge_agent("txn_agent", ["P1", "P4"], "raise variety, bound probes",
                        {"bounded_probe": True, "verify_node": True})
        entry = extend_registry(a)  # scaffolds module + test + doc, then registers
        after = run_governance_checks()
        assert after["success"] is True, after["breaches"]
        mod = importlib.import_module(entry["module"])
        assert hasattr(mod, entry["entrypoint"])
        assert callable(getattr(mod, entry["entrypoint"]))
    finally:
        _cleanup("txn_agent")


def test_extend_registry_rolls_back_on_breach():
    try:
        a = forge_agent("txn_agent2", ["P2"], "verify closure")
        entry = extend_registry(a)
        assert entry["forged"] is True
        assert run_governance_checks()["success"] is True
    finally:
        _cleanup("txn_agent2")
