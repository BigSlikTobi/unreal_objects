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
