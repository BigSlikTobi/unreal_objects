import logging
import re

import httpx
import os
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from typing import List

from .models import BusinessRule, BusinessRuleGroup, CreateRule, CreateRuleGroup, DatapointDefinition
from .store import RuleStore
from shared.middleware import InternalAuthMiddleware, check_production_api_key, internal_headers

logger = logging.getLogger(__name__)

_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')

check_production_api_key()

TOOL_AGENT_URL = os.getenv("TOOL_AGENT_URL", "http://127.0.0.1:8003")

app = FastAPI(title="Unreal Objects Rule Engine API")

_allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(InternalAuthMiddleware)

store = RuleStore(persistence_path=os.getenv("RULE_ENGINE_PERSISTENCE_PATH"))


def _require_admin_token_for_destructive_action(admin_token: str | None) -> None:
    expected_token = os.getenv("RULE_ENGINE_ADMIN_TOKEN")
    if not expected_token:
        if os.getenv("ENVIRONMENT") == "production":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service misconfigured",
            )
        return
    if admin_token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin token required for destructive action",
        )

@app.get("/v1/health")
async def health():
    return {"status": "ok", "service": "rule_engine"}

@app.post("/v1/groups", response_model=BusinessRuleGroup, status_code=201)
async def create_group(group: CreateRuleGroup):
    return store.create_group(group)

@app.get("/v1/groups", response_model=List[BusinessRuleGroup])
async def list_groups(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return store.list_groups()

def _validate_id(value: str, name: str = "id") -> None:
    if not _ID_PATTERN.match(value):
        raise HTTPException(status_code=400, detail=f"Invalid {name} format")


@app.get("/v1/groups/{group_id}", response_model=BusinessRuleGroup)
async def get_group(group_id: str, response: Response):
    _validate_id(group_id, "group_id")
    response.headers["Cache-Control"] = "no-store"
    group = store.get_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group

@app.delete("/v1/groups/{group_id}", status_code=204)
async def delete_group(group_id: str, x_admin_token: str | None = Header(default=None)):
    _validate_id(group_id, "group_id")
    _require_admin_token_for_destructive_action(x_admin_token)
    if not store.delete_group(group_id):
        raise HTTPException(status_code=404, detail="Group not found")

async def _notify_tool_agent(group_id: str, rule: BusinessRule, group_name: str):
    """Fire-and-forget webhook to the Tool Creation Agent. Silently ignored if agent is down."""
    try:
        async with httpx.AsyncClient(timeout=3.0, headers=internal_headers()) as client:
            await client.post(
                f"{TOOL_AGENT_URL}/v1/webhook/rule-created",
                json={
                    "group_id": group_id,
                    "group_name": group_name,
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "feature": rule.feature,
                    "rule_logic": rule.rule_logic,
                    "datapoints": rule.datapoints,
                },
            )
    except (httpx.RequestError, httpx.HTTPStatusError):
        pass  # Non-blocking: tool agent may not be running
    except Exception:
        logger.debug("Tool agent notification failed unexpectedly", exc_info=True)


@app.post("/v1/groups/{group_id}/rules", response_model=BusinessRule, status_code=201)
async def add_rule(group_id: str, rule: CreateRule, background_tasks: BackgroundTasks):
    _validate_id(group_id, "group_id")
    created = store.add_rule(group_id, rule)
    if not created:
        raise HTTPException(status_code=404, detail="Group not found")
    group = store.get_group(group_id)
    background_tasks.add_task(_notify_tool_agent, group_id, created, group.name)
    return created

@app.get("/v1/groups/{group_id}/rules/{rule_id}", response_model=BusinessRule)
async def get_rule(group_id: str, rule_id: str, response: Response):
    _validate_id(group_id, "group_id")
    _validate_id(rule_id, "rule_id")
    response.headers["Cache-Control"] = "no-store"
    rule = store.get_rule(group_id, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule

@app.delete("/v1/groups/{group_id}/rules/{rule_id}", status_code=204)
async def delete_rule(group_id: str, rule_id: str):
    _validate_id(group_id, "group_id")
    _validate_id(rule_id, "rule_id")
    if not store.delete_rule(group_id, rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")

@app.put("/v1/groups/{group_id}/rules/{rule_id}", response_model=BusinessRule)
async def update_rule(group_id: str, rule_id: str, rule: CreateRule):
    _validate_id(group_id, "group_id")
    _validate_id(rule_id, "rule_id")
    updated = store.update_rule(group_id, rule_id, rule)
    if not updated:
        raise HTTPException(status_code=404, detail="Rule or Group not found")
    return updated

@app.patch("/v1/groups/{group_id}/datapoints", response_model=BusinessRuleGroup)
async def update_datapoints(group_id: str, definitions: List[DatapointDefinition]):
    _validate_id(group_id, "group_id")
    group = store.update_datapoints(group_id, definitions)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group
