from typing import List, Dict, Any
from .models import DecisionOutcome

import re

def basic_evaluate_rule(rule_logic: str, context: Dict[str, Any]) -> str | None:
    """
    Evaluates simple rule expressions like:
      "IF amount > 500 THEN ASK_FOR_APPROVAL"
      "IF amount < 200 THEN APPROVE"
      "IF status == ACTIVE THEN APPROVE"
      "IF contract_partner = 'Amazon' THEN ASK_FOR_APPROVAL"
    Supports operators: >, <, >=, <=, ==, !=, =
    """
    pattern = r"IF\s+(\w+)\s*(>=|<=|!=|>|<|==|=)\s*(.+?)\s+THEN\s+(\w+)"
    match = re.match(pattern, rule_logic.strip(), re.IGNORECASE)
    if not match:
        return None
    
    field, operator, threshold_str, outcome = match.groups()
    value = context.get(field.lower())
    
    # Clean threshold string of quotes if present
    if threshold_str.startswith(("'", '"')) and threshold_str.endswith(("'", '"')):
        threshold_val = threshold_str[1:-1]
    else:
        try:
            threshold_val = float(threshold_str)
        except ValueError:
            threshold_val = threshold_str

    if operator == "=":
        operator = "=="

    if value is None:
        # Fail closed if field is missing but rule expects it
        return "ASK_FOR_APPROVAL"

    def safe_compare(op, a, b):
        try:
            if op == ">": return a > b
            if op == "<": return a < b
            if op == ">=": return a >= b
            if op == "<=": return a <= b
            if op == "==":
                if isinstance(a, str) and isinstance(b, str):
                    return a.lower() == b.lower()
                if type(a) != type(b) and not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
                    raise ValueError("Type mismatch in ==")
                return a == b
            if op == "!=":
                if isinstance(a, str) and isinstance(b, str):
                    return a.lower() != b.lower()
                if type(a) != type(b) and not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
                    raise ValueError("Type mismatch in !=")
                return a != b
        except TypeError:
            raise ValueError("Type mismatch")
        return False
    
    try:
        if safe_compare(operator, value, threshold_val):
            return outcome.upper()
    except ValueError:
        # Fail closed if type mismatch occurs
        return "ASK_FOR_APPROVAL"
        
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
        # Evaluate edge cases first
        edge_cases = r.get("edge_cases", [])
        edge_case_matched = False
        if edge_cases:
            for ec in edge_cases:
                ec_res = basic_evaluate_rule(ec, context)
                if ec_res:
                    edge_case_matched = True
                    if ec_res == "REJECT":
                        outcomes.append(DecisionOutcome.REJECT)
                        matched.append(r["id"])
                    elif ec_res == "ASK_FOR_APPROVAL":
                        outcomes.append(DecisionOutcome.ASK_FOR_APPROVAL)
                        matched.append(r["id"])
                    elif ec_res == "APPROVE":
                        outcomes.append(DecisionOutcome.APPROVE)
                        matched.append(r["id"])
                    break # Only one edge case needs to match to branch logic
        
        # Only evaluate rule_logic if no edge case overrode it
        if not edge_case_matched:
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
