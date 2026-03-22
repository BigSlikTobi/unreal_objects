"""Prompt templates for LLM-powered case generation."""

CASE_GENERATION_SYSTEM_PROMPT = """\
You are a realistic customer support case generator for a mid-size e-commerce company.

Your job is to produce ONE support case at a time as JSON. Each case must feel like a real \
inbound customer request — varied language, realistic details, and plausible scenarios.

The company sells electronics, home goods, and clothing online. Customers contact support \
via email, chat, phone, and social media.

You must return valid JSON matching this schema:
{
  "case_type": one of "account_update", "refund_request", "escalation", "sensitive_change", "suspicious_request",
  "customer_tier": one of "basic", "premium", "enterprise",
  "priority": one of "low", "medium", "high", "critical",
  "risk_score": float 0-100,
  "requested_action": string describing what the customer wants,
  "channel": one of "email", "chat", "phone", "social_media",
  "account_age_days": integer,
  "order_value": float,
  "refund_amount": float (0 if not a refund),
  "requires_identity_check": boolean,
  "contains_policy_exception": boolean,
  "narrative": string — a 2-4 sentence realistic description of the situation
}

Rules:
- risk_score should correlate with case severity (suspicious requests: 50-100, sensitive changes: 20-80, routine: 0-40)
- refund_amount should only be non-zero for refund_request cases
- narrative should sound like a real case note, not a template
- Vary the tone, specificity, and detail level across cases
- Do NOT include expected_business_path — that will be computed separately
"""


def build_case_prompt(
    customer_name: str | None = None,
    customer_history: dict | None = None,
    time_context: str | None = None,
    case_type_hint: str | None = None,
) -> str:
    parts = ["Generate one realistic support case."]

    if case_type_hint:
        parts.append(f"Case type should be: {case_type_hint}")

    if customer_name:
        parts.append(f"Customer name: {customer_name}")

    if customer_history:
        order_count = customer_history.get("total_orders", 0)
        prev_cases = customer_history.get("previous_cases", 0)
        tier = customer_history.get("tier", "basic")
        parts.append(
            f"Customer context: {tier} tier, {order_count} past orders, "
            f"{prev_cases} previous support cases"
        )

    if time_context:
        parts.append(f"Current time context: {time_context}")

    parts.append("Return ONLY the JSON object, no markdown fences or extra text.")
    return "\n".join(parts)
