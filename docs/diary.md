# Unreal Objects Diary

## Variable Swap: Token-Aware Replacement

**Date:** 2026-03-03

**What was built:**

Fixed a critical bug in `swap_variable_in_result()` where string replacement used naive `.replace()` / `.replaceAll()`, which could incorrectly replace substrings inside other variable names (e.g., swapping "amount" would also change "transaction_amount" to "transaction_new_var").

**Changes:**

### Backend (`decision_center/translator.py`)

1. **`_replace_variable_token(text, old_var, new_var)`** — new helper function that uses regex word boundaries (`\b`) to ensure only complete variable tokens are replaced, not substrings. Example: replacing "amount" in "transaction_amount > 100" leaves it unchanged, but "amount > 100 AND amount < 500" correctly becomes "price > 100 AND price < 500".

2. **`swap_variable_in_result()` updated** — now calls `_replace_variable_token()` for `rule_logic` and `edge_cases` string replacements instead of using `.replace()`.

### Frontend (`ui/src/components/ChatInterface.tsx`)

1. **`replaceVariableToken(text, oldVar, newVar)`** — new exported utility function mirroring the backend implementation using JavaScript regex with word boundaries.

2. **`swapVariableInResult()` updated** — now calls `replaceVariableToken()` for `rule_logic` and `edge_cases` string replacements instead of using `.replaceAll()`.

3. **Exported for testing** — both `replaceVariableToken` and `swapVariableInResult` are now exported so they can be unit tested.

### Tests

**Backend (`decision_center/tests/test_translator.py`):**
- `test_swap_variable_replaces_repeated_occurrences()` — verifies multiple occurrences of the same variable in rule_logic and edge_cases are all replaced
- `test_swap_variable_does_not_replace_substrings()` — verifies that swapping "amount" does not affect "transaction_amount" or "total_amount"

**Frontend (`ui/src/components/ChatInterface.test.tsx`):**
- `replaceVariableToken` suite (3 tests):
  - Replaces all occurrences of a variable
  - Does not replace substrings inside other variable names
  - Replaces standalone variable but leaves compound variables unchanged
- `swapVariableInResult` suite (3 tests):
  - Replaces variable in all parts of translation result
  - Replaces multiple occurrences in rule_logic
  - Does not replace substrings in compound variable names

**Result:** All 147 Python tests + 11 UI tests passing. The swap utility now correctly handles:
1. Multiple occurrences of the same variable (all replaced)
2. Variables that are substrings of other variables (left unchanged)
3. Edge cases in both string and JSON Logic forms

**How it was validated:**

```bash
# Backend tests
pytest decision_center/tests/test_translator.py -v  # 47 passed

# Frontend tests
cd ui && npm test -- ChatInterface.test.tsx  # 11 passed

# Full suite
pytest -v  # 147 passed
```

The fix ensures internal consistency when users swap datapoints via the UI dropdown or CLI prompt — no more accidental partial replacements that would break rule evaluation.

---

## Schema Translation: Candidate Alignment, Extension Flow, and Variable Swapping

**Date:** 2026-03-02

**What was built:**

Three major improvements to the schema-enforced translation workflow:

1. **Deterministic candidate alignment validator** — prevents the LLM from picking semantically wrong fields when better options exist
2. **Schema extension flow** — lets users add missing concepts inline and retry translation instantly (UI + CLI)
3. **Variable swapping** — post-translation interactive editing to replace extracted datapoints (UI + CLI)

**Changes:**

### Backend (`decision_center/translator.py`)

1. **`_validate_candidate_alignment(result, natural_language, context_schema)`** — new deterministic post-translation guard. Scores every variable actually used in `rule_logic_json` against the original rule text using the same word-overlap algorithm as `_find_candidate_fields`. If a variable scores below 50% of the best available score, raises `SchemaConceptMismatchError` with the better field as `proposed_field`. Example: `account_age_days` (score 3) vs `delivery_time_days` (score 8) for "delivery time > 10 days" → rejects with suggested field.

2. **`_extract_proposed_field(rule_logic)`** — scans the condition text for the first variable in a comparison expression and infers its type from the operator (`>/<` → number, `==/!=` → text). Called when `_validate_rule_logic_json_populated` detects empty logic with a condition present, so the error can suggest a specific field name and type.

3. **`_validate_rule_logic_json_populated` enhancement** — now calls `_extract_proposed_field` and includes the result in the raised `SchemaConceptMismatchError` when schema mode is active but the LLM returns empty JSON Logic.

4. **`SchemaConceptMismatchError.proposed_field`** — the error now carries an optional `{"name": "...", "description": "...", "type": "..."}` dict that the UI/CLI can surface as a pre-filled "add this field" form.

5. **`swap_variable_in_result(result, old_var, new_var)`** — new utility function that replaces a variable name throughout datapoints, rule_logic (string), rule_logic_json, edge_cases (strings), and edge_cases_json. Uses `_swap_var_in_json_logic` helper that recursively walks JSON Logic and swaps `{"var": old}` → `{"var": new}`.

### API (`decision_center/app.py`)

- 422 responses for `SchemaConceptMismatchError` now include a top-level `proposed_field` key (sibling to `detail`) via `JSONResponse` so clients can display structured field suggestions.

### UI (`ui/src/`)

1. **`DatapointChip` component** — each extracted datapoint in the proposal card is now a clickable badge with a dropdown:
   - Shows all schema fields sorted alphabetically (current field highlighted)
   - Each option displays field name + description
   - "Create new field" option with inline text input
   - Clicking a field calls `handleSwapVariable` which updates the message's `ruleData` in place using client-side `swapVariableInResult`

2. **Schema extension flow enhancement** — when translation fails with a 422 containing `proposed_field`, the UI renders a `SchemaExtensionOffer` card with pre-filled field name and type. User can edit and click "Add & Retry" → merges into `schemaExtensions` state and re-runs translation with the extended schema.

3. **`handleTranslate(extraSchema?: Record<string, string>)`** signature change — now accepts optional `extraSchema` parameter to avoid React async state timing issues when adding a field and immediately retrying.

4. **`ChevronDown` icon import** from lucide-react for the dropdown affordance.

### CLI (`decision_center/cli.py`)

1. **Schema extension prompt** — when `SchemaConceptMismatchError` is caught and `proposed_field` is present:
   - Shows suggested field name and type
   - Prompts "Add this field to the schema and retry? [Y/n]"
   - User can confirm or edit the field name and type
   - Merges into `context_schema` (initializing as `{}` if needed) and continues the `while True` translation loop

2. **Datapoint swap prompt** — after showing extracted datapoints (schema mode only):
   - "To change a datapoint, enter its number. Press Enter to skip."
   - If user picks a number → shows ranked candidates via `_find_candidate_fields(natural_language, context_schema, top_n=len(context_schema))`
   - Current field marked with `←`
   - Options: pick numbered field, or "N. Create a new field name"
   - If swapped → calls `swap_variable_in_result` and updates display immediately before Accept/Edit/Manual prompt

3. **Import additions** — `swap_variable_in_result`, `_find_candidate_fields`, `SchemaConceptMismatchError`

**Validation:**

- **Backend tests:** 5 new tests in `decision_center/tests/test_translator.py` for `_validate_candidate_alignment`, 2 for `swap_variable_in_result`. Full suite: 143/143 passing.
- **CLI tests:** 1 new test in `decision_center/tests/test_cli.py` for datapoint swap flow. Schema extension test updated to skip swap prompt. All CLI tests passing.
- **UI:** TypeScript compilation clean. Manual testing confirmed DatapointChip dropdown works, SchemaExtensionOffer renders, and swap updates the proposal correctly.

**Key findings:**

1. **Prompt-based steering is insufficient** — the LLM routinely ignored the ranked candidate list and schema descriptions. A deterministic post-translation score comparison (50% threshold) catches semantic mismatches reliably.

2. **Candidate ranking must use the original rule text** — not the LLM's output. The CLI initially passed `translation.get("rule_logic")` to `_find_candidate_fields`, which ranked against the already-wrong field name. Fixed to use `natural_language` instead.

3. **UI event handler pitfall** — `onClick={handleTranslate}` passed the React `MouseEvent` as `extraSchema`, causing JSON serialization circular reference errors. Fixed with `onClick={() => handleTranslate()}`.

4. **Schema extension creates context for swap prompt** — when the extension flow succeeds, `context_schema` is now populated → the swap prompt appears. CLI test for schema extension needed an extra `""` (skip) input after the second translation succeeds.

---

## Schema Translation Hardening — Semantic Concept Guard

**Date:** 2026-03-02

**What was built:**

The translator's schema-mode enforcement had a critical gap: when a schema was
active the LLM could silently substitute a "closest" schema field even when the
concept was semantically different (e.g. mapping *delivery time* to
`account_age_days` because both are measured in days).  Two complementary
safety nets were added.

**Changes:**

1. **`SchemaConceptMismatchError`** — a new `ValueError` subclass in
   `decision_center/translator.py` that is raised whenever the guard detects a
   concept violation.  Using a distinct type lets callers and the API layer
   handle it explicitly.

2. **`_detect_unsupported_sentinel`** — after translation the LLM response is
   inspected for a `UNSUPPORTED:` prefix in `rule_logic`.  The system prompt
   now instructs the model to emit this sentinel (rather than silently
   substituting) when no schema field clearly covers the requested concept.
   The sentinel is caught and re-raised as `SchemaConceptMismatchError`.

3. **`_validate_schema_variables`** — a deterministic post-translation guard
   that walks every `{"var": ...}` expression in `rule_logic_json` and
   `edge_cases_json` and verifies each variable exists in the active schema.
   This catches off-schema substitutions regardless of what the LLM said in its
   prose.

4. **Strengthened schema enforcement prompt block** — now lists schema fields
   line-by-line with descriptions (instead of a raw JSON dump), includes an
   explicit negative example (`account_age_days` ≠ `delivery time_days`),
   requires a *semantic* match (not just name similarity), and states the
   `UNSUPPORTED:` protocol.

5. **API layer (`decision_center/app.py`)** — `SchemaConceptMismatchError` is
   caught separately and returned as HTTP 422 so the UI can surface a clear
   "concept not in schema" message rather than a generic 500.

**Validation:**

13 new tests were added to `decision_center/tests/test_translator.py` covering:
prompt content assertions, standalone unit tests for both validators, and
end-to-end `translate_rule` integration scenarios (wrong-field substitution,
UNSUPPORTED sentinel, and a passing correct-field case).  Full suite ran
124 tests, all green, zero regressions.

**Key finding:**

The two mechanisms (translation-time steering and evaluation-time fuzzy
mapping) serve different purposes and must stay separated.  The fix belongs
entirely in the translation layer; the evaluator's fuzzy mapper is intentionally
left unchanged as it handles legitimate minor naming mismatches at runtime.

---

## UI App Import Parse Fix

**What was built:**

- Added a UI regression test that inspects `ui/src/App.tsx` source imports and
  fails if React hooks are split across duplicate `react` import lines.
- Removed the duplicate `useEffect` import from `ui/src/App.tsx` by merging the
  hook imports into a single React import statement.

**How it was validated:**

- Ran `npm test -- src/AppSource.test.ts` to prove the new regression fails
  before the fix and passes after it.
- Ran `npm test -- src/App.test.tsx`, `npm test`, `npm run lint`, and
  `npm run build` in `ui/` after the import fix landed.

**Key Findings:**

- The Vite dev-server failure came from a straightforward duplicate hook import,
  but a source-level regression is the safest guard here because syntax errors
  in `App.tsx` can prevent the normal component tests from loading at all.

## README Updated for Finance V6 Evaluation

**What was built:**

- Updated the README trust-signal snapshot and evaluation section to include the
  newly committed finance stress-test report in
  `evals/generative_evaluation_report_v6.md`.
- Kept the ecommerce V5 run as the strongest committed benchmark while adding
  the finance V6 metrics as a second schema-specific evidence point.

**How it was validated:**

- Cross-checked the README figures against `evals/generative_evaluation_report_v6.md`
  before updating the committed evidence tables and summary text.

**Key Findings:**

- The README now better reflects the actual evaluation state of the repo: one
  very strong ecommerce benchmark, one committed finance benchmark, and the
  remaining no-schema path still CLI-ready but not yet checked in as a report.

## Full Removal of Legacy `scripts/stress_test`

**What was built:**

- Removed the remaining legacy `scripts/stress_test/` files entirely, including
  the old quality-chaos utilities and historical dataset artifacts.
- Left `decision_center/stress_test/` as the single supported home for all
  current stress-test logic and workflows.
- Tightened the README language so it no longer suggests any fallback or
  reference stress-test directory still exists.

**How it was validated:**

- Re-read repository references to confirm the documentation now points only to
  the canonical CLI/module path.
- Ran the full Python suite after deleting the directory contents.

**Key Findings:**

- Once the new CLI, dataset preparation flow, and promotion workflow existed,
  the remaining `scripts/stress_test/` files only added ambiguity. Removing the
  directory contents makes the evaluation surface much easier to understand.

## Legacy Stress-Test Wrapper Removal

**What was built:**

- Removed the obsolete wrapper scripts
  `scripts/stress_test/generate_llm_dataset_sync.py`,
  `scripts/stress_test/batch_1_create_sync.py`, and
  `scripts/stress_test/batch_3_evaluate.py`.
- Kept the canonical stress-test implementation solely under
  `decision_center/stress_test/`.
- Left historical datasets, reports, and the separate quality-chaos tooling in
  `scripts/stress_test/` intact as reference artifacts rather than executable
  entrypoints.
- Updated the README so it now clearly points users to the CLI/module interface
  instead of the removed wrapper scripts.

**How it was validated:**

- Re-read the remaining references to ensure the README and current CLI docs no
  longer rely on the deleted wrapper paths.
- Ran the full Python suite after the deletions to confirm no tests still
  depended on those legacy entrypoints.

**Key Findings:**

- The wrapper scripts had served their short-term migration purpose, but keeping
  them around would continue to suggest that two orchestration paths were
  supported. Removing them makes the stress-test system easier to understand and
  reduces future drift risk.

## README Evaluation Refresh and Schema Trust Signal

**What was built:**

- Refreshed the README evaluation section so it matches the current
  stress-test CLI, reusable baseline workflow, candidate dataset preparation,
  promotion flow, and dataset listing command.
- Added a schema-by-schema trust-signal graphic near the top of the README that
  distinguishes between the strongest committed evaluation evidence
  (`ecommerce`) and the newer CLI-ready schema paths (`finance`, `none`).
- Added an explicit “current recorded evidence” section so readers can see the
  difference between checked-in reports, reusable baselines, and on-demand CLI
  support.
- Replaced the initial mermaid trust-signal graphic with a plain markdown
  table and ASCII-style summary after confirming the target renderer displayed
  mermaid source text instead of rendering the diagram.

**How it was validated:**

- Cross-checked the README claims against the checked-in `evals/` reports and
  the current artifact layout under `evals/artifacts/`.

**Key Findings:**

- The repository now has stronger operational tooling than the old README
  implied, but the strongest committed benchmark evidence is still the
  ecommerce V5 report. Calling that out explicitly is more trustworthy than
  implying all schemas already have equivalent published runs.

## Reusable Dataset Baselines, Candidate Generation, and Promotion

**What was built:**

- Extended the stress-test CLI so reusable datasets now follow a baseline plus
  candidate model instead of a single throwaway artifact.
- Kept the active reusable baseline at `evals/artifacts/<schema>/llm_test_dataset.json`
  and added versioned candidate datasets under
  `evals/artifacts/<schema>/datasets/`.
- Added `--prepare-datasets` to generate fresh candidate datasets for one
  schema or `all`, `--background` to launch that preparation run as a detached
  process, and `--promote-dataset` to copy a chosen candidate into the active
  reusable baseline.
- Kept regular evaluation runs fast by auto-reusing the promoted baseline and
  showing its age in the CLI phase output.

**How it was validated:**

- Added regression coverage for candidate dataset path generation, baseline
  reuse, age display, prepare-only runs, background process launching, and the
  dataset promotion workflow.
- Ran `.venv/bin/pytest decision_center/tests/test_stress_test_cli.py -q` and
  then `.venv/bin/pytest -q` to verify the new CLI workflow without regressing
  the rest of the system.

**Key Findings:**

- Stable evaluation baselines and fresh candidate generation solve different
  problems. Daily or repeated stress tests want comparability, while fresh
  candidate datasets are for drift discovery and benchmark refreshes. Making
  promotion explicit avoids silently changing the benchmark under users.

## Unified Stress-Test CLI with Dynamic Schema Discovery

**What was built:**

- Replaced the old split stress-test workflow with a packaged `uo-stress-test`
  CLI under `decision_center.stress_test`.
- Added automatic schema discovery from `schemas/*.json`, so new schema files
  become valid `--schema <slug>` targets without code changes.
- Added `--schema none` for freeform runs and `--schema all` to execute every
  discovered schema sequentially before running the no-schema variant.
- Added schema-scoped artifact folders in `evals/artifacts/<schema>/` and
  versioned markdown report generation in `evals/generative_evaluation_report_vN.md`.
- Folded the legacy `scripts/stress_test/*.py` entrypoints into thin wrappers
  around the new module so the repo no longer carries two separate stress-test
  implementations.

**How it was validated:**

- Added regression coverage for schema discovery, `all` expansion, prompt
  injection, artifact path resolution, report versioning, JSONL translation
  loading, markdown report content, and CLI orchestration order.
- Ran `.venv/bin/pytest decision_center/tests/test_stress_test_cli.py -q` and
  then `.venv/bin/pytest -q` to keep the full Python suite green through each
  round of the implementation.

**Key Findings:**

- The most important design change was making schema support data-driven instead
  of hard-coded. Once the CLI resolved schemas from disk, `finance`,
  `ecommerce`, future domain schemas, and the special `none`/`all` modes all
  fit the same orchestration path cleanly.

## Saved Rules Stay Attached to the Builder

**What was built:**

- Clarified and aligned the React save flow so saved rules remain attached to
  the builder after **Accept & Save** and **Save & Test** instead of appearing
  to clear and then silently re-enter edit mode.
- Kept **Stop Editing** as the explicit way to clear the builder and leave edit
  mode, and fixed the clear path so it also drops the parent-selected rule
  instead of instantly reloading the same saved rule.

**How it was validated:**

- Added UI regression coverage for the post-save editing state and the
  save-and-test flow.

**Key Findings:**

- The underlying workflow already depended on saving before testing. The real
  UX problem was mixed signaling: the UI claimed to clear the builder while the
  parent state immediately reattached the same saved rule for continued edits.

## Rule Management UX Hardening Wrap-Up

**What was built:**

- Completed the rule-lifecycle pass across the backend, CLI, and React UI so
  rules can be edited, deactivated without deletion, reactivated later, and
  kept visible for auditability.
- Moved saved-rule browsing out of the chat transcript into a dedicated rule
  library panel, with mobile slide-over behavior and a cleaner desktop
  three-column layout.
- Finished the supporting hardening work: class-based dark mode, explicit chat
  confirmations for lifecycle changes, and no-store reads so refreshed pages
  show the current rule state instead of stale cached cards.

**How it was validated:**

- Added and expanded backend, CLI, and UI regression coverage for rule editing,
  lifecycle toggles, cache behavior, dark mode, and responsive rule-library
  flows.
- Verified the branch with `.venv/bin/pytest -q`, `npm test`, `npm run lint`,
  and `npm run build`.

**Key Findings:**

- The most error-prone part of rule management was not the write path itself but
  the surrounding feedback loop: users need persistent rule state, immediate UI
  confirmation, and an editing surface that keeps saved rules accessible without
  cluttering the chat flow.

## Fresh Rule State After Refresh

**What was built:**

- Hardened rule-state reads so deactivate/reactivate changes remain visible after
  a browser refresh instead of reverting to stale card state.
- Added `Cache-Control: no-store` headers to the Rule Engine group and rule read
  endpoints in `rule_engine/app.py`.
- Updated the React API helpers in `ui/src/api.ts` so `fetchGroups()` and
  `getGroup()` explicitly bypass browser caches when loading saved rule state.

**How it was validated:**

- Added backend coverage in `rule_engine/tests/test_api.py` to assert group read
  endpoints disable HTTP caching.
- Added UI coverage in `ui/src/api.test.ts` to assert the saved-rule fetch
  helpers request `cache: 'no-store'`.
- Ran `.venv/bin/pytest rule_engine/tests/test_api.py -q` and confirmed all
  tests passed (`5 passed`).

**Key Findings:**

- The deactivation write path was already persisting correctly. The visible
  regression after refresh came from stale GET responses, so the fix needed to
  harden reads rather than change the rule update logic again.

## Rule Status Notices in Chat

**What was built:**

- Added an explicit rule-status notification path from the rule library into the
  chat/builder surface.
- When a user clicks **Deactivate** or **Reactivate** in the rule library, the
  chat now shows a clear assistant message confirming the action and its effect
  on evaluation behavior.
- Implemented the handoff through `ui/src/App.tsx`,
  `ui/src/components/RuleLibrary.tsx`, and
  `ui/src/components/ChatInterface.tsx`.

**How it was validated:**

- Added a UI regression test in `ui/src/App.test.tsx` covering the deactivate
  action and the resulting chat notice.
- Ran `npm test` in `ui/` and confirmed all UI tests passed (`6 passed`).
- Ran `npm run lint` and `npm run build` in `ui/` and confirmed both passed.

**Key Findings:**

- Deactivation inside a dedicated side panel needs a second feedback channel.
  Updating the card state alone is easy to miss, while a chat notice makes the
  action explicit and auditable in the user flow.

## Class-Based Dark Mode and Motion Polish

**What was built:**

- Switched the UI theme system to an explicit class-based dark variant in
  `ui/src/index.css`, so toggling dark mode now correctly affects Tailwind
  `dark:*` styles across the entire app.
- Added shell-level motion polish with enter animations for the mobile group
  drawer, mobile rule drawer, and the test console panel.
- Tightened the visual shell with sticky panel headers and more coherent
  full-page theming for `html`, `body`, and `#root`.
- Added a regression test in `ui/src/App.test.tsx` to verify that clicking the
  dark-mode toggle actually adds and removes the `dark` class on the document
  root.

**How it was validated:**

- Ran `npm run lint` in `ui/` and confirmed it passed.
- Ran `npm test` in `ui/` and confirmed all UI tests passed (`5 passed`).
- Ran `npm run build` in `ui/` and confirmed the production build succeeded.
- Ran `.venv/bin/pytest -q` and confirmed the full Python suite still passed
  (`51 passed`).

**Key Findings:**

- The dark-mode toggle logic in React was already working; the missing piece was
  Tailwind’s dark variant configuration. Without a class-based dark variant,
  toggling `.dark` on `document.documentElement` had no visible effect.
- Small motion cues matter most in the responsive shell. The slide-in drawers
  and bottom-sheet test console make it much clearer where content came from and
  where it returns.

## Frontend Shell Hardening and Dark Mode Cleanup

**What was built:**

- Added shared UI domain types in `ui/src/types.ts` and replaced the remaining
  `any`-based API/component contracts across the React app.
- Polished the responsive shell by making the sidebar, rule library, and test
  console behave like dedicated panels with sticky headers and mobile-friendly
  overlays/bottom-sheet behavior.
- Hardened dark mode in `ui/src/index.css` so `html`, `body`, and `#root`
  share the same dark background and browser color-scheme, fixing the mismatch
  where parts of the shell could remain visually light or default-styled.
- Kept the desktop three-column layout while improving the mobile experience
  for opening groups, browsing rules, and running tests.

**How it was validated:**

- Ran `npm run lint` in `ui/` and confirmed the frontend lint/type check passed.
- Ran `npm test` in `ui/` and confirmed all UI tests passed (`4 passed`).
- Ran `npm run build` in `ui/` and confirmed the production build succeeded.
- Ran `.venv/bin/pytest -q` and confirmed the full Python suite still passed
  (`51 passed`).

**Key Findings:**

- The dark-mode bug was partly a shell problem rather than a single component
  bug: global document surfaces needed to inherit the same theme variables and
  color-scheme as the React panels.
- Shared types pay off quickly in this repo because the same rule objects move
  through the library, builder, test console, and API layer.
- Mobile usability improved most once the test console stopped acting like a
  fixed desktop rail and became a mobile-first bottom sheet.

## Responsive Rule Library UX

**What was built:**

- Moved saved rule browsing out of the chat transcript and into a dedicated
  rule library panel in the React UI.
- Added `ui/src/components/RuleLibrary.tsx` to render saved rules as cards on
  the right side of the page on desktop.
- Changed the main UI flow so selecting a rule card loads that rule into the
  builder/chat area for editing instead of embedding rule cards inside the chat
  feed.
- Updated `ui/src/App.tsx` to coordinate the selected rule, refresh the rule
  library after saves, and provide explicit mobile controls for opening the
  group list and rule library.
- Made the shell responsive: desktop uses left sidebar + center builder + right
  rule library, while mobile uses slide-over panels for groups and saved rules.
- Updated the README UI section to document the new right-side rule library and
  mobile interaction model.

**How it was validated:**

- Added UI tests in `ui/src/App.test.tsx` covering the new flow where a rule is
  chosen from the rule library and loaded into the builder.
- Updated `ui/src/components/ChatInterface.test.tsx` so the builder is tested
  through the new selected-rule handoff instead of the old in-chat card list.
- Ran `npm test` in `ui/` and confirmed all UI tests passed (`4 passed`).
- Ran `npm run build` in `ui/` and confirmed the production build succeeded.
- Ran `.venv/bin/pytest -q` to verify the full Python suite still passed
  (`51 passed`).

**Key Findings:**

- The old chat-embedded rule list mixed two different jobs: conversation and
  library browsing. Moving saved rules into a dedicated panel makes rule review
  much faster and keeps the transcript focused on translation and validation.
- Mobile needs explicit entry points for side content. Slide-over panels for
  groups and saved rules preserve the full feature set without shrinking the
  builder into an unusable column.
- Keeping `App` as the owner of the currently selected rule makes the flow
  predictable: the library selects, the builder edits, and saves refresh the
  library.

## Rule Lifecycle Editing Across CLI and UI

**What was built:**

- Added an explicit `active` lifecycle flag to stored rules in the Rule Engine.
  Rules now remain persisted for documentation while being safely excluded from
  live evaluation when deactivated.
- Updated the Decision Center evaluator to skip inactive rules without deleting
  them.
- Reworked the CLI rule update flow in `decision_center/cli.py` so selecting an
  existing rule first shows the current stored rule, allows selective edits with
  Enter-to-keep defaults, preserves edge cases by default, and supports direct
  deactivate/reactivate actions.
- Extended the React UI in `ui/src/components/ChatInterface.tsx` with an
  existing-rule management panel so users can review saved rules, load one back
  into the builder for editing, and deactivate/reactivate it without deleting
  the record.
- Hardened `decision_center/translator.py` so provider responses that omit
  `rule_logic_json` or return edge-case strings without matching JSON entries
  still normalize into valid rule payloads.
- Added a lightweight Vitest + Testing Library harness for the UI and wired it
  into the Vite config.

**How it was validated:**

- Added failing backend tests for the new rule lifecycle semantics in
  `rule_engine/tests` and `decision_center/tests/test_api.py`.
- Added failing CLI tests for review-first editing, default-preserving updates,
  and deactivate behavior in `decision_center/tests/test_cli.py`.
- Added failing UI tests for rule review, editing, and deactivate behavior in
  `ui/src/components/ChatInterface.test.tsx`.
- Ran `.venv/bin/pytest -q` and confirmed the full Python suite passed
  (`51 passed`).
- Ran `npm test` in `ui/` and confirmed the UI test suite passed (`3 passed`).
- Ran `npm run build` in `ui/` and confirmed the production build succeeded.

**Key Findings:**

- The missing lifecycle state was the root cause for both products: without an
  explicit `active` flag, the CLI and UI had no safe way to retire rules while
  keeping them visible for audit and documentation.
- Showing the stored rule before prompting for edits is necessary in the CLI;
  otherwise the update path feels like re-creating a rule from scratch and
  invites accidental drift.
- The UI needed rule management in the same surface as creation. Loading an
  existing rule back into the builder keeps the mental model simple and avoids a
  separate edit screen.
- `npm run lint` still reports pre-existing repo-wide TypeScript `any` issues;
  they do not block runtime behavior, tests, or the production build, but they
  remain technical debt.

## Implementing Decision Center CLI Tool

**What was built:**

- Created a CLI tool (`decision_center/cli.py`) for the Decision Center to
  provide an interactive guided path for users.
- Features include: Prompting to boot internal servers (8001 and 8002),
  prompting to create/select a Business Rule Group, creating a Business Rule,
  and evaluating the rule automatically via API calls.

**How it was validated:**

- Structured 5-Round TDD Process defined in `agents.md`.
- Wrote failing unit tests for the CLI logic using `unittest.mock`.
- Built minimal implementations in `decision_center/cli.py` to satisfy each
  test.
- Ran the full `pytest` suite ensuring 100% test coverage for the changes and no
  regressions.

**Key Findings:**

- Prompting users sequentially for dynamic evaluation requires careful mock data
  mapping (`urllib.parse.quote` correctly encodes spaces to `%20` instead of
  `+`).
- Safely handling potential errors in synchronous API calls (`httpx.Client`) via
  basic JSON responses works well for a CLI interface.

## Extending CLI with Multi-LLM "Rule Wizard"

**What was built:**

- Added an optional LLM Rule Wizard directly into the CLI
  (`decision_center/cli.py`).
- Users can choose between **OpenAI** (gpt-5.2, gpt-5-mini, gpt-5-nano),
  **Anthropic** (Claude 4.6), and **Google Gemini** (3.1 Pro, 3 Flash).
- Implemented `decision_center/translator.py` which interfaces directly with
  each API's official Python SDK using strictly typed Pydantic models
  (Structured Outputs / Tool Calling) to extract `datapoints`, define
  constraints as `edge_cases`, and format `rule_logic`.
- Included interactive API Key smoke testing to prevent runtime errors later in
  the flow.
- Added an interactive refinement loop during rule creation, allowing users to
  review LLM outputs and optionally inject additional "edge case constraints".
  This triggers a recursive re-translation to guarantee manual conditions are
  correctly evaluated into structured JSON Logic.

**How it was validated:**

- Maintained the 5-Round TDD Process.
- Mocked out all 3 LLM SDK components (`openai.OpenAI`, `anthropic.Anthropic`,
  and `google.genai.Client`) directly in `test_translator.py` and `test_cli.py`
  to assert expected JSON schemas, connection behaviors, and CLI fallbacks.
- Full test suite passed without integration regressions (30 tests total).

**Key Findings:**

- Abstracting differing LLM SDK response pathways (OpenAI's `.parse()`,
  Anthropic's Tools, and Gemini's config schemas) into a single functional unit
  `translate_rule` keeps the CLI logic clean.
- Smoke-testing user-provided keys significantly improves CLI UX.
- The `basic_evaluate_rule` in the Decision Center needs to handle strings and
  LLM-style aliases (e.g., `=` mapped to `==`) as gracefully as strict numeric
  comparisons to be robust.

## JSON Logic Migration & Fail-Closed Hardening

**What was built:**

- Replaced the regex-based string evaluator with `json-logic-qubit` to
  deterministically evaluate business rules and edge cases formatted as JSON
  Logic.
- Updated Pydantic models in `rule_engine/models.py` and
  `decision_center/translator.py` (`rule_logic_json` and `edge_cases_json`) to
  parse the JSON logic from all 3 supported LLM providers.
- Modified the CLI tool to natively include JSON logic payloads and output them
  dynamically.
- Injected custom, strictly-typed operational overrides (`==`, `!=`, `<`, `>`,
  `<=`, `>=`) into `jsonLogic` from `decision_center/evaluator.py` to ensure
  type mismatches and missing payload values trigger critical ValueErrors.
- Implemented a "Fail-Closed" graceful severity downgrade mechanism (where
  `REJECT` defaults to `REJECT` and `APPROVE` defaults to `ASK_FOR_APPROVAL` if
  evaluation cannot complete).
- Restructured the `EvaluateRequest` return signatures and `DecisionResult`
  schema to include a `matched_details` payload, providing exact diagnostic
  traceability by exposing which specific edge cases or main rules triggered a
  decision.

**How it was validated:**

- Rewrote `decision_center/tests/test_evaluator.py` to pass equivalent strict
  JSON conditions through the overridden JSON logic implementation alongside
  legacy string fallbacks.
- Wrote full-blown E2E integration tests in `decision_center/tests/test_api.py`
  (`test_evaluate_with_json_logic`) to mock LLM interactions and verify that
  strictly typed rule structures directly execute during standard `v1/decide`
  requests.
- All 31 tests passed successfully.

**Key Findings:**

- Adopting the JSON Logic structure from `jsonlogic.com` offers deterministic
  nested condition handling, but since it is inherently "fail-open" based on
  JavaScript syntax (where string `costs` == `0` evaluates to False rather than
  Exception), relying purely on the library's built-in operators is highly
  insecure for access-control systems.
- Overwriting operators natively within the `jsonLogic` operation mapping allows
  developers to harness structured JSON rule representations while implementing
  rigid type enforcement internally.
- **OpenAI Structured Outputs vs. Dynamic Schemas:** OpenAI's `strict=True`
  Structured Outputs (triggered via `client.beta.chat.completions.parse`)
  enforce rigid, fully-defined property definitions. This fundamentally
  conflicts with nested, dynamic dictionaries required for JSON Logic arbitrary
  payloads. The solution relies on falling back to the standard `.create` method
  with `response_format={"type": "json_object"}` while manually injecting the
  Pydantic stringified schema directly into the prompt.

## Translator Edge Case Type Guard

**What was built:**

- Hardened `decision_center/translator.py` so `_validate_rule_payload()` only
  lowercases edge-case entries when they are actual strings.
- Preserved the existing validation contract for malformed model output:
  non-string `edge_cases` values now continue through Pydantic validation and
  raise `ValidationError` instead of crashing early with `AttributeError`.
- Added a regression test in `decision_center/tests/test_translator.py` that
  exercises `edge_cases` payloads containing `null` and numeric values.

**How it was validated:**

- Ran `.venv/bin/pytest decision_center/tests/test_translator.py -q` and
  confirmed the translator test module passed (`9 passed`).
- Ran `.venv/bin/pytest -q` and confirmed the full Python suite passed
  (`77 passed`).

**Key Findings:**

- The edge-case filtering logic was doing two jobs at once: removing known
  unwanted string patterns and implicitly assuming every model-provided value
  was already typed correctly. That assumption was the real bug.
- Guarding the string normalization step is sufficient here because it restores
  the intended failure mode without weakening the schema validation layer.

## Agent Permissions For HTTP MCP

**What was built:**

- Added a new auth domain in `mcp_server/auth.py` with:
  `agent_id` records, one-time enrollment tokens, scoped credentials,
  short-lived bearer tokens, and JSON-file persistence for registrations.
- Extended the HTTP MCP server in `mcp_server/server.py` to expose:
  admin routes for agent and credential management, an enrollment exchange
  route, an OAuth-style `/oauth/token` route, and bearer-token middleware for
  authenticated HTTP MCP traffic.
- Updated `evaluate_action` so authenticated requests carry `agent_id`,
  `credential_id`, `user_id`, and credential-bound rule-group selection into
  the Decision Center.
- Added `POST /v1/decide` to `decision_center/app.py` and expanded decision
  models and logs so atomic logs, chain events, and pending approvals now
  record identity metadata end to end.
- Wrote the missing schema contract in `spec/EVENT_SCHEMA.md` and updated
  `README.md` to document enrollment, token issuance, multi-credential agents,
  and the HTTP-only auth boundary.

**How it was validated:**

- Added `mcp_server/tests/test_auth.py` to cover persistent agent/credential
  state, one-time enrollment semantics, bearer-token protection, and principal
  propagation through the wrapped HTTP app.
- Added MCP tool regression coverage in `mcp_server/tests/test_tools.py` for
  authenticated `evaluate_action`, including `user_id` enforcement and identity
  propagation to the Decision Center payload.
- Added Decision Center API coverage in `decision_center/tests/test_api.py` to
  verify that authenticated identity fields land in atomic logs, chain events,
  and pending approvals.
- Ran `.venv/bin/pytest -q` and confirmed the full suite passed
  (`154 passed`).

**Key Findings:**

- The cleanest fit for this repo was not a full external identity provider but
  a lightweight split: durable client registrations on disk, short-lived access
  tokens in memory, and explicit HTTP middleware around the MCP transport.
- `agent_id`, `credential_id`, and `user_id` must remain separate fields.
  Collapsing them would destroy the audit value of scoped credentials and
  acting-on-behalf-of attribution.
- Authenticated MCP is materially cleaner on HTTP than on `stdio`. Treating
  `stdio` as dev-only when auth is enabled avoids inventing a second,
  incompatible credential story.

## Agent Admin UI And CLI

**What was built:**

- Added a new operator-facing admin panel in
  `ui/src/components/AgentAdminPanel.tsx` and embedded it into the existing
  settings modal in `ui/src/App.tsx`.
- The UI now lets operators:
  create agents, issue one-time enrollment tokens, and revoke credentials
  against the MCP server's admin API.
- Added typed admin API helpers in `ui/src/api.ts` and new frontend types in
  `ui/src/types.ts` for agents, credentials, and enrollment token responses.
- Added a new CLI entrypoint in `mcp_server/admin_cli.py` and exposed it as the
  `uo-agent-admin` console script through `pyproject.toml`.
- Updated the README and UI docs so operators have both browser and terminal
  workflows documented.

**How it was validated:**

- Added frontend API coverage in `ui/src/api.test.ts` for the new admin
  endpoints and header handling.
- Added component-level UI coverage in
  `ui/src/components/AgentAdminPanel.test.tsx` for the full workflow:
  connect, create agent, issue enrollment token, and revoke credential.
- Added App integration coverage in `ui/src/App.test.tsx` to verify the admin
  panel is reachable from the settings modal.
- Added CLI coverage in `mcp_server/tests/test_admin_cli.py` for the
  `create-agent`, `issue-enrollment-token`, and `revoke-credential` commands.
- Ran `.venv/bin/pytest -q` and confirmed the Python suite passed
  (`157 passed`).
- Ran `cd ui && npm test` and confirmed the UI suite passed (`31 passed`).

**Key Findings:**

- The existing settings modal was the right place for operator controls because
  it already owned environment-level configuration. Adding agent admin there
  kept the UI discoverable without creating a disconnected second workspace.
- Enrollment-token handling needs explicit one-time UX. Operators should see
  the token clearly at issuance time because the backend does not support
  retrieving the secret later.
- The CLI and UI are now thin shells over the same admin API, which keeps
  operational behavior aligned and reduces drift between manual and scripted
  workflows.

## Admin Group Selectors And Scope Clarification

**What was built:**

- Reworked the agent admin UI in `ui/src/components/AgentAdminPanel.tsx` so
  `Default Group` and `Allowed Groups` are populated from live rule groups
  fetched from the Rule Engine instead of raw text inputs.
- Updated the MCP admin CLI in `mcp_server/admin_cli.py` with a
  `--rule-engine-url` option and interactive group selection when
  `--default-group-id` or `--allowed-group-id` are omitted.
- Clarified in the docs that scopes are currently carried through enrollment,
  token issuance, and audit records, but rule-group binding is the actual
  enforcement mechanism in the current implementation.

**How it was validated:**

- Extended `ui/src/components/AgentAdminPanel.test.tsx` to verify group
  selection through real UI controls backed by fetched group options.
- Extended `mcp_server/tests/test_admin_cli.py` to verify interactive CLI
  selection against discovered rule groups from the Rule Engine API.
- Ran `.venv/bin/pytest -q` and confirmed the Python suite passed
  (`158 passed`).
- Ran `cd ui && npm test` and confirmed the UI suite passed (`31 passed`).

**Key Findings:**

- Group IDs are infrastructure detail. Asking operators to type them by hand
  was avoidable friction and a likely source of bad credentials.
- The current scope model should be documented conservatively until there is a
  second authorization layer that actually enforces scope semantics beyond
  group binding.

## Admin Panel Connection Persistence And Feedback

**What was built:**

- Updated `ui/src/components/AgentAdminPanel.tsx` so the panel now auto-connects
  on mount when `mcp_admin_base_url` and `mcp_admin_api_key` are already stored
  in `sessionStorage`.
- Added explicit success notices for:
  admin API connection, agent creation, enrollment token issuance, and
  credential revocation.
- Tightened the enrollment button logic so the UI clearly communicates that the
  admin API must be connected before credentials can be issued.

**How it was validated:**

- Added UI regression coverage in
  `ui/src/components/AgentAdminPanel.test.tsx` for automatic reconnect behavior.
- Added App-level coverage in `ui/src/App.test.tsx` to verify that reopening the
  settings modal restores the connected admin panel state instead of forcing
  the operator to reconnect manually.
- Ran `cd ui && npm test` and confirmed the UI suite passed (`33 passed`).
- Ran `.venv/bin/pytest -q` and confirmed the Python suite remained green
  (`158 passed`).

**Key Findings:**

- The original admin panel state was local component state only. Closing the
  settings modal destroyed that state even though the connection inputs were
  already persisted.
- Admin flows need visible feedback, especially when the same modal also
  handles unrelated LLM settings. Silent success looked indistinguishable from
  failure.

## Dedicated Agent Admin Workspace And Optional Scopes

**What was built:**

- Moved agent authentication management out of the LLM provider modal and into
  its own dedicated `Agent Admin` workspace accessible from the sidebar.
- Made enrollment-token scopes optional in the MCP admin API, CLI, and UI while
  keeping them documented and persisted when provided.
- Persisted the latest issued enrollment token in browser session storage so it
  remains visible after closing and reopening the UI.

**How it was validated:**

- Updated `ui/src/App.test.tsx` to verify that agent admin no longer appears in
  the LLM settings modal and opens instead as its own workspace from the
  sidebar.
- Updated `ui/src/components/AgentAdminPanel.test.tsx` to verify that token
  issuance works without scopes and that the most recent token is restored from
  session storage.
- Updated `mcp_server/tests/test_admin_cli.py` to verify CLI enrollment token
  issuance without `--scope`.
- Ran `cd ui && npm test`.
- Ran `.venv/bin/pytest -q`.

**Key Findings:**

- Agent onboarding is operational state, not LLM provider configuration. Giving
  it a dedicated workspace makes the flow persistent and easier to manage.
- Enrollment tokens behave like secrets and need persistence at the operator UI
  layer because the backend intentionally only returns them once.
- Persisting only one global latest token created a misleading UX where
  switching agents made it look like different agents shared the same token.
  Token persistence needs to be keyed by `agent_id`.

## Agent Admin Overlay And Richer Cards

**What was built:**

- Reworked the Agent Admin workspace so agent-specific management now opens in
  an overlay instead of expanding inline below the card grid.
- Enriched agent cards to carry status badges, credential counts, and latest
  token metadata directly on the card so operators can scan the fleet before
  opening any detail view.
- Preserved the existing enrollment and revocation workflows inside the new
  overlay context.

**How it was validated:**

- Extended `ui/src/components/AgentAdminPanel.test.tsx` to verify:
  - agent context stays hidden until a card is opened
  - the card opens a dialog-style overlay
  - the overlay can be closed again
  - card summaries show credential counts and latest token metadata
- Ran `cd ui && npx vitest run src/components/AgentAdminPanel.test.tsx src/App.test.tsx`.
- Ran `cd ui && npm test`.

**Key Findings:**

- Inline admin detail views made the workspace feel heavier than the rule
  library. The overlay preserves the browse-first rhythm while still allowing
  dense operational controls.
- Once token and credential summary state is visible on the cards, operators do
  not need to open each agent just to answer basic inventory questions.

## Public Bootstrap Instructions Endpoint

**What was built:**

- Added a public `GET /instructions` endpoint to the MCP server so agents can
  fetch the bootstrap recipe before they are authenticated.
- The endpoint returns simple JSON with relative paths like
  `/v1/agents/enroll` and `/oauth/token` plus a `same_host_as` field derived
  from the incoming request, so no LAN IP or hostname is hardcoded into the
  payload.
- Kept the endpoint outside bearer-token enforcement so a fresh agent can read
  the bootstrap instructions before enrollment.

**How it was validated:**

- Added `test_bootstrap_instructions_are_public_and_use_relative_paths` in
  `mcp_server/tests/test_auth.py`.
- Ran `.venv/bin/pytest mcp_server/tests/test_auth.py -q`.
- Ran `.venv/bin/pytest -q`.

**Key Findings:**

- Bootstrap instructions have to live outside the authenticated MCP session or
  they arrive too late to solve the enrollment problem.
- Returning relative paths is clearer and safer than hardcoding a specific
  machine IP into the instructions payload.

## Streamable HTTP MCP Lifespan Fix

**What was built:**

- Fixed the authenticated Streamable HTTP MCP endpoint so mounted `/mcp`
  requests now start the MCP sub-application lifecycle correctly.
- Added a regression test that performs a real authenticated `initialize`
  request against `/mcp` after enrollment and bearer-token issuance.

**How it was validated:**

- Reproduced the original failure locally and confirmed the root cause was:
  `RuntimeError: Task group is not initialized.`
- Added `test_streamable_http_mcp_initialize_works_after_auth` in
  `mcp_server/tests/test_auth.py`.
- Ran `.venv/bin/pytest mcp_server/tests/test_auth.py -q`.
- Ran `.venv/bin/pytest -q`.

**Key Findings:**

- The MCP app was mounted into the FastAPI wrapper, but its own lifespan was
  not being entered. That left the Streamable HTTP session manager unstarted,
  so authenticated JSON-RPC requests to `/mcp` crashed with a server-side 500.
- After the wrapper began entering the mounted app's lifespan, `/mcp`
  initialization succeeded as expected.

## Bootstrap Re-Authentication Guidance

**What was built:**

- Tightened the public `/instructions` payload so it now explicitly tells agents
  not to consume a one-time enrollment token again after they have already
  enrolled once.
- Added a direct re-authentication instruction telling agents to reuse their
  stored `client_id` and `client_secret` to request a fresh access token.

**How it was validated:**

- Updated the bootstrap instructions contract test in
  `mcp_server/tests/test_auth.py`.
- Ran `.venv/bin/pytest mcp_server/tests/test_auth.py -q`.
- Ran `.venv/bin/pytest -q`.

**Key Findings:**

- The confusing behavior was not in the auth backend any more; it was in the
  agent-side interpretation of the bootstrap flow after a successful first
  enrollment.
- Making the retry path explicit in `/instructions` reduces the chance that an
  agent will treat a normal reconnect as a request for a new one-time token.

## MVP Auth State Now Matches In-Memory Rule State

**What was built:**

- Removed on-disk persistence for MCP agent registrations, enrollment tokens,
  and credentials so the auth layer now matches the MVP's in-memory-only rule
  model.
- Simplified `AuthStore` in `mcp_server/auth.py` into an in-memory container and
  removed the `--auth-store-path` server option from `mcp_server/server.py`.
- Updated `README.md` to state clearly that restarting the MCP server clears
  agent auth state.

**How it was validated:**

- Replaced the auth persistence regression in `mcp_server/tests/test_auth.py`
  with a test that proves a fresh auth store does not contain prior agents or
  credentials.
- Ran `.venv/bin/pytest mcp_server/tests/test_auth.py -q`.
- Ran `.venv/bin/pytest -q`.

**Key Findings:**

- Persisting agent auth state while rules disappeared on restart created an
  inconsistent MVP boundary and implied a durability guarantee the rule system
  does not currently provide.
- Keeping both rules and auth state ephemeral is architecturally clearer until
  the project is ready to persist both sides together.

## Backend Stack Restart Script

**What was built:**

- Added `scripts/start_backend_stack.sh` as a single local launcher for the MVP
  backend stack.
- The script activates `.venv`, stops any existing Rule Engine, Decision
  Center, or MCP server processes matching the expected commands, then starts:
  `rule_engine` on `:8001`, `decision_center` on `:8002`, and the authenticated
  Streamable HTTP MCP server on `:8000`.
- Updated `README.md` so the quick-start flow includes the one-command restart
  path.

**How it was validated:**

- Added `tests/test_dev_scripts.py` to lock in the script path and the expected
  backend commands.
- Ran `.venv/bin/pytest tests/test_dev_scripts.py -q`.
- Ran `bash -n scripts/start_backend_stack.sh`.
- Ran `.venv/bin/pytest -q`.

**Key Findings:**

- The repo had no single restart command for the three backend services, which
  made it easy to leave stale local processes behind while switching between
  auth and non-auth runs.
- Matching the exact launch command strings is a pragmatic MVP way to clean up
  old local backend processes without introducing a heavier process manager.

## Agent Admin No Longer Shows Stale Persisted Agents

**What was built:**

- Removed the UI behavior that created synthetic agent cards from locally
  persisted enrollment-token state.
- Updated `ui/src/components/AgentAdminPanel.tsx` so the Agent Admin workspace
  now shows only agents returned by the live MCP admin API.
- Added pruning of stale local token entries whenever the admin API refreshes
  and an agent no longer exists on the backend.

**How it was validated:**

- Updated `ui/src/components/AgentAdminPanel.test.tsx` to verify that stale
  local agent/token state disappears after a backend restart.
- Ran `cd ui && npm test -- --run src/components/AgentAdminPanel.test.tsx`.
- Ran `cd ui && npm test`.
- Ran `.venv/bin/pytest -q`.

**Key Findings:**

- Persisting the latest token per agent is still useful, but only as metadata
  attached to a live server agent.
- Letting local token cache fabricate agent cards made the UI contradict the
  MVP's in-memory backend model and confused operators after every restart.

## Agent Admin Allowed Groups Uses Direct Toggles

**What was built:**

- Replaced the browser-native multi-select listbox for `Allowed Groups` in
  `ui/src/components/AgentAdminPanel.tsx` with an explicit checkbox list.
- Operators can now add or remove allowed rule groups one by one without using
  modifier keys or relying on browser-specific multi-select behavior.
- Updated the UI copy so the control explains the actual policy meaning instead
  of keyboard instructions.

**How it was validated:**

- Added UI coverage in `ui/src/components/AgentAdminPanel.test.tsx` for adding
  and removing allowed groups via direct toggles.
- Ran `cd ui && npm test -- --run src/components/AgentAdminPanel.test.tsx`.
- Ran `cd ui && npm test`.
- Ran `.venv/bin/pytest -q`.

**Key Findings:**

- The native multi-select was a poor fit for this operator workflow and made it
  look like all groups were permanently selected.
- A checkbox list matches the permission model much more clearly: each allowed
  group is an explicit on/off decision.

## Agent Admin Keeps Default Group Draft State

**What was built:**

- Updated `ui/src/components/AgentAdminPanel.tsx` so the selected default group
  is treated as implicitly allowed and shown as a disabled, greyed-out entry in
  the allowed-groups checklist.
- Added per-agent enrollment form draft persistence in session storage so
  closing and reopening the same agent context no longer clears the selected
  default group or other in-progress enrollment fields.

**How it was validated:**

- Extended `ui/src/components/AgentAdminPanel.test.tsx` with coverage for:
  default-group implicit allow behavior and reopening the agent context with the
  same draft state still present.
- Ran `cd ui && npm test -- --run src/components/AgentAdminPanel.test.tsx`.
- Ran `.venv/bin/pytest -q`.

**Key Findings:**

- The default group is not a separate policy choice from allowed groups; it is
  a stronger statement that should visually read as already included.
- Draft loss on close made the overlay feel unreliable. Storing per-agent draft
  state keeps the operator workflow stable without changing backend behavior.

## Agent Admin Draft Loop Freeze Fix

**What was built:**

- Fixed the Agent Admin enrollment form freeze caused by the new per-agent
  draft persistence logic.
- `ui/src/components/AgentAdminPanel.tsx` now hydrates draft state only when
  the selected agent changes, instead of replaying persisted draft state back
  into the form on every keystroke.
- Added a guard so identical draft writes do not trigger redundant state
  updates.

**How it was validated:**

- Extended `ui/src/components/AgentAdminPanel.test.tsx` to verify the form
  remains editable after choosing a default group.
- Ran `cd ui && npm test -- --run src/components/AgentAdminPanel.test.tsx`.
- Ran `cd ui && npm test`.
- Ran `.venv/bin/pytest -q`.

**Key Findings:**

- The freeze was a client-side rerender loop, not a backend issue.
- Persisting draft state is still useful, but the component must treat the
  live form fields as the source of truth while the overlay is open.

## HTTP Auth Bootstrap Routes Fail Closed

**What was built:**

- Updated `mcp_server/server.py` so the auth bootstrap surface
  (`/v1/admin/*`, `/v1/agents/enroll`, `/oauth/token`, `/instructions`) is
  only registered when authenticated HTTP mode is actually enabled and backed
  by an `AuthService`.
- Added a construction-time guard so `build_http_app(...)` now raises
  immediately if `auth_enabled=True` is paired with `auth_service=None`.
- Tightened `main()` so starting the server with `--admin-api-key` but without
  `--auth-enabled` exits early instead of serving a misleading partial config.
- Updated `docs/connecting-agents.md` and `README.md` so the documented startup
  path matches the enforced contract.

**How it was validated:**

- Added coverage in `mcp_server/tests/test_auth.py` for:
  auth-disabled apps returning `404` for the auth bootstrap surface,
  `build_http_app(...)` rejecting `auth_enabled=True` without an auth service,
  and `main()` rejecting `--admin-api-key` without `--auth-enabled`.
- Ran `.venv/bin/pytest mcp_server/tests/test_auth.py -k "main_requires_auth_enabled_when_admin_api_key_is_set or does_not_expose_auth_routes_when_auth_is_disabled or requires_auth_service_when_auth_is_enabled"`.
- Ran `.venv/bin/pytest tests/test_dev_scripts.py`.

**Key Findings:**

- The original crash was caused by route registration, not the auth middleware:
  handlers were present even when the auth backend was absent.
- Failing closed at route registration plus startup validation is safer than
  letting the server boot into a partially configured auth surface.

## CLI Datapoint Sync Failures No Longer Abort Rule Creation

**What was built:**

- Updated `decision_center/cli.py` so the LLM rule wizard treats datapoint
  definition sync as best-effort after translation succeeds.
- A failed `PATCH /v1/groups/{group_id}/datapoints` request now prints a
  warning and still proceeds to save the translated rule instead of dropping
  into manual fallback.
- Added explicit regression coverage in
  `decision_center/tests/test_cli.py` for the request-error case.
- Updated `docs/cli-wizard.md` to document that datapoint-definition sync is
  attempted automatically but does not block rule creation if the Rule Engine
  is temporarily unavailable.

**How it was validated:**

- Ran `.venv/bin/pytest decision_center/tests/test_cli.py -k "schema_extension_retry or swap_datapoint or saves_new_datapoints"`.
- Ran `.venv/bin/pytest decision_center/tests/test_cli.py -k "keeps_rule_when_datapoint_sync_fails or schema_extension_retry or swap_datapoint or saves_new_datapoints"`.
- Ran `.venv/bin/pytest decision_center/tests/test_cli.py`.
- Ran `.venv/bin/pytest decision_center/tests -q`.
- Ran `.venv/bin/pytest -q`.

**Key Findings:**

- The failing tests were not caused by translation logic. The translated rule
  was correct; the bug was that a later datapoint-definition sync error was
  caught by the broad translation fallback path.
- Treating datapoint sync as best-effort is the safer operator workflow:
  translated rules should not be discarded just because metadata persistence is
  temporarily unavailable.

---

## Agent Eval Harness

**Date:** 2026-03-16

**What was built:**

Implemented `evals/agent_eval/` — a fully deterministic, LLM-free end-to-end
evaluation harness for simulated agent behaviour. The harness validates that an
agent correctly calls the Decision Center, obeys APPROVE/REJECT/ASK_FOR_APPROVAL
outcomes, submits human approvals when required, and that the resulting audit
chain matches expected receipts.

**Architecture:**

- `models.py` — Pydantic models (`WorkflowStep`, `AgentScenario`, `ReceiptAssertion`,
  `StepResult`, `AgentRunResult`, `AgentEvalStats`) with validators enforcing
  that `human_approves` is set iff `expected_outcome == ASK_FOR_APPROVAL`, and
  that `receipt_assertions` length matches `workflow` length.
- `agent.py` — `SimulatedAgent`: a state machine that posts to `/v1/decide` and,
  for `ASK_FOR_APPROVAL` outcomes, immediately follows up with
  `/v1/decide/{request_id}/approve`. Accepts an injected `httpx.AsyncClient`
  for in-process ASGI testing.
- `receipt.py` — `validate_receipt`: fetches `/v1/logs/chains/{request_id}` and
  checks event types, EVALUATION outcome, and APPROVAL_STATUS details against
  a `ReceiptAssertion`.
- `runner.py` — `run_scenario`: creates a rule group, adds rules, runs each
  workflow step, validates receipts, and deletes the group unless `keep_group=True`.
  Returns an `AgentRunResult` with per-step details.
- `reporting.py` — `compute_stats` and `write_agent_eval_report`: compute
  four metrics (decision accuracy, obedience rate, receipt validity, human loop
  completion) and write a versioned markdown report.
- `cli.py` — `uo-agent-eval` console script with `--domain`, `--scenario`,
  `--report-dir`, `--keep-group`, and `--fail-on-missing-services` flags.
- `scenarios/finance.py` — 6 finance scenarios covering APPROVE, REJECT,
  ASK_FOR_APPROVAL (approved and rejected), multi-step mixed workflow, and
  fail-closed missing-data.
- `scenarios/ecommerce.py` — 3 ecommerce scenarios covering APPROVE, REJECT,
  and ASK_FOR_APPROVAL.

**Tests added (`evals/agent_eval/tests/`):**

- `test_models.py` — Pydantic validator edge cases.
- `test_scenarios.py` — Schema and invariant checks across all 9 scenarios.
- `test_agent.py` — Unit tests for `SimulatedAgent` with mock `httpx.AsyncClient`.
- `test_receipt.py` — Unit tests for `validate_receipt` covering all assertion paths.
- `test_runner.py` — Integration tests using in-process ASGI transport against
  real rule engine and decision center apps; patches `_fetch_group` to avoid
  live HTTP.
- `test_reporting.py` — Tests for `next_report_path` versioning, `compute_stats`,
  and `write_agent_eval_report`.
- `test_cli.py` — Tests for `_run` exit codes and `_get_scenarios` filtering.

**Key design decisions:**

- No LLM calls anywhere in the harness — all scenarios use pre-translated JSON
  Logic rules so results are fully reproducible.
- `SimulatedAgent` accepts an optional injected client so tests never touch a
  live network.
- The store reset fixture in `test_runner.py` uses the correct attribute names
  (`atomic_logs`, `chains`, `pending`) discovered by reading
  `decision_center/store.py`.
- `uo-agent-eval` is registered as a console script alongside `uo-stress-test`
  and `uo-agent-admin`.

**How it was validated:**

- All unit tests (models, scenarios, agent, receipt, reporting, cli) are
  self-contained and require no running services.
- `test_runner.py` uses `httpx.ASGITransport` with the real FastAPI apps to
  exercise the full pipeline in-process.
