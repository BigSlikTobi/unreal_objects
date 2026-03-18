import re
import httpx
from typing import List, Dict, Any
from .models import DecisionOutcome
from json_logic import jsonLogic, add_operation
import difflib

def extract_vars_from_jsonlogic(logic: Any, vars_set: set):
    """Recursively finds all requested variables in a JSON Logic dict."""
    if isinstance(logic, dict):
        if "var" in logic:
            var_val = logic["var"]
            if isinstance(var_val, str):
                vars_set.add(var_val)
            elif isinstance(var_val, list) and len(var_val) > 0 and isinstance(var_val[0], str):
                vars_set.add(var_val[0])
        else:
            for v in logic.values():
                extract_vars_from_jsonlogic(v, vars_set)
    elif isinstance(logic, list):
        for item in logic:
            extract_vars_from_jsonlogic(item, vars_set)

def map_missing_variables(rule_json: dict, context: Dict[str, Any]):
    """
    Finds required variables in rule_json. If missing from context, 
    fuzzily matches them against available keys and aliases them.
    """
    if not rule_json:
        return
        
    required_vars = set()
    extract_vars_from_jsonlogic(rule_json, required_vars)
    
    available_keys = list(context.keys())
    
    for req_var in required_vars:
        if req_var not in context:
            # 1. Substring Match (e.g., "amount" in "transaction_amount" or vice versa)
            substring_matches = [k for k in available_keys if req_var in k or k in req_var]
            if substring_matches:
                # Pick the shortest match to avoid overly broad grabs
                best_match = min(substring_matches, key=len)
                context[req_var] = context[best_match]
                continue
                
            # 2. Fuzzy Match Backup
            matches = difflib.get_close_matches(req_var, available_keys, n=1, cutoff=0.4)
            if matches:
                alias = matches[0]
                context[req_var] = context[alias]

# ── Type coercion helpers ──
# Agents and UIs send context values as strings ("500", "true") while JSON Logic
# rules use native types (500, true).  Rather than failing closed on every
# type mismatch, we attempt safe coercion at the operator level so that the
# rule can be evaluated correctly.

def _try_coerce_numeric(s: str):
    """Attempt to parse a string as int or float.  Returns the original string on failure."""
    try:
        return int(s) if "." not in s else float(s)
    except (ValueError, OverflowError):
        return s


def _coerce_pair(a, b):
    """If one side is a string and the other a number, try to coerce the string.

    Returns the (possibly coerced) pair.  Does NOT coerce bool strings here —
    that is handled upstream in _coerce_bool_strings so it covers all operators
    uniformly.
    """
    if isinstance(a, str) and isinstance(b, (int, float)) and not isinstance(b, bool):
        a = _try_coerce_numeric(a)
    elif isinstance(b, str) and isinstance(a, (int, float)) and not isinstance(a, bool):
        b = _try_coerce_numeric(b)
    return a, b


# Enforce fail-closed type checking within JSON Logic
def strict_eq(a, b):
    if a is None or b is None: raise ValueError("Missing data")
    a, b = _coerce_pair(a, b)
    if type(a) != type(b) and not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        raise ValueError("Type mismatch in ==")
    if isinstance(a, str) and isinstance(b, str): return a.lower() == b.lower()
    return a == b

def strict_neq(a, b):
    if a is None or b is None: raise ValueError("Missing data")
    a, b = _coerce_pair(a, b)
    if type(a) != type(b) and not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        raise ValueError("Type mismatch in !=")
    if isinstance(a, str) and isinstance(b, str): return a.lower() != b.lower()
    return a != b

def strict_gt(a, b):
    if a is None or b is None: raise ValueError("Missing data")
    a, b = _coerce_pair(a, b)
    return a > b

def strict_lt(a, b):
    if a is None or b is None: raise ValueError("Missing data")
    a, b = _coerce_pair(a, b)
    return a < b

def strict_gte(a, b):
    if a is None or b is None: raise ValueError("Missing data")
    a, b = _coerce_pair(a, b)
    return a >= b

def strict_lte(a, b):
    if a is None or b is None: raise ValueError("Missing data")
    a, b = _coerce_pair(a, b)
    return a <= b

# Overwrite built-ins to secure them
add_operation("==", strict_eq)
add_operation("!=", strict_neq)
add_operation(">", strict_gt)
add_operation("<", strict_lt)
add_operation(">=", strict_gte)
add_operation("<=", strict_lte)
add_operation("=", strict_eq)

def legacy_evaluate_rule(rule_logic: str, context: Dict[str, Any]) -> str | None:
    """Legacy string-based rule evaluation."""
    pattern = r"IF\s+(\w+)\s*(>=|<=|!=|>|<|==|=)\s*(.+?)\s+THEN\s+(\w+)"
    match = re.match(pattern, rule_logic.strip(), re.IGNORECASE)
    if not match:
        return None
    
    field, operator, threshold_str, outcome = match.groups()
    value = context.get(field.lower())
    
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
        # Missing data — escalate to human, never silently approve or reject
        return "ASK_FOR_APPROVAL"

    try:
        if operator == "==" and strict_eq(value, threshold_val): return outcome.upper()
        if operator == "!=" and strict_neq(value, threshold_val): return outcome.upper()
        if operator == ">" and strict_gt(value, threshold_val): return outcome.upper()
        if operator == "<" and strict_lt(value, threshold_val): return outcome.upper()
        if operator == ">=" and strict_gte(value, threshold_val): return outcome.upper()
        if operator == "<=" and strict_lte(value, threshold_val): return outcome.upper()
    except (ValueError, TypeError):
        # Type mismatch after coercion — we cannot evaluate the rule, so we
        # must not claim it matched.  Always escalate to human review.
        return "ASK_FOR_APPROVAL"
        
    return None

def _coerce_bool_strings(context: Dict[str, Any]) -> None:
    """Coerce string 'true'/'false' values to actual booleans.

    JSON Logic rules use real booleans, but callers (UI, agents) sometimes
    send string representations.  Without coercion, strict_eq raises a type
    mismatch and the rule fail-closes instead of evaluating correctly.
    """
    for k, v in context.items():
        if isinstance(v, str):
            low = v.lower()
            if low == "true":
                context[k] = True
            elif low == "false":
                context[k] = False


def evaluate_rule(rule_json: dict | None, rule_logic: str, context: Dict[str, Any]) -> str | None:
    """Evaluates rules using JSON Logic if available, falling back to legacy string parsing."""
    if not rule_json:
        return legacy_evaluate_rule(rule_logic, context)

    try:
        # Coerce string booleans before evaluation
        _coerce_bool_strings(context)
        # Map missing variables via fuzzy matching before evaluating
        map_missing_variables(rule_json, context)

        # Evaluate safely
        result = jsonLogic(rule_json, context)
        if result in ["APPROVE", "REJECT", "ASK_FOR_APPROVAL"]:
            return result
        # If False/None, the condition wasn't met
        return None
    except (ValueError, TypeError):
        # Type mismatch or missing data *after* coercion — we cannot
        # determine what the rule would have decided, so we must not claim
        # it matched (REJECT) or that it didn't (APPROVE).  Always
        # escalate to human review.
        return "ASK_FOR_APPROVAL"

import httpx

async def _fetch_group(group_id: str):
    """Extracted to allow clean mocking in tests without patching all of httpx."""
    async with httpx.AsyncClient() as client:
        return await client.get(f"http://127.0.0.1:8001/v1/groups/{group_id}")

async def evaluate_request(
    context: Dict[str, Any],
    group_id: str | None,
    rule_id: str | None = None,
) -> tuple[DecisionOutcome, list[str], list[dict]]:
    if not group_id:
        # Default behavior: execute without rules
        return DecisionOutcome.APPROVE, [], []

    # Fetch rules from rule engine
    try:
        resp = await _fetch_group(group_id)
        if resp.status_code != 200:
            return DecisionOutcome.ASK_FOR_APPROVAL, ["unreachable_or_missing_group"], []
        group_data = resp.json()
        rules = group_data.get("rules", [])
    except httpx.RequestError:
        return DecisionOutcome.ASK_FOR_APPROVAL, ["rule_engine_unreachable"], []

    if rule_id:
        rules = [rule for rule in rules if rule.get("id") == rule_id]
        if not rules:
            return DecisionOutcome.ASK_FOR_APPROVAL, ["rule_not_found"], []

    # Evaluate rules
    outcomes = []
    matched = []
    matched_details = []
    
    for r in rules:
        if r.get("active", True) is False:
            continue

        # Evaluate edge cases first
        edge_cases = r.get("edge_cases", [])
        edge_cases_json = r.get("edge_cases_json", [])
        edge_case_matched = False
        if edge_cases:
            for i, ec_str in enumerate(edge_cases):
                ec_json = edge_cases_json[i] if i < len(edge_cases_json) else {}
                ec_res = evaluate_rule(ec_json, ec_str, context)
                if ec_res:
                    edge_case_matched = True
                    matched.append(r["id"])
                    matched_details.append({
                        "rule_id": r["id"],
                        "rule_name": r.get("name", "Unknown Rule"),
                        "hit_type": "edge_case",
                        "trigger_expression": ec_str
                    })
                    if ec_res == "REJECT":
                        outcomes.append(DecisionOutcome.REJECT)
                    elif ec_res == "ASK_FOR_APPROVAL":
                        outcomes.append(DecisionOutcome.ASK_FOR_APPROVAL)
                    elif ec_res == "APPROVE":
                        outcomes.append(DecisionOutcome.APPROVE)
                    break # Only one edge case needs to match to branch logic
        
        # Only evaluate rule_logic if no edge case overrode it
        if not edge_case_matched:
            r_json = r.get("rule_logic_json", {})
            res = evaluate_rule(r_json, r["rule_logic"], context)
            if res:
                matched.append(r["id"])
                matched_details.append({
                    "rule_id": r["id"],
                    "rule_name": r.get("name", "Unknown Rule"),
                    "hit_type": "rule_logic",
                    "trigger_expression": r.get("rule_logic", "Unknown Logic")
                })
                if res == "REJECT":
                    outcomes.append(DecisionOutcome.REJECT)
                elif res == "ASK_FOR_APPROVAL":
                    outcomes.append(DecisionOutcome.ASK_FOR_APPROVAL)
                elif res == "APPROVE":
                    outcomes.append(DecisionOutcome.APPROVE)

    # Apply most restrictive wins
    if DecisionOutcome.REJECT in outcomes:
        return DecisionOutcome.REJECT, matched, matched_details
    if DecisionOutcome.ASK_FOR_APPROVAL in outcomes:
        return DecisionOutcome.ASK_FOR_APPROVAL, matched, matched_details
    
    # Either all approved or no matching rules (default to APPROVE per spec)
    return DecisionOutcome.APPROVE, matched, matched_details
