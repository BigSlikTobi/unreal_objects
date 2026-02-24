import pytest
from unittest.mock import patch, MagicMock

from mcp_server.server import (
    list_rule_groups,
    get_rule_group,
    evaluate_action,
    submit_approval,
    get_decision_log,
    get_pending
)

@pytest.fixture
def mock_httpx_get():
    with patch("mcp_server.server.httpx.AsyncClient.get") as m:
        yield m
        
@pytest.fixture
def mock_httpx_post():
    with patch("mcp_server.server.httpx.AsyncClient.post") as m:
        yield m

@pytest.mark.asyncio
async def test_list_rule_groups(mock_httpx_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [{"id": "g1", "name": "Test Group"}]
    mock_httpx_get.return_value = mock_resp

    res = await list_rule_groups()
    assert len(res) == 1
    assert res[0]["name"] == "Test Group"

@pytest.mark.asyncio
async def test_evaluate_action(mock_httpx_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "request_id": "req-1",
        "outcome": "APPROVE",
        "matched_rules": []
    }
    mock_httpx_get.return_value = mock_resp

    res = await evaluate_action(request_description="Test", context_json='{"amount": 100}', group_id="g1")
    assert res["outcome"] == "APPROVE"

@pytest.mark.asyncio
async def test_submit_approval(mock_httpx_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "success"}
    mock_httpx_post.return_value = mock_resp

    res = await submit_approval("req-1", True, "Admin")
    assert res["status"] == "success"
