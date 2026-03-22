"""Deterministic case generator for batch/fallback mode."""

import random
from support_company.models import (
    CaseType,
    CustomerTier,
    Priority,
    SupportCase,
)

# Weighted case families for realistic distribution
CASE_FAMILIES = [
    (CaseType.ACCOUNT_UPDATE, 0.30),
    (CaseType.REFUND_REQUEST, 0.25),
    (CaseType.ESCALATION, 0.20),
    (CaseType.SENSITIVE_CHANGE, 0.15),
    (CaseType.SUSPICIOUS_REQUEST, 0.10),
]

CHANNELS = ["email", "chat", "phone", "social_media"]
TIERS = list(CustomerTier)
PRIORITIES = list(Priority)

REQUESTED_ACTIONS = {
    CaseType.ACCOUNT_UPDATE: [
        "Update shipping address",
        "Change email address",
        "Update phone number",
        "Modify notification preferences",
    ],
    CaseType.REFUND_REQUEST: [
        "Full refund for order",
        "Partial refund for damaged item",
        "Refund for late delivery",
        "Store credit request",
    ],
    CaseType.ESCALATION: [
        "Escalate unresolved complaint",
        "Manager callback requested",
        "Formal complaint filing",
        "Service recovery request",
    ],
    CaseType.SENSITIVE_CHANGE: [
        "Change payment method",
        "Update bank account for payouts",
        "Change account owner",
        "Reset two-factor authentication",
    ],
    CaseType.SUSPICIOUS_REQUEST: [
        "Bulk order from new account",
        "Address change right before shipment",
        "Multiple refund attempts",
        "Account access from new region",
    ],
}


def _pick_weighted(items: list[tuple], rng: random.Random):
    values, weights = zip(*items)
    return rng.choices(values, weights=weights, k=1)[0]


def _compute_expected_path(case_type: CaseType, risk_score: float, **kwargs) -> str:
    if risk_score > 90:
        return "REJECT"
    if case_type == CaseType.SUSPICIOUS_REQUEST:
        if risk_score > 80:
            return "REJECT"
        return "ASK_FOR_APPROVAL"
    if case_type == CaseType.SENSITIVE_CHANGE:
        return "ASK_FOR_APPROVAL"
    if case_type == CaseType.REFUND_REQUEST and kwargs.get("refund_amount", 0) > 500:
        return "ASK_FOR_APPROVAL"
    if case_type == CaseType.ESCALATION:
        if kwargs.get("priority") == Priority.CRITICAL:
            return "ASK_FOR_APPROVAL"
        if kwargs.get("customer_tier") == CustomerTier.ENTERPRISE:
            return "ASK_FOR_APPROVAL"
    if kwargs.get("requires_identity_check"):
        return "ASK_FOR_APPROVAL"
    if kwargs.get("contains_policy_exception"):
        return "ASK_FOR_APPROVAL"
    if case_type == CaseType.ACCOUNT_UPDATE and risk_score > 70:
        return "ASK_FOR_APPROVAL"
    return "APPROVE"


def generate_case(seed: int | None = None, index: int = 0) -> SupportCase:
    rng = random.Random(seed if seed is not None else None)
    # Advance state for index so batch generation is deterministic per-index
    for _ in range(index):
        rng.random()

    case_type = _pick_weighted(CASE_FAMILIES, rng)
    tier = rng.choice(TIERS)
    priority = rng.choice(PRIORITIES)
    channel = rng.choice(CHANNELS)
    action = rng.choice(REQUESTED_ACTIONS[case_type])
    account_age = rng.randint(1, 3650)
    order_value = round(rng.uniform(10, 2000), 2)

    # Risk score distribution depends on case type
    if case_type == CaseType.SUSPICIOUS_REQUEST:
        risk_score = round(rng.uniform(50, 100), 1)
    elif case_type == CaseType.SENSITIVE_CHANGE:
        risk_score = round(rng.uniform(20, 80), 1)
    else:
        risk_score = round(rng.uniform(0, 60), 1)

    refund_amount = round(rng.uniform(10, 1500), 2) if case_type == CaseType.REFUND_REQUEST else 0.0
    requires_identity = case_type == CaseType.SENSITIVE_CHANGE or rng.random() < 0.1
    policy_exception = rng.random() < 0.08

    expected = _compute_expected_path(
        case_type, risk_score,
        refund_amount=refund_amount,
        priority=priority,
        customer_tier=tier,
        requires_identity_check=requires_identity,
        contains_policy_exception=policy_exception,
    )

    return SupportCase(
        case_type=case_type,
        customer_tier=tier,
        priority=priority,
        risk_score=risk_score,
        requested_action=action,
        channel=channel,
        account_age_days=account_age,
        order_value=order_value,
        refund_amount=refund_amount,
        requires_identity_check=requires_identity,
        contains_policy_exception=policy_exception,
        expected_business_path=expected,
    )


def generate_batch(count: int = 10, seed: int = 42) -> list[SupportCase]:
    return [generate_case(seed=seed, index=i) for i in range(count)]
