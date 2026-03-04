# 🎮 Interactive CLI Wizard

A native CLI tool hooked up to modern LLMs (OpenAI, Anthropic, Gemini) that lets
you create and test governance rules entirely from the terminal — using the same
**fill-in-the-blank builder** as the React UI.

## 1. Boot the Core Servers

The CLI will offer to start the servers automatically, or run them manually:

```bash
source .venv/bin/activate
uvicorn rule_engine.app:app --port 8001 &
uvicorn decision_center.app:app --port 8002 &
```

## 2. Launch the Rule Wizard

```bash
python decision_center/cli.py
```

## 3. Wizard Flow

1. **Pick a Provider** — select OpenAI, Anthropic, or Gemini and enter your API
   key (or set `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` in your
   environment).
2. **Select a Group** — choose an existing rule group or create a new one.
3. **Name your rule** and set a **Feature** label (e.g. `Fraud Check`).
4. **Choose a Schema** — optionally lock the LLM to the E-Commerce or Finance
   blueprint.
5. **Fill in the builder** — the same structured IF / THEN / ELSE pattern as the
   UI:

```
--- Rule Builder ---
  IF   : amount > 500

  THEN :
    1. APPROVE
    2. ASK_FOR_APPROVAL
    3. REJECT
  Select [1-3]: 2

  ELSE : (optional)
    4. (none — skip ELSE branch)
  Select [1-4]: 4

  Add an edge case? [y/N]: y
    IF   : open_bills_count > 10
    THEN : REJECT

  Add an edge case? [y/N]: n
```

6. **Review the proposal** — the wizard shows extracted datapoints, edge cases,
   and the generated JSON Logic.
7. **Accept, Edit, deactivate, or fall back to Manual** — the wizard shows the
   current stored rule before editing, lets you update only the fields you want
   to change, and can mark a rule inactive without deleting it.
8. **Auto-Test** — immediately simulate an agent payload against the saved rule
   and see the exact decision outcome.
