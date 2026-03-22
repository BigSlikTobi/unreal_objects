"""Tests for the deterministic case generator (batch/fallback mode)."""

from support_company.generator import generate_batch, generate_case
from support_company.models import CaseType, SupportCase


def test_generate_case_returns_support_case():
    case = generate_case(seed=42)
    assert isinstance(case, SupportCase)
    assert case.case_id is not None
    assert case.case_type in list(CaseType)


def test_seeded_generation_is_deterministic():
    case1 = generate_case(seed=42, index=0)
    case2 = generate_case(seed=42, index=0)
    assert case1.case_type == case2.case_type
    assert case1.risk_score == case2.risk_score
    assert case1.requested_action == case2.requested_action


def test_different_indices_produce_different_cases():
    case1 = generate_case(seed=42, index=0)
    case2 = generate_case(seed=42, index=5)
    # Very unlikely to be identical across different indices
    assert case1.case_id != case2.case_id


def test_generate_batch():
    cases = generate_batch(count=20, seed=42)
    assert len(cases) == 20
    # Should have multiple case types in a batch of 20
    types = {c.case_type for c in cases}
    assert len(types) >= 2


def test_expected_business_path_always_set():
    cases = generate_batch(count=50, seed=99)
    for case in cases:
        assert case.expected_business_path in ("APPROVE", "REJECT", "ASK_FOR_APPROVAL")


def test_refund_amount_only_for_refunds():
    cases = generate_batch(count=100, seed=42)
    for case in cases:
        if case.case_type != CaseType.REFUND_REQUEST:
            assert case.refund_amount == 0.0


def test_suspicious_requests_have_higher_risk():
    cases = generate_batch(count=200, seed=42)
    suspicious = [c for c in cases if c.case_type == CaseType.SUSPICIOUS_REQUEST]
    if suspicious:
        avg_risk = sum(c.risk_score for c in suspicious) / len(suspicious)
        assert avg_risk >= 50  # Suspicious cases: risk_score uniform 50-100


def test_case_required_fields():
    case = generate_case(seed=1)
    assert case.case_type is not None
    assert case.customer_tier is not None
    assert case.priority is not None
    assert case.channel in ("email", "chat", "phone", "social_media")
    assert case.account_age_days >= 1
