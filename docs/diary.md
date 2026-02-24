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
  (Structured Outputs / Tool Calling) to extract `datapoints` and format
  `rule_logic`.
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
