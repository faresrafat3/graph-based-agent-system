"""TDD test for opus5_consult channel + ledger integration (Task G7).

Mocks the consult so we don't call the network in CI. Asserts the review is recorded in
the ledger as independent provenance (not self-written), per Fares's 'opus-5 participates'.
"""

from system.distillation_ledger import DistillationLedger, attach_opus5_review


def test_attach_opus5_review_records_provenance(tmp_path, monkeypatch):
    # Stub consult_opus5 to avoid the live network call in tests.
    import system.distillation_ledger as dl

    class FakeReview:
        def __init__(self, rid, text):
            self.ok = True
        @property
        def reply(self): return "stub opus-5 critique"
        @property
        def channel(self): return "agentrouter-org/claude-opus-5"

    def fake_review(ruling_id, ruling_text):
        return {"ruling_id": ruling_id, "opus5_reply": "stub opus-5 critique",
                "channel": "agentrouter-org/claude-opus-5"}

    monkeypatch.setattr(dl, "review_ruling" if False else "attach_opus5_review", attach_opus5_review)
    # Monkeypatch the inner consult instead:
    import system.opus5_consult as oc
    monkeypatch.setattr(oc, "review_ruling", fake_review)

    ledger = DistillationLedger(path=str(tmp_path / "ledger.jsonl"))
    ledger.record(ref="C1", text="meta-loop proposes only", source="opus-5 audit", status="enforced")
    prov = attach_opus5_review(ledger, "C1", "meta-loop proposes only")

    assert prov["type"] == "opus5_review"
    assert prov["ruling_id"] == "C1"
    # The review line was appended to the ledger file.
    lines = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
    assert any('"opus5_review"' in ln for ln in lines)
