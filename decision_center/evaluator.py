from typing import List, Dict, Any
from .models import DecisionOutcome

import re

def basic_evaluate_rule(rule_logic: str, context: Dict[str, Any]) -> str | None:
    """
    Evaluates simple rule expressions like:
      "IF amount > 500 THEN ASK_FOR_APPROVAL"
      "IF amount < 200 THEN APPROVE"
    Supports operators: >, <, >=, <=, ==, !=
    """
    pattern = r"IF\s+(\w+)\s*(>=|<=|!=|>|<|==)\s*(\d+(?:\.\d+)?)\s+THEN\s+(\w+)"
    match = re.match(pattern, rule_logic.strip(), re.IGNORECASE)
    if not match:
        return None
    
    field, operator, threshold_str, outcome = match.groups()
    threshold = float(threshold_str)
    value = context.get(field.lower())
    
    if not isinstance(value, (int, float)):
        return None
    
    ops = {
        ">": value > threshold,
        "<": value < threshold,
        ">=": value >= threshold,
        "<=": value <= threshold,
        "==": value == threshold,
        "!=": value != threshold,
    }
    
    if ops.get(operator, False):
        return outcome.upper()
    return None

import httpx

async def _fetch_group(group_id: str):
    """Extracted to allow clean mocking in tests without patching all of httpx."""
    async with httpx.AsyncClient() as client:
        return await client.get(f"http://127.0.0.1:8001/v1/groups/{group_id}")

async def evaluate_request(context: Dict[str, Any], group_id: str | None) -> tuple[DecisionOutcome, list[str]]:
    if not group_id:
        # Default behavior: execute without rules
        return DecisionOutcome.APPROVE, []

    # Fetch rules from rule engine
    try:
        resp = await _fetch_group(group_id)
        if resp.status_code != 200:
            return DecisionOutcome.ASK_FOR_APPROVAL, ["unreachable_or_missing_group"]
        group_data = resp.json()
        rules = group_data.get("rules", [])
    except httpx.RequestError:
        return DecisionOutcome.ASK_FOR_APPROVAL, ["rule_engine_unreachable"]

    # Evaluate rules
    outcomes = []
    matched = []
    for r in rules:
        res = basic_evaluate_rule(r["rule_logic"], context)
        if res == "REJECT":
            outcomes.append(DecisionOutcome.REJECT)
            matched.append(r["id"])
        elif res == "ASK_FOR_APPROVAL":
            outcomes.append(DecisionOutcome.ASK_FOR_APPROVAL)
            matched.append(r["id"])
        elif res == "APPROVE":
            outcomes.append(DecisionOutcome.APPROVE)
            matched.append(r["id"])

    # Apply most restrictive wins
    if DecisionOutcome.REJECT in outcomes:
        return DecisionOutcome.REJECT, matched
    if DecisionOutcome.ASK_FOR_APPROVAL in outcomes:
        return DecisionOutcome.ASK_FOR_APPROVAL, matched
    
    # Either all approved or no matching rules (default to APPROVE per spec)
    return DecisionOutcome.APPROVE, matched
