import pytest
import subprocess
import time
import httpx
import sys
from unittest.mock import MagicMock, AsyncMock

from mcp_server.server import (
    Clients,
    RULE_ENGINE_URL,
    DECISION_CENTER_URL,
    BACKEND_TIMEOUT,
    list_rule_groups,
    evaluate_action,
    submit_approval,
    get_decision_log,
)


def _live_ctx(rule_client, dc_client):
    """Build a mock Context wired to real httpx clients."""
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.debug = AsyncMock()
    ctx.error = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.request_context.lifespan_context = Clients(
        rule_engine=rule_client,
        decision_center=dc_client,
    )
    return ctx


@pytest.fixture(scope="module", autouse=True)
def live_servers():
    # Start rule engine on port 8001
    p1 = subprocess.Popen([sys.executable, "-m", "uvicorn", "rule_engine.app:app", "--port", "8001"])
    # Start decision center on port 8002
    p2 = subprocess.Popen([sys.executable, "-m", "uvicorn", "decision_center.app:app", "--port", "8002"])

    # Wait for servers to be healthy
    time.sleep(2)

    yield

    # Teardown
    p1.terminate()
    p2.terminate()
    p1.wait()
    p2.wait()

@pytest.mark.asyncio
async def test_e2e_flow():
    # 1. Create rule group via Rule Engine API directly (since MCP server only reads them)
    async with httpx.AsyncClient() as client:
        resp = await client.post("http://127.0.0.1:8001/v1/groups", json={"name": "E2E Group", "description": "Group for E2E tests"})
        assert resp.status_code == 201
        group_id = resp.json()["id"]

        # Add rule
        resp = await client.post(f"http://127.0.0.1:8001/v1/groups/{group_id}/rules", json={
            "name": "E2E Rule",
            "feature": "E2E Test",
            "datapoints": ["amount"],
            "edge_cases": [],
            "rule_logic": "IF amount > 100 THEN ASK_FOR_APPROVAL"
        })
        assert resp.status_code == 201

    # Build a context with real HTTP clients
    async with (
        httpx.AsyncClient(base_url=RULE_ENGINE_URL, timeout=BACKEND_TIMEOUT) as re_client,
        httpx.AsyncClient(base_url=DECISION_CENTER_URL, timeout=BACKEND_TIMEOUT) as dc_client,
    ):
        ctx = _live_ctx(re_client, dc_client)

        # 2. Verify MCP can list the group
        groups = await list_rule_groups(ctx=ctx)
        assert any(g["id"] == group_id for g in groups)

        # 3. Evaluate an action that triggers the rule (amount=150) via MCP
        res = await evaluate_action("Buy Server", '{"amount": 150}', ctx, group_id)
        assert res["outcome"] == "ASK_FOR_APPROVAL"
        req_id = res["request_id"]

        # 4. Submit approval via MCP
        appr_res = await submit_approval(req_id, True, "CEO", ctx=ctx)
        assert appr_res["status"] == "success"

        # 5. Check log via MCP
        chain = await get_decision_log("chain", request_id=req_id, ctx=ctx)
        assert chain["request_id"] == req_id
        assert chain["events"][-1]["event_type"] == "APPROVAL_STATUS"
        assert chain["events"][-1]["details"]["status"] == "APPROVED"
