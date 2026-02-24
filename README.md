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

## 🎮 How To Use (The Full Flow)

### 1. Boot the Core Servers

First, start the Rule Engine and Decision Center servers in separate terminal
windows:

```bash
# Terminal 1: Rule Engine
source .venv/bin/activate
uvicorn rule_engine.app:app --port 8001

# Terminal 2: Decision Center
source .venv/bin/activate
uvicorn decision_center.app:app --port 8002
```

### 2. Define Your Rules

Rules belong to "Groups". Let's create a Transaction Monitoring group and add a
rule to it.

```bash
# Create the Group
curl -X POST http://127.0.0.1:8001/v1/groups \
  -H "Content-Type: application/json" \
  -d '{"name": "Transaction Rules", "description": "Limits on purchases"}'
```

_Take note of the `id` returned in the response._

Now, let's add a dynamic rule. Our engine evaluates expressions dynamically!

```bash
# Add a Rule to the Group
curl -X POST http://127.0.0.1:8001/v1/groups/<YOUR_GROUP_ID>/rules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "High Value Transaction",
    "feature": "Limit Purchases",
    "datapoints": ["amount"],
    "edge_cases": [],
    "edge_cases_json": [],
    "rule_logic": "IF amount > 500 THEN ASK_FOR_APPROVAL",
    "rule_logic_json": {"if": [{">": [{"var": "amount"}, 500]}, "ASK_FOR_APPROVAL", null]}
  }'
```

### 3. Evaluate a Decision

To see the engine in action, simulate evaluating a request:

```bash
# Simulating an agent wanting to spend 750 (triggers approval!)
curl "http://127.0.0.1:8002/v1/decide?request_description=Buying+Laptop&context={\"amount\":750}&group_id=<YOUR_GROUP_ID>"
```

---

## 🤖 Connecting Your AI Agents

Instead of using `curl`, AI agents can interact with Unreal Objects directly
through the **MCP Server**.

### Running the MCP Server natively (for LAN/External Agents)

If your AI agent (like OpenClaw) is running on a different machine or docker
container in your network, start the MCP Server via SSE (Server-Sent Events)
bound to your local IP:

```bash
# Terminal 3: MCP Server
source .venv/bin/activate
python mcp_server/server.py --transport sse --host 0.0.0.0 --port 8000
```

### Exposing the Tools

Once connected, the agent immediately discovers these capabilities:

- `list_rule_groups()`: Read available governance groups.
- `evaluate_action(request_description, context_json, group_id)`: Try to execute
  a governed action.
- `submit_approval(request_id, approved, approver)`: Route a blocked action to a
  human for sign-off.
- `get_decision_log(log_type, request_id)`: Read the audit trail of decisions.

### Example: Connect OpenClaw / Claude Desktop

Add exactly this to your bot's MCP settings:

- **Transport**: `SSE`
- **URL**: `http://<YOUR_LAN_IP>:8000/sse`

Your agent is now governed by Unreal Objects! ✨
