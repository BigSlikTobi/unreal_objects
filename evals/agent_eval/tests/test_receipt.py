import pytest
from unittest.mock import AsyncMock, MagicMock
import httpx

from evals.agent_eval.receipt import validate_receipt
from evals.agent_eval.models import ReceiptAssertion


def make_mock_response(status_code: int, json_data: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    if json_data is not None:
        resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


def make_chain(events: list[dict]) -> dict:
    return {"request_id": "req-001", "events": events}


def make_approve_chain():
    return make_chain([
        {"event_type": "REQUEST", "details": {}},
        {"event_type": "EVALUATION", "details": {"outcome": "APPROVE"}},
    ])


def make_ask_chain(status="APPROVED", approver="simulated-human"):
    return make_chain([
        {"event_type": "REQUEST", "details": {}},
        {"event_type": "EVALUATION", "details": {"outcome": "ASK_FOR_APPROVAL"}},
        {"event_type": "APPROVAL_STATUS", "details": {"status": status, "approver": approver}},
    ])


@pytest.mark.asyncio
async def test_valid_approve_receipt():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = make_mock_response(200, make_approve_chain())

    assertion = ReceiptAssertion(
        must_have_event_types=["REQUEST", "EVALUATION"],
        outcome_in_evaluation="APPROVE",
    )
    valid, errors = await validate_receipt("req-001", assertion, "http://dc", client=mock_client)
    assert valid is True
    assert errors == []


@pytest.mark.asyncio
async def test_receipt_not_found_404():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = make_mock_response(404)

    assertion = ReceiptAssertion(
        must_have_event_types=["REQUEST", "EVALUATION"],
        outcome_in_evaluation="APPROVE",
    )
    valid, errors = await validate_receipt("req-missing", assertion, "http://dc", client=mock_client)
    assert valid is False
    assert any("404" in e for e in errors)


@pytest.mark.asyncio
async def test_missing_event_type():
    chain = make_chain([
        {"event_type": "REQUEST", "details": {}},
        # EVALUATION missing
    ])
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = make_mock_response(200, chain)

    assertion = ReceiptAssertion(
        must_have_event_types=["REQUEST", "EVALUATION"],
        outcome_in_evaluation="APPROVE",
    )
    valid, errors = await validate_receipt("req-001", assertion, "http://dc", client=mock_client)
    assert valid is False
    assert any("EVALUATION" in e for e in errors)


@pytest.mark.asyncio
async def test_wrong_outcome_in_evaluation():
    chain = make_chain([
        {"event_type": "REQUEST", "details": {}},
        {"event_type": "EVALUATION", "details": {"outcome": "REJECT"}},
    ])
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = make_mock_response(200, chain)

    assertion = ReceiptAssertion(
        must_have_event_types=["REQUEST", "EVALUATION"],
        outcome_in_evaluation="APPROVE",
    )
    valid, errors = await validate_receipt("req-001", assertion, "http://dc", client=mock_client)
    assert valid is False
    assert any("APPROVE" in e for e in errors)


@pytest.mark.asyncio
async def test_valid_ask_receipt_with_approval():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = make_mock_response(200, make_ask_chain("APPROVED", "simulated-human"))

    assertion = ReceiptAssertion(
        must_have_event_types=["REQUEST", "EVALUATION", "APPROVAL_STATUS"],
        outcome_in_evaluation="ASK_FOR_APPROVAL",
        approval_status="APPROVED",
        approver="simulated-human",
    )
    valid, errors = await validate_receipt("req-001", assertion, "http://dc", client=mock_client)
    assert valid is True
    assert errors == []


@pytest.mark.asyncio
async def test_wrong_approval_status():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = make_mock_response(200, make_ask_chain("REJECTED", "simulated-human"))

    assertion = ReceiptAssertion(
        must_have_event_types=["REQUEST", "EVALUATION", "APPROVAL_STATUS"],
        outcome_in_evaluation="ASK_FOR_APPROVAL",
        approval_status="APPROVED",
        approver="simulated-human",
    )
    valid, errors = await validate_receipt("req-001", assertion, "http://dc", client=mock_client)
    assert valid is False
    assert any("APPROVED" in e for e in errors)


@pytest.mark.asyncio
async def test_wrong_approver():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = make_mock_response(200, make_ask_chain("APPROVED", "wrong-human"))

    assertion = ReceiptAssertion(
        must_have_event_types=["REQUEST", "EVALUATION", "APPROVAL_STATUS"],
        outcome_in_evaluation="ASK_FOR_APPROVAL",
        approval_status="APPROVED",
        approver="simulated-human",
    )
    valid, errors = await validate_receipt("req-001", assertion, "http://dc", client=mock_client)
    assert valid is False
    assert any("simulated-human" in e for e in errors)
