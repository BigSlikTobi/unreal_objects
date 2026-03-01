import pytest
import httpx
from unittest.mock import patch, MagicMock, AsyncMock

from mcp_server.server import (
    list_rule_groups,
    get_rule_group,
    evaluate_action,
    submit_approval,
    get_decision_log,
    get_pending,
    guardrail_heartbeat,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(status_code: int, json_body):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_body
    return mock_resp

# ---------------------------------------------------------------------------
# Existing happy-path tests (kept working after refactor)
# ---------------------------------------------------------------------------

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
    mock_httpx_get.return_value = _mock_response(200, [{"id": "g1", "name": "Test Group"}])
    res = await list_rule_groups()
    assert len(res) == 1
    assert res[0]["name"] == "Test Group"

@pytest.mark.asyncio
async def test_evaluate_action(mock_httpx_get):
    mock_httpx_get.return_value = _mock_response(200, {
        "request_id": "req-1",
        "outcome": "APPROVE",
        "matched_rules": []
    })
    res = await evaluate_action(request_description="Test", context_json='{"amount": 100}', group_id="g1")
    assert res["outcome"] == "APPROVE"

@pytest.mark.asyncio
async def test_submit_approval(mock_httpx_post):
    mock_httpx_post.return_value = _mock_response(200, {"status": "success"})
    res = await submit_approval("req-1", True, "Admin")
    assert res["status"] == "success"

# ---------------------------------------------------------------------------
# Fail-closed: ConnectError → REJECT
# ---------------------------------------------------------------------------

def _patch_get_raises(exc):
    return patch("mcp_server.server.httpx.AsyncClient.get", side_effect=exc)

def _patch_post_raises(exc):
    return patch("mcp_server.server.httpx.AsyncClient.post", side_effect=exc)

def _assert_reject(result):
    assert result["outcome"] == "REJECT"
    assert result["error"] is True
    assert result["reason"] == "BACKEND_UNREACHABLE"
    assert "Do NOT proceed" in result["instruction"]

@pytest.mark.asyncio
async def test_list_rule_groups_connect_error():
    with _patch_get_raises(httpx.ConnectError("refused")):
        result = await list_rule_groups()
    _assert_reject(result)

@pytest.mark.asyncio
async def test_get_rule_group_connect_error():
    with _patch_get_raises(httpx.ConnectError("refused")):
        result = await get_rule_group("g1")
    _assert_reject(result)

@pytest.mark.asyncio
async def test_evaluate_action_connect_error():
    with _patch_get_raises(httpx.ConnectError("refused")):
        result = await evaluate_action("buy", '{"amount": 100}')
    _assert_reject(result)

@pytest.mark.asyncio
async def test_get_pending_connect_error():
    with _patch_get_raises(httpx.ConnectError("refused")):
        result = await get_pending()
    _assert_reject(result)

@pytest.mark.asyncio
async def test_get_decision_log_connect_error():
    with _patch_get_raises(httpx.ConnectError("refused")):
        result = await get_decision_log("atomic")
    _assert_reject(result)

@pytest.mark.asyncio
async def test_submit_approval_connect_error():
    with _patch_post_raises(httpx.ConnectError("refused")):
        result = await submit_approval("req-1", True, "Admin")
    _assert_reject(result)

# ---------------------------------------------------------------------------
# Fail-closed: HTTPStatusError (500) → REJECT
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_evaluate_action_http_status_error():
    bad_resp = MagicMock()
    bad_resp.status_code = 500
    exc = httpx.HTTPStatusError("Server Error", request=MagicMock(), response=bad_resp)
    with _patch_get_raises(exc):
        result = await evaluate_action("buy", '{"amount": 100}')
    _assert_reject(result)
    assert "HTTPStatusError" in result["detail"]

# ---------------------------------------------------------------------------
# Fail-closed: ReadTimeout → REJECT
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_evaluate_action_read_timeout():
    with _patch_get_raises(httpx.ReadTimeout("timed out")):
        result = await evaluate_action("buy", '{"amount": 100}')
    _assert_reject(result)
    assert "ReadTimeout" in result["detail"]

# ---------------------------------------------------------------------------
# guardrail_heartbeat
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_heartbeat_both_healthy():
    with patch("mcp_server.server.httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = _mock_response(200, {"status": "ok"})
        result = await guardrail_heartbeat()
    assert result["healthy"] is True
    assert result["rule_engine"]["reachable"] is True
    assert result["decision_center"]["reachable"] is True
    assert "operational" in result["instruction"].lower()

@pytest.mark.asyncio
async def test_heartbeat_decision_center_down():
    call_count = 0

    async def side_effect(url, **kwargs):
        nonlocal call_count
        call_count += 1
        if "8001" in url:
            return _mock_response(200, {"status": "ok"})
        raise httpx.ConnectError("refused")

    with patch("mcp_server.server.httpx.AsyncClient.get", side_effect=side_effect):
        result = await guardrail_heartbeat()

    assert result["healthy"] is False
    assert result["rule_engine"]["reachable"] is True
    assert result["decision_center"]["reachable"] is False
    assert "Do NOT proceed" in result["instruction"]

@pytest.mark.asyncio
async def test_heartbeat_both_down():
    with patch("mcp_server.server.httpx.AsyncClient.get", side_effect=httpx.ConnectError("refused")):
        result = await guardrail_heartbeat()
    assert result["healthy"] is False
    assert result["rule_engine"]["reachable"] is False
    assert result["decision_center"]["reachable"] is False
