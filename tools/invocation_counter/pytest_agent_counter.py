"""Opt-in pytest plugin that activates the agent invocation counter.

Loaded explicitly with ``-p pytest_agent_counter`` (never auto-discovered), so
the default test run is completely unchanged. Activation additionally requires
AGENT_INVOCATION_COUNTER=1 in the environment.

Usage:
    AGENT_INVOCATION_COUNTER=1 AGENT_COUNTER_OUT=/tmp/counts.json \
      PYTHONPATH=tools/invocation_counter python -m pytest -q -p pytest_agent_counter
"""

from __future__ import annotations

import os

_ACTIVE = os.environ.get("AGENT_INVOCATION_COUNTER") == "1"


def pytest_configure(config):
    if not _ACTIVE:
        return
    import counter

    counter.install()


def pytest_unconfigure(config):
    if not _ACTIVE:
        return
    import counter

    counter.dump()
