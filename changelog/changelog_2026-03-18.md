# Changelog — 2026-03-18

## Summary
Three areas of improvement to the feat/ai-schema-creator branch: evaluator type coercion hardening (string→bool, string→number with uniform fail-closed behavior), a schema management API with conflict detection and optional admin auth, and an MCP config snippet UI in AgentAdminPanel. Also fixed the stale conversation history bug in SchemaWorkshop.

## Changes

### Evaluator: type coercion hardening (`decision_center/evaluator.py`)
- Added `_coerce_bool_strings(context)`: mutates context in-place before JSON Logic evaluation, converting `"true"`/`"false"` strings to real booleans. Prevents spurious type-mismatch fail-closes when agents or the UI send string-encoded booleans.
- Added `_coerce_pair(a, b)` and `_try_coerce_numeric(s)`: applied at operator level in all six strict comparators (`strict_eq`, `strict_neq`, `strict_gt`, `strict_lt`, `strict_gte`, `strict_lte`). Coerces string-number mismatches (e.g. `"600"` vs `500`) before the type guard fires.
- Unified fail-closed behavior: both legacy and JSON Logic paths now always return `ASK_FOR_APPROVAL` on missing data or un-coerceable type mismatch, regardless of the rule's own outcome. The previous behavior that inherited the rule's `REJECT` outcome on fail-close was removed.
  - Updated `legacy_evaluate_rule`: removed the `fail_closed_outcome` derived from the rule outcome; missing data and type mismatches now unconditionally return `ASK_FOR_APPROVAL`.
  - Updated `evaluate_rule`: removed the regex-based `fail_closed_outcome` computation from the JSON Logic path; error path returns `ASK_FOR_APPROVAL` unconditionally.

### Schema management API (`decision_center/schema_generator.py`, `decision_center/app.py`, `decision_center/models.py`)
- Added `list_schemas(schemas_dir)` in `schema_generator.py`: reads all `.json` files from the schemas directory, returns a list of `{key, name, description, schema}` dicts. Skips unreadable files silently.
- Added `SchemaExistsError(FileExistsError)`: raised by `save_schema` when the target file already exists and `overwrite=False`.
- Extended `save_schema` signature with `overwrite: bool = False`; raises `SchemaExistsError` instead of silently overwriting.
- Added `GET /v1/schemas` endpoint: calls `list_schemas()`, returns all saved schemas.
- Added `overwrite: bool = False` field to `SchemaSaveRequest` model.
- Updated `POST /v1/schemas/save` to pass `overwrite` flag; returns HTTP 409 on `SchemaExistsError`.
- Added optional admin auth to `POST /v1/schemas/save` via `_require_admin(request)`. Reads `ADMIN_API_KEY` from environment; if unset, access is open (dev mode). If set, requires `X-Admin-Key` header matching the configured value; returns 401 otherwise.
- Updated `scripts/start_backend_stack.sh` to pass `ADMIN_API_KEY=admin-secret` when launching the Decision Center for local stack runs.

### MCP config snippets UI (`ui/src/components/AgentAdminPanel.tsx`)
- Removed unused imports `ChangeEvent` and `KeyRound`; added `Check` and `Copy` from lucide-react.
- Added `MCP_CLIENT_CONFIGS` constant array with four config generators: Claude Desktop (HTTP), Claude Desktop (stdio), Cursor/Windsurf, and Generic/Other.
- Added tab UI within the issued-token panel: clicking a tab renders the appropriate snippet in a `<pre>` block, with a copy-to-clipboard button that shows a transient checkmark icon on success.
- Agent name derived from the matched agent record; server name slug formatted as `{agent-name}-unreal-objects`.

### Dynamic schema loading in ChatInterface (`ui/src/components/ChatInterface.tsx`, `ui/src/api.ts`)
- Removed the hardcoded `SCHEMAS` constant (ecommerce and finance blueprints) from `ChatInterface.tsx`.
- Added `SchemaEntry` interface and `fetchSchemas()` function to `api.ts` — calls `GET /v1/schemas`.
- `ChatInterface` now fetches schemas from the backend on mount via a `useEffect`; stores them in a `schemas` state map. The schema dropdown, translation call, and datapoint swap all reference this dynamic map instead of the static constant.
  - Silent failure if the schemas endpoint is unavailable: dropdown stays empty, no crash.

### SchemaWorkshop bug fix (`ui/src/components/SchemaWorkshop.tsx`)
- Fixed stale conversation history: the `generate_schema` API call was passing `conversationHistory` (the state value before the current user message was appended) instead of `newHistory` (which includes it). Corrected to pass `newHistory`.

### Gemini import cleanup (`decision_center/schema_generator.py`)
- Removed dead `google.generativeai.types` import and the legacy try/except import fallback for `google-generativeai`. The module now imports only `google.genai` (the new `google-genai` SDK).

### Tests (`decision_center/tests/test_api.py`, `decision_center/tests/test_evaluator.py`)
- Added 10 new API tests covering: `GET /v1/schemas` listing, `POST /v1/llm/schema` generation (mocked OpenAI), `POST /v1/schemas/save` success, 409 conflict, overwrite, and four admin auth scenarios (missing key, wrong key, correct key, open-access dev mode).
- Added 4 new evaluator tests: string boolean coercion (true/false combinations), string number coercion (match, non-match, non-numeric escalation), and updated 4 existing tests to reflect the unified `ASK_FOR_APPROVAL` fail-close behavior.
- Total test count: 227 (was 213 before today's additions).

## Files Modified
- `decision_center/app.py` — added `list_schemas` endpoint, `overwrite` forwarding, 409 handling, admin auth guard
- `decision_center/evaluator.py` — type coercion helpers, unified fail-close, bool-string coercion pass
- `decision_center/models.py` — added `overwrite` field to `SchemaSaveRequest`
- `decision_center/schema_generator.py` — added `list_schemas`, `SchemaExistsError`, extended `save_schema`; cleaned up Gemini imports
- `decision_center/tests/test_api.py` — 10 new tests for schema API and admin auth
- `decision_center/tests/test_evaluator.py` — 4 new coercion tests; 4 updated fail-close assertions
- `scripts/start_backend_stack.sh` — passes `ADMIN_API_KEY=admin-secret` for Decision Center
- `ui/src/api.ts` — added `SchemaEntry` interface, `fetchSchemas()`, `adminApiKey` param to `saveSchema()`
- `ui/src/components/AgentAdminPanel.tsx` — MCP config snippet tabs with copy-to-clipboard
- `ui/src/components/ChatInterface.tsx` — replaced static SCHEMAS with dynamic fetch from backend
- `ui/src/components/SchemaWorkshop.tsx` — fixed stale conversation history bug

New untracked files committed:
- `schemas/conflict_test.json`, `schemas/high_value_global_box_shipment.json`, `schemas/test_schema.json` — test/example schema files created during development
- `changelog/changelog_2026-03-18.md` — this file

## Code Quality Notes
- **Backend tests**: 227/227 passed (0 failures, 0 errors). Up from 213 before today.
- **UI lint**: 4 problems remain (2 errors, 2 warnings), all pre-existing.
  - 2 errors: `react-refresh/only-export-components` in `ChatInterface.tsx` (pattern constants exported alongside components — pre-existing).
  - 2 warnings: `react-hooks/exhaustive-deps` in `AgentAdminPanel.tsx` (missing deps in two `useEffect` calls — pre-existing).
  - Net improvement: today's work removed 2 pre-existing unused-import errors (`ChangeEvent`, `KeyRound`).
- No TODO/FIXME/HACK comments introduced. No debug print statements added.

## Open Items / Carry-over
- The `react-refresh/only-export-components` errors in `ChatInterface.tsx` are pre-existing and require refactoring pattern constants into a separate file — not addressed today.
- The `react-hooks/exhaustive-deps` warnings in `AgentAdminPanel.tsx` are pre-existing and require careful dependency analysis before fixing.
- `scripts/start_backend_stack.sh` now hard-codes `ADMIN_API_KEY=admin-secret` for local dev convenience. For production use, this should be replaced with an environment variable or secret management approach.
- The three schema JSON files in `schemas/` (`conflict_test.json`, `high_value_global_box_shipment.json`, `test_schema.json`) appear to be development artifacts. Consider whether they should be kept, gitignored, or replaced by a seeded set of canonical blueprints.
