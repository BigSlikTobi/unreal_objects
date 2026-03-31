# Railway Deployment Setup

This guide covers deploying Unreal Objects to Railway as a submodule of `unreal_objects_inc`.

## Architecture on Railway

Each service runs as a separate Railway service within one project. They communicate over Railway's private network.

| Service | Start Command | Port |
|---------|--------------|------|
| Rule Engine | `uvicorn rule_engine.app:app --host 0.0.0.0 --port $PORT` | 8001 |
| Decision Center | `uvicorn decision_center.app:app --host 0.0.0.0 --port $PORT` | 8002 |
| MCP Server | `python mcp_server/server.py --transport streamable-http --host 0.0.0.0 --port $PORT --auth-enabled --admin-api-key $MCP_ADMIN_API_KEY` | 8000 |
| Tool Agent | `uvicorn mcp_server.tool_agent:app --host 0.0.0.0 --port $PORT` | 8003 |
| Company Server | `uvicorn company_server.app:app --host 0.0.0.0 --port $PORT` | 8010 |
| UI | `npm run build` (static deploy from `ui/`) | - |

Railway assigns `$PORT` dynamically. Always use `--port $PORT` in start commands.

## Generate Secrets

Run this locally to generate all required secrets at once:

```bash
python3 -c "import secrets; [print(f'{n}={secrets.token_urlsafe(32)}') for n in ['INTERNAL_API_KEY','RULE_ENGINE_ADMIN_TOKEN','MCP_ADMIN_API_KEY']]"
```

Copy the output and paste the values into Railway's variable settings.

## Environment Variables

### Shared (set on ALL services)

| Variable | Required | Description |
|----------|----------|-------------|
| `ENVIRONMENT` | Yes | Set to `production`. Activates auth enforcement, rate limiting, and blocks runtime LLM config changes. |
| `INTERNAL_API_KEY` | Yes | Shared secret for service-to-service auth. **Must be the same value on every service.** Requests between services automatically include this in the `X-Internal-Key` header. |
| `ALLOWED_ORIGINS` | Yes | Comma-separated list of allowed CORS origins. Set to your UI domain, e.g. `https://your-ui.railway.app`. |

### Service Discovery

Each service needs to know the internal URLs of the services it calls. Railway's private networking uses the format `http://<service-name>.railway.internal`.

**On MCP Server:**
```
RULE_ENGINE_URL=http://rule-engine.railway.internal:8001
DECISION_CENTER_URL=http://decision-center.railway.internal:8002
```

**On Tool Agent:**
```
RULE_ENGINE_URL=http://rule-engine.railway.internal:8001
DECISION_CENTER_URL=http://decision-center.railway.internal:8002
```

**On Decision Center:**
```
RULE_ENGINE_URL=http://rule-engine.railway.internal:8001
```

**On Rule Engine:**
```
TOOL_AGENT_URL=http://tool-agent.railway.internal:8003
```

**On Company Server:**
```
COMPANY_RULE_ENGINE_URL=http://rule-engine.railway.internal:8001
COMPANY_DECISION_CENTER_URL=http://decision-center.railway.internal:8002
```

Replace `rule-engine`, `decision-center`, etc. with the actual service names you create in Railway.

### Service-Specific Variables

**Rule Engine:**

| Variable | Required | Description |
|----------|----------|-------------|
| `RULE_ENGINE_ADMIN_TOKEN` | Yes (prod) | Token required for DELETE operations. Without it, the service returns 503 on destructive actions in production. |
| `RULE_ENGINE_PERSISTENCE_PATH` | No | Path to JSON store file. Defaults to `./data/rule_engine_store.json`. Mount a Railway volume and point this to the mounted path if rules should survive redeploys. |

**MCP Server:**

| Variable | Required | Description |
|----------|----------|-------------|
| `MCP_ADMIN_API_KEY` | Yes | Admin key for agent enrollment and management. Passed via `--admin-api-key` CLI arg in the start command. |
| `MCP_AUTH_PERSISTENCE_PATH` | No | Path to the JSON auth store. Mount a Railway volume and point this to the mounted path if agent registrations and credentials should survive redeploys. |

**Decision Center:**

| Variable | Required | Description |
|----------|----------|-------------|
| `DECISION_CENTER_PERSISTENCE_PATH` | No | Path to the JSON decision store for atomic logs, chains, and pending approvals. Mount a Railway volume and point this to the mounted path if approvals should survive redeploys. |

**Decision Center + Tool Agent (LLM access):**

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | One of three | For OpenAI-based rule translation and tool analysis. |
| `ANTHROPIC_API_KEY` | One of three | For Anthropic-based rule translation and tool analysis. |
| `GOOGLE_API_KEY` | One of three | For Gemini-based rule translation and tool analysis. |
| `GPT_MODEL` | No | Override the default model. Defaults to `gpt-4o-mini` (OpenAI) or equivalent per provider. |

At least one LLM API key is needed for rule translation and tool agent analysis to work.

**UI (build-time variables):**

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_RULE_ENGINE_BASE_URL` | Yes | Public URL of the Rule Engine, e.g. `https://rule-engine.railway.app` |
| `VITE_DECISION_CENTER_BASE_URL` | Yes | Public URL of the Decision Center |
| `VITE_TOOL_AGENT_BASE_URL` | Yes | Public URL of the Tool Agent |

These are baked into the UI at build time (Vite replaces `import.meta.env.VITE_*`).

## How Auth Works

### Service-to-Service (automatic)

All services share `INTERNAL_API_KEY`. When one service calls another (e.g., MCP Server calls Rule Engine), the `X-Internal-Key` header is sent automatically. No code changes needed.

- GET requests and health endpoints are always open (no auth needed).
- POST, PUT, PATCH, DELETE requests require the header.
- If the header is missing or wrong, the service returns `401 Unauthorized`.

### MCP Agent Auth (for external bots)

The MCP Server has its own OAuth2-based auth for external AI agents:

1. Admin creates an agent: `POST /v1/admin/agents` with `X-Admin-Key: <MCP_ADMIN_API_KEY>`
2. Admin issues an enrollment token for the agent
3. Agent exchanges the token for `client_id` + `client_secret`
4. Agent exchanges credentials for a Bearer token
5. Agent uses the Bearer token on MCP tool calls

Use `uo-agent-admin` CLI or the Agent Admin Panel in the UI to manage agents.

### Rule Engine Admin Token

`RULE_ENGINE_ADMIN_TOKEN` protects DELETE endpoints only. Send it via `X-Admin-Token` header when deleting rule groups or rules. The Company Server and other internal services that call delete endpoints should have this token configured if they perform deletions.

## Security Features Active in Production

When `ENVIRONMENT=production`:

| Feature | What it does |
|---------|-------------|
| Internal API key enforcement | All mutating requests between services require `X-Internal-Key` |
| Admin token enforcement | DELETE on Rule Engine requires `RULE_ENGINE_ADMIN_TOKEN` or returns 503 |
| CORS restrictions | Only origins in `ALLOWED_ORIGINS` are accepted |
| Rate limiting | `/v1/decide` (60/min), `/v1/llm/translate` (10/min), `/v1/llm/schema` (10/min) |
| LLM config lockdown | `POST /v1/config` on Tool Agent is rejected (LLM keys must come from env vars) |
| Prompt injection defense | User input in LLM prompts is wrapped in XML delimiters |
| Error sanitization | Internal errors return generic messages, not stack traces |
| Code injection guard | LLM-generated tool code is AST-validated before persisting |
| Input validation | group_id, request_id, and approver fields are validated |

None of these activate in local development (without `ENVIRONMENT=production`), so your dev workflow is unchanged.

## Health Checks

Configure Railway health checks for each service:

| Service | Health Endpoint |
|---------|----------------|
| Rule Engine | `/v1/health` |
| Decision Center | `/v1/health` |
| MCP Server | (use TCP check on port) |
| Tool Agent | `/v1/health` |
| Company Server | `/health` |

## Important Notes

### Persistent Volumes for Stateful Services

Railway containers are ephemeral, so JSON persistence only survives redeploys if
you mount a Railway volume and store the files there. Recommended volume-backed
paths:

- `RULE_ENGINE_PERSISTENCE_PATH=/app/data/rule_engine_store.json`
- `DECISION_CENTER_PERSISTENCE_PATH=/app/data/decision_center_store.json`
- `MCP_AUTH_PERSISTENCE_PATH=/app/data/mcp_auth_store.json`

With those paths backed by volumes:
- Rule Engine keeps rules and datapoints across redeploys
- Decision Center keeps decision logs and pending approvals across redeploys
- MCP Server keeps agent registrations, enrollment tokens, and credentials across redeploys

Still ephemeral after restart:
- issued bearer access tokens
- active in-flight MCP HTTP connections

For higher-scale production durability, consider replacing JSON-on-volume with PostgreSQL in a future iteration.

### Tool Agent Limitations

The Tool Agent writes generated code to `server.py` on disk. On Railway's ephemeral filesystem, these changes are lost on redeploy. This means auto-generated MCP tools won't persist across deployments. For now, manually add approved tool code to the codebase and commit it.

### Submodule Setup

Since `unreal_objects` is a submodule of `unreal_objects_inc`:
- Railway should be configured to clone recursively (include submodules)
- Environment variables are set at the Railway project level, not in the submodule
- The `.env` file is gitignored and never committed
