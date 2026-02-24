import pytest
from pydantic import ValidationError
from datetime import datetime

from decision_center.models import (
    DecisionOutcome,
    DecisionState,
    EvaluateRequest,
    DecisionResult,
    ApprovalSubmission,
    AtomicLogEntry,
    ChainEvent,
    DecisionChain
)

def test_enums():
    assert DecisionOutcome.APPROVE.value == "APPROVE"
    assert DecisionOutcome.REJECT.value == "REJECT"
    assert DecisionOutcome.ASK_FOR_APPROVAL.value == "ASK_FOR_APPROVAL"

    assert DecisionState.APPROVED.value == "APPROVED"
    assert DecisionState.REJECTED.value == "REJECTED"
    assert DecisionState.APPROVAL_REQUIRED.value == "APPROVAL_REQUIRED"

def test_evaluate_request_model():
    req = EvaluateRequest(
        request_description="Buy 200 Paperclips",
        context={"purchase": True, "amount": 3},
        group_id="group-1"
    )
    assert req.request_description == "Buy 200 Paperclips"
    assert req.group_id == "group-1"

    # group_id is optional
    req2 = EvaluateRequest(
        request_description="Test",
        context={}
    )
    assert req2.group_id is None

def test_atomic_log_entry():
    log = AtomicLogEntry(
        request_description="Test",
        context={"k": "v"},
        decision=DecisionState.APPROVED
    )
    assert log.decision == DecisionState.APPROVED
    assert isinstance(log.timestamp, datetime)
