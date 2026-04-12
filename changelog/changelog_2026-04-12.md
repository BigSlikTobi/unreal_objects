# Changelog — 2026-04-12

## Summary

Major code-excellence and cost-optimization day: 10 targeted correctness fixes (UTC timestamps, context mutation, HTTP method, path validation, exception handling, httpx client reuse, type coercion, Literal types, health check, async context manager), bounded in-memory growth in DecisionStore and CompanyState, concurrent dict-access safety in the company server, non-blocking LLM translation, and a Railway cost-reduction workstream (lazy SDK imports, per-service dep groups, slimmed Dockerfiles, combined backend process). A new `code-excellence` reusable agent was also added to `.claude/agents/`.

## Changes

### Code Excellence Fixes

- **UTC-aware timestamps**: Replaced `datetime.now()` with `datetime.now(timezone.utc)` in `rule_engine/models.py` and `decision_center/models.py` to avoid naive datetimes drifting at DST boundaries
- **Context mutation bug fixed** (`decision_center/evaluator.py`): `evaluate_rule` now shallow-copies `context` before fuzzy variable mapping so cross-rule pollution is eliminated
- **UI test console switched to POST** (`ui/src/api.ts`): `executeTest` now sends `POST /v1/decide` instead of GET, preventing context values from leaking into URLs/logs
- **Path parameter validation** (`rule_engine/app.py`): all endpoints that accept a rule or group ID now validate the parameter before use, returning 404 with a clear message for unknown IDs
- **`_notify_tool_agent` exception handling narrowed** (`mcp_server/tool_agent.py`): catches specific exceptions instead of bare `except`; adds debug logging on failure
- **Reusable `httpx.AsyncClient` in evaluator** (`decision_center/evaluator.py`): client is created once at module level instead of per-request, reducing overhead and connection churn
- **`_coerce_numeric_strings` pre-evaluation pass** (`decision_center/evaluator.py`): uniform numeric string coercion pass runs before JSON Logic evaluation, complementing the existing bool-string coercion
- **`DatapointDefinition.type` narrowed to `Literal`** (`decision_center/models.py`): field type changed from `str` to `Literal["text","number","boolean","enum"]`, enabling static validation
- **Anthropic health check replaced** (`decision_center/translator.py`): billable `messages.create` probe replaced with the free `models.list()` call
- **`principal_context` made async** (`mcp_server/auth.py` and `mcp_server/server.py`): sync context manager converted to async to avoid blocking the event loop

### Reliability Fixes

- **Bounded in-memory growth** (`decision_center/store.py`, `company_server/state.py`):
  - `DecisionStore` now enforces configurable FIFO eviction: `MAX_ATOMIC_LOGS` (env, default 10000) and `MAX_CHAINS` (env, default 5000)
  - `CompanyState` enforces `max_cases=5000`; when the cap is hit, resolved cases are evicted first
- **Company server concurrent dict-access safety** (`company_server/app.py`, `company_server/webhooks.py`): all sync `def` route handlers converted to `async def` so they share the event loop with the background scheduler, preventing dict mutation races

### Performance / Async

- **Non-blocking LLM translation** (`decision_center/translator.py`, `decision_center/app.py`): added `translate_rule_async` and `check_llm_connection_async` wrappers using `asyncio.to_thread()`; Decision Center endpoints now `await` these wrappers instead of calling blocking sync functions directly

### Railway Cost Optimization (~30-45% projected cost reduction)

- **Lazy LLM SDK imports** (`decision_center/translator.py`): `openai`, `anthropic`, and `google-genai` are imported inside provider-specific branches; saves ~47 MB RSS at startup when only one provider is used
- **Dropped `mcp[cli]` extra** (`pyproject.toml`): removes unused CLI dependencies from the MCP server install
- **Per-service dependency groups** (`pyproject.toml`): added `rule-engine`, `decision-center`, `mcp-server`, `tool-agent`, and `all` optional groups so each Docker image installs only its required packages
- **Slimmed Dockerfiles** (`docker/*.Dockerfile`): each service Dockerfile now copies only its own source directory and installs only its dependency group
- **Combined backend** (`shared/combined_app.py`, `docker/combined_backend.Dockerfile`): new `combined_app.py` mounts Rule Engine + Decision Center as sub-apps in one Uvicorn process; `use_local_rule_store()` in the evaluator enables direct store access without HTTP in combined mode; combined Dockerfile provided for single-dyno deployment
- **Deployment docs updated** (`docs/deployment-railway.md`): added resource limit recommendations and combined vs. separate architecture decision guide

### Tooling

- **`code-excellence` agent** (`.claude/agents/code-excellence.md`): reusable sub-agent that audits the codebase, outputs prioritized findings, and creates GitHub issues for selected items
- **CLAUDE.md commands section refactored**: replaced inline bash blocks with a skill-reference table; updated architecture notes to reflect async decisions endpoint and per-service dep groups

## Files Modified

- `.claude/agents/code-excellence.md` — new file; reusable code-excellence audit agent
- `CLAUDE.md` — commands section replaced with skill table; architecture notes updated
- `company_server/app.py` — sync endpoints converted to async
- `company_server/config.py` — `max_cases` config field added
- `company_server/state.py` — FIFO eviction cap on `SupportCase` collection
- `company_server/webhooks.py` — async conversion
- `decision_center/app.py` — LLM endpoints now await async translation wrappers
- `decision_center/evaluator.py` — context copy fix, reusable httpx client, `_coerce_numeric_strings`, `use_local_rule_store()`
- `decision_center/models.py` — `DatapointDefinition.type` narrowed to `Literal`; UTC timestamps
- `decision_center/store.py` — `MAX_ATOMIC_LOGS` / `MAX_CHAINS` FIFO eviction
- `decision_center/tests/test_translator.py` — test updated for new async translator API
- `decision_center/translator.py` — lazy imports, `translate_rule_async`, `check_llm_connection_async`, health check fix
- `docker/combined_backend.Dockerfile` — new file; single-process combined backend image
- `docker/decision_center.Dockerfile` — slimmed to decision-center dep group
- `docker/mcp.Dockerfile` — slimmed to mcp-server dep group
- `docker/rule_engine.Dockerfile` — slimmed to rule-engine dep group
- `docker/tool_agent.Dockerfile` — slimmed to tool-agent dep group
- `docs/deployment-railway.md` — cost optimization guide and combined architecture docs
- `mcp_server/auth.py` — `principal_context` converted to async context manager
- `mcp_server/server.py` — awaits async `principal_context`
- `mcp_server/tests/test_tools.py` — updated for async auth changes
- `mcp_server/tool_agent.py` — narrowed exception handling + debug logging
- `pyproject.toml` — per-service dep groups, dropped `mcp[cli]`
- `rule_engine/app.py` — path parameter validation on all ID endpoints
- `rule_engine/models.py` — UTC-aware timestamps
- `shared/combined_app.py` — new file; combined Rule Engine + Decision Center ASGI app
- `ui/src/api.ts` — `executeTest` switched from GET to POST

## Code Quality Notes

- **Tests**: 306 passed, 5 errors in `evals/agent_eval/tests/test_runner.py`
  - Errors are due to `dc_store.atomic_logs.clear()` — the test fixture accesses the attribute directly on `DecisionStore`, but after today's refactor, data lives at `dc_store.data.atomic_logs`. The tests did not ship with the store refactor. **Carry-over: update `test_runner.py` fixture to use `dc_store.data.atomic_logs.clear()` and `dc_store.data.chains.clear()`.**
- **UI Linting**: 2 errors + 2 warnings (pre-existing, not introduced today)
  - `ChatInterface.tsx`: 2 `react-refresh/only-export-components` errors (exported constants alongside components)
  - `AgentAdminPanel.tsx`: 2 `react-hooks/exhaustive-deps` warnings (missing hook dependencies)

## Open Items / Carry-over

- **`evals/agent_eval/tests/test_runner.py` fixture** — update `dc_store.atomic_logs.clear()` → `dc_store.data.atomic_logs.clear()` (and same for `chains`, `pending`) to fix 5 test errors introduced by the `DecisionStore` refactor
- **UI lint errors** — `ChatInterface.tsx` fast-refresh errors need exported constants moved to a separate file
- **Rule Engine volume mount bug** — trailing space in Railway mount path (`/app/data `) causes rules to write to ephemeral disk; rules are wiped on redeploy
- **`refresh_mcp_token.service` unit type** — `Type=oneshot` but script loops forever; should be `Type=simple` with `Restart=on-failure`
- **Decision Center in-memory** — audit log + pending approvals reset on every Railway redeploy; export via `GET /v1/logs/export` before any deploy
- **Schema files ephemeral** — `schemas/*.json` saved in UI vanish on redeploy unless committed to git
