#!/usr/bin/env python3
"""Record the 3-model comparative-study reviews into the distillation ledger as provenance.

Fares wants ALL opus-5 / model replies retrievable (future value for understanding AI).
This appends the verbatim comparative-study replies (opus-5, gpt-5.6-sol, opus-4-8) to
system/distillation_ledger.jsonl with type=model_review.
"""

import json
from pathlib import Path

from system.distillation_ledger import DistillationLedger

REVIEWS = [
    {
        "type": "model_review",
        "ruling_id": "CIR",  # Context-Isolated Reasoning study
        "channel": "agentrouter-org/claude-opus-5",
        "reply": (
            "Real, not roleplay - but mislabeled. Mechanism = context-window hygiene: execution "
            "artifacts contaminate attention. 'Philosopher/executor' is decorative; the mechanism "
            "is context isolation + model specialization. Not strictly higher quality - higher "
            "coherence at cost of grounding. Trap: bullshit machine (no skin in game), handoff "
            "loss, over-philosophizing. Law: (a) no reasoning token shares context with execution; "
            "(b) Thinking->spec buffer only, Doing->executable only; (c) every cross-boundary claim "
            "carries a falsification hook. Curate thinker inputs ruthlessly."
        ),
        "delegation_id": "deleg_83597cba",
    },
    {
        "type": "model_review",
        "ruling_id": "CIR",
        "channel": "agentrouter-org/gpt-5.6-sol",
        "reply": (
            "Not emergent, mostly engineered + theatrical. Real gain = context/task decoupling "
            "(cuts mode-confusion). 'Philosopher' label inflates divergence; selection bias. "
            "Philosophy isn't intrinsically better - reasoning-while-executing earns grounding; "
            "deepity trap (abstract prose reads profound). Quality task-relative. Trap: ungrounded "
            "mandate + 2x cost + ossifying one decomposition as law harms fused tasks. Formalize as "
            "separate mutually-bounded agents + mandatory reconciliation; OPTIONAL not absolute."
        ),
        "delegation_id": "deleg_edf35b40",
    },
    {
        "type": "model_review",
        "ruling_id": "CIR",
        "channel": "agentrouter-org/claude-opus-4-8",
        "reply": (
            "Genuine mechanic, not role-play - but overstated. Stripping tools frees attention "
            "budget; 'depth' = survivorship bias. Same quality, different axis: pure reasoning is "
            "ungrounded, execution constrained by ground truth. No A/B -> salience not superiority. "
            "Trap: high-status hallucinator feeding ungrounded plans to executor. Formalize as "
            "disjoint stages: Thinker zero tool-calls + scored on falsifiability; Doer zero theory "
            "+ scored on measurement; mandatory Reconciler diffs intent<->output. Gate by complexity."
        ),
        "delegation_id": "deleg_e7bcc2bc",
    },
]


def main():
    ledger = DistillationLedger()
    ledger.path.parent.mkdir(parents=True, exist_ok=True)
    for r in REVIEWS:
        with ledger.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Recorded {len(REVIEWS)} model reviews into", ledger.path)


if __name__ == "__main__":
    main()
