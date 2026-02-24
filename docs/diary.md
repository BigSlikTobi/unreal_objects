# Unreal Objects Diary

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
