# Railway Deployment Setup

This guide covers deploying Unreal Objects to Railway as a submodule of `unreal_objects_inc`.

## Architecture on Railway

Services can be deployed separately or combined. The **combined backend** (recommended for cost optimization) runs Rule Engine + Decision Center in a single process, eliminating one container and replacing internal HTTP calls with direct function calls.

### Option A: Combined Backend (recommended)

| Service | Dockerfile | Runtime Port |
|---------|------------|--------------|
| Combined Backend | `docker/combined_backend.Dockerfile` | 8001 |
| MCP Server | `docker/mcp.Dockerfile` | 8000 |
| Tool Agent | `docker/tool_agent.Dockerfile` | 8003 |
| UI | `docker/ui.Dockerfile` | `$PORT` |

The combined backend mounts Rule Engine at `/rule-engine/v1/...` and Decision Center at `/decision-center/v1/...`. Update `RULE_ENGINE_URL` and `DECISION_CENTER_URL` on other services accordingly (e.g., `http://combined-backend.railway.internal:8001/rule-engine` and `http://combined-backend.railway.internal:8001/decision-center`).

### Option B: Separate Services

| Service | Dockerfile | Runtime Port |
|---------|------------|--------------|
| Rule Engine | `docker/rule_engine.Dockerfile` | 8001 |
| Decision Center | `docker/decision_center.Dockerfile` | 8002 |
| MCP Server | `docker/mcp.Dockerfile` | 8000 |
| Tool Agent | `docker/tool_agent.Dockerfile` | 8003 |
| UI | `docker/ui.Dockerfile` | `$PORT` |

Railway assigns `$PORT` dynamically. The backend Dockerfiles honor it in their container commands, and the UI Dockerfile renders the Nginx config at startup so it listens on `$PORT` as well.

## Build Configuration

Use Dockerfile deployments for the Unreal Objects services instead of Railway's inferred build/start command flow.

### Combined Backend

| Service | Root Directory | Dockerfile Path | Watch Paths |
|---------|----------------|-----------------|------------|
| Combined Backend | `/` | `docker/combined_backend.Dockerfile` | `/rule_engine/**`, `/decision_center/**`, `/shared/**`, `/schemas/**`, `/pyproject.toml`, `/docker/combined_backend.Dockerfile` |
| MCP Server | `/` | `docker/mcp.Dockerfile` | `/mcp_server/**`, `/shared/**`, `/pyproject.toml`, `/docker/mcp.Dockerfile` |
| Tool Agent | `/` | `docker/tool_agent.Dockerfile` | `/mcp_server/**`, `/shared/**`, `/pyproject.toml`, `/docker/tool_agent.Dockerfile` |
| UI | `/` | `docker/ui.Dockerfile` | `/ui/**`, `/docker/ui.Dockerfile`, `/docker/ui-nginx.conf` |

### Separate Services

| Service | Root Directory | Dockerfile Path | Watch Paths |
|---------|----------------|-----------------|------------|
| Rule Engine | `/` | `docker/rule_engine.Dockerfile` | `/rule_engine/**`, `/shared/**`, `/pyproject.toml`, `/docker/rule_engine.Dockerfile` |
| Decision Center | `/` | `docker/decision_center.Dockerfile` | `/decision_center/**`, `/shared/**`, `/schemas/**`, `/pyproject.toml`, `/docker/decision_center.Dockerfile` |
| MCP Server | `/` | `docker/mcp.Dockerfile` | `/mcp_server/**`, `/shared/**`, `/pyproject.toml`, `/docker/mcp.Dockerfile` |
| Tool Agent | `/` | `docker/tool_agent.Dockerfile` | `/mcp_server/**`, `/shared/**`, `/pyproject.toml`, `/docker/tool_agent.Dockerfile` |
| UI | `/` | `docker/ui.Dockerfile` | `/ui/**`, `/docker/ui.Dockerfile`, `/docker/ui-nginx.conf` |

If you still deploy `company_server` from this repo, keep the current start-command setup for now or add a dedicated Dockerfile for it later.

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

The Decision Center keeps atomic logs, decision chains, and pending approvals **in process memory only** — no env var, no volume. Logs reset on every redeploy. Use `GET /v1/logs/export` (or the "Download JSON" button in the UI Decision Log panel, or option 3 in the `decision_center/cli.py` wizard) to capture a snapshot before redeploying.

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
| `VITE_RULE_ENGINE_BASE_URL` | Yes | Use the same-origin proxy path: `/api/rule-engine` |
| `VITE_DECISION_CENTER_BASE_URL` | Yes | Use the same-origin proxy path: `/api/decision-center` |
| `VITE_TOOL_AGENT_BASE_URL` | No | Optional. If you deploy Tool Agent, prefer `/api/tool-agent`; otherwise omit it. |

These are baked into the UI at build time (Vite replaces `import.meta.env.VITE_*`). In production, point the UI at the nginx proxy paths above so browser requests stay same-origin.

**UI (runtime env vars for nginx proxy):**

| Variable | Required | Description |
|----------|----------|-------------|
| `RULE_ENGINE_UPSTREAM` | Yes | Private Railway URL of the Rule Engine including `/v1`, e.g. `http://ruleengine.railway.internal:8080/v1` |
| `DECISION_CENTER_UPSTREAM` | Yes | Private Railway URL of the Decision Center including `/v1`, e.g. `http://decisioncenter.railway.internal:8080/v1` |
| `INTERNAL_API_KEY` | Yes | Same internal service key used by the backend services. nginx forwards it as `X-Internal-Key` for browser-originated writes. |

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

## Resource Limits (Cost Optimization)

Railway bills for allocated CPU and memory. Without explicit limits, containers may be over-provisioned. Set these per-service in the Railway dashboard under **Settings → Resources**:

| Service | CPU Limit | Memory Limit | Notes |
|---------|-----------|--------------|-------|
| Rule Engine | 0.25 vCPU | 128 MB | Lightweight CRUD store |
| Decision Center | 0.25 vCPU | 256 MB | Higher memory for LLM SDK imports (lazy-loaded) |
| MCP Server | 0.25 vCPU | 192 MB | Proxies to other services; long-lived SSE connections |
| Tool Agent | 0.25 vCPU | 256 MB | Only active during rule creation; consider removing if unused |
| UI (nginx) | 0.125 vCPU | 64 MB | Static file serving only |

These limits match observed usage (near-zero CPU, 75-300 MB memory per service). Adjust upward if you see OOM restarts.

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
- `MCP_AUTH_PERSISTENCE_PATH=/app/data/mcp_auth_store.json`

With those paths backed by volumes:
- Rule Engine keeps rules and datapoints across redeploys
- MCP Server keeps agent registrations, enrollment tokens, and credentials across redeploys

The **Decision Center does not use a volume**. Atomic logs, decision chains, and pending approvals live in process memory and reset on every redeploy. Capture them on demand via `GET /v1/logs/export`, the "Download JSON" button in the UI Decision Log, or option 3 of the `decision_center/cli.py` wizard.

Still ephemeral after restart:
- the entire Decision Center audit log and pending approvals queue
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
