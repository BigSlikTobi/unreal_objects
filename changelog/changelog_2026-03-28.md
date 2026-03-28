# Changelog — 2026-03-28

## Summary
Fixed an infinite loop bug in the rule builder's "Add & Retry" flow caused by `_validate_candidate_alignment()` raising `SchemaConceptMismatchError` even when the better field was already present in the schema. The fix auto-swaps the wrong variable for the correct one when both exist, and only raises to prompt the user to add a missing field when it is genuinely absent.

## Changes
- **Bug fix — auto-swap in `_validate_candidate_alignment()`** (`decision_center/translator.py`):
  - Previously, when the LLM picked a semantically wrong field (e.g. `account_age_days` instead of `delivery_time_days`) and both fields existed in the schema, the validator raised `SchemaConceptMismatchError`. The UI caught this, offered "Add & Retry", which re-ran the same LLM call, which chose the same wrong field — an infinite loop.
  - Fix: when `best_field` (the better match) is already in `context_schema`, call `swap_variable_in_result()` to silently correct the variable in-place. Iteration state (`used_vars`, `ordered`) is cleared and rebuilt from the updated result to avoid stale references.
  - The `SchemaConceptMismatchError` path is now reserved exclusively for the case where the better field is absent from the schema and must be added by the user.

- **Test updates** (`decision_center/tests/test_translator.py`):
  - Renamed `test_validate_candidate_alignment_rejects_wrong_field` → `test_validate_candidate_alignment_autoswaps_when_both_fields_exist`: asserts auto-swap occurs and no exception is raised when both fields are in the schema.
  - Renamed `test_validate_candidate_alignment_proposed_field_carries_best_match` → `test_validate_candidate_alignment_raises_when_var_not_in_schema`: updated to use a variable (`shipping_delay`) that is genuinely absent from the schema, ensuring the error path still works correctly for the intended use case.

## Files Modified
- `decision_center/translator.py` — added auto-swap branch in `_validate_candidate_alignment()` before the `SchemaConceptMismatchError` raise
- `decision_center/tests/test_translator.py` — updated two test cases to reflect new behavior (auto-swap vs. raise-on-missing)
- `.DS_Store` — filesystem metadata (not committed)

## Code Quality Notes
- **Tests**: 280 passed, 0 failed, 0 skipped. Full suite clean.
- **Linting**: No UI files changed; ESLint not run (pre-existing errors in `AgentAdminPanel.tsx` and `ChatInterface.tsx` remain unchanged).
- No debug print statements, TODO/FIXME/HACK comments, or commented-out code blocks introduced.

## Open Items / Carry-over
- Pre-existing UI ESLint errors (2 errors, 2 warnings in `ChatInterface.tsx` and `AgentAdminPanel.tsx`) are unrelated to today's work and remain open.
- Pre-existing `tests/test_sse.py` port-conflict issue remains (not related to today's change).
