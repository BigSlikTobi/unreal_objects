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
    assert data["active"] is True


def test_update_rule_api_can_deactivate(populated_client):
    client, group_id, rule_id = populated_client

    update_payload = {
        "name": "Updated API Rule",
        "feature": "Updated API Feature",
        "datapoints": ["amount"],
        "edge_cases": [],
        "edge_cases_json": [],
        "rule_logic": "IF amount > 100 THEN ASK_FOR_APPROVAL",
        "rule_logic_json": {},
        "active": False
    }

    resp = client.put(f"/v1/groups/{group_id}/rules/{rule_id}", json=update_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["active"] is False


def test_update_rule_api_persists_deactivation_on_refetch(populated_client):
    client, group_id, rule_id = populated_client

    update_payload = {
        "name": "Updated API Rule",
        "feature": "Updated API Feature",
        "datapoints": ["amount"],
        "edge_cases": [],
        "edge_cases_json": [],
        "rule_logic": "IF amount > 100 THEN ASK_FOR_APPROVAL",
        "rule_logic_json": {},
        "active": False
    }

    update_resp = client.put(f"/v1/groups/{group_id}/rules/{rule_id}", json=update_payload)
    assert update_resp.status_code == 200

    get_resp = client.get(f"/v1/groups/{group_id}")
    assert get_resp.status_code == 200
    group = get_resp.json()
    stored_rule = next(rule for rule in group["rules"] if rule["id"] == rule_id)
    assert stored_rule["active"] is False


def test_group_reads_disable_http_caching(populated_client):
    client, group_id, _ = populated_client

    list_resp = client.get("/v1/groups")
    assert list_resp.status_code == 200
    assert list_resp.headers["cache-control"] == "no-store"

    group_resp = client.get(f"/v1/groups/{group_id}")
    assert group_resp.status_code == 200
    assert group_resp.headers["cache-control"] == "no-store"


def test_delete_group_requires_admin_token_when_configured(client, store, monkeypatch):
    monkeypatch.setenv("RULE_ENGINE_ADMIN_TOKEN", "sudo-secret")
    create_resp = client.post("/v1/groups", json={"name": "Protected Group"})
    assert create_resp.status_code == 201
    group_id = create_resp.json()["id"]

    missing_token_resp = client.delete(f"/v1/groups/{group_id}")
    assert missing_token_resp.status_code == 403
    assert missing_token_resp.json()["detail"] == "Admin token required for destructive action"

    wrong_token_resp = client.delete(
        f"/v1/groups/{group_id}",
        headers={"X-Admin-Token": "wrong-secret"},
    )
    assert wrong_token_resp.status_code == 403

    delete_resp = client.delete(
        f"/v1/groups/{group_id}",
        headers={"X-Admin-Token": "sudo-secret"},
    )
    assert delete_resp.status_code == 204
    assert store.get_group(group_id) is None


def test_delete_group_without_admin_token_keeps_backwards_compatibility(client, store, monkeypatch):
    monkeypatch.delenv("RULE_ENGINE_ADMIN_TOKEN", raising=False)
    create_resp = client.post("/v1/groups", json={"name": "Ephemeral Group"})
    assert create_resp.status_code == 201
    group_id = create_resp.json()["id"]

    delete_resp = client.delete(f"/v1/groups/{group_id}")
    assert delete_resp.status_code == 204
    assert store.get_group(group_id) is None

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
