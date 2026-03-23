# Changelog — 2026-03-23

## Summary
Removed the optional `ADMIN_API_KEY` authentication guard from the Decision Center's schema save endpoint, simplifying the endpoint to always allow open access. Related dead code and test scaffolding were cleaned up accordingly.

## Changes
- **Remove admin key auth from `/v1/schemas/save`** (`decision_center/app.py`)
  - Deleted `_ADMIN_API_KEY` module-level variable and `_require_admin()` guard function
  - `save_schema_api` no longer accepts a `Request` parameter or enforces any API key check
  - Removed unused imports: `os`, `Request` from FastAPI
- **Remove `ADMIN_API_KEY` env var from backend startup script** (`scripts/start_backend_stack.sh`)
  - Dropped `ADMIN_API_KEY=admin-secret` prefix from the Decision Center `uvicorn` launch command
- **Simplify schema save tests** (`decision_center/tests/test_api.py`)
  - Replaced 4 auth-related tests (`rejects_missing_key`, `rejects_wrong_key`, `accepts_correct_key`, `open_access_when_no_key`) with a single `test_save_schema_no_auth_required` test
  - Removed unused import: `decision_center.app as app_module`

## Files Modified
- `decision_center/app.py` — removed `_ADMIN_API_KEY`, `_require_admin`, and two unused imports; updated `save_schema_api` signature
- `decision_center/tests/test_api.py` — replaced 4 admin-key tests with 1 open-access test; removed `app_module` import
- `scripts/start_backend_stack.sh` — removed `ADMIN_API_KEY=admin-secret` env var from Decision Center launch command

## Code Quality Notes
- All 175 tests pass (175 passed, 0 failed, 0 warnings)
- No linting issues found in changed files (clean removals only — unused imports deleted, no new code introduced)
- No TODO/FIXME/debug statements in changed files

## Open Items / Carry-over
- None. This was a clean, self-contained removal with full test coverage.
