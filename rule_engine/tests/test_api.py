import pytest
from httpx import AsyncClient, ASGITransport

from rule_engine.app import app

@pytest.mark.asyncio
async def test_crud_rule_groups():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create group
        payload = {"name": "Test Group", "description": "Desc"}
        resp = await client.post("/v1/groups", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        group_id = data["id"]
        assert data["name"] == "Test Group"
        assert data["rules"] == []

        # List groups
        resp = await client.get("/v1/groups")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        # Add rule
        rule_payload = {
            "name": "Limit rule",
            "feature": "Limit purchases",
            "datapoints": ["amount"],
            "edge_cases": ["no amount"],
            "rule_logic": "IF no amount THEN REJECT"
        }
        resp = await client.post(f"/v1/groups/{group_id}/rules", json=rule_payload)
        assert resp.status_code == 201
        rule_data = resp.json()
        rule_id = rule_data["id"]

        # Get specific rule
        resp = await client.get(f"/v1/groups/{group_id}/rules/{rule_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Limit rule"

        # Get group (should include rules)
        resp = await client.get(f"/v1/groups/{group_id}")
        assert resp.status_code == 200
        assert len(resp.json()["rules"]) == 1

        # Delete rule
        resp = await client.delete(f"/v1/groups/{group_id}/rules/{rule_id}")
        assert resp.status_code == 204

        # Delete group
        resp = await client.delete(f"/v1/groups/{group_id}")
        assert resp.status_code == 204

        # Group should be gone
        resp = await client.get(f"/v1/groups/{group_id}")
        assert resp.status_code == 404
