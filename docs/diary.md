# Unreal Objects Diary

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
