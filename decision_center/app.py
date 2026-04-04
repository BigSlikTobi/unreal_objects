import logging
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List
import json

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from .models import (
    DecisionOutcome, DecisionState, EvaluateRequest, DecisionResult,
    ApprovalSubmission, AtomicLogEntry, DecisionChain, LLMConnectionRequest, RuleTranslationRequest,
    SchemaGenerationRequest, SchemaSaveRequest,
)
from .store import DecisionStore
from .evaluator import evaluate_request
from .translator import check_llm_connection, translate_rule, SchemaConceptMismatchError
from .schema_generator import generate_schema, list_schemas, save_schema, SchemaProposal, SchemaExistsError
from shared.middleware import InternalAuthMiddleware, check_production_api_key
import uuid

logger = logging.getLogger(__name__)

check_production_api_key()

def _get_real_client_ip(request: Request) -> str:
    """Use X-Forwarded-For when behind Railway's proxy, fall back to remote addr."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

limiter = Limiter(key_func=_get_real_client_ip, enabled=os.getenv("ENVIRONMENT") == "production")

app = FastAPI(title="Unreal Objects Decision Center API")
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

_allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(InternalAuthMiddleware)

store = DecisionStore(persistence_path=os.getenv("DECISION_CENTER_PERSISTENCE_PATH"))


def _outcome_to_state(outcome: DecisionOutcome) -> DecisionState:
    if outcome == DecisionOutcome.APPROVE:
        return DecisionState.APPROVED
    elif outcome == DecisionOutcome.REJECT:
        return DecisionState.REJECTED
    return DecisionState.APPROVAL_REQUIRED


async def _evaluate_and_log(req: EvaluateRequest) -> DecisionResult:
    outcome, matched_rules, matched_details = await evaluate_request(req.context, req.group_id, req.rule_id)
    req_id = str(uuid.uuid4())
    state = _outcome_to_state(outcome)

    identity = req.identity_dict()

    store.log_atomic(AtomicLogEntry(
        request_id=req_id,
        request_description=req.request_description,
        context=req.context,
        decision=state,
        **identity,
    ))

    store.log_chain_event(req_id, "REQUEST", details={
        "description": req.request_description,
        "context": req.context,
        **identity,
    })
    store.log_chain_event(req_id, "EVALUATION", details={
        "outcome": outcome.value,
        "matched_rules": matched_rules,
        "matched_details": matched_details,
        **identity,
    })

    if state == DecisionState.APPROVAL_REQUIRED:
        store.add_pending(req_id, {
            "description": req.request_description,
            "context": req.context,
            **identity,
        })

    return DecisionResult(
        request_id=req_id,
        outcome=outcome,
        matched_rules=matched_rules,
        matched_details=matched_details,
        **identity,
    )

@app.get("/v1/health")
async def health():
    return {"status": "ok", "service": "decision_center"}

@app.get("/v1/decide", response_model=DecisionResult)
@limiter.limit("60/minute")
async def evaluate(request: Request, request_description: str, context: str, group_id: str = None, rule_id: str = None):
    try:
        ctx_dict = json.loads(context)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid context JSON")
    return await _evaluate_and_log(EvaluateRequest(
        request_description=request_description,
        context=ctx_dict,
        group_id=group_id,
        rule_id=rule_id,
    ))


@app.post("/v1/decide", response_model=DecisionResult)
@limiter.limit("60/minute")
async def evaluate_post(request: Request, req: EvaluateRequest):
    return await _evaluate_and_log(req)

@app.get("/v1/pending", response_model=List[dict])
async def get_pending():
    return store.get_pending()

@app.post("/v1/decide/{request_id}/approve")
async def submit_approval(request_id: str, submission: ApprovalSubmission):
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', request_id):
        raise HTTPException(status_code=400, detail="Invalid request_id format")
    if submission.approver and len(submission.approver) > 200:
        raise HTTPException(status_code=400, detail="Approver name too long")
    chain = store.get_chain(request_id)
    if not chain:
        raise HTTPException(status_code=404, detail="Decision chain not found")
    
    # Guard against double-approval: pending is removed on first resolution.
    # If it's gone, the request was already approved or rejected.
    if not store.is_pending(request_id):
        raise HTTPException(status_code=409, detail="Decision already resolved")

    status = "APPROVED" if submission.approved else "REJECTED"
    pending = store.resolve_pending(request_id) or {}

    store.log_chain_event(request_id, "APPROVAL_STATUS", details={
        "status": status,
        "approver": submission.approver,
        "agent_id": pending.get("agent_id"),
        "credential_id": pending.get("credential_id"),
        "user_id": pending.get("user_id"),
        "effective_group_id": pending.get("effective_group_id"),
    })

    final_decision = DecisionState.APPROVED if submission.approved else DecisionState.REJECTED
    store.log_atomic(AtomicLogEntry(
        request_id=request_id,
        request_description=pending.get("description", ""),
        context=pending.get("context", {}),
        decision=final_decision,
        agent_id=pending.get("agent_id"),
        credential_id=pending.get("credential_id"),
        user_id=pending.get("user_id"),
        effective_group_id=pending.get("effective_group_id"),
    ))

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

@app.post("/v1/llm/connection")
async def check_connection(req: LLMConnectionRequest):
    success = check_llm_connection(req.provider, req.model, req.api_key)
    if not success:
        raise HTTPException(status_code=400, detail="Connection failed. Check your API key and model.")
    return {"status": "ok"}

@app.post("/v1/llm/translate")
@limiter.limit("10/minute")
async def translate_rule_api(request: Request, req: RuleTranslationRequest):
    try:
        result = translate_rule(
            natural_language=req.natural_language,
            feature=req.feature,
            name=req.name,
            provider=req.provider,
            model=req.model,
            api_key=req.api_key,
            context_schema=req.context_schema,
            datapoint_definitions=req.datapoint_definitions
        )
        return result
    except SchemaConceptMismatchError as e:
        content: dict = {"detail": str(e)}
        if e.proposed_field:
            content["proposed_field"] = e.proposed_field
        return JSONResponse(status_code=422, content=content)
    except Exception:
        logger.exception("LLM translation failed")
        raise HTTPException(status_code=500, detail="Internal processing error")

@app.post("/v1/llm/schema")
@limiter.limit("10/minute")
async def generate_schema_api(request: Request, req: SchemaGenerationRequest):
    try:
        proposal = generate_schema(
            req.user_message,
            req.conversation_history,
            req.current_schema,
            req.provider,
            req.model,
            req.api_key,
        )
        return proposal.model_dump()
    except Exception:
        logger.exception("Schema generation failed")
        raise HTTPException(status_code=500, detail="Internal processing error")

@app.get("/v1/schemas")
async def list_schemas_api():
    return list_schemas()

@app.post("/v1/schemas/save")
async def save_schema_api(req: SchemaSaveRequest):
    try:
        proposal = SchemaProposal(
            name=req.name,
            description=req.description,
            fields=req.fields,
            message="",
        )
        path = save_schema(proposal, overwrite=req.overwrite)
        return {"path": path, "name": proposal.name}
    except SchemaExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception:
        logger.exception("Schema save failed")
        raise HTTPException(status_code=500, detail="Internal processing error")
