# 🖥️ React UI — Visual Rule Builder

The React UI gives you a point-and-click interface for building and testing
governance rules — no terminal required.

## Start the UI

```bash
# Boot the backend services first (see Quick Start in the main README)
cd ui
npm install
npm run dev   # → http://localhost:5173
```

---

## Structured Rule Builder

Instead of typing free-form text, the UI uses a **fill-in-the-blank builder** in
the center column and a **rule library panel** on the right:

```
IF [amount > 500 ──────────────────] THEN [ASK_FOR_APPROVAL ▼] ELSE [─── ▼]
↳ IF [open_bills_count > 10 ───────] THEN [REJECT ▼]  [✕]
↳ IF [user_region == "EU" ─────────] THEN [ASK_FOR_APPROVAL ▼]  [✕]

[+ Add Edge Case]                              [✦ Translate with AI →]
```

- **Main rule row** — condition input + `THEN` outcome dropdown + optional
  `ELSE` branch
- **Edge case rows** — amber-bordered rows, each with their own condition +
  outcome + remove button
- **Right-side rule library** — saved rules as cards; selecting a card loads it
  into the builder
- **Lifecycle feedback** — deactivating or reactivating a rule posts a
  confirmation message into the chat transcript
- **"Translate with AI"** — sends the complete structured state to the LLM in
  one shot; every translate is a fresh complete translation
- **Theme toggle** — dark mode changes the entire shell, drawers, and form
  controls together
- **Responsive layout** — on mobile, group list and rule library collapse into
  slide-over panels
- **Motion polish** — rule drawers and test console animate in from the
  side/bottom

---

## LLM Wizard Flow

1. Fill in the condition (`amount > 500`) and select an outcome
   (`ASK_FOR_APPROVAL`)
2. Optionally add edge cases with **+ Add Edge Case**
3. Click **Translate with AI** — the UI builds a precise structured prompt and
   sends it to your configured LLM (OpenAI / Anthropic / Gemini)
4. Review the **Proposed Logic** card — inspect extracted datapoints, edge
   cases, and main rule logic
5. Use the **rule library panel** to review previously saved rules
6. Choose an action:
   - **Accept & Save** — persist the rule to the Rule Engine
   - **Save & Test** — save and open the Test Console immediately
   - **Deactivate / Reactivate** — keep the rule for documentation while
     removing or restoring it from live evaluation
   - **Add Edge Case** — add another row and re-translate
   - **Optimize** — update fields and re-translate
   - **Refuse** — discard and clear the builder
7. After a save, the builder stays attached to that saved rule so you can keep
   iterating. Use **Stop Editing** to clear the builder and leave edit mode.

---

## Test Console

After saving a rule, the built-in **Test Console** lets you simulate agent
payloads and see the exact decision outcome in real time — no separate tool
needed.

---

## Agent Admin Panel

The sidebar includes an **Agent Admin** workspace for managing AI agent
permissions without touching the terminal:

- Create agents and assign names/descriptions
- Issue one-time enrollment tokens with scopes and group bindings
- Revoke credentials

The Agent Admin workspace calls the MCP server's admin HTTP endpoints and
requires the MCP base URL and admin API key (usually configured via the settings
panel).
