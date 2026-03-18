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

def _split_var_parts(name: str) -> set[str]:
    """Split a variable name into semantic parts (by underscore)."""
    return {p for p in name.lower().split("_") if p}


def map_missing_variables(rule_json: dict, context: Dict[str, Any]):
    """
    Finds required variables in rule_json. If missing from context,
    fuzzily matches them against available keys and aliases them.

    Matching strategy (in order):
    1. Containment match — one name fully contains the other AND they share
       at least one semantic word part beyond common suffixes like 'score',
       'amount', 'days', 'rate', 'pct', 'count', 'id', 'value', 'time'.
    2. Fuzzy match — difflib with cutoff=0.7 (raised from 0.4 to prevent
       false positives on shared suffixes).
    """
    if not rule_json:
        return

    required_vars = set()
    extract_vars_from_jsonlogic(rule_json, required_vars)

    available_keys = list(context.keys())
    # Common suffixes that should NOT be sufficient for a match on their own
    _GENERIC_PARTS = {"score", "amount", "days", "rate", "pct", "count", "id", "value", "time", "kg", "km"}

    for req_var in required_vars:
        if req_var not in context:
            req_parts = _split_var_parts(req_var)

            # 1. Containment match with semantic overlap check
            substring_matches = [k for k in available_keys if req_var in k or k in req_var]
            if substring_matches:
                best_match = None
                for candidate in substring_matches:
                    cand_parts = _split_var_parts(candidate)
                    shared = req_parts & cand_parts
                    # Single-part variable names (e.g. "amount") that are fully
                    # contained in a context key are always valid matches.
                    # For multi-part names, require a shared part beyond generic
                    # suffixes to prevent e.g. aml_score → credit_score.
                    if len(req_parts) <= 1:
                        ok = bool(shared)
                    else:
                        ok = bool(shared - _GENERIC_PARTS)
                    if ok:
                        if best_match is None or len(candidate) < len(best_match):
                            best_match = candidate
                if best_match is not None:
                    context[req_var] = context[best_match]
                    continue

            # 2. Fuzzy match backup (stricter cutoff + semantic check)
            matches = difflib.get_close_matches(req_var, available_keys, n=1, cutoff=0.7)
            if matches:
                alias = matches[0]
                # Apply same semantic check: multi-part names must share
                # a meaningful (non-generic) part to prevent false positives.
                alias_parts = _split_var_parts(alias)
                shared = req_parts & alias_parts
                if len(req_parts) <= 1 or bool(shared - _GENERIC_PARTS):
                    context[req_var] = context[alias]

# Enforce fail-closed type checking within JSON Logic
def strict_eq(a, b):
    if a is None or b is None: raise ValueError("Missing data")
    if type(a) != type(b) and not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        raise ValueError("Type mismatch in ==")
    if isinstance(a, str) and isinstance(b, str): return a.lower() == b.lower()
    return a == b

def strict_neq(a, b):
    if a is None or b is None: raise ValueError("Missing data")
    if type(a) != type(b) and not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        raise ValueError("Type mismatch in !=")
    if isinstance(a, str) and isinstance(b, str): return a.lower() != b.lower()
    return a != b

def strict_gt(a, b):
    if a is None or b is None: raise ValueError("Missing data")
    return a > b

def strict_lt(a, b):
    if a is None or b is None: raise ValueError("Missing data")
    return a < b

def strict_gte(a, b):
    if a is None or b is None: raise ValueError("Missing data")
    return a >= b

def strict_lte(a, b):
    if a is None or b is None: raise ValueError("Missing data")
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

    _RESTRICTIVE = {"REJECT", "ASK_FOR_APPROVAL"}
    fail_closed_outcome = outcome.upper() if outcome.upper() in _RESTRICTIVE else "ASK_FOR_APPROVAL"

    if value is None: return fail_closed_outcome

    try:
        if operator == "==" and strict_eq(value, threshold_val): return outcome.upper()
        if operator == "!=" and strict_neq(value, threshold_val): return outcome.upper()
        if operator == ">" and strict_gt(value, threshold_val): return outcome.upper()
        if operator == "<" and strict_lt(value, threshold_val): return outcome.upper()
        if operator == ">=" and strict_gte(value, threshold_val): return outcome.upper()
        if operator == "<=" and strict_lte(value, threshold_val): return outcome.upper()
    except (ValueError, TypeError):
        return fail_closed_outcome
        
    return None

def evaluate_rule(rule_json: dict | None, rule_logic: str, context: Dict[str, Any]) -> str | None:
    """Evaluates rules using JSON Logic if available, falling back to legacy string parsing."""
    if not rule_json:
        return legacy_evaluate_rule(rule_logic, context)

    # Calculate safe fallback based on the legacy string severity
    _RESTRICTIVE = {"REJECT", "ASK_FOR_APPROVAL"}
    fail_closed_outcome = "ASK_FOR_APPROVAL"
    pattern = r"THEN\s+(\w+)"
    match = re.search(pattern, rule_logic, re.IGNORECASE)
    if match and match.group(1).upper() in _RESTRICTIVE:
        fail_closed_outcome = match.group(1).upper()

    try:
        # Map missing variables via fuzzy matching before evaluating
        map_missing_variables(rule_json, context)
        
        # Evaluate safely
        result = jsonLogic(rule_json, context)
        if result in ["APPROVE", "REJECT", "ASK_FOR_APPROVAL"]:
            return result
        # If False/None, the condition wasn't met
        return None
    except (ValueError, TypeError):
        # Type mismatch or missing data
        return fail_closed_outcome

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
