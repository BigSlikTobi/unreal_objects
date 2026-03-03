import json

import pytest
import httpx
from unittest.mock import MagicMock, AsyncMock

import mcp_server.server as server_module
from mcp_server.server import (
    Clients,
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
    mock_resp.raise_for_status = MagicMock()
    if status_code >= 400:
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=mock_resp
        )
    return mock_resp


def _mock_ctx(rule_client=None, dc_client=None):
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.debug = AsyncMock()
    ctx.error = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.request_context.lifespan_context = Clients(
        rule_engine=rule_client or AsyncMock(),
        decision_center=dc_client or AsyncMock(),
    )
    return ctx


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_rule_groups():
    rc = AsyncMock()
    rc.get.return_value = _mock_response(200, [{"id": "g1", "name": "Test Group"}])
    ctx = _mock_ctx(rule_client=rc)
    res = await list_rule_groups(ctx=ctx)
    assert len(res) == 1
    assert res[0]["name"] == "Test Group"
    rc.get.assert_called_once_with("/v1/groups")


@pytest.mark.asyncio
async def test_get_rule_group():
    rc = AsyncMock()
    rc.get.return_value = _mock_response(200, {"id": "g1", "name": "Test Group", "rules": []})
    ctx = _mock_ctx(rule_client=rc)
    res = await get_rule_group(group_id="g1", ctx=ctx)
    assert res["id"] == "g1"
    rc.get.assert_called_once_with("/v1/groups/g1")


@pytest.mark.asyncio
async def test_evaluate_action():
    dc = AsyncMock()
    dc.get.return_value = _mock_response(200, {
        "request_id": "req-1",
        "outcome": "APPROVE",
        "matched_rules": []
    })
    ctx = _mock_ctx(dc_client=dc)
    res = await evaluate_action(
        request_description="Test",
        context_json='{"amount": 100}',
        group_id="g1",
        ctx=ctx,
    )
    assert res["outcome"] == "APPROVE"


@pytest.mark.asyncio
async def test_evaluate_action_without_group_id():
    dc = AsyncMock()
    dc.get.return_value = _mock_response(200, {
        "request_id": "req-2",
        "outcome": "APPROVE",
        "matched_rules": []
    })
    ctx = _mock_ctx(dc_client=dc)
    res = await evaluate_action(
        request_description="Test",
        context_json='{"amount": 50}',
        ctx=ctx,
    )
    assert res["outcome"] == "APPROVE"
    call_kwargs = dc.get.call_args
    params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
    assert "group_id" not in params


@pytest.mark.asyncio
async def test_evaluate_action_accepts_group_id_as_fourth_positional_argument():
    """Verify that with the new signature (ctx before group_id), group_id can be passed positionally."""
    dc = AsyncMock()
    dc.get.return_value = _mock_response(200, {
        "request_id": "req-3",
        "outcome": "ASK_FOR_APPROVAL",
        "matched_rules": []
    })
    ctx = _mock_ctx(dc_client=dc)

    res = await evaluate_action("Test", '{"amount": 150}', ctx, "g1")

    assert res["outcome"] == "ASK_FOR_APPROVAL"
    call_kwargs = dc.get.call_args
    params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
    assert params["group_id"] == "g1"


@pytest.mark.asyncio
async def test_submit_approval():
    dc = AsyncMock()
    dc.post.return_value = _mock_response(200, {"status": "success"})
    ctx = _mock_ctx(dc_client=dc)
    res = await submit_approval("req-1", True, "Admin", ctx=ctx)
    assert res["status"] == "success"


@pytest.mark.asyncio
async def test_get_decision_log_atomic():
    dc = AsyncMock()
    dc.get.return_value = _mock_response(200, [{"id": "log-1"}])
    ctx = _mock_ctx(dc_client=dc)
    res = await get_decision_log(log_type="atomic", ctx=ctx)
    assert res == [{"id": "log-1"}]
    dc.get.assert_called_once_with("/v1/logs/atomic")


@pytest.mark.asyncio
async def test_get_decision_log_chains():
    dc = AsyncMock()
    dc.get.return_value = _mock_response(200, [{"chain": "c1"}])
    ctx = _mock_ctx(dc_client=dc)
    res = await get_decision_log(log_type="chains", ctx=ctx)
    assert res == [{"chain": "c1"}]
    dc.get.assert_called_once_with("/v1/logs/chains")


@pytest.mark.asyncio
async def test_get_decision_log_chain_with_request_id():
    dc = AsyncMock()
    dc.get.return_value = _mock_response(200, {"chain": "c1", "events": []})
    ctx = _mock_ctx(dc_client=dc)
    res = await get_decision_log(log_type="chain", request_id="req-1", ctx=ctx)
    assert res["chain"] == "c1"
    dc.get.assert_called_once_with("/v1/logs/chains/req-1")


@pytest.mark.asyncio
async def test_get_decision_log_invalid_log_type():
    ctx = _mock_ctx()
    res = await get_decision_log(log_type="invalid", ctx=ctx)
    assert res["error"] is True
    assert res["reason"] == "INVALID_INPUT"
    assert "Invalid log_type" in res["detail"]


@pytest.mark.asyncio
async def test_get_decision_log_chain_missing_request_id():
    ctx = _mock_ctx()
    res = await get_decision_log(log_type="chain", ctx=ctx)
    assert res["error"] is True
    assert res["reason"] == "INVALID_INPUT"
    assert "request_id" in res["detail"]


@pytest.mark.asyncio
async def test_get_pending():
    dc = AsyncMock()
    dc.get.return_value = _mock_response(200, [{"request_id": "req-1", "status": "pending"}])
    ctx = _mock_ctx(dc_client=dc)
    res = await get_pending(ctx=ctx)
    assert len(res) == 1
    assert res[0]["status"] == "pending"


# ---------------------------------------------------------------------------
# Input validation: evaluate_action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evaluate_action_invalid_json():
    ctx = _mock_ctx()
    res = await evaluate_action(
        request_description="Test",
        context_json="not valid json",
        ctx=ctx,
    )
    assert res["error"] is True
    assert res["reason"] == "INVALID_INPUT"
    assert "not valid JSON" in res["detail"]


@pytest.mark.asyncio
async def test_evaluate_action_oversized_context():
    ctx = _mock_ctx()
    big_json = json.dumps({"data": "x" * (100 * 1024)})
    res = await evaluate_action(
        request_description="Test",
        context_json=big_json,
        ctx=ctx,
    )
    assert res["error"] is True
    assert res["reason"] == "INVALID_INPUT"
    assert "exceeds maximum size" in res["detail"]


# ---------------------------------------------------------------------------
# Fail-closed: ConnectError → REJECT
# ---------------------------------------------------------------------------


def _assert_reject(result):
    assert result["outcome"] == "REJECT"
    assert result["error"] is True
    assert result["reason"] == "BACKEND_UNREACHABLE"
    assert "Do NOT proceed" in result["instruction"]


@pytest.mark.asyncio
async def test_list_rule_groups_connect_error():
    rc = AsyncMock()
    rc.get.side_effect = httpx.ConnectError("refused")
    ctx = _mock_ctx(rule_client=rc)
    result = await list_rule_groups(ctx=ctx)
    _assert_reject(result)


@pytest.mark.asyncio
async def test_get_rule_group_connect_error():
    rc = AsyncMock()
    rc.get.side_effect = httpx.ConnectError("refused")
    ctx = _mock_ctx(rule_client=rc)
    result = await get_rule_group("g1", ctx=ctx)
    _assert_reject(result)


@pytest.mark.asyncio
async def test_evaluate_action_connect_error():
    dc = AsyncMock()
    dc.get.side_effect = httpx.ConnectError("refused")
    ctx = _mock_ctx(dc_client=dc)
    result = await evaluate_action("buy", '{"amount": 100}', ctx=ctx)
    _assert_reject(result)


@pytest.mark.asyncio
async def test_get_pending_connect_error():
    dc = AsyncMock()
    dc.get.side_effect = httpx.ConnectError("refused")
    ctx = _mock_ctx(dc_client=dc)
    result = await get_pending(ctx=ctx)
    _assert_reject(result)


@pytest.mark.asyncio
async def test_get_decision_log_connect_error():
    dc = AsyncMock()
    dc.get.side_effect = httpx.ConnectError("refused")
    ctx = _mock_ctx(dc_client=dc)
    result = await get_decision_log("atomic", ctx=ctx)
    _assert_reject(result)


@pytest.mark.asyncio
async def test_submit_approval_connect_error():
    dc = AsyncMock()
    dc.post.side_effect = httpx.ConnectError("refused")
    ctx = _mock_ctx(dc_client=dc)
    result = await submit_approval("req-1", True, "Admin", ctx=ctx)
    _assert_reject(result)


# ---------------------------------------------------------------------------
# Fail-closed: HTTPStatusError (500) → REJECT
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evaluate_action_http_status_error():
    dc = AsyncMock()
    bad_resp = MagicMock()
    bad_resp.status_code = 500
    dc.get.side_effect = httpx.HTTPStatusError("Server Error", request=MagicMock(), response=bad_resp)
    ctx = _mock_ctx(dc_client=dc)
    result = await evaluate_action("buy", '{"amount": 100}', ctx=ctx)
    _assert_reject(result)
    assert "HTTPStatusError" in result["detail"]


# ---------------------------------------------------------------------------
# Fail-closed: ReadTimeout → REJECT
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evaluate_action_read_timeout():
    dc = AsyncMock()
    dc.get.side_effect = httpx.ReadTimeout("timed out")
    ctx = _mock_ctx(dc_client=dc)
    result = await evaluate_action("buy", '{"amount": 100}', ctx=ctx)
    _assert_reject(result)
    assert "ReadTimeout" in result["detail"]


# ---------------------------------------------------------------------------
# Fail-closed: ctx.error() is called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fail_closed_calls_ctx_error():
    rc = AsyncMock()
    rc.get.side_effect = httpx.ConnectError("refused")
    ctx = _mock_ctx(rule_client=rc)
    await list_rule_groups(ctx=ctx)
    ctx.error.assert_called_once()
    assert "ConnectError" in ctx.error.call_args[0][0]


# ---------------------------------------------------------------------------
# guardrail_heartbeat
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_heartbeat_both_healthy():
    rc = AsyncMock()
    dc = AsyncMock()
    rc.get.return_value = _mock_response(200, {"status": "ok"})
    dc.get.return_value = _mock_response(200, {"status": "ok"})
    ctx = _mock_ctx(rule_client=rc, dc_client=dc)
    result = await guardrail_heartbeat(ctx=ctx)
    assert result["healthy"] is True
    assert result["rule_engine"]["reachable"] is True
    assert result["decision_center"]["reachable"] is True
    assert "operational" in result["instruction"].lower()


@pytest.mark.asyncio
async def test_heartbeat_decision_center_down():
    rc = AsyncMock()
    dc = AsyncMock()
    rc.get.return_value = _mock_response(200, {"status": "ok"})
    dc.get.side_effect = httpx.ConnectError("refused")
    ctx = _mock_ctx(rule_client=rc, dc_client=dc)
    result = await guardrail_heartbeat(ctx=ctx)
    assert result["healthy"] is False
    assert result["decision_center"]["reachable"] is False
    assert "Do NOT proceed" in result["instruction"]


@pytest.mark.asyncio
async def test_heartbeat_both_down():
    rc = AsyncMock()
    dc = AsyncMock()
    rc.get.side_effect = httpx.ConnectError("refused")
    dc.get.side_effect = httpx.ConnectError("refused")
    ctx = _mock_ctx(rule_client=rc, dc_client=dc)
    result = await guardrail_heartbeat(ctx=ctx)
    assert result["healthy"] is False
    assert result["rule_engine"]["reachable"] is False
    assert result["decision_center"]["reachable"] is False


@pytest.mark.asyncio
async def test_heartbeat_uses_shared_clients():
    rc = AsyncMock()
    dc = AsyncMock()
    rc.get.return_value = _mock_response(200, {"status": "ok"})
    dc.get.return_value = _mock_response(200, {"status": "ok"})
    ctx = _mock_ctx(rule_client=rc, dc_client=dc)
    await guardrail_heartbeat(ctx=ctx)
    rc.get.assert_called_once_with("/v1/health")
    dc.get.assert_called_once_with("/v1/health")


# ---------------------------------------------------------------------------
# _DEFAULT_GROUP_ID propagation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_default_group_id_used_in_evaluate_action(monkeypatch):
    monkeypatch.setattr(server_module, "_DEFAULT_GROUP_ID", "grp-configured")
    dc = AsyncMock()
    dc.get.return_value = _mock_response(200, {"outcome": "APPROVE", "matched_rules": []})
    ctx = _mock_ctx(dc_client=dc)

    await evaluate_action(request_description="test", context_json="{}", ctx=ctx)

    call_kwargs = dc.get.call_args
    params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
    assert params["group_id"] == "grp-configured"
