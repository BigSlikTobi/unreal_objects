# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## What This Project Does

Unreal Objects is accountability infrastructure for autonomous AI agents. It sits between an AI agent and the real world, evaluating every action against business rules before execution. The system decides to `APPROVE`, `REJECT`, or `ASK_FOR_APPROVAL` (human-in-the-loop) for each request.

## Commands

Requires **Python 3.11+** and **Node.js 18+**. Procedural commands are available as skills:

| Skill | Purpose |
|---|---|
| `/setup` | Create venv and install dependencies |
| `/start-backend` | Start Rule Engine + Decision Center + MCP Server |
| `/start-company` | Start the Living Virtual Company server |
| `/test` | Run tests (accepts target: `all`, `integration`, `evaluator`, `api`, `mcp`, `company`) |
| `/eval` | Run agent eval scenarios |
| `/ui` | UI dev server, build, or lint |

CLI entry points (installed via `pip install -e ".[dev]"`): `uo-stress-test`, `uo-agent-admin`, `uo-agent-eval`, `uo-company-server`. CLI wizard: `python decision_center/cli.py`.

## Architecture

Python microservices communicate via HTTP. The Rule Engine has optional file-based persistence (`RULE_ENGINE_PERSISTENCE_PATH`, defaults to `data/rule_engine_store.json` when started via the stack script). The Decision Center is **in-memory only** — its state resets on restart.

### Service Map

| Service | Port | Module | Purpose |
|---|---|---|---|
| Rule Engine | 8001 | `rule_engine/` | CRUD for rule groups and rules |
| Decision Center | 8002 | `decision_center/` | Evaluates requests against rules; audit log |
| MCP Server | 8000 | `mcp_server/` | MCP bridge for AI agents to call the above |
| Tool Creation Agent | 8003 | `mcp_server/tool_agent.py` | LLM agent that proposes new guarded_ tools when rules require them (started separately, not part of the stack script) |

### Rule Evaluation Pipeline (`decision_center/evaluator.py`)

When an action is evaluated (`GET /v1/decide` or `POST /v1/decide`):
1. The Decision Center fetches the rule group from the Rule Engine at `127.0.0.1:8001`.
2. For each rule, **edge cases are evaluated first** (they short-circuit if matched).
3. If no edge case matches, the main `rule_logic_json` (JSON Logic AST) is evaluated.
4. Strict fail-closed type checking: type mismatches or missing variables always default to `ASK_FOR_APPROVAL` (regardless of the rule's own outcome). A missing `group_id` defaults to `APPROVE`. String booleans (`"true"`/`"false"`) and string numbers (`"600"`) are coerced to native types before evaluation; un-coerceable mismatches escalate to `ASK_FOR_APPROVAL`.
5. Outcome precedence: `REJECT` > `ASK_FOR_APPROVAL` > `APPROVE` (most restrictive wins).
6. All decisions are written to two audit logs: atomic log (flat entries) and decision chains (event sequences per request).

### Rule Data Model (`rule_engine/models.py`)

Rules have both a human-readable string (`rule_logic`: `IF amount > 500 THEN ASK_FOR_APPROVAL`) and a [JSON Logic](http://jsonlogic.com/) AST (`rule_logic_json`). Edge cases follow the same dual-format pattern. The JSON Logic form is what actually drives evaluation; the string form is for display and legacy fallback.

### LLM Translation (`decision_center/translator.py`)

Natural language rules are translated to `RuleLogicDefinition` (Pydantic) via three providers:
- **OpenAI**: JSON mode response format
- **Anthropic**: Tool use / forced tool call (`submit_rule`)
- **Gemini**: Structured output with `response_schema`

The system prompt instructs the LLM to emit both human-readable and JSON Logic formats. Translation is called either from the CLI (`decision_center/cli.py`) or via `POST /v1/llm/translate` on the Decision Center API.
If a provider omits `datapoints` but still returns usable JSON Logic, the translator derives datapoints from referenced `{"var": ...}` expressions so the downstream configuration flow never receives an empty extracted-datapoints list for variable-based rules.

### MCP Server (`mcp_server/server.py`)

Uses `FastMCP` and proxies calls to the Rule Engine and Decision Center. Supports `stdio` (local Claude Desktop) and `streamable-http` (HTTP for LAN agents) transports. Optional `--auth-enabled` flag enables agent authentication with API key enrollment and per-agent audit identity.

### Schema Management API (`decision_center/schema_generator.py`, `decision_center/app.py`)

- `GET /v1/schemas`: lists all `.json` files under `schemas/`, returning `{key, name, description, schema}` per entry.
- `POST /v1/schemas/save`: persists a `SchemaProposal` as JSON. Requires `overwrite: true` to replace an existing file; returns HTTP 409 (`SchemaExistsError`) otherwise. Optionally protected by `ADMIN_API_KEY` env var (checked via `X-Admin-Key` header); if the env var is unset, the endpoint is open (dev mode).

### React UI (`ui/`)

Vite + React + TypeScript + Tailwind CSS. Talks directly to Rule Engine (`:8001`) and Decision Center (`:8002`). Main components: `Sidebar` (group management), `ChatInterface` (LLM wizard for rule creation), `TestConsole` (action simulation), `DecisionLog` (audit trail viewer with expandable chain timelines).

The `ChatInterface` schema dropdown is dynamically populated from `GET /v1/schemas` on mount (previously a hardcoded constant). `AgentAdminPanel` includes an MCP config snippet generator with tabs for Claude Desktop (HTTP/stdio), Cursor/Windsurf, and Generic clients, plus copy-to-clipboard.

## Key Design Decisions

- **Fuzzy variable mapping** (`evaluator.py:map_missing_variables`): Before JSON Logic evaluation, missing variables are resolved via substring containment and difflib fuzzy matching against available context keys. To prevent false positives on shared generic suffixes (`_score`, `_amount`, `_days`, etc.), multi-part variable names must share at least one non-generic semantic part. Single-part names (e.g., `amount`) bypass this filter. The difflib cutoff is 0.7.
- **Fail-closed**: All evaluation errors (type mismatch, unreachable Rule Engine, missing data) produce `ASK_FOR_APPROVAL`, never a silent `APPROVE` or an inherited `REJECT`. This is uniform across both the legacy string-parsing path and the JSON Logic path. Before failing closed, the evaluator attempts safe type coercion: `_coerce_bool_strings` converts `"true"`/`"false"` strings to booleans, and `_coerce_pair` converts string-number mismatches at the operator level.
- **Dual rule format**: Every rule stores both a human-readable string and a JSON Logic AST. The string is used for CLI display and legacy fallback; the AST is authoritative for evaluation.
- **Schema enforcement**: The CLI and UI both support optionally loading a JSON schema from `schemas/` (ecommerce or finance blueprints) to constrain variable names the LLM may use when generating rules.
- **Schema-constrained translation**: When a schema is provided, translator prompts explicitly forbid pseudo-datapoints such as `exists`, `missing`, or helper field-presence flags. Built-in blueprints should cover common delivery/shipping and transfer/beneficiary concepts so the model can stay inside the approved vocabulary.
- **No-schema translation steering**: Even without a schema, translator prompts still forbid pseudo-datapoints and should prefer reusing known group datapoint names when they fit the rule. No-schema mode stays flexible, but it should not surface explanation words as business fields.
- **Semantic concept validation** (`_validate_candidate_alignment`): Post-translation guard that scores every LLM-chosen variable against the original rule text using word-overlap heuristics. If a variable scores below 50% of the best available field's score, the translation is rejected with a `SchemaConceptMismatchError` carrying a `proposed_field` suggestion. Prevents semantically wrong mappings like `account_age_days` when `delivery_time_days` is the correct match.
- **Schema extension flow**: When translation fails due to missing schema concepts, both UI and CLI offer an inline escape hatch: add the missing field with a suggested name (from `proposed_field`) and type, then retry immediately. The UI stores extensions in `schemaExtensions` state; the CLI merges them into `context_schema`. Extensions persist for the session so future translations can reference them.
- **Interactive datapoint swapping** (`swap_variable_in_result`): After translation, users can replace any extracted datapoint via UI dropdown (clickable badges with ranked schema fields) or CLI prompt (numbered datapoint list → ranked candidates). The swap utility recursively updates `datapoints`, `rule_logic`, `rule_logic_json`, `edge_cases`, and `edge_cases_json` to keep the translation internally consistent.
