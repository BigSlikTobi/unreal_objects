# Changelog — 2026-04-13

## Summary
Resolved pre-existing test and linting failures, addressed Copilot PR review feedback on socket hygiene and code cleanliness, and fixed nginx proxy routing for the combined Railway backend deployment. All changes merged to main as PR #41.

## Changes

### Test Fixes
- Fixed 5 eval test errors in `evals/agent_eval/tests/test_runner.py` — updated fixture references from `dc_store.atomic_logs` / `.chains` / `.pending` to `dc_store.data.atomic_logs` / `.data.chains` / `.data.pending` after `DecisionStore` was refactored to use a nested `DecisionStoreData` model

### ESLint Fixes
- Fixed 2 ESLint `react-refresh/only-export-components` errors in `ChatInterface.tsx` by extracting `replaceVariableToken`, `swapVariableInResult`, and `swapVarInJsonLogic` into a dedicated `ui/src/utils/variableSwap.ts` utility module
- Updated `ChatInterface.test.tsx` import to pull from the new utility path

### Copilot PR Review Feedback (db4921e)
- Added `close_http_client()` method to `decision_center/evaluator.py` and wired it into the Decision Center FastAPI lifespan context manager to prevent socket leaks on shutdown
- Removed `httpx.HTTPStatusError` from the `_notify_tool_agent` exception catch in `mcp_server/tool_agent.py` — that exception is never raised without an explicit `raise_for_status()` call
- Removed unused `import os` from `shared/combined_app.py`
- Updated install instructions in `CLAUDE.md` and `AGENTS.md` from `.[dev]` to `.[all,dev]` to reflect the dependency-group split introduced in the code-excellence session

### Nginx Combined Backend Routing Fix (3f0824e)
- Changed nginx rewrite rule from `^/api/rule-engine/(.*)` to `^/api/(.*)` in `docker/ui-nginx.conf` so that the combined backend's `/rule-engine/` and `/decision-center/` mount prefixes are preserved in the proxied request
- Fixed Railway upstream environment variable values: corrected protocol (`https` → `http`), port (`:8080`, not `:8001`), and path handling for the combined backend deployment

### Railway Infrastructure
- Migrated 3 rule groups (7 rules, 13 datapoint definitions) from the old standalone Rule Engine service to the combined backend via API export/import
- Old standalone `rule_engine` and `decision_center` Railway services and their associated volumes can now be safely deleted

## Files Modified
- `evals/agent_eval/tests/test_runner.py` — updated 5 fixture attribute paths for `DecisionStoreData` refactor
- `ui/src/components/ChatInterface.tsx` — removed inline swap utilities (extracted to util module)
- `ui/src/components/ChatInterface.test.tsx` — updated import path
- `ui/src/utils/variableSwap.ts` — new file: extracted variable-swap utility functions
- `decision_center/evaluator.py` — added `close_http_client()` for clean shutdown
- `decision_center/app.py` — wired `close_http_client()` into FastAPI lifespan
- `mcp_server/tool_agent.py` — removed incorrect `HTTPStatusError` catch clause
- `shared/combined_app.py` — removed unused `import os`
- `CLAUDE.md` — updated install command to `.[all,dev]`
- `AGENTS.md` — updated install command to `.[all,dev]`
- `docker/ui-nginx.conf` — fixed rewrite rule to preserve backend mount path prefixes

## Code Quality Notes
- **Tests**: 310 passed, 0 errors, 0 failures (`pytest -v`, excluding integration tests)
  - This resolves the 5 pre-existing `test_runner.py` errors from the previous session
- **ESLint**: 0 errors, 2 warnings
  - 2 warnings in `AgentAdminPanel.tsx` (`react-hooks/exhaustive-deps`) — pre-existing, not introduced today
  - The 2 `ChatInterface.tsx` fast-refresh errors from the previous session are now resolved

## Open Items / Carry-over
- `AgentAdminPanel.tsx` has 2 pre-existing `react-hooks/exhaustive-deps` warnings — low priority, no behavioural impact
- Integration test suite (`tests/test_integration.py`) requires live services running — not run in this session
- Old Railway services (`rule_engine`, `decision_center`) and their volumes still need manual deletion from the Railway dashboard
