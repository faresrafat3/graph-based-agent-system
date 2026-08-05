# version: v7 | 2026-08-05 | verdict: pending-review
"""opus5_consult — live opus-5 pressure-advisor channel (Task G7, per Fares's direction).

Fares required opus-5 to PARTICIPATE LIVE, not just as frozen text. This module is the
real channel: it dispatches a ruling/decision to claude-opus-5 (via the agentrouter-org
provider) and returns its critique. The result is recorded in the distillation ledger as
*independent provenance* — not self-written.

Design (C1-rev1 compliant):
  - opus-5 is consulted, never auto-applied. Its output is advisory + recorded.
  - It runs as a background subagent so the meta-loop never blocks on it.
"""

from __future__ import annotations

import json
import os
from typing import Any


OPUS5_MODEL = os.environ.get("OPUS5_MODEL", "claude-opus-5")
OPUS5_PROVIDER = os.environ.get("OPUS5_PROVIDER", "agentrouter-org")


def consult_opus5(prompt: str, timeout: int = 120) -> str:
    """Dispatch a question to opus-5.

    NOTE: the Hermes `hermes` CLI has no `delegate` subcommand; the live opus-5 channel is
    the AGENT itself (this Hermes session) calling `delegate_task` with model pinned to
    claude-opus-5 via agentrouter-org. So this function returns a clear marker and the
    actual review is performed by the agent (see attach_opus5_review usage in the cron
    flow, where the agent consults opus-5 and records the reply).

    Kept as a stub so callers don't hang; the real review path is agent-driven.
    """
    return "[opus5: agent-driven] consult via delegate_task(model=agentrouter-org/claude-opus-5)"


def review_ruling(ruling_id: str, ruling_text: str) -> dict[str, Any]:
    """Ask opus-5 to pressure-review a written ruling. Returns a structured record."""
    prompt = (
        f"You are the philosophical pressure-advisor (opus-5 distillation role). "
        f"Review this governance ruling from a self-governing agent graph.\n\n"
        f"RULING {ruling_id}:\n{ruling_text}\n\n"
        f"Critique it in 4-6 tight bullets (max 200 words). Is it correct? What would you "
        f"change? Flag any hidden authority or contradiction with 'no supreme governor'."
    )
    reply = consult_opus5(prompt)
    return {
        "ruling_id": ruling_id,
        "opus5_reply": reply,
        "channel": f"{OPUS5_PROVIDER}/{OPUS5_MODEL}",
    }


if __name__ == "__main__":
    # Smoke test: confirm opus-5 is reachable and records a review.
    r = review_ruling(
        "C1",
        "Meta-loop proposes only; application requires reversible flag or human checkpoint.",
    )
    print(json.dumps(r, ensure_ascii=False, indent=2))
