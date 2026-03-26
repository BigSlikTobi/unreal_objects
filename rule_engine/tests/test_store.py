import pytest
from rule_engine.store import RuleStore
from rule_engine.models import CreateRuleGroup, CreateRule, DatapointDefinition

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


def test_update_rule_can_deactivate(populated_store):
    store, group_id, rule_id = populated_store

    update_data = CreateRule(
        name="Inactive Rule",
        feature="Updated Feature",
        datapoints=["dp1"],
        edge_cases=[],
        rule_logic="IF dp1 == 1 THEN APPROVE",
        rule_logic_json={},
        edge_cases_json=[],
        active=False,
    )

    updated_rule = store.update_rule(group_id, rule_id, update_data)

    assert updated_rule is not None
    assert updated_rule.active is False

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


def test_persistence_restores_groups_and_rules(tmp_path):
    path = tmp_path / "rule_engine_store.json"
    store = RuleStore(persistence_path=path)
    group = store.create_group(CreateRuleGroup(name="Persistent Group", description="Desc"))
    store.add_rule(group.id, CreateRule(
        name="Persistent Rule",
        feature="Waste",
        datapoints=["volume"],
        edge_cases=[],
        rule_logic="IF volume > 10 THEN ASK_FOR_APPROVAL",
        rule_logic_json={},
    ))

    restored = RuleStore(persistence_path=path)
    groups = restored.list_groups()

    assert len(groups) == 1
    assert groups[0].name == "Persistent Group"
    assert groups[0].rules[0].name == "Persistent Rule"


def test_update_datapoints_persists(tmp_path):
    path = tmp_path / "rule_engine_store.json"
    store = RuleStore(persistence_path=path)
    group = store.create_group(CreateRuleGroup(name="Datapoints", description="Desc"))

    updated = store.update_datapoints(group.id, [
        DatapointDefinition(name="volume", type="number"),
        DatapointDefinition(name="waste_type", type="text"),
    ])

    assert updated is not None
    restored = RuleStore(persistence_path=path)
    restored_group = restored.get_group(group.id)
    assert restored_group is not None
    assert {definition.name for definition in restored_group.datapoint_definitions} == {"volume", "waste_type"}


def test_missing_persistence_file_starts_empty(tmp_path):
    path = tmp_path / "missing.json"
    store = RuleStore(persistence_path=path)

    assert store.list_groups() == []


def test_corrupted_persistence_file_raises(tmp_path):
    path = tmp_path / "rule_engine_store.json"
    path.write_text("{not-valid-json")

    with pytest.raises(RuntimeError, match="Failed to parse rule store"):
        RuleStore(persistence_path=path)
