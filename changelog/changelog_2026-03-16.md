# Changelog — 2026-03-16

## Summary

Two major pieces of work landed today: a Decision Log UI panel that surfaces the Decision Center's audit trail directly in the React frontend, and a hardening of the fuzzy variable mapper that fixes a false-positive match bug discovered during agent eval runs.

## Changes

### UI — Decision Log panel
- Added four new TypeScript types to `ui/src/types.ts`: `DecisionState`, `AtomicLogEntry`, `ChainEvent`, `DecisionChain` — matching the Decision Center's `/logs/atomic` and `/logs/chains/:id` API shapes.
- Added two API functions to `ui/src/api.ts`: `fetchAtomicLogs` (polls `/logs/atomic`) and `fetchDecisionChain` (fetches `/logs/chains/:id`) — both using `cache: 'no-store'` to avoid stale data.
- Created `ui/src/components/DecisionLog.tsx` — a new full-page workspace view with:
  - Color-coded outcome badges: emerald (APPROVED), red (REJECTED), amber (APPROVAL_REQUIRED).
  - Reverse-chronological card list with timestamps, group ID, agent ID, and truncated request IDs.
  - Expandable chain timeline per entry: clicking a card fetches and renders the full decision chain as a vertical timeline with per-event JSON details.
  - Empty state and error state handling.
  - Manual refresh button with spinner.
- Updated `ui/src/components/Sidebar.tsx`: added a "Decision Log" navigation button using the `ScrollText` Lucide icon.
- Updated `ui/src/App.tsx`: added `'decision-log'` to the `WorkspaceView` union type and wired the routing so the Decision Log renders in the main content area with a `max-w-6xl` container.

### Backend — fuzzy variable mapper hardening (`decision_center/evaluator.py`)
- Identified a false-positive bug: the original containment matcher picked the shortest substring match without checking semantic overlap. Example failure: `aml_score` was silently resolved to `credit_score` because both end in `_score`, bypassing a REJECT rule that should have fired on missing data.
- Fix: multi-part variable names now require at least one non-generic semantic word part to be shared between the rule variable and the candidate key. Generic suffixes (`score`, `amount`, `days`, `rate`, `pct`, `count`, `id`, `value`, `time`, `kg`, `km`) are excluded from this check.
- Raised the `difflib` fuzzy-match cutoff from 0.4 to 0.7 to prevent near-miss false positives on shared suffixes.
- Single-part names (e.g. bare `amount`) retain the original looser matching since there are no multi-part ambiguities.
- Added `_split_var_parts()` helper function.

### Evals — generated scenario corpus and CLI improvements (`evals/agent_eval/`)
- Added `evals/agent_eval/scenarios/generated.py`: 500 deterministic, seed-controlled scenarios covering 12 edge-case patterns across 5 domains (finance, ecommerce, healthcare, logistics, HR).
  - Patterns include: boundary values, fail-closed missing data, type mismatch, fuzzy variable mapping, edge-case short-circuit, inactive rules, outcome precedence, legacy string fallback, multi-step workflows, fail-closed + multi-rule.
- Updated `evals/agent_eval/cli.py`:
  - Added `--domain generated` and `--domain full` (handwritten + generated, 509 total) options.
  - Added `--seed` argument: integer for reproducible runs, `'random'` for a fresh set each time (seed is printed for replay).
  - Services auto-start: if the Rule Engine and Decision Center are not already running, the CLI starts them as subprocesses and stops them when the run finishes. Use `--fail-on-missing-services` to opt out (e.g., in CI).
  - Refactored `_run()` to use a `try/finally` block for reliable service teardown.
- Added `_start_services()` and `_stop_services()` helpers.
- Updated `evals/agent_eval/tests/test_scenarios.py`: 6 new tests for the generated corpus (count, ID uniqueness, no overlap with handwritten, schema validity, outcome coverage, required rule fields).
- Updated `evals/agent_eval/tests/test_cli.py`: added `seed=42` to all `Namespace` mocks.

### Documentation
- `README.md`: renamed section to "Evaluation Snapshot", added Agent Eval results table (500 generated, 6 finance, 3 ecommerce — all 100%).
- `docs/evaluation.md`: added seed control usage, auto-start behavior, full generated pattern breakdown table, current results table, and a "Notable Findings" section documenting the fuzzy mapper false-positive incident.
- `CLAUDE.md`: updated `DecisionLog` into the React UI component list; updated MCP server transport from `sse` to `streamable-http`; added `uo-agent-eval` and `uo-agent-admin` CLI entry points; expanded fuzzy variable mapping design decision entry with the new semantic-parts filtering rule.

## Files Modified

| File | Change |
|---|---|
| `ui/src/types.ts` | Added `DecisionState`, `AtomicLogEntry`, `ChainEvent`, `DecisionChain` types |
| `ui/src/api.ts` | Added `fetchAtomicLogs`, `fetchDecisionChain` |
| `ui/src/components/DecisionLog.tsx` | New component — audit log viewer with chain timeline |
| `ui/src/components/Sidebar.tsx` | Added Decision Log navigation button |
| `ui/src/App.tsx` | Added `decision-log` workspace view route |
| `decision_center/evaluator.py` | Fuzzy mapper false-positive fix; raised difflib cutoff to 0.7 |
| `evals/agent_eval/scenarios/generated.py` | New — 500 generated edge-case scenarios |
| `evals/agent_eval/cli.py` | `--domain generated/full`, `--seed`, auto-start services |
| `evals/agent_eval/tests/test_cli.py` | Added `seed=42` to Namespace mocks |
| `evals/agent_eval/tests/test_scenarios.py` | 6 new tests for generated corpus |
| `evals/agent_eval_report_v1.md` through `v6.md` | Generated eval run outputs (untracked) |
| `README.md` | Added agent eval results table |
| `docs/evaluation.md` | Seed control, auto-start docs, pattern table, notable findings |
| `CLAUDE.md` | DecisionLog component, transport update, CLI entry points, fuzzy mapper details |

## Code Quality Notes

- Python tests: **223 passed, 0 failed** (12.02s). Full suite including 6 new generated-scenario tests.
- UI lint (today's changed files only): **0 errors, 0 warnings**. `DecisionLog.tsx`, `App.tsx`, `api.ts`, `types.ts`, `Sidebar.tsx` all lint-clean.
- UI lint (full project): 4 errors and 2 warnings in pre-existing files (`AgentAdminPanel.tsx`, `ChatInterface.tsx`) — none introduced today.

## Open Items / Carry-over

- Pre-existing UI lint errors in `AgentAdminPanel.tsx` (unused `ChangeEvent` and `KeyRound` imports) and `ChatInterface.tsx` (`react-refresh/only-export-components`) remain unaddressed. These were present before today's work.
- The Decision Log UI currently requires a manual refresh — there is no auto-polling. A future enhancement could add a configurable poll interval.
- `evals/agent_eval_report_v1.md` through `v6.md` are untracked — they are generated outputs and not committed. Consider documenting this in `.gitignore` if these should remain excluded permanently.
