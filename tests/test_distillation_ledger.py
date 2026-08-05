"""TDD tests for Task D: distillation ledger (G4, C5).

Every opus-5-sourced principle must have a ledger entry proving it was distilled (source,
date, frozen text, status), not just written. A principle without a ledger entry is
advisory-only. Resolves C5.
"""

from system.distillation_ledger import (
    DistillationLedger,
    PrincipleEntry,
    LedgerError,
)


def test_ledger_records_principle_with_provenance():
    ledger = DistillationLedger()
    entry = ledger.record(
        ref="P4",
        text="Bounded Probing: complex work runs N attempts, each a NEW falsifiable hypothesis.",
        source="opus-5 philosophical audit (PHILOSOPHICAL_AUDIT_WORKBOOK.md)",
        status="distilled",
    )
    assert entry.ref == "P4"
    assert entry.status == "distilled"
    assert "opus-5" in entry.source.lower()


def test_ledger_rejects_principle_without_source():
    ledger = DistillationLedger()
    try:
        ledger.record(ref="P9", text="some new principle", source="", status="enforced")
        assert False, "should have raised"
    except LedgerError:
        pass


def test_ledger_status_transitions_valid():
    ledger = DistillationLedger()
    e1 = ledger.record(ref="P3", text="Domain-gated governance", source="opus-5 audit", status="proposed")
    e2 = ledger.record(ref="P3", text="Domain-gated governance", source="opus-5 audit", status="enforced")
    # latest status wins
    assert ledger.status_of("P3") == "enforced"


def test_principle_without_ledger_entry_is_advisory():
    ledger = DistillationLedger()
    # P7 is in the ledger (from CONSTITUTION); an unrecorded ref is advisory.
    ledger.record(ref="P7", text="Least Sufficient Intervention", source="opus-5 audit", status="enforced")
    assert ledger.is_enforced("P7") is True
    assert ledger.is_enforced("P99") is False  # no entry -> advisory only


def test_ledger_persists_to_disk(tmp_path):
    p = tmp_path / "ledger.jsonl"
    ledger = DistillationLedger(path=str(p))
    ledger.record(ref="P1", text="Requisite Variety", source="opus-5 audit", status="enforced")
    ledger2 = DistillationLedger(path=str(p))
    assert ledger2.is_enforced("P1") is True
