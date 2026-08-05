"""TDD tests for strong-model review #2 fix: the council must fuse REAL disagreement, not echo.

Verifies: (a) distinct sages emit DISTINCT view bodies (no consensus theater), and (b) the
conflict detector fires on genuinely opposing stances across the real registry council.
"""

from agents.sage_council import build_council_from_registry, Sage, SageCouncil


def _strip_name(view: str) -> str:
    # remove the [name|refs] prefix so we compare the actual stance body
    return view.split("] ", 1)[1] if "] " in view else view


def test_distinct_sages_emit_distinct_view_bodies():
    c = build_council_from_registry()
    m = {"complexity_score": 9, "repeated_hypothesis_count": 3,
         "breach_count": 2, "success_rate": 0.4}
    out = c.convene(m)
    bodies = [_strip_name(v) for v in out["views"]]
    # strong-model review measured 1 distinct body across 14 sages -> must now be > 1
    assert len(set(bodies)) > 1, f"consensus theater: all bodies identical -> {bodies[0]}"


def test_conflict_detected_on_opposing_stances():
    # a governance sage (P1->raise_variety) and a systems sage (P7->prune_unused) oppose
    sages = [
        Sage("gov", ["P1"], role="governance", weight=1.3),
        Sage("sys", ["P7"], role="systems_layer", weight=1.2),
    ]
    c = SageCouncil(sages=sages, topology="peer", complexity_threshold=4)
    out = c.convene({"complexity_score": 9, "breach_count": 2,
                     "repeated_hypothesis_count": 0, "success_rate": 0.5})
    assert out["consensus"]["conflicts"], "expected a detected conflict between grow vs cut"
    assert "CONFLICTS" in out["reconciled_spec"]


def test_council_still_produces_falsifiable_spec():
    c = build_council_from_registry()
    out = c.convene({"complexity_score": 9, "breach_count": 1,
                     "repeated_hypothesis_count": 2, "success_rate": 0.6})
    assert "DIAALECTIC" in out["reconciled_spec"]
    assert "FALSIFICATION" in out["reconciled_spec"]
