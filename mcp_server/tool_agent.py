"""Tool Creation Agent — FastAPI service on port 8003.

Workflow:
1. Rule Engine fires POST /v1/webhook/rule-created whenever a rule is created.
2. Agent asks an LLM: does this rule require a new guarded_ MCP tool?
3. If yes: generate tool code → evaluate against "Unreal Objects System" meta-rule
   (always routes to ASK_FOR_APPROVAL — no auto-writes).
4. Proposal stored; super user reviews and approves in the UI.
5. POST /v1/proposals/{id}/review with approved=True → appends code to server.py.
   Restart the MCP server for the new tool to take effect.

LLM configuration (three options, applied in order):
  1. POST /v1/config at runtime (UI sends this automatically when you save LLM settings)
  2. Environment variables: ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY
  3. No key configured → analysis is skipped, no proposals are generated
"""

import ast
import asyncio
import json
import keyword
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from shared.middleware import InternalAuthMiddleware, check_production_api_key, internal_headers

check_production_api_key()

RULE_ENGINE_URL = os.getenv("RULE_ENGINE_URL", "http://127.0.0.1:8001")
DECISION_CENTER_URL = os.getenv("DECISION_CENTER_URL", "http://127.0.0.1:8002")
SERVER_PY_PATH = os.path.join(os.path.dirname(__file__), "server.py")

# ---------------------------------------------------------------------------
# LLM configuration — provider, model, api_key
# Auto-detected from env vars on startup; overridable via POST /v1/config.
# ---------------------------------------------------------------------------

def _detect_llm_config() -> dict:
    """Pick a provider from available environment variables."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return {
            "provider": "anthropic",
            "model": "claude-haiku-4-5-20251001",
            "api_key": os.environ["ANTHROPIC_API_KEY"],
        }
    if os.environ.get("OPENAI_API_KEY"):
        return {"provider": "openai", "model": "gpt-4o-mini", "api_key": os.environ["OPENAI_API_KEY"]}
    if os.environ.get("GOOGLE_API_KEY"):
        return {"provider": "gemini", "model": "gemini-2.0-flash", "api_key": os.environ["GOOGLE_API_KEY"]}
    return {"provider": "anthropic", "model": "claude-haiku-4-5-20251001", "api_key": ""}


_llm_config: dict = _detect_llm_config()

# In-memory proposal store: request_id → proposal dict
_proposals: dict[str, dict] = {}
_system_group_id: str | None = None


# ---------------------------------------------------------------------------
# Startup: ensure the "Unreal Objects System" group + meta-rule exist
# ---------------------------------------------------------------------------

async def _ensure_system_group() -> None:
    global _system_group_id
    async with httpx.AsyncClient(base_url=RULE_ENGINE_URL, timeout=5.0, headers=internal_headers()) as client:
        resp = await client.get("/v1/groups")
        resp.raise_for_status()
        for g in resp.json():
            if g["name"] == "Unreal Objects System":
                _system_group_id = g["id"]
                print(f"[tool_agent] Using existing system group: {_system_group_id}")
                return

        resp = await client.post("/v1/groups", json={
            "name": "Unreal Objects System",
            "description": "Meta-governance rules for the Unreal Objects system itself.",
        })
        resp.raise_for_status()
        group = resp.json()
        _system_group_id = group["id"]

        # Meta-rule: every tool generation action requires human approval — always.
        await client.post(f"/v1/groups/{_system_group_id}/rules", json={
            "name": "Tool Generation Authorization",
            "feature": "MCP Tool Creation",
            "datapoints": ["action"],
            "edge_cases": [],
            "edge_cases_json": [],
            "rule_logic": "IF action = 'tool_generation' THEN ASK_FOR_APPROVAL",
            "rule_logic_json": {
                "if": [
                    {"===": [{"var": "action"}, "tool_generation"]},
                    "ASK_FOR_APPROVAL",
                    "APPROVE",
                ]
            },
        })
        print(f"[tool_agent] Created system group with meta-rule: {_system_group_id}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await _ensure_system_group()
    except Exception as exc:
        print(f"[tool_agent] Warning: could not set up system group: {exc}")
    yield


app = FastAPI(title="Unreal Objects Tool Creation Agent", lifespan=lifespan)

_allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(InternalAuthMiddleware)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class RuleCreatedPayload(BaseModel):
    group_id: str
    group_name: str
    rule_id: str
    rule_name: str
    feature: str
    rule_logic: str
    datapoints: list[str]


class ReviewDecision(BaseModel):
    approved: bool
    reviewer: str


class LLMConfig(BaseModel):
    provider: str   # "openai" | "anthropic" | "gemini"
    model: str
    api_key: str


# ---------------------------------------------------------------------------
# LLM analysis — supports OpenAI, Anthropic, and Gemini
# ---------------------------------------------------------------------------

_ANALYSIS_PROMPT = """\
You are analyzing a business rule to determine if it requires a new MCP guardrail tool.

The existing MCP tools already cover:
- guarded_http_request: any outbound HTTP call (REST APIs, webhooks, etc.)
- guarded_file_write: writing to any file on disk

A new guarded_ tool is needed ONLY if the rule governs an action that CANNOT be
expressed as an HTTP request or file write — for example:
- Sending email via SMTP (not a REST API)
- Writing to a SQL database via a Python driver (not HTTP)
- Making a phone call via a telephony SDK
- Interacting with OS resources (processes, sockets, etc.)

A new tool is NOT needed if:
- The rule is purely declarative (e.g., "IF amount > 100 THEN REJECT")
- The action is an outbound HTTP call (already covered by guarded_http_request)
- The action is a file write (already covered by guarded_file_write)

Business rule:
  Name: {name}
  Feature: {feature}
  Logic: {rule_logic}
  Datapoints: {datapoints}

Respond with JSON only (no markdown, no code fences):
{{
  "needs_tool": true or false,
  "reason": "brief one-sentence explanation",
  "tool_name": "guarded_snake_case_name",
  "action_description": "what this tool does in one sentence",
  "parameters": [
    {{"name": "param_name", "type": "str", "description": "what this parameter is"}}
  ]
}}
The tool_name, action_description, and parameters fields are required only when needs_tool is true.
"""


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences that some models wrap around JSON."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Drop first line (``` or ```json) and last line (```)
        inner = lines[1:] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner).rstrip("`").strip()
    return text


async def _analyze_rule(rule: RuleCreatedPayload) -> dict:
    """Call the configured LLM provider to decide if a new MCP tool is needed."""
    provider = _llm_config["provider"]
    model = _llm_config["model"]
    api_key = _llm_config["api_key"]

    if not api_key:
        return {
            "needs_tool": False,
            "reason": "No LLM API key configured. Use POST /v1/config or set ANTHROPIC_API_KEY / OPENAI_API_KEY / GOOGLE_API_KEY.",
        }

    from shared.sanitize import delimit_user_input
    prompt = _ANALYSIS_PROMPT.format(
        name=delimit_user_input(rule.rule_name, "rule_name"),
        feature=delimit_user_input(rule.feature, "feature"),
        rule_logic=delimit_user_input(rule.rule_logic, "rule_logic"),
        datapoints=", ".join(rule.datapoints) or "(none)",
    )

    if provider == "openai":
        import openai
        client = openai.AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)

    if provider == "anthropic":
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)
        message = await client.messages.create(
            model=model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return json.loads(_strip_code_fences(message.content[0].text))

    if provider == "gemini":
        from google import genai
        def _sync_call() -> dict:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            return json.loads(response.text)
        return await asyncio.to_thread(_sync_call)

    raise ValueError(f"Unknown LLM provider: {provider!r}. Must be 'openai', 'anthropic', or 'gemini'.")


# ---------------------------------------------------------------------------
# Code generation safety
# ---------------------------------------------------------------------------

_BLOCKED_IMPORTS = frozenset({
    "os", "sys", "subprocess", "shutil", "importlib", "builtins",
    "ctypes", "socket", "pickle", "shelve", "tempfile", "signal",
    "multiprocessing", "threading", "code", "codeop", "compileall",
})

_BLOCKED_CALLS = frozenset({
    "eval", "exec", "compile", "__import__", "getattr", "setattr",
    "delattr", "globals", "locals", "open", "breakpoint",
})


def _validate_generated_code(code: str) -> tuple[bool, str]:
    """Validate LLM-generated Python code is safe to persist.

    Returns (is_valid, reason).
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"Syntax error: {e}"

    # Top level must only contain function definitions (with decorators)
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return False, f"Top-level {type(node).__name__} not allowed; only function definitions permitted"

    # Walk entire AST
    for node in ast.walk(tree):
        # Block imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in _BLOCKED_IMPORTS:
                    return False, f"Import of '{alias.name}' is blocked"
        if isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                if top in _BLOCKED_IMPORTS:
                    return False, f"Import from '{node.module}' is blocked"

        # Block any reference to builtins / __builtins__ (prevents sandbox escape)
        if isinstance(node, ast.Name):
            if node.id in {"__builtins__", "builtins"}:
                return False, f"Reference to '{node.id}' is blocked"

        # Block dangerous function calls, including indirect calls via subscripting
        if isinstance(node, ast.Call):
            func = node.func
            name = None
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            elif isinstance(func, ast.Subscript):
                # Catch __builtins__["__import__"](...) pattern
                container_name = None
                if isinstance(func.value, ast.Name):
                    container_name = func.value.id
                elif isinstance(func.value, ast.Attribute):
                    container_name = func.value.attr
                if container_name in {"__builtins__", "builtins"}:
                    if isinstance(func.slice, ast.Constant) and isinstance(func.slice.value, str):
                        name = func.slice.value
            if name and name in _BLOCKED_CALLS:
                return False, f"Call to '{name}()' is blocked"

        # Block dunder access (except __name__, __doc__)
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and node.attr.endswith("__"):
                if node.attr not in ("__name__", "__doc__"):
                    return False, f"Access to '{node.attr}' is blocked"
            if node.attr in {"__builtins__", "builtins"}:
                return False, f"Access to '{node.attr}' is blocked"

    # Verify function names start with guarded_
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("guarded_"):
                return False, f"Function '{node.name}' must start with 'guarded_'"

    return True, "OK"


def _validate_tool_parameters(params: list[dict]) -> tuple[bool, str]:
    """Validate that LLM-generated parameter names are safe Python identifiers."""
    for p in params:
        name = p.get("name", "")
        if not name.isidentifier() or keyword.iskeyword(name):
            return False, f"Invalid parameter name: {name!r}"
        ptype = p.get("type", "str")
        if ptype not in ("str", "int", "float", "bool", "list", "dict"):
            return False, f"Invalid parameter type: {ptype!r}"
    return True, "OK"


def _generate_tool_code(analysis: dict) -> str:
    """Generate Python source for a new guarded_ MCP tool."""
    tool_name = analysis["tool_name"]
    action_desc = analysis["action_description"]
    params = analysis.get("parameters", [])

    sig_parts = [f'    {p["name"]}: {p["type"]}' for p in params]
    sig_parts += ["    request_description: str", "    ctx: Context = None"]
    sig = ",\n".join(sig_parts) + ","

    doc_args = "\n".join(f'        {p["name"]}: {p["description"]}.' for p in params)
    if doc_args:
        doc_args += "\n        request_description: Plain-English description of why this action is being taken."
    else:
        doc_args = "        request_description: Plain-English description of why this action is being taken."

    ctx_items = ", ".join(f'"{p["name"]}": {p["name"]}' for p in params)
    ctx_dict = "{" + ctx_items + "}" if ctx_items else "{}"

    pending_items = ", ".join(f'"{p["name"]}": {p["name"]}' for p in params)
    pending_dict = "{" + pending_items + "}" if pending_items else "{}"

    return f'''

@mcp.tool(annotations=ToolAnnotations(destructiveHint=True, openWorldHint=True))
@fail_closed
async def {tool_name}(
{sig}
):
    """{action_desc}. Evaluated against business rules before execution.

    Args:
{doc_args}
    """
    if ctx:
        await ctx.info(f"{tool_name}: {{request_description}}")

    decision = await _evaluate_before_act(
        request_description,
        {ctx_dict},
        ctx,
    )
    outcome = decision.get("outcome")

    if outcome == "APPROVE":
        if ctx:
            await ctx.info(f"{tool_name} approved, executing")
        # TODO: implement actual {tool_name.replace("guarded_", "")} logic here
        # Also add a branch to _execute_pending() for action type "{tool_name}"
        return {{"outcome": "APPROVE", "result": "TODO: implement execution logic"}}

    if outcome == "ASK_FOR_APPROVAL":
        req_id = decision.get("request_id")
        if req_id:
            _pending_actions[req_id] = {{
                "type": "{tool_name}",
                "params": {pending_dict},
            }}
            if ctx:
                await ctx.info(f"{tool_name} deferred, pending request_id={{req_id}}")

    if ctx:
        await ctx.warning(f"{tool_name} blocked: {{outcome}}")
    return decision
'''


# ---------------------------------------------------------------------------
# Background task: analyze + store proposal
# ---------------------------------------------------------------------------

async def _process_rule(rule: RuleCreatedPayload) -> None:
    try:
        analysis = await _analyze_rule(rule)
    except Exception as exc:
        print(f"[tool_agent] LLM analysis failed for rule '{rule.rule_name}': {exc}")
        return

    if not analysis.get("needs_tool"):
        print(f"[tool_agent] Rule '{rule.rule_name}': no new tool needed. {analysis.get('reason', '')}")
        return

    # Validate parameter names before code generation
    params = analysis.get("parameters", [])
    params_ok, params_reason = _validate_tool_parameters(params)
    if not params_ok:
        print(f"[tool_agent] Rule '{rule.rule_name}': unsafe parameters rejected: {params_reason}")
        return

    code = _generate_tool_code(analysis)

    # Validate generated code is safe
    code_ok, code_reason = _validate_generated_code(code)
    if not code_ok:
        print(f"[tool_agent] Rule '{rule.rule_name}': generated code rejected: {code_reason}")
        return
    context = {
        "action": "tool_generation",
        "tool_name": analysis["tool_name"],
        "trigger_rule": rule.rule_name,
        "trigger_group": rule.group_name,
    }

    request_id = str(uuid.uuid4())
    try:
        async with httpx.AsyncClient(base_url=DECISION_CENTER_URL, timeout=5.0, headers=internal_headers()) as dc:
            resp = await dc.get("/v1/decide", params={
                "request_description": (
                    f"Generate MCP tool '{analysis['tool_name']}' "
                    f"(triggered by rule '{rule.rule_name}' in group '{rule.group_name}')"
                ),
                "context": json.dumps(context),
                "group_id": _system_group_id,
            })
            resp.raise_for_status()
            decision = resp.json()
            request_id = decision.get("request_id", request_id)
    except Exception as exc:
        print(f"[tool_agent] DC evaluation failed: {exc}. Using local request_id.")
        decision = {"outcome": "ASK_FOR_APPROVAL", "request_id": request_id}

    _proposals[request_id] = {
        "id": request_id,
        "status": "pending_review",
        "created_at": datetime.now().isoformat(),
        "trigger_rule": rule.rule_name,
        "trigger_group": rule.group_name,
        "group_id": rule.group_id,
        "tool_name": analysis["tool_name"],
        "action_description": analysis["action_description"],
        "reason": analysis["reason"],
        "generated_code": code,
        "llm_provider": _llm_config["provider"],
        "llm_model": _llm_config["model"],
        "decision": decision,
    }
    print(f"[tool_agent] Proposal created: '{analysis['tool_name']}' (id={request_id})")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/v1/health")
async def health():
    return {"status": "ok", "service": "tool_agent"}


@app.get("/v1/config")
async def get_config():
    """Return the current LLM config (without the API key)."""
    return {
        "provider": _llm_config["provider"],
        "model": _llm_config["model"],
        "configured": bool(_llm_config["api_key"]),
    }


@app.post("/v1/config")
async def set_config(config: LLMConfig):
    """Set the LLM provider, model, and API key used for rule analysis.

    The UI calls this automatically whenever the user saves their LLM settings.
    Supported providers: 'openai', 'anthropic', 'gemini'.
    """
    if os.getenv("ENVIRONMENT") == "production":
        raise HTTPException(
            status_code=403,
            detail="Runtime LLM config changes are disabled in production. Use environment variables.",
        )
    if config.provider not in ("openai", "anthropic", "gemini"):
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider {config.provider!r}. Must be 'openai', 'anthropic', or 'gemini'.",
        )
    _llm_config["provider"] = config.provider
    _llm_config["model"] = config.model
    _llm_config["api_key"] = config.api_key
    print(f"[tool_agent] LLM config updated: provider={config.provider}, model={config.model}")
    return {"provider": config.provider, "model": config.model, "configured": True}


@app.post("/v1/webhook/rule-created", status_code=202)
async def webhook_rule_created(payload: RuleCreatedPayload, background_tasks: BackgroundTasks):
    """Receive rule creation event from the Rule Engine."""
    background_tasks.add_task(_process_rule, payload)
    return {"accepted": True}


@app.get("/v1/proposals")
async def list_proposals():
    """List all tool proposals (pending, approved, and rejected)."""
    return list(_proposals.values())


@app.get("/v1/proposals/{proposal_id}")
async def get_proposal(proposal_id: str):
    """Get a specific proposal including the generated code."""
    p = _proposals.get(proposal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return p


@app.post("/v1/proposals/{proposal_id}/review")
async def review_proposal(proposal_id: str, decision: ReviewDecision):
    """Approve or reject a tool proposal.

    On approval, the generated code is appended to mcp_server/server.py.
    The MCP server must be restarted manually for the new tool to take effect.
    """
    p = _proposals.get(proposal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if p["status"] != "pending_review":
        raise HTTPException(status_code=409, detail=f"Proposal already {p['status']}")

    # Record decision in Decision Center for audit trail
    try:
        async with httpx.AsyncClient(base_url=DECISION_CENTER_URL, timeout=5.0, headers=internal_headers()) as dc:
            await dc.post(
                f"/v1/decide/{proposal_id}/approve",
                json={"approved": decision.approved, "approver": decision.reviewer},
            )
    except Exception as exc:
        print(f"[tool_agent] Warning: could not record DC decision: {exc}")

    if not decision.approved:
        p["status"] = "rejected"
        p["reviewer"] = decision.reviewer
        return {"status": "rejected", "proposal_id": proposal_id}

    # Validate generated code before writing
    code_ok, code_reason = _validate_generated_code(p["generated_code"])
    if not code_ok:
        raise HTTPException(status_code=400, detail=f"Generated code failed safety validation: {code_reason}")

    # Write the generated code to server.py
    try:
        with open(SERVER_PY_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n# --- Auto-generated tool: {p['tool_name']} ---\n")
            f.write(f"# Triggered by rule: {p['trigger_rule']} in group: {p['trigger_group']}\n")
            f.write(f"# Approved by: {decision.reviewer}\n")
            f.write(p["generated_code"])
    except OSError as exc:
        import logging
        logging.getLogger(__name__).exception("Failed to write generated tool code")
        raise HTTPException(status_code=500, detail="Failed to persist tool code")

    p["status"] = "approved"
    p["reviewer"] = decision.reviewer
    return {
        "status": "approved",
        "proposal_id": proposal_id,
        "tool_name": p["tool_name"],
        "message": (
            f"Tool '{p['tool_name']}' appended to server.py. "
            "Restart the MCP server for it to take effect."
        ),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8003)
