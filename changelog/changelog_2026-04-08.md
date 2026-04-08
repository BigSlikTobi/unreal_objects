# Changelog — 2026-04-08

## Summary
Removed the Decision Center's filesystem persistence layer and replaced it with an in-memory-only store plus an on-demand export endpoint, eliminating the Railway volume cost. The export surface is exposed through a new API endpoint, a UI "Download JSON" button, and a new CLI wizard mode.

## Changes

### Decision Center — persistence removal
- Removed `DECISION_CENTER_PERSISTENCE_PATH` env var wiring from `decision_center/app.py`; `DecisionStore()` is now constructed with no arguments.
- The audit store (`atomic_logs`, `chains`, `pending`) lives entirely in process memory and resets on every restart/redeploy.

### Decision Center — export endpoint
- Added `GET /v1/logs/export` to `decision_center/app.py`.
  - Returns the full `DecisionStoreData` as a JSON response with a `Content-Disposition: attachment` header and a timestamped filename (`decision_log_YYYYMMDDTHHMMSSZ.json`).
  - No authentication required (consistent with other read-only log endpoints).

### Decision Center CLI — download mode
- Added `download_decision_log(output_path, base_url)` helper that `GET`s the export endpoint and saves the response to disk.
- Added `run_download_log_wizard()` interactive prompt for choosing the output filename.
- Extended the top-level mode menu in `decision_center/cli.py` with option 3 ("Download Decision Log").

### React UI — Decision Log panel
- Added `downloadDecisionLog()` helper in `ui/src/api.ts` (fetches `/v1/logs/export` and returns a `Blob`).
- Added a "Download JSON" button in `ui/src/components/DecisionLog.tsx` next to the existing Refresh button.
  - Uses the `Download` icon from `lucide-react`.
  - Icon pulses while the download is in progress; errors surface in the existing error banner.

### Tests
- Added `test_export_logs_returns_full_store_as_attachment` in `decision_center/tests/test_api.py`.
  - Verifies HTTP 200, `Content-Disposition: attachment` header, timestamped filename, and that all three store keys (`atomic_logs`, `chains`, `pending`) are present.
  - Verifies the request ID from a prior `/v1/decide` call appears in all three keys.

### Documentation
- `CLAUDE.md`: Updated step 6 of the Rule Evaluation Pipeline section to document the in-memory-only model and the three export surfaces.
- `README.md`: Removed mention of `DECISION_CENTER_PERSISTENCE_PATH`; added description of in-memory model and export instructions.
- `docs/deployment-railway.md`: Removed the Decision Center env var table row for `DECISION_CENTER_PERSISTENCE_PATH`; replaced with an explanatory prose block and removed the volume-backed path recommendation.

## Files Modified

| File | Change |
|---|---|
| `decision_center/app.py` | Remove persistence path arg from `DecisionStore()`; add `GET /v1/logs/export` |
| `decision_center/cli.py` | Add `download_decision_log()`, `run_download_log_wizard()`, and mode 3 |
| `decision_center/tests/test_api.py` | Add `test_export_logs_returns_full_store_as_attachment` |
| `ui/src/api.ts` | Add `downloadDecisionLog()` helper |
| `ui/src/components/DecisionLog.tsx` | Add "Download JSON" button and `handleDownload` callback |
| `CLAUDE.md` | Document in-memory model and export surfaces |
| `README.md` | Remove `DECISION_CENTER_PERSISTENCE_PATH`; document export model |
| `docs/deployment-railway.md` | Remove Decision Center volume guidance; document in-memory + export model |

## Code Quality Notes

- **Tests — decision_center/tests/test_api.py**: 20/20 passed (including the new export test).
- **Tests — full suite**: 306 passed, 5 errors. The 5 errors are all pre-existing in `evals/agent_eval/tests/test_runner.py` (`dc_store.atomic_logs.clear()` attribute mismatch) and were present on the baseline before today's changes. Not introduced by today's work.
- **UI lint**: 4 problems (2 errors, 2 warnings) — identical to the pre-change baseline. All are pre-existing issues in `AgentAdminPanel.tsx` and `ChatInterface.tsx`. No new lint issues introduced.

## Open Items / Carry-over

- **5 pre-existing eval test errors** in `evals/agent_eval/tests/test_runner.py`: `test_runner.py` calls `dc_store.atomic_logs.clear()` directly but `DecisionStore` exposes `get_atomic_logs()`, not a public `atomic_logs` attribute. These were broken before today's changes but are worth fixing.
- **Deployment decision pending**: Changes are uncommitted in the working tree. The user has not yet decided whether to commit directly to this submodule or route through the `unreal_objects_inc` parent repo. Do not push to remote until authorized.
- **Railway volume decommission**: The Railway volume mounted on the Decision Center service is still active. Once this change is deployed, the volume can be safely removed (saves ~362 MB of stored data).
- **Log loss on redeploy**: Accepted trade-off. Users should download the log before intentional redeploys.
