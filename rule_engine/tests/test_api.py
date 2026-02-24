import pytest
from fastapi.testclient import TestClient
from rule_engine.app import app, store

@pytest.fixture
def store():
    from rule_engine.app import store as app_store
    app_store.groups.clear()
    return app_store

@pytest.fixture
def client(store):
    return TestClient(app)

@pytest.fixture
def populated_client(client, store):
    resp = client.post("/v1/groups", json={"name": "Test Group"})
    group_id = resp.json()["id"]
    
    resp = client.post(f"/v1/groups/{group_id}/rules", json={
        "name": "Initial Rule",
        "feature": "Initial Feature",
        "datapoints": ["amount"],
        "edge_cases": [],
        "rule_logic": "APPROVE"
    })
    rule_id = resp.json()["id"]
    return client, group_id, rule_id

def test_update_rule_api_success(populated_client):
    client, group_id, rule_id = populated_client
    
    update_payload = {
        "name": "Updated API Rule",
        "feature": "Updated API Feature",
        "datapoints": ["amount", "age"],
        "edge_cases": ["IF age < 18 THEN REJECT"],
        "edge_cases_json": [{}],
        "rule_logic": "IF amount > 100 THEN ASK_FOR_APPROVAL",
        "rule_logic_json": {}
    }
    
    resp = client.put(f"/v1/groups/{group_id}/rules/{rule_id}", json=update_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated API Rule"
    assert data["id"] == rule_id
    assert len(data["datapoints"]) == 2

def test_update_rule_api_not_found(populated_client):
    client, group_id, rule_id = populated_client
    
    update_payload = {
        "name": "Updated Rule",
        "feature": "Updated Feature",
        "datapoints": [],
        "edge_cases": [],
        "rule_logic": "APPROVE"
    }
    
    # Invalid Rule ID
    resp = client.put(f"/v1/groups/{group_id}/rules/invalid_id", json=update_payload)
    assert resp.status_code == 404
    
    # Invalid Group ID
    resp = client.put(f"/v1/groups/invalid_id/rules/{rule_id}", json=update_payload)
    assert resp.status_code == 404
