import pytest
from httpx import AsyncClient, ASGITransport

from decision_center.app import app

# We need to mock the Rule Engine API call in real life, but for MVP evaluator tests
# we can just use a mocked httpx transport or patch it. Since the app makes outbound
# calls, we will just patch the httpx.AsyncClient GET method.
from unittest.mock import patch, MagicMock

@pytest.mark.asyncio
async def test_evaluate_no_group():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/decide?request_description=Test&context={}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["outcome"] == "APPROVE"

@pytest.fixture
def mock_rule_engine():
    with patch("decision_center.evaluator._fetch_group") as mock_get:
        yield mock_get

@pytest.mark.asyncio
async def test_evaluate_with_rules_restrictive_wins(mock_rule_engine):
    # Mock rule engine returning 1 APPROVE and 1 REJECT rule
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "g1",
        "name": "Grp",
        "rules": [
            {"id": "r1", "rule_logic": "IF amount > 100 THEN REJECT"},
            {"id": "r2", "rule_logic": "IF amount < 200 THEN APPROVE"}
        ]
    }
    mock_rule_engine.return_value = mock_response

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Context has amount=150, which triggers both rules. Most restrictive wins.
        context_str = '{"amount": 150}'
        resp = await client.get(f"/v1/decide?request_description=Test&context={context_str}&group_id=g1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["outcome"] == "REJECT"

@pytest.mark.asyncio
async def test_approval_flow_and_logs(mock_rule_engine):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "g1",
        "name": "Grp",
        "rules": [
            {"id": "r1", "rule_logic": "IF amount > 100 THEN ASK_FOR_APPROVAL"}
        ]
    }
    mock_rule_engine.return_value = mock_response

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Ask for approval
        context_str = '{"amount": 150}'
        resp = await client.get(f"/v1/decide?request_description=NeedLaptop&context={context_str}&group_id=g1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["outcome"] == "ASK_FOR_APPROVAL"
        req_id = data["request_id"]

        # 2. Check pending
        resp = await client.get("/v1/pending")
        assert resp.status_code == 200
        assert any(p["request_id"] == req_id for p in resp.json())

        # 3. Submit approval
        resp = await client.post(f"/v1/decide/{req_id}/approve", json={"approved": True, "approver": "Bob"})
        assert resp.status_code == 200

        # 4. Check chain decision log
        resp = await client.get(f"/v1/logs/chains/{req_id}")
        assert resp.status_code == 200
        chain = resp.json()
        assert chain["request_id"] == req_id
        assert len(chain["events"]) >= 2
        # Starts with REQUEST, ends with APPROVED
        assert chain["events"][0]["event_type"] == "REQUEST"
        assert chain["events"][-1]["event_type"] == "APPROVAL_STATUS"
        assert chain["events"][-1]["details"]["status"] == "APPROVED"

@pytest.mark.asyncio
async def test_evaluate_with_edge_cases(mock_rule_engine):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "g1",
        "name": "Grp",
        "rules": [
            {
                "id": "r1",
                "rule_logic": "IF amount > 100 THEN ASK_FOR_APPROVAL",
                "edge_cases": ["IF currency == GBP THEN REJECT"]
            }
        ]
    }
    mock_rule_engine.return_value = mock_response

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Triggers edge case
        context_str = '{"amount": 150, "currency": "GBP"}'
        resp = await client.get(f"/v1/decide?request_description=Test&context={context_str}&group_id=g1")
        assert resp.status_code == 200
        assert resp.json()["outcome"] == "REJECT"

        # 2. Passes edge case, triggers rule logic
        context_str = '{"amount": 150, "currency": "EUR"}'
        resp = await client.get(f"/v1/decide?request_description=Test&context={context_str}&group_id=g1")
        assert resp.status_code == 200
        assert resp.json()["outcome"] == "ASK_FOR_APPROVAL"

@pytest.mark.asyncio
async def test_evaluate_user_report(mock_rule_engine):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "g1",
        "name": "Grp",
        "rules": [
            {
                "id": "r1",
                "rule_logic": "IF contract_partner_name = 'Amazon' THEN ASK_FOR_APPROVAL",
                "edge_cases": []
            }
        ]
    }
    mock_rule_engine.return_value = mock_response

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # EXACT PAYLOAD LOGGED BY THE USER:
        # /v1/decide?request_description=Purchase%20of%20100%20paper%20clips%20at%20Amazon&context=%7B%22contract_partner_name%22%3A%20%22Amazon%22%7D&group_id=db0d2fd1-d716-4007-b2fe-389887ba565b
        import urllib.parse
        context_str = urllib.parse.quote('{"contract_partner_name": "Amazon"}')
        request_desc = urllib.parse.quote("Purchase of 100 paper clips at Amazon")
        group_id = "db0d2fd1-d716-4007-b2fe-389887ba565b"
        
        resp = await client.get(f"/v1/decide?request_description={request_desc}&context={context_str}&group_id={group_id}")
        assert resp.status_code == 200
        assert resp.json()["outcome"] == "ASK_FOR_APPROVAL"
