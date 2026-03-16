import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, call, patch

from evals.agent_eval.agent import SimulatedAgent
from evals.agent_eval.models import WorkflowStep


def make_step(expected_outcome, human_approves=None):
    return WorkflowStep(
        action_description="test action",
        context={"amount": 100},
        expected_outcome=expected_outcome,
        human_approves=human_approves,
    )


def make_mock_response(status_code: int, json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


@pytest.fixture
def mock_dc_client():
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.mark.asyncio
async def test_approve_step_calls_decide_no_approve(mock_dc_client):
    mock_dc_client.post.return_value = make_mock_response(
        200, {"request_id": "req-001", "outcome": "APPROVE"}
    )
    agent = SimulatedAgent(decision_center_url="http://dc", client=mock_dc_client)
    decision, agent_obeyed = await agent.execute_step(make_step("APPROVE"), "group-1")

    assert decision["outcome"] == "APPROVE"
    assert agent_obeyed is True
    # Only one POST call (decide), no approve call
    assert mock_dc_client.post.call_count == 1
    call_args = mock_dc_client.post.call_args
    assert "/v1/decide" in call_args[0][0]


@pytest.mark.asyncio
async def test_reject_step_calls_decide_no_approve(mock_dc_client):
    mock_dc_client.post.return_value = make_mock_response(
        200, {"request_id": "req-002", "outcome": "REJECT"}
    )
    agent = SimulatedAgent(decision_center_url="http://dc", client=mock_dc_client)
    decision, agent_obeyed = await agent.execute_step(make_step("REJECT"), "group-1")

    assert decision["outcome"] == "REJECT"
    assert agent_obeyed is True
    assert mock_dc_client.post.call_count == 1


@pytest.mark.asyncio
async def test_ask_step_calls_decide_then_approve(mock_dc_client):
    decide_resp = make_mock_response(
        200, {"request_id": "req-003", "outcome": "ASK_FOR_APPROVAL"}
    )
    approve_resp = make_mock_response(
        200, {"status": "success", "final_state": "APPROVED"}
    )
    mock_dc_client.post.side_effect = [decide_resp, approve_resp]

    agent = SimulatedAgent(decision_center_url="http://dc", client=mock_dc_client)
    step = make_step("ASK_FOR_APPROVAL", human_approves=True)
    decision, agent_obeyed = await agent.execute_step(step, "group-1")

    assert decision["outcome"] == "ASK_FOR_APPROVAL"
    assert agent_obeyed is True
    assert mock_dc_client.post.call_count == 2

    approve_call = mock_dc_client.post.call_args_list[1]
    assert "/approve" in approve_call[0][0]
    assert approve_call[1]["json"]["approved"] is True
    assert approve_call[1]["json"]["approver"] == "simulated-human"


@pytest.mark.asyncio
async def test_ask_step_human_rejects(mock_dc_client):
    decide_resp = make_mock_response(
        200, {"request_id": "req-004", "outcome": "ASK_FOR_APPROVAL"}
    )
    approve_resp = make_mock_response(
        200, {"status": "success", "final_state": "REJECTED"}
    )
    mock_dc_client.post.side_effect = [decide_resp, approve_resp]

    agent = SimulatedAgent(decision_center_url="http://dc", client=mock_dc_client)
    step = make_step("ASK_FOR_APPROVAL", human_approves=False)
    decision, agent_obeyed = await agent.execute_step(step, "group-1")

    assert agent_obeyed is True
    approve_call = mock_dc_client.post.call_args_list[1]
    assert approve_call[1]["json"]["approved"] is False


@pytest.mark.asyncio
async def test_decide_request_includes_identity_fields(mock_dc_client):
    mock_dc_client.post.return_value = make_mock_response(
        200, {"request_id": "req-005", "outcome": "APPROVE"}
    )
    agent = SimulatedAgent(decision_center_url="http://dc", client=mock_dc_client)
    await agent.execute_step(make_step("APPROVE"), "group-xyz")

    call_json = mock_dc_client.post.call_args[1]["json"]
    assert call_json["agent_id"] == "simulated-agent"
    assert call_json["credential_id"] == "eval-credential"
    assert call_json["user_id"] == "eval-user"
    assert call_json["group_id"] == "group-xyz"
