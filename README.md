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

## 🏗️ Architecture

Unreal Objects is cleanly decoupled into 3 modular microservices:

1. 📏 **Rule Engine (`:8001`)**: Where you create, manage, and store your
   business rules and governance logic.
2. 🧠 **Decision Center & Log (`:8002`)**: The engine that evaluates agent
   actions against your rules, enforces outcomes (like `APPROVE`, `REJECT`, or
   `ASK_FOR_APPROVAL`), and maintains an immutable audit trail of every
   decision.
3. 🔌 **MCP Server (`:8000`)**: A native
   [Model Context Protocol](https://modelcontextprotocol.io) integration. This
   allows any modern AI agent (OpenClaw, Claude Desktop, LangChain) to
   seamlessly connect to your governance system.

---

## 🛠️ Quick Start & Setup

Requires Python 3.11+.

```bash
# Clone and setup the environment
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run the test suite
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

---

## 🎮 How To Use (The Interactive CLI Wizard)

We've built a native CLI tool hooked up to modern LLMs (OpenAI, Anthropic,
Gemini) that allows you to draft these complex JsonLogic rules entirely in
English.

### 1. Boot the Core Servers

Start the Rule Engine and Decision Center servers in the background. Note: The
CLI will offer to start these for you automatically!

```bash
# Terminal 1: Rule Engine
source .venv/bin/activate
uvicorn rule_engine.app:app --port 8001

# Terminal 2: Decision Center
source .venv/bin/activate
uvicorn decision_center.app:app --port 8002
```

### 2. Launch the LLM Rule Wizard

Run the interactive CLI loop. You can pass your API keys securely, or source
them straight from your environment variables (`OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`, etc.)

```bash
python decision_center/cli.py
```

1. **Pick a Provider:** Select your preferred reasoning model.
2. **Create/Update Rules:** Describe what you want exactly how you'd say it:
   > _"If the transaction originates in California, or if the user owes more
   > than $100, then ask them for manual approval immediately."_
3. **Iterative Refinement:** Don't like the generated JSON Logic structure? The
   wizard lets you type `E` to seamlessly append additional **Edge Cases** on
   the fly without breaking the main logic branch.
4. **Auto-Test:** Instantly simulate agent requests and review exactly which
   expression node triggered the outcome securely within the wizard console.

---

## 🤖 Connecting Your AI Agents

Instead of using the wizard's auto-tester, your actual autonomous AI agents can
interact with Unreal Objects natively through the built-in **MCP Server**.

### Running the MCP Server natively (for LAN/External Agents)

If your AI agent (like OpenClaw) is running on a different machine or Docker
container in your network, start the MCP Server via SSE (Server-Sent Events)
bound to your local IP:

```bash
source .venv/bin/activate
python mcp_server/server.py --transport sse --host 0.0.0.0 --port 8000
```

### Exposing the Tools

Once hooked up, your agent discovers these protected capabilities:

- `list_rule_groups()`: Read available governance groups.
- `evaluate_action(request_description, context_json, group_id)`: Try to execute
  a governed action.
- `submit_approval(request_id, approved, approver)`: Route a blocked action to a
  human for sign-off.
- `get_decision_log(log_type, request_id)`: Read the audit trail of decisions.

Your infrastructure is now fully governed and transparent! ✨
