import pytest
from decision_center.evaluator import legacy_evaluate_rule, evaluate_rule

def test_legacy_evaluate_rule_numeric():
    assert legacy_evaluate_rule("IF amount > 500 THEN ASK_FOR_APPROVAL", {"amount": 600}) == "ASK_FOR_APPROVAL"
    assert legacy_evaluate_rule("IF amount < 200 THEN APPROVE", {"amount": 100}) == "APPROVE"
    assert legacy_evaluate_rule("IF amount == 500 THEN REJECT", {"amount": 500}) == "REJECT"

def test_legacy_evaluate_rule_fail_closed_missing_data():
    # Missing data always escalates to human review, regardless of the rule's outcome
    assert legacy_evaluate_rule("IF order_total_cost = 0 THEN REJECT", {}) == "ASK_FOR_APPROVAL"
    assert legacy_evaluate_rule("IF status == ACTIVE THEN APPROVE", {}) == "ASK_FOR_APPROVAL"

def test_legacy_evaluate_rule_fail_closed_type_mismatch():
    # Type mismatches escalate to human review — never inherit the rule's REJECT
    context = {"order_total_cost": "costs "}
    assert legacy_evaluate_rule("IF order_total_cost = 0 THEN REJECT", context) == "ASK_FOR_APPROVAL"
    context2 = {"status": 200}
    assert legacy_evaluate_rule("IF status == ACTIVE THEN APPROVE", context2) == "ASK_FOR_APPROVAL"

def test_evaluate_rule_json_logic_numeric():
    rule_json_1 = {"if": [{">": [{"var": "amount"}, 500]}, "ASK_FOR_APPROVAL", None]}
    assert evaluate_rule(rule_json_1, "IF amount > 500 THEN ASK_FOR_APPROVAL", {"amount": 600}) == "ASK_FOR_APPROVAL"
    
    rule_json_2 = {"if": [{"<": [{"var": "amount"}, 200]}, "APPROVE", None]}
    assert evaluate_rule(rule_json_2, "IF amount < 200 THEN APPROVE", {"amount": 100}) == "APPROVE"
    
    rule_json_3 = {"if": [{"==": [{"var": "amount"}, 500]}, "REJECT", None]}
    assert evaluate_rule(rule_json_3, "IF amount == 500 THEN REJECT", {"amount": 500}) == "REJECT"

def test_evaluate_rule_json_logic_string_equals():
    rule_json = {"if": [{"==": [{"var": "contract_partner_name"}, "Amazon"]}, "ASK_FOR_APPROVAL", None]}
    # Test strict equal
    assert evaluate_rule(rule_json, "IF contract_partner_name == 'Amazon' THEN ASK_FOR_APPROVAL", {"contract_partner_name": "Amazon"}) == "ASK_FOR_APPROVAL"
    # Case insensitivity supported explicitly via python logic overloads, but depends on operators
    assert evaluate_rule(rule_json, "IF contract_partner_name == 'Amazon' THEN ASK_FOR_APPROVAL", {"contract_partner_name": "AMAZON"}) == "ASK_FOR_APPROVAL"

def test_evaluate_rule_json_logic_fail_closed_missing_data():
    # Missing data always escalates to human review, regardless of rule outcome
    rule_json = {"if": [{"==": [{"var": "order_total_cost"}, 0]}, "REJECT", None]}
    assert evaluate_rule(rule_json, "IF order_total_cost = 0 THEN REJECT", {}) == "ASK_FOR_APPROVAL"

    rule_json_2 = {"if": [{"==": [{"var": "status"}, "ACTIVE"]}, "APPROVE", None]}
    assert evaluate_rule(rule_json_2, "IF status == ACTIVE THEN APPROVE", {}) == "ASK_FOR_APPROVAL"

def test_evaluate_rule_json_logic_fail_closed_type_mismatch():
    # Type mismatches escalate to human review — never inherit the rule's REJECT
    rule_json = {"if": [{"==": [{"var": "order_total_cost"}, 0]}, "REJECT", None]}
    context = {"order_total_cost": "costs "}
    assert evaluate_rule(rule_json, "IF order_total_cost = 0 THEN REJECT", context) == "ASK_FOR_APPROVAL"

    rule_json_2 = {"if": [{"==": [{"var": "status"}, "ACTIVE"]}, "APPROVE", None]}
    context2 = {"status": 200}
    assert evaluate_rule(rule_json_2, "IF status == ACTIVE THEN APPROVE", context2) == "ASK_FOR_APPROVAL"


def test_evaluate_rule_coerces_string_booleans():
    """String 'true'/'false' values must be coerced to real booleans before evaluation.

    Without coercion, strict_eq raises a type mismatch (str vs bool) and the
    rule fail-closes — which is wrong when the condition doesn't actually match.
    """
    edge_json = {"if": [{"and": [
        {"==": [{"var": "dangerous_goods_flag"}, True]},
        {"==": [{"var": "temperature_control_required"}, True]},
    ]}, "REJECT", None]}
    edge_str = "IF dangerous_goods_flag == true AND temperature_control_required == true THEN REJECT"

    # String "false" should NOT trigger — was returning REJECT before the fix
    assert evaluate_rule(edge_json, edge_str, {"dangerous_goods_flag": "true", "temperature_control_required": "false"}) is None

    # String "true" for both should trigger
    assert evaluate_rule(edge_json, edge_str, {"dangerous_goods_flag": "true", "temperature_control_required": "true"}) == "REJECT"

    # Real booleans still work
    assert evaluate_rule(edge_json, edge_str, {"dangerous_goods_flag": True, "temperature_control_required": False}) is None


def test_evaluate_rule_coerces_string_numbers():
    """String numbers like '500' must be coerced when compared against numeric thresholds."""
    rule_json = {"if": [{">": [{"var": "amount"}, 500]}, "REJECT", None]}
    rule_str = "IF amount > 500 THEN REJECT"

    # String "600" should be coerced to 600 and match
    assert evaluate_rule(rule_json, rule_str, {"amount": "600"}) == "REJECT"

    # String "400" should be coerced and NOT match
    assert evaluate_rule(rule_json, rule_str, {"amount": "400"}) is None

    # Non-numeric string cannot be coerced — escalates to human review
    assert evaluate_rule(rule_json, rule_str, {"amount": "lots"}) == "ASK_FOR_APPROVAL"

    # Real numbers still work
    assert evaluate_rule(rule_json, rule_str, {"amount": 600}) == "REJECT"
    assert evaluate_rule(rule_json, rule_str, {"amount": 400}) is None

