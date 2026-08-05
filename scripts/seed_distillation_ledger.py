#!/usr/bin/env python3
"""Seed the distillation ledger with the 7 opus-5 principles (P1-P7).

Run once to record that P1-P7 have provenance (source = opus-5 philosophical audit),
so Ruling C5 holds: every enforced principle is ledger-recorded. Idempotent — re-running
just bumps the latest status to 'enforced'.
"""
from system.distillation_ledger import DistillationLedger

SEED = [
    ("P1", "Requisite Response Variety", "opus-5 philosophical audit (CONSTITUTION Article VI)", "enforced"),
    ("P2", "Verified Closure", "opus-5 philosophical audit (CONSTITUTION Article VI)", "enforced"),
    ("P3", "Domain-Gated Governance", "opus-5 philosophical audit (CONSTITUTION Article VI)", "enforced"),
    ("P4", "Bounded Probing", "opus-5 philosophical audit (CONSTITUTION Article VI)", "enforced"),
    ("P5", "Custodial Context", "opus-5 philosophical audit (CONSTITUTION Article VI)", "enforced"),
    ("P6", "Productive Contradiction", "opus-5 philosophical audit (CONSTITUTION Article VI)", "enforced"),
    ("P7", "Least Sufficient Intervention", "opus-5 philosophical audit (CONSTITUTION Article VI)", "enforced"),
]

if __name__ == "__main__":
    ledger = DistillationLedger()
    for ref, text, source, status in SEED:
        ledger.record(ref=ref, text=text, source=source, status=status)
    print(f"Ledger now has {len(ledger.all())} principles; P1-P7 enforced.")
