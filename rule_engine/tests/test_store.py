import pytest
from rule_engine.store import RuleStore
from rule_engine.models import CreateRuleGroup, CreateRule

@pytest.fixture
def store():
    return RuleStore()

@pytest.fixture
def populated_store(store):
    group = store.create_group(CreateRuleGroup(name="Test Group", description="Desc"))
    rule = store.add_rule(group.id, CreateRule(
        name="Test Rule",
        feature="Test Feature",
        datapoints=("dp1",),
        edge_cases=("IF x > 1 THEN REJECT",),
        rule_logic="IF dp1 == 1 THEN APPROVE"
    ))
    return store, group.id, rule.id

def test_update_rule_success(populated_store):
    store, group_id, rule_id = populated_store
    
    update_data = CreateRule(
        name="Updated Rule",
        feature="Updated Feature",
        datapoints=["dp1", "dp2"],
        edge_cases=["IF x > 1 THEN REJECT", "IF dp2 == 0 THEN ASK_FOR_APPROVAL"],
        edge_cases_json=[{}, {}],
        rule_logic="IF dp1 == 1 THEN APPROVE",
        rule_logic_json={}
    )
    
    updated_rule = store.update_rule(group_id, rule_id, update_data)
    
    assert updated_rule is not None
    assert updated_rule.name == "Updated Rule"
    assert updated_rule.feature == "Updated Feature"
    assert len(updated_rule.datapoints) == 2
    assert len(updated_rule.edge_cases) == 2
    assert updated_rule.id == rule_id # Ensure ID doesn't change

def test_update_rule_not_found(populated_store):
    store, group_id, rule_id = populated_store
    
    update_data = CreateRule(
        name="Updated Rule",
        feature="Updated Feature",
        datapoints=[],
        edge_cases=[],
        rule_logic="APPROVE",
        rule_logic_json={},
        edge_cases_json=[]
    )
    
    # Invalid Rule ID
    assert store.update_rule(group_id, "invalid_rule", update_data) is None
    
    # Invalid Group ID
    assert store.update_rule("invalid_group", rule_id, update_data) is None
