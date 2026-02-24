from datetime import datetime
from pydantic import ValidationError
import pytest

from rule_engine.models import BusinessRule, BusinessRuleGroup, CreateRule, CreateRuleGroup

def test_business_rule_validation():
    rule = BusinessRule(
        id="rule-1",
        name="Test Rule",
        feature="Test Feature",
        datapoints=["point1"],
        edge_cases=["case1"],
        rule_logic="IF X THEN Y",
        created_at=datetime.now()
    )
    assert rule.id == "rule-1"

    # Test missing fields
    with pytest.raises(ValidationError):
        BusinessRule(id="rule-2", name="Bad Rule")


def test_business_rule_group_validation():
    rule = BusinessRule(
        id="rule-1",
        name="Test",
        feature="F",
        datapoints=[],
        edge_cases=[],
        rule_logic="IF",
        created_at=datetime.now()
    )
    group = BusinessRuleGroup(
        id="group-1",
        name="Test Group",
        description="A group",
        rules=[rule]
    )
    assert group.id == "group-1"
    assert len(group.rules) == 1
