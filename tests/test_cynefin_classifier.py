"""TDD tests for Task C: Cynefin domain classifier (G3, C4/P3).

Replaces the keyword-based detect_task_type with a Cynefin classifier that derives
control intensity from domain + reversibility, not substring matching. Resolves C4
(P3 says domain-gated, not keyword-gated).
"""

from agents.cynefin_classifier import (
    classify_domain,
    DOMAIN_CONTROL,
    CynefinDomain,
)


def test_classify_clear_high_confidence():
    d = classify_domain("Build a login page with email auth", reversibility="reversible")
    assert d.domain == CynefinDomain.CLEAR
    # Clear + reversible -> VERIFY only
    assert DOMAIN_CONTROL[d.domain]["control"] == "verify_only"


def test_classify_complex_low_reversibility():
    d = classify_domain(
        "Migrate legacy monolith to microservices with zero downtime, many unknowns",
        reversibility="irreversible",
    )
    assert d.domain in (CynefinDomain.COMPLEX, CynefinDomain.CHAOTIC)
    # Complex/Chaotic -> probe budget or human
    assert DOMAIN_CONTROL[d.domain]["control"] in ("probe_budget", "human")


def test_classify_complicated():
    d = classify_domain(
        "Implement OAuth2 + OIDC with MFA per SOC2 spec", reversibility="reversible"
    )
    assert d.domain == CynefinDomain.COMPLICATED
    assert DOMAIN_CONTROL[d.domain]["control"] == "analysis_plus_verify"


def test_classifier_ignores_keyword_hints_for_domain():
    # The keyword router would call this "humaneval"; Cynefin cares about ambiguity+
    # reversibility, not the word. A precise, reversible spec is Complicated, not Complex.
    d = classify_domain("Solve humaneval/116 sort_array", reversibility="reversible")
    assert d.domain != CynefinDomain.CHAOTIC
    # It's a well-defined function with a clear spec -> Clear/Complicated, not Chaotic.
    assert d.domain in (CynefinDomain.CLEAR, CynefinDomain.COMPLICATED)


def test_control_intensity_matches_p3():
    # P3: Clear+high conf -> VERIFY only; Complicated -> analysis+VERIFY;
    # Complex -> probe budget; Chaotic -> immediate human.
    assert DOMAIN_CONTROL[CynefinDomain.CLEAR]["control"] == "verify_only"
    assert DOMAIN_CONTROL[CynefinDomain.COMPLICATED]["control"] == "analysis_plus_verify"
    assert DOMAIN_CONTROL[CynefinDomain.COMPLEX]["control"] == "probe_budget"
    assert DOMAIN_CONTROL[CynefinDomain.CHAOTIC]["control"] == "human"
