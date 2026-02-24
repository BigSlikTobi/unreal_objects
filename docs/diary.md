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
