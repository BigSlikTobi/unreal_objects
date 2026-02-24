import pytest
from decision_center.evaluator import legacy_evaluate_rule, evaluate_rule

def test_legacy_evaluate_rule_numeric():
    assert legacy_evaluate_rule("IF amount > 500 THEN ASK_FOR_APPROVAL", {"amount": 600}) == "ASK_FOR_APPROVAL"
    assert legacy_evaluate_rule("IF amount < 200 THEN APPROVE", {"amount": 100}) == "APPROVE"
    assert legacy_evaluate_rule("IF amount == 500 THEN REJECT", {"amount": 500}) == "REJECT"

def test_legacy_evaluate_rule_fail_closed_missing_data():
    assert legacy_evaluate_rule("IF order_total_cost = 0 THEN REJECT", {}) == "REJECT"
    assert legacy_evaluate_rule("IF status == ACTIVE THEN APPROVE", {}) == "ASK_FOR_APPROVAL"

def test_legacy_evaluate_rule_fail_closed_type_mismatch():
    context = {"order_total_cost": "costs "}
    assert legacy_evaluate_rule("IF order_total_cost = 0 THEN REJECT", context) == "REJECT"
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
    # A REJECT rule with missing data should fail closed to REJECT
    rule_json = {"if": [{"==": [{"var": "order_total_cost"}, 0]}, "REJECT", None]}
    assert evaluate_rule(rule_json, "IF order_total_cost = 0 THEN REJECT", {}) == "REJECT"
    
    # An APPROVE rule with missing data should escalate to ASK_FOR_APPROVAL
    rule_json_2 = {"if": [{"==": [{"var": "status"}, "ACTIVE"]}, "APPROVE", None]}
    assert evaluate_rule(rule_json_2, "IF status == ACTIVE THEN APPROVE", {}) == "ASK_FOR_APPROVAL"

def test_evaluate_rule_json_logic_fail_closed_type_mismatch():
    # REJECT rule: string provided for numeric comparison -> fail closed to REJECT
    rule_json = {"if": [{"==": [{"var": "order_total_cost"}, 0]}, "REJECT", None]}
    context = {"order_total_cost": "costs "}
    assert evaluate_rule(rule_json, "IF order_total_cost = 0 THEN REJECT", context) == "REJECT"
    
    # APPROVE rule: int provided for string comparison -> fail closed to ASK_FOR_APPROVAL
    rule_json_2 = {"if": [{"==": [{"var": "status"}, "ACTIVE"]}, "APPROVE", None]}
    context2 = {"status": 200}
    assert evaluate_rule(rule_json_2, "IF status == ACTIVE THEN APPROVE", context2) == "ASK_FOR_APPROVAL"

