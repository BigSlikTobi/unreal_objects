import pytest
from decision_center.evaluator import basic_evaluate_rule

def test_basic_evaluate_rule_numeric():
    assert basic_evaluate_rule("IF amount > 500 THEN ASK_FOR_APPROVAL", {"amount": 600}) == "ASK_FOR_APPROVAL"
    assert basic_evaluate_rule("IF amount < 200 THEN APPROVE", {"amount": 100}) == "APPROVE"
    assert basic_evaluate_rule("IF amount == 500 THEN REJECT", {"amount": 500}) == "REJECT"

def test_basic_evaluate_rule_string_equals():
    # Using strict ==
    assert basic_evaluate_rule("IF contract_partner_name == 'Amazon' THEN ASK_FOR_APPROVAL", {"contract_partner_name": "Amazon"}) == "ASK_FOR_APPROVAL"

def test_basic_evaluate_rule_string_single_equals():
    # LLM typically outputs = instead of ==
    assert basic_evaluate_rule("IF contract_partner_name = 'Amazon' THEN ASK_FOR_APPROVAL", {"contract_partner_name": "Amazon"}) == "ASK_FOR_APPROVAL"
    # Case insensitivity test
    assert basic_evaluate_rule("IF contract_partner_name = 'amazon' THEN ASK_FOR_APPROVAL", {"contract_partner_name": "AMAZON"}) == "ASK_FOR_APPROVAL"

def test_basic_evaluate_rule_string_unquoted():
    # If the user or LLM forgets quotes
    assert basic_evaluate_rule("IF status = ACTIVE THEN APPROVE", {"status": "ACTIVE"}) == "APPROVE"

def test_basic_evaluate_rule_user_report():
    # Exact scenario reported by user:
    # Rule: IF contract_partner_name = 'Amazon' THEN ASK_FOR_APPROVAL
    # Context: {"contract_partner_name": "Amazon", "purchase_cost_eur": 50}
    context = {"contract_partner_name": "Amazon", "purchase_cost_eur": 50}
    
    # Using =
    assert basic_evaluate_rule("IF contract_partner_name = 'Amazon' THEN ASK_FOR_APPROVAL", context) == "ASK_FOR_APPROVAL"
    # Using ==
    assert basic_evaluate_rule("IF contract_partner_name == 'Amazon' THEN ASK_FOR_APPROVAL", context) == "ASK_FOR_APPROVAL"

def test_basic_evaluate_rule_fail_closed_missing_data():
    # A REJECT rule with missing data should fail closed to REJECT (preserves severity)
    assert basic_evaluate_rule("IF order_total_cost = 0 THEN REJECT", {}) == "REJECT"
    # An APPROVE rule with missing data should escalate to ASK_FOR_APPROVAL
    assert basic_evaluate_rule("IF status == ACTIVE THEN APPROVE", {}) == "ASK_FOR_APPROVAL"

def test_basic_evaluate_rule_fail_closed_type_mismatch():
    # REJECT rule: string provided for numeric comparison → fail closed to REJECT
    context = {"order_total_cost": "costs "}
    assert basic_evaluate_rule("IF order_total_cost = 0 THEN REJECT", context) == "REJECT"
    
    # APPROVE rule: int provided for string comparison → fail closed to ASK_FOR_APPROVAL
    context2 = {"status": 200}
    assert basic_evaluate_rule("IF status == ACTIVE THEN APPROVE", context2) == "ASK_FOR_APPROVAL"
