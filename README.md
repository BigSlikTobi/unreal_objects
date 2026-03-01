<div align="center">
  <h1><img src="assets/unreal_objects_logo.png" alt="Unreal Objects Mascot" width="75" style="vertical-align: middle;"/> Unreal Objects <img src="assets/unreal_objects_logo.png" alt="Unreal Objects Mascot" width="75" style="vertical-align: middle;"/> </h1>
  <p><b>Accountability infrastructure for autonomous systems.</b></p>
</div>

---

## 🔮 What is Unreal Objects?

As AI agents become more autonomous, they start doing things that impact the
real world—spending money, sending emails, or changing systems. **Unreal
Objects** is the safety net that sits between your AI agent and reality.

It safely records, explains, and **governs** every automated decision _before_
it executes. If an agent tries to do something sensitive, Unreal Objects catches
it, evaluates it against your business rules, and transparently routes it for
Human-in-the-Loop approval.

Think of it as **Autonomy with Receipts.** 🧾

---

## ✅ What Unreal Objects is — and what it is not

This is the most important thing to understand before you write your first rule.
Get this wrong and your rules will fight the agent instead of guarding it.

### The agent decides. Unreal Objects governs.

An AI agent is autonomous by design. It reads context, reasons about a
situation, and decides what action to take. That autonomy is the whole point —
if you wanted a scripted system, you would not use an agent.

**Unreal Objects does not take that autonomy away.** It does not tell the agent
what to do. It governs *how* the agent's own decisions are processed — whether
they execute immediately, require human sign-off, or are blocked entirely.

```
Agent reasons:   "Given this situation, I should send an email to the client."
                                          │
                                          ▼
                    evaluate_action("Send email to client", context)
                                          │
                              Unreal Objects evaluates:
                     "IF contact_person is premium THEN ASK_FOR_APPROVAL"
                                          │
                              ┌───────────┼───────────┐
                           APPROVE   ASK_FOR_   REJECT
                        (agent sends) APPROVAL (blocked)
                                     (human decides;
                                     agent sends if approved)
```

The agent made the decision to send the email. Unreal Objects decided the
*conditions* under which that decision executes.

---

### ✅ This IS how business rules work here

Rules describe **conditions on an action the agent has already chosen to take.**

| Rule | What it means |
|---|---|
| `IF contact_person == 'premium' THEN ASK_FOR_APPROVAL` | When the agent sends anything to a premium contact, pause and get a human to sign off first |
| `IF transfer_amount > 10000 THEN REJECT` | Block any transfer the agent tries above this threshold, unconditionally |
| `IF recipient_country NOT IN approved_list THEN ASK_FOR_APPROVAL` | Flag cross-border actions for review, regardless of what the agent intended |
| `IF file_path CONTAINS '/etc/' THEN REJECT` | The agent cannot write to system directories, ever |

These rules fire at the moment the agent **acts**. They say nothing about what
the agent should or should not decide to do — only about how that decision is
processed when it arrives.

---

### ❌ This is NOT how business rules work here

Rules that prescribe **what the agent should do** are process instructions, not
governance rules. They do not belong here.

| Rule | Why it's wrong |
|---|---|
| `IF contact_person == 'premium' THEN send_email` | This tells the agent to act — that is the agent's job, not a governance rule |
| `IF order_value > 500 THEN notify_customer` | This is a business process step, not a guardrail |
| `IF user is inactive THEN deactivate_account` | Automation logic — should live in the agent's reasoning, not in the rule engine |

Writing rules like this would create a second decision layer on top of the
agent's own reasoning, making behaviour unpredictable and the agent's autonomy
meaningless. The agent would become a pass-through for your rule engine rather
than an intelligent reasoner.

---

### The line in one sentence

> **The agent decides what to do. Unreal Objects decides whether, and under what
> conditions, that decision is allowed to execute.**

---

## 📈 Stress-Test Snapshot

The project now carries a schema-aware generative evaluation harness with
reusable baselines, candidate dataset generation, and explicit dataset
promotion. The current checked-in stress-test state by schema is:

| Schema | Status | Current Signal | Evidence |
| ------ | ------ | -------------- | -------- |
| **E-Commerce** | `Strongest committed evidence` | Full end-to-end stress-test report checked in | `evals/generative_evaluation_report_v5.md` |
| **Finance** | `Committed schema report available` | Full finance-schema report now checked in, with reusable baseline for follow-up runs | `evals/generative_evaluation_report_v6.md` |
| **No Schema** | `CLI-ready` | Evaluation path supported, but no committed baseline/report yet | Generated on demand via CLI |

```text
Trust Signal Summary

E-Commerce   [##########] 98.7% committed full-report pass rate
Finance      [#########-] 92.3% committed finance-schema pass rate
No Schema    [####------] CLI path ready, baseline/report not committed yet
```

This is meant as a trust signal, not marketing gloss:

- **E-Commerce** has the strongest committed evidence today, with a checked-in
  end-to-end report showing **98.7%** pass rate across **532** cases.
- **Finance** now also has a checked-in schema-specific report showing
  **92.3%** pass rate across **519** cases, alongside its reusable baseline
  dataset for repeat runs.
- **No schema** is supported by the same CLI and evaluation pipeline, but no
  committed baseline/report is checked in yet.

## 🏗️ Architecture

Unreal Objects is cleanly decoupled into modular services:

| Service                       | Port    | Purpose                                                                        |
| ----------------------------- | ------- | ------------------------------------------------------------------------------ |
| 📏 **Rule Engine**            | `:8001` | CRUD for rule groups, rules, and datapoint definitions                         |
| 🧠 **Decision Center**        | `:8002` | Evaluates actions against rules; maintains immutable audit log                 |
| 🔌 **MCP Server**             | `:8000` | [Model Context Protocol](https://modelcontextprotocol.io) bridge for AI agents |
| 🖥️ **React UI**               | `:5173` | Visual rule builder with structured fill-in-the-blank editor and test console  |

---

## 🛠️ Quick Start & Setup

Requires **Python 3.11+** and **Node.js 18+**.

```bash
# 1. Python backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Start the services
uvicorn rule_engine.app:app --port 8001 &
uvicorn decision_center.app:app --port 8002 &

# 3. MCP Server (for AI agents)
python mcp_server/server.py --transport streamable-http --host 0.0.0.0 --port 8000 --group-id <your-group-id> &

# 4. React UI (optional — open http://localhost:5173)
cd ui && npm install && npm run dev

# 5. Run the test suite
pytest -v
```

---

## ⚙️ The Rule Engine

The core heart of Unreal Objects is the **Rule Engine** and its twin, the
**Decision Center**. Together, they form an isolation layer that inspects the
chaotic, unpredictable outputs of an LLM agent and enforces strict,
deterministic business conditions.

### How Decisions Are Made (The Evaluation Pipeline)

When an AI agent requests to take an action (e.g., spending company money,
sending an email), the Decision Center funnels that request through a 3-step
pipeline safely governed by the Rule Engine's stored groups.

```text
 [AI Agent] 
     │ 
     ▼ (Request: "I want to purchase a laptop for $750")
┌─────────────────────────────────────────────────────────┐
│                  DECISION CENTER                        │
│                                                         │
│  1. Context parsing mapped against Datapoints           │
│       (e.g., {"amount": 750})                           │
│                          │                              │
│  2. ⚡️ Edge Case Evaluation  [FAIL-CLOSED]              │
│       Checks conditions:   "amount > 10000 -> REJECT"   │
│       (If triggered, execution STOPS immediately)       │
│                          │                              │
│  3. 🧠 Core Rule Logic Evaluation (JSON Logic)          │
│       Checks condition:  "amount > 500 -> ASK"          │
│                          │                              │
│  4. 🧾 Immutable Audit Trail Logged                     │
└──────────────────────────┼──────────────────────────────┘
                           ▼
                   [Outcome Enforced]
                (e.g., "ASK_FOR_APPROVAL")
```

- **Fail-Closed by Default:** Any missing data, type mismatches (e.g., putting a
  string "750" in a numeric operation), or evaluation timeouts instantly
  hard-fail to `ASK_FOR_APPROVAL` or `REJECT`.
- **JSON Logic Engine:** Under the hood, we compile your natural language rules
  into highly resilient, strictly auditable AST representations known as
  [JsonLogic](http://jsonlogic.com/).
- **Rule lifecycle:** Rules are never required to be deleted to retire them.
  Each rule can be marked active or inactive. Inactive rules remain visible for
  documentation and audit history, but the Decision Center skips them during
  evaluation until they are reactivated.

### 📐 Schema Blueprints — Why They Matter

When the LLM translates a plain-English rule into JSON Logic it has to choose
variable names. Without guidance it invents them freely — the same concept might
become `amount` in one rule, `transaction_amount` in the next, and
`purchase_amount` in a third. Your AI agent only sends one name in its payload,
so the other two rules silently fail to match.

**Schemas fix this by locking the LLM to a pre-approved vocabulary.** Every rule
that uses the E-Commerce schema will always call the order total
`transaction_amount`, no matter how it was phrased in plain English — so all
rules stay consistent and your agent only needs to send one predictable payload.

| Schema         | Use when your rules are about…                                  |
| -------------- | --------------------------------------------------------------- |
| **No schema**  | Custom domains, or when your variable names are already decided |
| **E-Commerce** | Orders, payments, cart contents, shipping, user accounts        |
| **Finance**    | Withdrawals, balances, loans, KYC verification, AML risk scores |

> **Note:** Schemas are a strong nudge, not a hard validator. They work best
> when your rules genuinely belong to the domain the blueprint covers. For
> concepts outside the schema the LLM may still invent a name — if that happens,
> switch to No schema and name the variable explicitly in your condition.

---

## 🖥️ React UI — Visual Rule Builder

The React UI gives you a point-and-click interface for building and testing
governance rules — no terminal required.

### Start the UI

```bash
# Boot the backend services first (see Quick Start above)
cd ui
npm install
npm run dev   # → http://localhost:5173
```

### Structured Rule Builder

Instead of typing free-form text, the UI uses a **fill-in-the-blank builder**
in the center column and a **rule library panel** on the right. The builder
eliminates ambiguity during creation, while the rule library keeps saved rules
visible without pushing them into the chat transcript:

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
- **Right-side rule library** — saved rules appear as cards in a dedicated
  panel; selecting a card loads that rule into the builder for editing
- **Lifecycle feedback** — deactivating or reactivating a saved rule updates the
  card state and posts a clear confirmation message into the chat transcript so
  the action stays visible in the working flow
- **"Translate with AI"** — sends the complete structured state to the LLM in
  one shot; every translate is a fresh complete translation, so edge cases can
  never silently overwrite each other
- **Theme toggle** — dark mode is a class-based theme switch, so the entire
  shell, drawers, and form controls change together instead of only isolated
  components
- **Fresh rule state** — saved-rule lists are always re-fetched as live state,
  so deactivations and reactivations stay accurate after refreshes instead of
  showing stale cached cards
- **Responsive layout** — on mobile, the group list and rule library collapse
  into slide-over panels so rule review and editing still work on smaller
  screens
- **Motion polish** — rule drawers and the test console animate in from the
  side/bottom to preserve spatial context on mobile and desktop

### LLM Wizard Flow

1. Fill in the condition (`amount > 500`) and select an outcome
   (`ASK_FOR_APPROVAL`)
2. Optionally add edge cases with **+ Add Edge Case**
3. Click **Translate with AI** — the UI builds a precise structured prompt and
   sends it to your configured LLM (OpenAI / Anthropic / Gemini)
4. Review the **Proposed Logic** card — inspect extracted datapoints, edge
   cases, and main rule logic
5. Use the **rule library panel** to review previously saved rules. Selecting a
   rule card pulls it into the builder for editing.
6. Choose an action:
   - **Accept & Save** — persist the rule to the Rule Engine
   - **Save & Test** — save and open the Test Console immediately
   - **Deactivate / Reactivate** — keep the rule for documentation while
     removing or restoring it from live evaluation
   - **Add Edge Case** — add another row to the builder and re-translate
   - **Optimize** — update fields in the builder and re-translate
   - **Refuse** — discard and clear the builder
7. After a save, the builder stays attached to that saved rule so you can keep
   iterating without reselecting it from the rule library. Use **Stop Editing**
   when you want to clear the builder and leave edit mode. Leaving edit mode
   also clears the current rule selection, so the builder stays blank until you
   explicitly pick another saved rule.

### Test Console

After saving a rule, the built-in **Test Console** lets you simulate agent
payloads and see the exact decision outcome in real time — no separate tool
needed.

---

## 🎮 Interactive CLI Wizard

We've built a native CLI tool hooked up to modern LLMs (OpenAI, Anthropic,
Gemini) that lets you create and test governance rules entirely from the
terminal using the same **fill-in-the-blank builder** as the React UI.

### 1. Boot the Core Servers

The CLI will offer to start the servers automatically, or run them manually:

```bash
source .venv/bin/activate
uvicorn rule_engine.app:app --port 8001 &
uvicorn decision_center.app:app --port 8002 &
```

### 2. Launch the Rule Wizard

```bash
python decision_center/cli.py
```

### 3. Wizard Flow

1. **Pick a Provider** — select OpenAI, Anthropic, or Gemini and enter your API key (or set `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` in your environment).
2. **Select a Group** — choose an existing rule group or create a new one.
3. **Name your rule** and set a **Feature** label (e.g. `Fraud Check`).
4. **Choose a Schema** — optionally lock the LLM to the E-Commerce or Finance blueprint (see [Schema Blueprints](#-schema-blueprints--why-they-matter) above).
5. **Fill in the builder** — the same structured IF / THEN / ELSE pattern as the UI:

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

6. **Review the proposal** — the wizard shows extracted datapoints, edge cases, and the generated JSON Logic.
7. **Accept, Edit, deactivate, or fall back to Manual** — the wizard shows the
   current stored rule before editing, lets you update only the fields you want
   to change, and can mark a rule inactive without deleting it.
8. **Auto-Test** — immediately simulate an agent payload against the saved rule and see the exact decision outcome.

---

## 🤖 Connecting Your AI Agents

Instead of using the wizard's auto-tester, your actual autonomous AI agents
interact with Unreal Objects exclusively through the built-in **MCP Server**.
The MCP Server is the single enforced gateway between your agent and the real
world — it does not just advise the agent, it *is* the only path to real
actions.

### Starting the MCP Server

**Local / stdio** (for Claude Desktop or local agents):

```bash
python mcp_server/server.py --transport stdio --group-id <your-group-id>
```

**LAN / remote agents** (Streamable HTTP — recommended):

```bash
python mcp_server/server.py \
  --transport streamable-http \
  --host 0.0.0.0 \
  --port 8000 \
  --group-id <your-group-id>
```

**Legacy SSE** (still supported for backward compatibility):

```bash
python mcp_server/server.py --transport sse --host 0.0.0.0 --port 8000 \
  --group-id <your-group-id>
```

| Flag | Default | Purpose |
|---|---|---|
| `--transport` | `stdio` | `stdio`, `streamable-http`, or `sse` |
| `--host` | `127.0.0.1` | Bind address for HTTP transports |
| `--port` | `8000` | Port for HTTP transports |
| `--group-id` | *(none)* | Rule group applied to all evaluations — agent cannot override this |
| `--allowed-hosts` | auto | Comma-separated Host headers to accept; defaults to `*` when `--host 0.0.0.0` |

> **`--group-id` is the key security flag.** When set, every `evaluate_action`
> call is evaluated against that rule group. The agent never sees, chooses, or
> influences which ruleset applies to it.

### How the guardrail works

On every `initialize` handshake the MCP Server sends a mandatory protocol
statement directly to the agent via the MCP `instructions` field. This is
injected by the MCP client into the agent's context *separately from and in
addition to* any operator system prompt. The agent is told:

- Call `guardrail_heartbeat` on startup. Stop if the system is unhealthy.
- Call `evaluate_action` before every real-world action and obey the outcome absolutely.
- `APPROVE` → proceed. `REJECT` → stop and explain. `ASK_FOR_APPROVAL` → pause, surface to the human, call `submit_approval` with the human's decision.

```
Agent wants to send an email
        │
        ▼
  evaluate_action("Send invoice email to client", '{"recipient": "acme@example.com"}')
        │
        ├─ REJECT           → agent stops. Explains to user. Does not retry.
        │
        ├─ APPROVE          → agent calls its own email tool and sends.
        │
        └─ ASK_FOR_APPROVAL → agent tells user what it wanted to do.
                              User decides. Agent calls submit_approval(...).
                              If approved=True, agent proceeds to send.
                              If approved=False, nothing is sent.
```

The agent always executes actions using its own tools — Unreal Objects does not
proxy or intercept traffic. The guardrail is purely a decision layer.

### ASK_FOR_APPROVAL — human-in-the-loop flow

When `evaluate_action` returns `ASK_FOR_APPROVAL`, the agent surfaces the
request to the human. Once the human decides, the agent calls `submit_approval`:

- `approved=True` → agent proceeds with the action using its own tools.
- `approved=False` → agent stops. Nothing is executed.

The `request_id` from `evaluate_action` ties together the Decision Center audit
log entry, the `submit_approval` record, and the agent's own execution — giving
operators a complete, tamper-evident chain.

### Available tools

| Tool | Purpose |
|---|---|
| `guardrail_heartbeat` | Checks that Rule Engine and Decision Center are reachable. Call on startup. |
| `evaluate_action` | Evaluates a planned action against business rules. Call before every real-world action. |
| `submit_approval` | Records a human approval decision for an `ASK_FOR_APPROVAL` outcome. |
| `list_rule_groups` | Lists all configured rule groups. |
| `get_rule_group` | Gets a specific rule group and its rules. |
| `get_decision_log` | Reads the audit log (`atomic`, `chains`, or `chain` by `request_id`). |
| `get_pending` | Lists actions currently awaiting human approval. |

`evaluate_action` is the critical integration point. The agent calls it before
every real-world side effect, then executes using its own tools only when the
outcome is `APPROVE` or a human has approved via `submit_approval`.

### Governing your agent's actions

The governance pattern is always the same, regardless of what the agent is doing:

```
Agent decides to act → calls evaluate_action → obeys the outcome → acts with its own tools
```

A correctly written rule for sending to premium customers looks like:

```
Feature:    Email Notification
Rule logic: IF contact_person == 'premium' THEN ASK_FOR_APPROVAL
Edge case:  IF contact_person == 'blocked' THEN REJECT
```

Your agent then does:

```python
# Before sending the email:
decision = await evaluate_action(
    "Send invoice email",
    '{"contact_person": "premium", "recipient": "acme@example.com"}'
)
if decision["outcome"] == "APPROVE":
    send_email(...)            # agent's own tool
elif decision["outcome"] == "ASK_FOR_APPROVAL":
    # surface to user, call submit_approval, then send if approved
elif decision["outcome"] == "REJECT":
    # explain to user, do not send
```

No special proxy tools or server-side execution plumbing is needed. The agent's
existing action tools (email, HTTP, file, database) stay exactly where they are.
`evaluate_action` is the single integration point.


---

## ⚠️ Enforcement model and its limits

Unreal Objects relies on the agent calling `evaluate_action` before acting.
For a compliant, well-aligned model this is a strong and effective control —
the mandatory protocol injected at `initialize` and the `REJECT`/`ASK_FOR_APPROVAL`
outcomes are clear and hard to misinterpret.

The model of enforcement is **instructional, not architectural**. The server
does not intercept network traffic or own the agent's action tools. An agent
that bypasses `evaluate_action` — whether due to jailbreak, prompt injection,
or a separate tool on a different MCP server — is not constrained at the
transport layer.

| Threat | Stopped? |
|---|---|
| Agent forgets to call evaluate_action | Yes — mandatory protocol instruction |
| User instructs agent to skip rules | Partially — strong deterrent for aligned models |
| Jailbreak / adversarial prompt injection | No — instructional controls only |
| Agent has a parallel MCP tool for the same action | No — nothing prevents a direct call |

### How to strengthen enforcement

- **Single-MCP deployment:** Give the agent only one MCP server (Unreal
  Objects). Any action capability the agent needs should be implemented there,
  not on a separate server it can call without going through `evaluate_action`.
- **Operator system prompt:** Reinforce the governance requirement in your
  own system prompt. The MCP `instructions` field is a strong nudge; an
  explicit operator-level instruction adds a second layer.
- **Audit log monitoring:** Check `get_decision_log` regularly. Any real-world
  action that has no matching evaluation entry is a signal of bypass.

---

## 📊 Evaluation

The generative evaluation harness now runs through a single CLI entrypoint:

```bash
uo-stress-test --schema ecommerce
uo-stress-test --schema finance
uo-stress-test --schema none
uo-stress-test --schema all
```

If the console script has not been reinstalled into your virtualenv yet, the
equivalent module form is:

```bash
python -m decision_center.stress_test.cli --schema finance
```

The CLI performs the full pipeline in one command:

1. generate a synthetic dataset of natural-language rules and matching context
2. translate those rules into JSON Logic
3. evaluate them against the running Rule Engine and Decision Center
4. write a versioned markdown report to `evals/generative_evaluation_report_vN.md`

When the CLI starts, it clears the terminal, prints an ASCII-art banner, and
shows explicit phase markers such as service checks, dataset generation,
translation, evaluation, and report writing so the operator can see which step
is active during long runs. Before dataset generation begins, it also prints a
short explanatory paragraph describing what the evaluation is doing, why the
first phase takes time, why the pipeline is useful, and what report/artifact
output to expect at the end.

The translation stage is also resilient to occasional malformed LLM outputs. If
a provider returns a schema-shaped object or another invalid rule payload, the
harness retries the translation once and otherwise records that case as a
translation error instead of aborting the full schema run.

By default, the CLI now reuses an existing generated dataset for the selected
schema so repeated evaluation runs stay fast and comparable. Use
`--refresh-dataset` when you want a brand-new synthetic sample instead of the
stored one. When a dataset is reused, the CLI shows the artifact age in the
phase output.

Reusable datasets are now managed in two layers:

- the promoted baseline dataset at `evals/artifacts/<schema>/llm_test_dataset.json`
- versioned candidate datasets under `evals/artifacts/<schema>/datasets/`

Create fresh candidate datasets without running a full evaluation:

```bash
uo-stress-test --prepare-datasets --schema finance
uo-stress-test --prepare-datasets --schema all --background
```

Promote a candidate dataset into the active baseline:

```bash
uo-stress-test --schema finance --promote-dataset latest
uo-stress-test --schema finance --promote-dataset evals/artifacts/finance/datasets/llm_test_dataset_20260301_130000.json
```

`--prepare-datasets` generates versioned candidates only. It does not replace
the active baseline automatically. `--promote-dataset` is the explicit workflow
that copies a chosen candidate into the schema’s reusable baseline.

List the active baseline and available candidate datasets before promotion:

```bash
uo-stress-test --schema finance --list-datasets
uo-stress-test --schema all --list-datasets
```

### Recommended Workflow

For routine regression checks:

```bash
python -m decision_center.stress_test.cli --schema finance
```

That reuses the promoted baseline dataset automatically when one exists.

For a fresh dataset candidate:

```bash
python -m decision_center.stress_test.cli --prepare-datasets --schema finance
python -m decision_center.stress_test.cli --schema finance --list-datasets
python -m decision_center.stress_test.cli --schema finance --promote-dataset latest
python -m decision_center.stress_test.cli --schema finance
```

For bulk candidate refresh:

```bash
python -m decision_center.stress_test.cli --prepare-datasets --schema all --background
```

This keeps the benchmark stable by default while still making it easy to create
and promote fresher datasets intentionally.

The canonical implementation now lives under `decision_center/stress_test/`.
There is no secondary legacy stress-test path anymore; routine evaluation work
should go through the CLI/module entrypoint only.

### Schema-Aware Evaluation

The CLI discovers available schemas automatically from `schemas/*.json`. The
filename stem becomes the CLI slug:

- `schemas/ecommerce.json` → `--schema ecommerce`
- `schemas/finance.json` → `--schema finance`

To add a new schema to the stress-test CLI:

1. create a valid JSON file in `schemas/<slug>.json`
2. include either a top-level `schema` object or a plain dictionary body
3. run `uo-stress-test --schema <slug>`

No code change should be required to expose a new schema in the CLI.

Special modes:

- `--schema none` runs the evaluation without injecting any schema vocabulary
- `--schema all` runs every discovered schema sequentially and then runs the
  no-schema scenario last

### Artifact Layout

Each schema run writes intermediate artifacts into its own folder:

- `evals/artifacts/<schema>/llm_test_dataset.json`
- `evals/artifacts/<schema>/dataset_manifest.json`
- `evals/artifacts/<schema>/datasets/llm_test_dataset_<timestamp>.json`
- `evals/artifacts/<schema>/batch_results.jsonl`
- `evals/artifacts/<schema>/eval_output_raw.txt`

Each completed run writes one new markdown report:

- `evals/generative_evaluation_report_vN.md`

When `--schema all` is used, the CLI writes one new versioned report per schema
run.

### Current Recorded Evidence

The checked-in evaluation evidence in this repository currently shows:

| Schema | Current committed state | Evidence |
| ------ | ----------------------- | -------- |
| `ecommerce` | Latest full end-to-end report available | `evals/generative_evaluation_report_v5.md` |
| `finance` | Full finance-schema report and reusable baseline dataset available | `evals/generative_evaluation_report_v6.md` |
| `none` | Supported by CLI; no committed baseline/report yet | Generated on demand via CLI |

The latest committed full-report results are:

| Schema | Cases | Pass Rate | Failed | Translation Errors | Report |
| ------ | ----- | --------- | ------ | ------------------ | ------ |
| `ecommerce` | 532 | 98.7% | 6 safe mismatches | 1 parse error | `evals/generative_evaluation_report_v5.md` |
| `finance` | 519 | 92.3% | 6 | 34 | `evals/generative_evaluation_report_v6.md` |

The strongest committed benchmark remains the **E-Commerce V5** run:

| Metric | Result |
| ------ | ------ |
| Cases | 532 |
| Pass Rate | 98.7% |
| Safe Mismatches | 6 |
| Parse Errors | 1 |
| Report | `evals/generative_evaluation_report_v5.md` |

### Operational Requirements

Before running the CLI:

- Rule Engine must already be running on `http://127.0.0.1:8001`
- Decision Center must already be running on `http://127.0.0.1:8002`
- the relevant provider API key must be present either in your shell
  environment or in a project `.env` file that the CLI can load automatically

### Historical Results

We previously ran a five-iteration generative evaluation to validate that the
full pipeline — natural language rule → LLM translation → JSON Logic →
Decision Center evaluation — works correctly at scale.

**What we evaluated:** The end-to-end accuracy of translating 532 business rules
written in plain English into executable JSON Logic, and then evaluating those
rules against matching context payloads. Each test case was generated by
GPT-5-mini (`gpt-5-mini-2025-08-07`): the model wrote a natural language rule,
produced a realistic context payload, and declared the expected outcome
(`APPROVE`, `REJECT`, or `ASK_FOR_APPROVAL`). A separate LLM call then
translated the rule through `decision_center.translator` into JSON Logic, which
was uploaded to the Rule Engine and evaluated by the Decision Center. A "pass"
means the engine returned the expected outcome; a "fail" is always a safe
fail-closed outcome (`ASK_FOR_APPROVAL` or `REJECT`), never a silent insecure
approval.

**How we iterated:** Over five evaluation runs we progressively fixed both the
pipeline and the test harness. V1 (baseline, no schema constraints) reached
46.9% accuracy. V2 added strict variable-naming instructions to the system
prompt, reaching 60%. V3 introduced schema injection (constraining the LLM to a
curated `ecommerce.json` variable dictionary) and a fuzzy context-mapping
pre-processor (resolving minor naming mismatches via `difflib`) — but accuracy
appeared to drop to 51.5% because the test dataset itself was flawed:
`context_data` did not always include every variable the rule referenced,
causing the engine's correct fail-closed behaviour to register as a mismatch. V4
fixed an async variable-shadowing bug in the translation pipeline. V5 corrected
the dataset generation so every variable mentioned in a rule is guaranteed
present in `context_data`.

**Result:** The best committed end-to-end result is still **V5 E-Commerce** at
**98.7% accuracy** across 532 cases. The newly committed **V6 Finance** run
lands at **92.3%** across 519 cases, with the main drag coming from **34
translation errors** rather than evaluator instability. Together, these runs
show that the stress-test CLI is now producing schema-specific, repeatable
evidence instead of a single monolithic benchmark.

| Version | Key Change                                                | Accuracy  |
| ------- | --------------------------------------------------------- | --------- |
| V1      | Baseline — no schema, no pre-processor                    | 46.9%     |
| V2      | Strict variable-naming prompts                            | 60.0%     |
| V3      | Schema injection + fuzzy context mapping + null EC filter | 51.5%*    |
| V4      | Async pipeline bug fix                                    | 51.5%     |
| V5      | Context-complete test data                                | **98.7%** |

> *V3/V4 accuracy reflects a dataset generation flaw (missing context
> variables), not a translation regression.

---

## Appendix: Tool Creation Agent *(not ready for use)*

> **Do not use this in production.** The Tool Creation Agent is an early
> experiment and is preserved in the repository for reference only. It is not
> wired into the UI or the default startup. The core principle of Unreal Objects
> is that it holds business rules and governs decisions — it does not generate
> or execute code.

The **Tool Creation Agent** (`mcp_server/tool_agent.py`) is a FastAPI service
(port 8003) that watches new rules as they are created and uses an LLM to
propose MCP tool scaffolds when a new feature domain appears. Every generated
scaffold requires human approval before any code is written.

**To run it manually (for experimentation only):**

```bash
ANTHROPIC_API_KEY=sk-...  uvicorn mcp_server.tool_agent:app --port 8003
# or: OPENAI_API_KEY=sk-...  / GOOGLE_API_KEY=...
```

**Interact via curl:**

```bash
# List proposals
curl http://127.0.0.1:8003/v1/proposals | python3 -m json.tool

# Approve a proposal (writes scaffold to mcp_server/server.py)
curl -X POST http://127.0.0.1:8003/v1/proposals/<id>/review \
  -H "Content-Type: application/json" \
  -d '{"approved": true, "reviewer": "Your Name"}'

# Reject
curl -X POST http://127.0.0.1:8003/v1/proposals/<id>/review \
  -H "Content-Type: application/json" \
  -d '{"approved": false, "reviewer": "Your Name"}'
```

On startup it creates an **"Unreal Objects System"** rule group in the Rule
Engine with a meta-rule (`IF action = 'tool_generation' THEN ASK_FOR_APPROVAL`)
so the agent can never approve its own code.
