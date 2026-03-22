# Changelog — 2026-03-22

## Summary
Closed GitHub issue #19: human approval outcomes (approve/reject via `submit_approval`) now emit a second atomic log entry so the flat audit timeline reflects the final decision, not just the initial `APPROVAL_REQUIRED` trigger.

## Changes
- **Fix: human approval outcomes logged in atomic decision log** (`decision_center/app.py`)
  - `submit_approval` endpoint now calls `store.log_atomic()` after resolving a pending request
  - The new entry carries `APPROVED` or `REJECTED` as its `decision`, preserving all original identity fields (`agent_id`, `credential_id`, `user_id`, `effective_group_id`, `context`, `request_description`) from the stored pending record
  - Previously only a `decision_chain` event was written; the flat atomic log was silent on the human decision outcome

- **Tests: 3 new cases covering approval atomic logging** (`decision_center/tests/test_api.py`)
  - `test_approval_logs_atomic_entry_approved` — verifies two atomic entries exist after approval, second has `APPROVED` decision with correct description and context
  - `test_approval_logs_atomic_entry_rejected` — same scenario for rejection; second entry has `REJECTED`
  - `test_approval_preserves_identity_in_atomic_entry` — verifies `agent_id`, `credential_id`, `user_id` are copied from the original request into the approval atomic entry

## Files Modified
- `decision_center/app.py` — Added `log_atomic()` call in `submit_approval` (+13 lines)
- `decision_center/tests/test_api.py` — Added 3 new test functions (+104 lines)
- `AGENTS.md` — Renamed from `agents.md` (case correction); content is a condensed copy of CLAUDE.md without company server sections (pre-existing from earlier session)
- `CLAUDE.md` — Added Living Virtual Company section, updated service map, added company server commands and key design decisions (pre-existing additions from earlier session, carried on this branch)
- `pyproject.toml` — Added `pydantic-settings` dependency, `uo-company-server` entry point, `company_server/` and `support_company/` packages, company server test path (pre-existing from earlier session)

## Code Quality Notes
- **Tests**: 282 passed, 1 failed (`tests/test_sse.py::test`) — pre-existing failure unrelated to today's changes. The SSE test tries to bind port 8010, which conflicts with the company server; this test has been flaky since the company server was introduced.
- **Linting**: UI files not changed today; no new lint issues introduced.
- **No debug statements, TODOs, or commented-out code blocks** found in the changed files.
- The 3 new tests in `test_api.py` are well-structured: they mock the Rule Engine, use `AsyncClient`, and make precise assertions on log entry count and field values.

## Open Items / Carry-over
- `tests/test_sse.py` pre-existing failure: the test starts an MCP server on port 8010, conflicting with the company server. Should either be moved to a different port or gated to only run when port 8010 is free.
- `AGENTS.md` does not yet include the Living Virtual Company / company server sections that CLAUDE.md has; these could be added in a follow-up pass.
