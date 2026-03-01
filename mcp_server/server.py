import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import wraps

import httpx
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RULE_ENGINE_URL = "http://127.0.0.1:8001"
DECISION_CENTER_URL = "http://127.0.0.1:8002"
BACKEND_TIMEOUT = httpx.Timeout(5.0, connect=3.0)

MAX_CONTEXT_JSON_BYTES = 100 * 1024  # 100 KB

# Set by main() via --group-id. When set, all evaluate_action calls use this
# group without the agent needing to know or specify it.
_DEFAULT_GROUP_ID: str | None = None

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
    async with (
        httpx.AsyncClient(base_url=RULE_ENGINE_URL, timeout=BACKEND_TIMEOUT) as re_client,
        httpx.AsyncClient(base_url=DECISION_CENTER_URL, timeout=BACKEND_TIMEOUT) as dc_client,
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
    request_description: str, context_json: str, ctx: Context, group_id: str = None
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
        json.loads(context_json)
    except (json.JSONDecodeError, TypeError) as exc:
        return _invalid_input(f"context_json is not valid JSON: {exc}")

    clients = _clients(ctx)
    params = {
        "request_description": request_description,
        "context": context_json,
    }
    effective_group_id = group_id or _DEFAULT_GROUP_ID
    if effective_group_id:
        params["group_id"] = effective_group_id

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

    args = parser.parse_args()

    global _DEFAULT_GROUP_ID
    _DEFAULT_GROUP_ID = args.group_id
    if _DEFAULT_GROUP_ID:
        print(f"Default rule group: {_DEFAULT_GROUP_ID}")

    if args.transport in ("sse", "streamable-http"):
        import uvicorn
        from starlette.middleware.cors import CORSMiddleware

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

        app = CORSMiddleware(
            base_app,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        uvicorn.run(app, host=args.host, port=args.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
