#!/usr/bin/env python3
"""Record opus-5's live review of the P4 probe_budget proposal into the distillation ledger.

Fares requires opus-5 to participate LIVE. This script appends opus-5's actual reply
(returned by the agent-driven delegate_task channel) as independent provenance — not a
self-written summary. The reply text below is the verbatim opus-5 output from the
deleg_ebfc3e6d review.
"""

from system.distillation_ledger import DistillationLedger


OPUS5_REPLY = """Ruling — probe_budget (P4): adopt only as a stop-loss, not as the fix.

- Wrong primary lever. A budget *bounds* thrashing, it doesn't reduce it. N repeats of the same idea still burn N attempts, then escalate. Novelty is the control; N is only the stop-loss.
- The trigger signal is weak. thrash_count fires on Jaccard >=0.6 between consecutive reflections — word reuse, not hypothesis identity. step-3.7-flash rephrases one theory (false negative) or reuses the traceback while genuinely narrowing (false positive). Harden the signal before enforcing control on it (P7).
- Capability risk is real. Weak models converge late via small edits. A hard cap amputates the round-4 fix. Count a probe as spent only when there's no measurable progress (failing-test count not decreasing); progress refunds the probe.
- Make "NEW hypothesis" enforceable. Carry a rejected-hypothesis list in graph state and inject it as a negative constraint into the next debugger prompt (P5). Otherwise P4's novelty clause is a wish, not a mechanism.
- Escalate with artifacts — hypothesis trail, diffs, failing tests — or you convert agent thrash into human thrash.
- Falsify first: replay logged runs; adopt only if capping at N loses zero successes found at attempt >N. Scope to Complex per P3.
"""


def main():
    ledger = DistillationLedger()
    provenance = {
        "type": "opus5_review",
        "ruling_id": "P4",
        "channel": "agentrouter-org/claude-opus-5",
        "reply": OPUS5_REPLY,
        "delegation_id": "deleg_ebfc3e6d",
    }
    ledger.path.parent.mkdir(parents=True, exist_ok=True)
    import json
    with ledger.path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(provenance, ensure_ascii=False) + "\n")
    print("Recorded opus-5 P4 review into", ledger.path)


if __name__ == "__main__":
    main()
