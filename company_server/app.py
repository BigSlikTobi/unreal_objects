"""FastAPI server for the living virtual company."""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from company_server.clock import CompanyClock
from company_server.config import CompanyConfig
from company_server.scheduler import CompanyScheduler
from company_server.state import CompanyState
from company_server.webhooks import WebhookDispatcher
from support_company.models import CaseStatus
from shared.middleware import InternalAuthMiddleware, check_production_api_key, internal_headers

check_production_api_key()

logger = logging.getLogger(__name__)

# Module-level state — set during lifespan
_state: CompanyState | None = None
_clock: CompanyClock | None = None
_config: CompanyConfig | None = None
_scheduler: CompanyScheduler | None = None
_group_id: str | None = None

# Allow external override before app starts (used by CLI)
_startup_config: CompanyConfig | None = None
_startup_use_ai: bool = True


def configure(config: CompanyConfig, use_ai: bool = True) -> None:
    global _startup_config, _startup_use_ai
    _startup_config = config
    _startup_use_ai = use_ai


async def _load_rule_pack(config: CompanyConfig) -> str | None:
    rule_pack_path = Path(config.rule_pack_path)
    if not rule_pack_path.exists():
        logger.warning("Rule pack not found at %s", rule_pack_path)
        return None

    with open(rule_pack_path) as f:
        pack = json.load(f)

    try:
        async with httpx.AsyncClient(timeout=10, headers=internal_headers()) as client:
            # Create the rule group
            resp = await client.post(
                f"{config.rule_engine_url}/v1/groups",
                json={"name": pack["name"], "description": pack.get("description", "")},
            )
            resp.raise_for_status()
            group = resp.json()
            group_id = group["id"]

            # Add each rule
            for rule in pack["rules"]:
                resp = await client.post(
                    f"{config.rule_engine_url}/v1/groups/{group_id}/rules",
                    json=rule,
                )
                resp.raise_for_status()

            logger.info("Loaded rule pack '%s' as group %s with %d rules", pack["name"], group_id, len(pack["rules"]))
            return group_id
    except Exception:
        logger.error("Failed to load rule pack into Rule Engine", exc_info=True)
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _state, _clock, _config, _scheduler, _group_id

    _config = _startup_config or CompanyConfig()
    _clock = CompanyClock(acceleration=_config.acceleration)
    _state = CompanyState()

    # Seed data
    _state.seed_customers(_config.initial_customers)
    _state.seed_orders(_config.initial_orders)
    logger.info("Seeded %d customers and %d orders", len(_state.customers), len(_state.orders))

    # Load rule pack
    _group_id = await _load_rule_pack(_config)

    # Start scheduler
    webhook = WebhookDispatcher(_config.webhook_url, _config.webhook_secret)
    _scheduler = CompanyScheduler(
        config=_config,
        state=_state,
        clock=_clock,
        webhook=webhook,
        use_ai=_startup_use_ai,
    )
    _scheduler.start()
    logger.info("Company server running at %gx acceleration", _config.acceleration)

    yield

    _scheduler.stop()
    logger.info("Company server shutting down")


app = FastAPI(title="Unreal Objects Virtual Company", version="0.1.0", lifespan=lifespan)

from fastapi.middleware.cors import CORSMiddleware

_allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(InternalAuthMiddleware)


# --- Request/Response models ---

class AssignRequest(BaseModel):
    bot_id: str


class ResolveRequest(BaseModel):
    resolution: str


class CreateRuleRequest(BaseModel):
    name: str
    feature: str
    active: bool = True
    datapoints: list[str] = []
    edge_cases: list[str] = []
    edge_cases_json: list[dict] = []
    rule_logic: str = ""
    rule_logic_json: dict = {}


class UpdateRuleRequest(BaseModel):
    name: str | None = None
    feature: str | None = None
    active: bool | None = None
    datapoints: list[str] | None = None
    edge_cases: list[str] | None = None
    edge_cases_json: list[dict] | None = None
    rule_logic: str | None = None
    rule_logic_json: dict | None = None


# --- Endpoints ---

@app.get("/health")
def health():
    return {"status": "ok", "service": "company_server"}


@app.get("/api/v1/status")
def get_status():
    return {
        "virtual_time": _clock.now().isoformat() if _clock else None,
        "acceleration": _config.acceleration if _config else None,
        "group_id": _group_id,
        "stats": _state.stats() if _state else {},
    }


@app.get("/api/v1/clock")
def get_clock():
    if not _clock:
        raise HTTPException(503, "Clock not initialized")
    vt = _clock.now()
    return {
        "virtual_time": vt.isoformat(),
        "acceleration": _clock.acceleration,
        "is_business_hours": _clock.is_business_hours(),
        "activity_multiplier": _clock.activity_multiplier(),
        "day_of_week": vt.strftime("%A"),
    }


@app.get("/api/v1/cases")
def list_cases(status: str | None = Query(None)):
    if not _state:
        raise HTTPException(503, "State not initialized")
    cases = list(_state.cases.values())
    if status:
        try:
            filter_status = CaseStatus(status)
            cases = [c for c in cases if c.status == filter_status]
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")
    return {"cases": [c.model_dump(mode="json") for c in cases], "total": len(cases)}


@app.get("/api/v1/cases/{case_id}")
def get_case(case_id: str):
    if not _state:
        raise HTTPException(503, "State not initialized")
    case = _state.cases.get(case_id)
    if not case:
        raise HTTPException(404, "Case not found")

    result = case.model_dump(mode="json")
    if case.customer_id:
        result["customer_context"] = _state.get_customer_history(case.customer_id)
    return result


@app.post("/api/v1/cases/{case_id}/assign")
def assign_case(case_id: str, req: AssignRequest):
    if not _state:
        raise HTTPException(503, "State not initialized")
    case = _state.assign_case(case_id, req.bot_id)
    if not case:
        raise HTTPException(404, "Case not found or not open")
    return case.model_dump(mode="json")


@app.post("/api/v1/cases/{case_id}/resolve")
def resolve_case(case_id: str, req: ResolveRequest):
    if not _state:
        raise HTTPException(503, "State not initialized")
    case = _state.resolve_case(case_id, req.resolution)
    if not case:
        raise HTTPException(404, "Case not found or not assigned")
    return case.model_dump(mode="json")


@app.get("/api/v1/customers")
def list_customers():
    if not _state:
        raise HTTPException(503, "State not initialized")
    return {
        "customers": [c.model_dump(mode="json") for c in _state.customers.values()],
        "total": len(_state.customers),
    }


@app.get("/api/v1/customers/{customer_id}")
def get_customer(customer_id: str):
    if not _state:
        raise HTTPException(503, "State not initialized")
    customer = _state.customers.get(customer_id)
    if not customer:
        raise HTTPException(404, "Customer not found")
    result = customer.model_dump(mode="json")
    result["history"] = _state.get_customer_history(customer_id)
    return result


# --- Dynamic Rule Management ---

@app.post("/api/v1/rules")
async def create_rule(req: CreateRuleRequest):
    if not _group_id:
        raise HTTPException(503, "No rule group loaded")
    async with httpx.AsyncClient(timeout=10, headers=internal_headers()) as client:
        resp = await client.post(
            f"{_config.rule_engine_url}/v1/groups/{_group_id}/rules",
            json=req.model_dump(),
        )
        if resp.status_code >= 400:
            raise HTTPException(resp.status_code, resp.json())
        return resp.json()


@app.get("/api/v1/rules")
async def list_rules():
    if not _group_id:
        raise HTTPException(503, "No rule group loaded")
    async with httpx.AsyncClient(timeout=10, headers=internal_headers()) as client:
        resp = await client.get(f"{_config.rule_engine_url}/v1/groups/{_group_id}")
        if resp.status_code >= 400:
            raise HTTPException(resp.status_code, resp.json())
        group = resp.json()
        return {"rules": group.get("rules", []), "group_id": _group_id}


@app.put("/api/v1/rules/{rule_id}")
async def update_rule(rule_id: str, req: UpdateRuleRequest):
    if not _group_id:
        raise HTTPException(503, "No rule group loaded")
    update_data = req.model_dump(exclude_none=True)
    async with httpx.AsyncClient(timeout=10, headers=internal_headers()) as client:
        resp = await client.put(
            f"{_config.rule_engine_url}/v1/groups/{_group_id}/rules/{rule_id}",
            json=update_data,
        )
        if resp.status_code >= 400:
            raise HTTPException(resp.status_code, resp.json())
        return resp.json()


@app.delete("/api/v1/rules/{rule_id}")
async def delete_rule(rule_id: str):
    if not _group_id:
        raise HTTPException(503, "No rule group loaded")
    async with httpx.AsyncClient(timeout=10, headers=internal_headers()) as client:
        resp = await client.delete(
            f"{_config.rule_engine_url}/v1/groups/{_group_id}/rules/{rule_id}",
        )
        if resp.status_code >= 400:
            raise HTTPException(resp.status_code, resp.json())
        return {"deleted": rule_id}
