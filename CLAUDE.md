# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

Unreal Objects is accountability infrastructure for autonomous AI agents. It sits between an AI agent and the real world, evaluating every action against business rules before execution. The system decides to `APPROVE`, `REJECT`, or `ASK_FOR_APPROVAL` (human-in-the-loop) for each request.

## Commands

### Python Backend

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run services
uvicorn rule_engine.app:app --port 8001
uvicorn decision_center.app:app --port 8002
python mcp_server/server.py --transport sse --host 0.0.0.0 --port 8000

# Tests
pytest -v                                          # all tests
pytest rule_engine/tests/test_api.py -v            # single file
pytest decision_center/tests/test_evaluator.py -v  # evaluator unit tests
pytest tests/test_integration.py -v               # end-to-end (starts live servers)

# CLI wizard
python decision_center/cli.py
```

### React UI (`ui/`)

```bash
cd ui
npm install
npm run dev      # dev server (Vite)
npm run build    # production build
npm run lint     # ESLint
```

## Architecture

Three independent Python microservices communicate via HTTP. All state is **in-memory** (no database), so data resets on restart.

### Service Map

| Service | Port | Module | Purpose |
|---|---|---|---|
| Rule Engine | 8001 | `rule_engine/` | CRUD for rule groups and rules |
| Decision Center | 8002 | `decision_center/` | Evaluates requests against rules; audit log |
| MCP Server | 8000 | `mcp_server/` | MCP bridge for AI agents to call the above |

### Rule Evaluation Pipeline (`decision_center/evaluator.py`)

When an action is evaluated (`GET /v1/decide`):
1. The Decision Center fetches the rule group from the Rule Engine at `127.0.0.1:8001`.
2. For each rule, **edge cases are evaluated first** (they short-circuit if matched).
3. If no edge case matches, the main `rule_logic_json` (JSON Logic AST) is evaluated.
4. Strict fail-closed type checking: type mismatches or missing variables default to `ASK_FOR_APPROVAL` or `REJECT`. A missing `group_id` defaults to `APPROVE`.
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

### MCP Server (`mcp_server/server.py`)

Uses `FastMCP` and proxies calls to the Rule Engine and Decision Center. Supports both `stdio` (local Claude Desktop) and `sse` (SSE/HTTP for LAN agents) transports.

### React UI (`ui/`)

Vite + React + TypeScript + Tailwind CSS. Talks directly to Rule Engine (`:8001`) and Decision Center (`:8002`). Main components: `Sidebar` (group management), `ChatInterface` (LLM wizard for rule creation), `TestConsole` (action simulation).

## Key Design Decisions

- **Fuzzy variable mapping** (`evaluator.py:map_missing_variables`): Before JSON Logic evaluation, missing variables are resolved via substring and difflib fuzzy matching against available context keys. This tolerates minor naming inconsistencies between rule definitions and agent context payloads.
- **Fail-closed**: All evaluation errors (type mismatch, unreachable Rule Engine, missing data) produce a restrictive outcome, never a silent `APPROVE`.
- **Dual rule format**: Every rule stores both a human-readable string and a JSON Logic AST. The string is used for CLI display and legacy fallback; the AST is authoritative for evaluation.
- **Schema enforcement**: The CLI and UI both support optionally loading a JSON schema from `schemas/` (ecommerce or finance blueprints) to constrain variable names the LLM may use when generating rules.
