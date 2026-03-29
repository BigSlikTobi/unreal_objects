import json
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import wraps

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

from mcp_server.auth import AuthService, AuthStore, get_current_principal, principal_context
from shared.middleware import internal_headers

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RULE_ENGINE_URL = os.getenv("RULE_ENGINE_URL", "http://127.0.0.1:8001")
DECISION_CENTER_URL = os.getenv("DECISION_CENTER_URL", "http://127.0.0.1:8002")
BACKEND_TIMEOUT = httpx.Timeout(5.0, connect=3.0)

MAX_CONTEXT_JSON_BYTES = 100 * 1024  # 100 KB

# Set by main() via --group-id. When set, all evaluate_action calls use this
# group without the agent needing to know or specify it.
_DEFAULT_GROUP_ID: str | None = None
_AUTH_ENABLED = False
_AUTH_SERVICE: AuthService | None = None
_ADMIN_API_KEY: str | None = None

# ---------------------------------------------------------------------------
# Server instructions — injected into the agent's context on every connection
# ---------------------------------------------------------------------------

_INSTRUCTIONS = """\
You are connected to Unreal Objects — a non-negotiable business rule guardrail.

== MANDATORY PROTOCOL — no exceptions, no override ==

1. STARTUP
   Call guardrail_heartbeat before any other action.
   If healthy=false, stop immediately and tell the user the guardrail system is unavailable.

2. BEFORE EVERY REAL-WORLD ACTION call evaluate_action with a clear description
   and the relevant context. Do not proceed until you have a decision.

3. OBEY OUTCOMES ABSOLUTELY:
     APPROVE          → proceed with the action.
     REJECT           → action is blocked; explain to the user; do NOT retry or reframe.
     ASK_FOR_APPROVAL → stop; tell the user what you wanted to do and why approval is needed.
                        Call submit_approval(request_id, approved, approver) with the
                        human's decision, then proceed only if approved=true.

4. NEVER skip evaluate_action, reframe a rejected action to get a different outcome,
   or proceed after a REJECT. The guardrail decision is final.
"""

# ---------------------------------------------------------------------------
# Lifespan-managed shared HTTP clients
# ---------------------------------------------------------------------------

@dataclass
class Clients:
    rule_engine: httpx.AsyncClient
    decision_center: httpx.AsyncClient


@asynccontextmanager
async def lifespan(server: FastMCP):
    _int_headers = internal_headers()
    async with (
        httpx.AsyncClient(base_url=RULE_ENGINE_URL, timeout=BACKEND_TIMEOUT, headers=_int_headers) as re_client,
        httpx.AsyncClient(base_url=DECISION_CENTER_URL, timeout=BACKEND_TIMEOUT, headers=_int_headers) as dc_client,
    ):
        yield Clients(rule_engine=re_client, decision_center=dc_client)


mcp = FastMCP("Unreal Objects", lifespan=lifespan, instructions=_INSTRUCTIONS)


def _clients(ctx: Context) -> Clients:
    return ctx.request_context.lifespan_context


# ---------------------------------------------------------------------------
# Fail-closed decorator
# ---------------------------------------------------------------------------

def fail_closed(tool_func):
    @wraps(tool_func)
    async def wrapper(*args, **kwargs):
        try:
            return await tool_func(*args, **kwargs)
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            ctx = kwargs.get("ctx")
            if ctx:
                await ctx.error(
                    f"fail_closed triggered: {type(exc).__name__}: {exc}"
                )
            return {
                "outcome": "REJECT",
                "error": True,
                "reason": "BACKEND_UNREACHABLE",
                "detail": f"Guardrail infrastructure unavailable: {type(exc).__name__}",
                "instruction": "Do NOT proceed with this action. The business rule evaluation system is unreachable."
            }
    return wrapper


# ---------------------------------------------------------------------------
# Structured error helper
# ---------------------------------------------------------------------------

def _invalid_input(message: str) -> dict:
    return {"error": True, "reason": "INVALID_INPUT", "detail": message}


def _effective_group_id(group_id: str | None, principal) -> str | None:
    if principal is None:
        return group_id or _DEFAULT_GROUP_ID

    if group_id:
        if group_id not in principal.allowed_group_ids:
            raise ValueError("group_id is not allowed for this credential")
        return group_id

    if principal.default_group_id:
        return principal.default_group_id

    raise ValueError("no default group is configured for this credential")


class CreateAgentRequest(BaseModel):
    name: str
    description: str = ""
    metadata: dict = Field(default_factory=dict)


class CreateEnrollmentTokenRequest(BaseModel):
    credential_name: str
    scopes: list[str] = Field(default_factory=list)
    default_group_id: str | None = None
    allowed_group_ids: list[str] = Field(default_factory=list)
    ttl_seconds: int = 3600


class EnrollAgentRequest(BaseModel):
    enrollment_token: str


class OAuthTokenRequest(BaseModel):
    grant_type: str
    client_id: str
    client_secret: str
    scope: str | None = None


def _require_admin(request: Request, admin_api_key: str | None):
    if not admin_api_key or request.headers.get("X-Admin-Key") != admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid admin API key")


def _bootstrap_instructions(request: Request) -> dict:
    same_host_as = str(request.base_url).rstrip("/")
    return {
        "version": 1,
        "name": "Unreal Objects Bootstrap",
        "bootstrap_prompt": "If you have already enrolled before, do not enroll again. Reuse your stored client_id and client_secret and request a fresh access token. Otherwise, ask the user for the one-time enrollment token, then follow the steps below on this same host.",
        "same_host_as": same_host_as,
        "mcp_http_path": "/mcp",
        "enroll_path": "/v1/agents/enroll",
        "token_path": "/oauth/token",
        "mcp_headers": {
            "Accept": "application/json, text/event-stream",
        },
        "steps": [
            "POST your one-time enrollment token to /v1/agents/enroll as JSON.",
            "Store agent_id, credential_id, client_id, and client_secret from the response.",
            "POST client_credentials to /oauth/token.",
            "Use the returned access_token as Bearer auth for POST /mcp requests.",
            "Include Accept: application/json, text/event-stream on MCP HTTP requests.",
            "Report back when MCP access is working.",
        ],
        "notes": [
            "Use the same host you called for /instructions; the paths above are relative.",
            "If you have already enrolled before, do not enroll again. Reuse stored client credentials and request a fresh access token.",
            "Do not send the enrollment token as a Bearer token.",
            "The enrollment token can only be used once.",
        ],
    }


def build_http_app(
    base_app,
    auth_enabled: bool,
    auth_service: AuthService | None,
    admin_api_key: str | None,
):
    if auth_enabled and auth_service is None:
        raise ValueError("auth_service is required when auth is enabled")

    auth_routes_enabled = auth_enabled and auth_service is not None

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        lifespan_context = getattr(getattr(base_app, "router", None), "lifespan_context", None)
        if lifespan_context is None:
            yield
            return

        async with lifespan_context(base_app):
            yield

    app = FastAPI(lifespan=lifespan)

    @app.middleware("http")
    async def bearer_auth_middleware(request: Request, call_next):
        exempt_prefixes = ("/v1/admin", "/v1/agents/enroll", "/oauth/token", "/instructions")
        if not auth_enabled or request.url.path.startswith(exempt_prefixes):
            return await call_next(request)

        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Missing bearer token"})

        token = authorization.split(" ", 1)[1].strip()
        principal = auth_service.authenticate_bearer(token) if auth_service else None
        if not principal:
            return JSONResponse(status_code=401, content={"detail": "Invalid or expired bearer token"})

        with principal_context(principal):
            return await call_next(request)

    if auth_routes_enabled:
        @app.post("/v1/admin/agents", status_code=201)
        async def create_agent(request: Request, payload: CreateAgentRequest):
            _require_admin(request, admin_api_key)
            agent = auth_service.create_agent(
                name=payload.name,
                description=payload.description,
                metadata=payload.metadata,
            )
            return agent.model_dump()

        @app.get("/instructions")
        async def bootstrap_instructions(request: Request):
            return _bootstrap_instructions(request)

        @app.get("/v1/admin/agents")
        async def list_agents(request: Request):
            _require_admin(request, admin_api_key)
            return [agent.model_dump() for agent in auth_service.list_agents()]

        @app.get("/v1/admin/credentials")
        async def list_credentials(request: Request):
            _require_admin(request, admin_api_key)
            return [credential.model_dump(exclude={"client_secret_hash"}) for credential in auth_service.list_credentials()]

        @app.post("/v1/admin/agents/{agent_id}/enrollment-tokens", status_code=201)
        async def create_enrollment_token(request: Request, agent_id: str, payload: CreateEnrollmentTokenRequest):
            _require_admin(request, admin_api_key)
            try:
                return auth_service.create_enrollment_token(
                    agent_id=agent_id,
                    credential_name=payload.credential_name,
                    scopes=payload.scopes,
                    default_group_id=payload.default_group_id,
                    allowed_group_ids=payload.allowed_group_ids,
                    ttl_seconds=payload.ttl_seconds,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @app.post("/v1/admin/credentials/{credential_id}/revoke")
        async def revoke_credential(request: Request, credential_id: str):
            _require_admin(request, admin_api_key)
            try:
                credential = auth_service.revoke_credential(credential_id)
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            return credential.model_dump(exclude={"client_secret_hash"})

        @app.post("/v1/admin/agents/{agent_id}/revoke")
        async def revoke_agent(request: Request, agent_id: str):
            _require_admin(request, admin_api_key)
            try:
                agent = auth_service.revoke_agent(agent_id)
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            return agent.model_dump()

        @app.post("/v1/agents/enroll")
        async def enroll_agent(payload: EnrollAgentRequest):
            try:
                bootstrap = auth_service.exchange_enrollment_token(payload.enrollment_token)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return bootstrap.model_dump()

        @app.post("/oauth/token")
        async def issue_oauth_token(payload: OAuthTokenRequest):
            if payload.grant_type != "client_credentials":
                raise HTTPException(status_code=400, detail="Unsupported grant_type")
            try:
                token = auth_service.issue_access_token(
                    client_id=payload.client_id,
                    client_secret=payload.client_secret,
                    requested_scope=payload.scope,
                )
            except ValueError as exc:
                raise HTTPException(status_code=401, detail=str(exc)) from exc
            return token.model_dump()

    app.mount("/", base_app)
    return app


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=True))
async def guardrail_heartbeat(ctx: Context):
    """Check if the guardrail system is operational.
    Call this on startup. If healthy=false, do NOT proceed with any actions."""
    await ctx.info("guardrail_heartbeat called")
    clients = _clients(ctx)
    rule_engine_ok = False
    decision_center_ok = False

    try:
        resp = await clients.rule_engine.get("/v1/health")
        rule_engine_ok = resp.status_code == 200
    except (httpx.RequestError, httpx.HTTPStatusError):
        rule_engine_ok = False

    try:
        resp = await clients.decision_center.get("/v1/health")
        decision_center_ok = resp.status_code == 200
    except (httpx.RequestError, httpx.HTTPStatusError):
        decision_center_ok = False

    healthy = rule_engine_ok and decision_center_ok
    await ctx.debug(f"heartbeat result: healthy={healthy}")
    return {
        "healthy": healthy,
        "rule_engine": {"reachable": rule_engine_ok},
        "decision_center": {"reachable": decision_center_ok},
        "instruction": "System operational. Proceed normally." if healthy else "Guardrail system is degraded. Do NOT proceed with any actions until healthy=true."
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
@fail_closed
async def evaluate_action(
    request_description: str,
    context_json: str,
    ctx: Context,
    group_id: str = None,
    user_id: str = None,
):
    """Evaluate a planned action against business rules before executing it.

    Call this before every real-world action. The outcome tells you whether
    to proceed (APPROVE), stop (REJECT), or wait for human sign-off (ASK_FOR_APPROVAL).

    Args:
        request_description: Plain-English description of what you want to do.
        context_json: JSON string with the relevant data (e.g. recipient, amount).
        group_id: Rule group to evaluate against. If omitted, uses the server default.
    """
    await ctx.info(f"evaluate_action called: group_id={group_id}")

    if len(context_json.encode("utf-8")) > MAX_CONTEXT_JSON_BYTES:
        return _invalid_input(
            f"context_json exceeds maximum size of {MAX_CONTEXT_JSON_BYTES} bytes"
        )
    try:
        parsed_context = json.loads(context_json)
    except (json.JSONDecodeError, TypeError) as exc:
        return _invalid_input(f"context_json is not valid JSON: {exc}")

    clients = _clients(ctx)
    principal = get_current_principal() if _AUTH_ENABLED else None

    if _AUTH_ENABLED:
        if not principal:
            return _invalid_input("authenticated principal missing for protected request")
        if not user_id:
            return _invalid_input("user_id is required when agent auth is enabled")
        try:
            effective_group = _effective_group_id(group_id, principal)
        except ValueError as exc:
            return _invalid_input(str(exc))
        payload = {
            "request_description": request_description,
            "context": parsed_context,
            "group_id": effective_group,
            "agent_id": principal.agent_id,
            "credential_id": principal.credential_id,
            "user_id": user_id,
            "scope": " ".join(principal.scopes),
        }
        resp = await clients.decision_center.post("/v1/decide", json=payload)
    else:
        params = {
            "request_description": request_description,
            "context": context_json,
        }
        effective_group = _effective_group_id(group_id, None)
        if effective_group:
            params["group_id"] = effective_group
        resp = await clients.decision_center.get("/v1/decide", params=params)

    resp.raise_for_status()
    await ctx.debug("evaluate_action success")
    return resp.json()


@mcp.tool(annotations=ToolAnnotations(destructiveHint=False, openWorldHint=True))
@fail_closed
async def submit_approval(request_id: str, approved: bool, approver: str, ctx: Context):
    """Record a human approval decision for a pending ASK_FOR_APPROVAL outcome.

    After calling this with approved=True, proceed with the action yourself.
    After approved=False, the action is rejected — do not proceed.
    """
    await ctx.info(f"submit_approval called: request_id={request_id}, approved={approved}")
    clients = _clients(ctx)

    resp = await clients.decision_center.post(
        f"/v1/decide/{request_id}/approve",
        json={"approved": approved, "approver": approver},
    )
    resp.raise_for_status()
    await ctx.debug("submit_approval recorded")
    return resp.json()


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
@fail_closed
async def list_rule_groups(ctx: Context):
    """List all available business rule groups."""
    await ctx.info("list_rule_groups called")
    clients = _clients(ctx)
    resp = await clients.rule_engine.get("/v1/groups")
    resp.raise_for_status()
    await ctx.debug("list_rule_groups success")
    return resp.json()


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
@fail_closed
async def get_rule_group(group_id: str, ctx: Context):
    """Get a specific rule group with all its rules."""
    await ctx.info(f"get_rule_group called: group_id={group_id}")
    clients = _clients(ctx)
    resp = await clients.rule_engine.get(f"/v1/groups/{group_id}")
    resp.raise_for_status()
    await ctx.debug("get_rule_group success")
    return resp.json()


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
@fail_closed
async def get_decision_log(log_type: str, ctx: Context, request_id: str = None):
    """Retrieve decision logs.

    Args:
        log_type: 'atomic' (all decisions), 'chains' (all chains), or 'chain' (one chain by request_id).
        request_id: Required when log_type is 'chain'.
    """
    await ctx.info(f"get_decision_log called: log_type={log_type}")

    if log_type == "atomic":
        url = "/v1/logs/atomic"
    elif log_type == "chains":
        url = "/v1/logs/chains"
    elif log_type == "chain":
        if not request_id:
            return _invalid_input("request_id is required for log_type 'chain'")
        url = f"/v1/logs/chains/{request_id}"
    else:
        return _invalid_input(f"Invalid log_type: {log_type}. Must be 'atomic', 'chains', or 'chain'.")

    clients = _clients(ctx)
    resp = await clients.decision_center.get(url)
    resp.raise_for_status()
    await ctx.debug("get_decision_log success")
    return resp.json()


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
@fail_closed
async def get_pending(ctx: Context):
    """List all actions currently awaiting human approval."""
    await ctx.info("get_pending called")
    clients = _clients(ctx)
    resp = await clients.decision_center.get("/v1/pending")
    resp.raise_for_status()
    await ctx.debug("get_pending success")
    return resp.json()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Unreal Objects MCP Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
    )
    parser.add_argument(
        "--allowed-hosts",
        default=None,
        help="Comma-separated Host headers to accept. Defaults to 'localhost,127.0.0.1' for loopback or '*' for 0.0.0.0.",
    )
    parser.add_argument(
        "--group-id",
        default=None,
        help="Default rule group applied to all evaluate_action calls. Agent cannot override this.",
    )
    parser.add_argument(
        "--auth-enabled",
        action="store_true",
        help="Require authenticated HTTP MCP access using agent credentials.",
    )
    parser.add_argument(
        "--admin-api-key",
        default=None,
        help="Admin API key required for agent registration and credential management routes.",
    )
    parser.add_argument(
        "--token-ttl-seconds",
        type=int,
        default=900,
        help="Lifetime for issued bearer access tokens.",
    )

    args = parser.parse_args()

    global _DEFAULT_GROUP_ID, _AUTH_ENABLED, _AUTH_SERVICE, _ADMIN_API_KEY
    _DEFAULT_GROUP_ID = args.group_id
    _AUTH_ENABLED = args.auth_enabled
    _ADMIN_API_KEY = args.admin_api_key
    _AUTH_SERVICE = None
    if _DEFAULT_GROUP_ID:
        print(f"Default rule group: {_DEFAULT_GROUP_ID}")
    if _ADMIN_API_KEY and not _AUTH_ENABLED:
        raise SystemExit("--admin-api-key requires --auth-enabled")
    if _AUTH_ENABLED:
        _AUTH_SERVICE = AuthService(
            store=AuthStore(),
            token_ttl_seconds=args.token_ttl_seconds,
        )

    if args.transport in ("sse", "streamable-http"):
        import uvicorn

        if args.allowed_hosts is not None:
            allowed_hosts = [h.strip() for h in args.allowed_hosts.split(",")]
        elif args.host in ("0.0.0.0", ""):
            allowed_hosts = ["*"]
        else:
            allowed_hosts = ["localhost", "127.0.0.1"]

        mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=("*" not in allowed_hosts),
            allowed_hosts=[] if "*" in allowed_hosts else allowed_hosts,
        )

        if "*" not in allowed_hosts:
            print(f"Allowed Host headers: {', '.join(allowed_hosts)}")

        if args.transport == "streamable-http":
            print(f"Starting Unreal Objects MCP Server (Streamable HTTP) on http://{args.host}:{args.port}")
            base_app = mcp.streamable_http_app()
        else:
            print(f"Starting Unreal Objects MCP Server (SSE) on http://{args.host}:{args.port}")
            base_app = mcp.sse_app()

        wrapped_app = build_http_app(
            base_app=base_app,
            auth_enabled=_AUTH_ENABLED,
            auth_service=_AUTH_SERVICE,
            admin_api_key=_ADMIN_API_KEY,
        )
        _allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
        app = CORSMiddleware(
            wrapped_app,
            allow_origins=_allowed_origins,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        uvicorn.run(app, host=args.host, port=args.port)
    else:
        if _AUTH_ENABLED:
            raise SystemExit("Authenticated MCP is only supported for HTTP transports")
        mcp.run()


if __name__ == "__main__":
    main()
