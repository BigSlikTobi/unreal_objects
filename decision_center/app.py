from fastapi import FastAPI, HTTPException, Request
from typing import List
import json

from .models import (
    DecisionOutcome, DecisionState, EvaluateRequest, DecisionResult,
    ApprovalSubmission, AtomicLogEntry, DecisionChain
)
from .store import DecisionStore
from .evaluator import evaluate_request
import uuid

app = FastAPI(title="Unreal Objects Decision Center API")
store = DecisionStore()

def _outcome_to_state(outcome: DecisionOutcome) -> DecisionState:
    if outcome == DecisionOutcome.APPROVE:
        return DecisionState.APPROVED
    elif outcome == DecisionOutcome.REJECT:
        return DecisionState.REJECTED
    return DecisionState.APPROVAL_REQUIRED

@app.get("/v1/decide", response_model=DecisionResult)
async def evaluate(request_description: str, context: str, group_id: str = None):
    try:
        ctx_dict = json.loads(context)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid context JSON")

    # Evaluate
    outcome, matched_rules = await evaluate_request(ctx_dict, group_id)
    req_id = str(uuid.uuid4())
    
    # Log Atomic Decision
    state = _outcome_to_state(outcome)
    store.log_atomic(AtomicLogEntry(
        request_description=request_description,
        context=ctx_dict,
        decision=state
    ))

    # Log Chain Event
    store.log_chain_event(req_id, "REQUEST", details={"description": request_description, "context": ctx_dict})
    store.log_chain_event(req_id, "EVALUATION", details={"outcome": outcome.value, "matched_rules": matched_rules})

    if state == DecisionState.APPROVAL_REQUIRED:
        store.add_pending(req_id, {"description": request_description, "context": ctx_dict})

    return DecisionResult(
        request_id=req_id,
        outcome=outcome,
        matched_rules=matched_rules
    )

@app.get("/v1/pending", response_model=List[dict])
async def get_pending():
    return store.get_pending()

@app.post("/v1/decide/{request_id}/approve")
async def submit_approval(request_id: str, submission: ApprovalSubmission):
    chain = store.get_chain(request_id)
    if not chain:
        raise HTTPException(status_code=404, detail="Decision chain not found")
    
    status = "APPROVED" if submission.approved else "REJECTED"
    
    store.log_chain_event(request_id, "APPROVAL_STATUS", details={
        "status": status,
        "approver": submission.approver
    })
    store.resolve_pending(request_id)
    return {"status": "success", "request_id": request_id, "final_state": status}

@app.get("/v1/logs/atomic", response_model=List[AtomicLogEntry])
async def get_atomic_logs():
    return store.get_atomic_logs()

@app.get("/v1/logs/chains", response_model=List[DecisionChain])
async def get_all_chains():
    return store.get_all_chains()

@app.get("/v1/logs/chains/{request_id}", response_model=DecisionChain)
async def get_chain(request_id: str):
    chain = store.get_chain(request_id)
    if not chain:
        raise HTTPException(status_code=404, detail="Chain not found")
    return chain

