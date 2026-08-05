"""TDD tests for Task A: methodology reconciliation (G1, C1-C5, F2).

Verifies that the five contradictions + the metric-honesty fallacy each have an explicit
ruling recorded in CONSTITUTION Article VI Section 1b, and that the reconciliation doc
exists. This is the "contract" that the reconciliation actually happened, not just talk.
"""

from pathlib import Path

CONSTITUTION = Path("CONSTITUTION.md").read_text(encoding="utf-8")
RECON_DOC = Path("docs/reconciliation/METHODOLOGY-RECONCILIATION.md")


def test_reconciliation_doc_exists():
    assert RECON_DOC.exists()
    text = RECON_DOC.read_text(encoding="utf-8")
    # Every contradiction label present
    for label in ["C1", "C2", "C3", "C4", "C5"]:
        assert f"### {label}" in text, f"{label} missing from reconciliation doc"
    # Every fallacy label present
    for label in ["F1", "F2", "F3"]:
        assert f"### {label}" in text, f"{label} missing from reconciliation doc"


def test_constitution_has_reconciliation_section():
    assert "Section 1b: Reconciliation Rulings" in CONSTITUTION


def test_each_contradiction_has_ruling_in_constitution():
    for ruling in ["Ruling C1", "Ruling C2", "Ruling C3", "Ruling C4", "Ruling C5"]:
        assert ruling in CONSTITUTION, f"{ruling} not recorded in CONSTITUTION"


def test_ruling_c1_meta_loop_is_proposer_only():
    # C1: meta-loop proposes, never auto-applies
    idx = CONSTITUTION.index("Ruling C1")
    snippet = CONSTITUTION[idx:idx + 400]
    assert "proposer only" in snippet
    assert "human checkpoint" in snippet or "reversible" in snippet


def test_ruling_c3_llm_boundary_narrowed():
    # C3: Law 11 = no LLM in verdict only; reflection is input
    idx = CONSTITUTION.index("Ruling C3")
    snippet = CONSTITUTION[idx:idx + 400]
    assert "verdict" in snippet
    assert "input to propose" in snippet


def test_ruling_f2_metric_split_recorded():
    # F2: governance_score separate from success_rate
    idx = CONSTITUTION.index("Ruling F2")
    snippet = CONSTITUTION[idx:idx + 400]
    assert "governance_score" in snippet
    assert "success_rate" in snippet
