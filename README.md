<div align="center">
  <h1><img src="assets/unreal_objects_logo.png" alt="Unreal Objects Mascot" width="75" style="vertical-align: middle;"/> Unreal Objects <img src="assets/unreal_objects_logo.png" alt="Unreal Objects Mascot" width="75" style="vertical-align: middle;"/> </h1>
  <p><b>Accountability infrastructure for autonomous systems.</b></p>
</div>

---

## 🔮 What is Unreal Objects?

As AI agents become more autonomous, they start doing things that impact the
real world — spending money, sending emails, or changing systems. **Unreal
Objects** is the safety net that sits between your AI agent and reality.

It safely records, explains, and **governs** every automated decision _before_
it executes. If an agent tries to do something sensitive, Unreal Objects catches
it, evaluates it against your business rules, and transparently routes it for
Human-in-the-Loop approval.

Think of it as **Autonomy with Receipts.** 🧾

> **The agent decides what to do. Unreal Objects decides whether, and under what
> conditions, that decision is allowed to execute.**

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

---

## 🏗️ Architecture

| Service                | Port    | Purpose                                                                                             |
| ---------------------- | ------- | --------------------------------------------------------------------------------------------------- |
| 📏 **Rule Engine**     | `:8001` | CRUD for rule groups, rules, and datapoint definitions                                              |
| 🧠 **Decision Center** | `:8002` | Evaluates actions against rules; maintains immutable audit log with agent identity                  |
| 🔌 **MCP Server**      | `:8000` | [Model Context Protocol](https://modelcontextprotocol.io) bridge for AI agents plus HTTP agent auth |
| 🖥️ **React UI**        | `:5173` | Visual rule builder with structured fill-in-the-blank editor and test console                       |

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
# Add --auth-enabled and --admin-api-key when you need the agent bootstrap/admin surface.
python mcp_server/server.py --transport streamable-http --host 0.0.0.0 --port 8000 --group-id <your-group-id> --auth-enabled --admin-api-key admin-secret &

# Or restart all backend services together (kills old backend processes first)
./scripts/start_backend_stack.sh

# 4. React UI (optional — open http://localhost:5173)
cd ui && npm install && npm run dev

# 5. Run the test suite
pytest -v
```

---

## 📈 Stress-Test Snapshot

| Schema         | Pass Rate             | Evidence                                   |
| -------------- | --------------------- | ------------------------------------------ |
| **E-Commerce** | **98.7%** (532 cases) | `evals/generative_evaluation_report_v5.md` |
| **Finance**    | **92.3%** (519 cases) | `evals/generative_evaluation_report_v6.md` |
| **No Schema**  | CLI-ready             | No committed baseline yet                  |

---

## 📚 Documentation

| Guide                                                     | What's inside                                                                                          |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| [⚙️ Rule Engine & Concepts](docs/rule-engine.md)          | How the evaluation pipeline works, what rules are (and aren't), schema blueprints, semantic validation |
| [🤖 Connecting Your AI Agents](docs/connecting-agents.md) | MCP server setup, available tools, auth flow, enrollment, audit identity, enforcement model            |
| [🖥️ React UI](docs/react-ui.md)                           | Rule builder, LLM wizard flow, test console, Agent Admin panel                                         |
| [🎮 CLI Wizard](docs/cli-wizard.md)                       | Terminal-based rule creation wizard, step-by-step flow                                                 |
| [📊 Evaluation Harness](docs/evaluation.md)               | Running the stress-test CLI, dataset management, schema-aware evaluation, current results              |

---

## Appendix: Tool Creation Agent _(not ready for use)_

> **Do not use this in production.** The Tool Creation Agent is an early
> experiment preserved for reference only. It is not wired into the UI or the
> default startup.

The **Tool Creation Agent** (`mcp_server/tool_agent.py`) is a FastAPI service
(port 8003) that watches new rules and uses an LLM to propose MCP tool scaffolds
when a new feature domain appears. Every generated scaffold requires human
approval before any code is written.

```bash
ANTHROPIC_API_KEY=sk-...  uvicorn mcp_server.tool_agent:app --port 8003
```

```bash
# List proposals
curl http://127.0.0.1:8003/v1/proposals | python3 -m json.tool

# Approve (writes scaffold to mcp_server/server.py)
curl -X POST http://127.0.0.1:8003/v1/proposals/<id>/review \
  -H "Content-Type: application/json" \
  -d '{"approved": true, "reviewer": "Your Name"}'
```
