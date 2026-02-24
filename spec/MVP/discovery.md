# STRATEGY & DISCOVERY

## 1️⃣ Why Unreal Objects Is Attractive

### Core Attractiveness (Market Level)

AI agents are transitioning from experiments to real operational workflows.
However, most current systems lack:

- ❌ Clear auditability
- ❌ Human-interrupt control for risky actions
- ❌ Evidence-linked traceability
- ❌ Explainable execution history

Organizations increasingly require:

- ✅ Compliance documentation (GDPR, SOC2, ISO27001)
- ✅ Operational visibility
- ✅ Human-in-the-loop safety
- ✅ Internal trust for adoption

### Strategic Reframing

Unreal Objects transforms autonomy from:

> "The agent did something."

into:

> "The agent did X — here is why, here is the evidence, and here is who approved
> it."

This reframing closes the **trust gap** in autonomous systems.

---

## 2️⃣ Define the Players (Users)

| User Type                                  | Examples                                                    | Core Motivation                                  | Core Need                             |
| ------------------------------------------ | ----------------------------------------------------------- | ------------------------------------------------ | ------------------------------------- |
| **Primary: AI Product Builders**           | AI founders, automation engineers, agent framework builders | Ship autonomous workflows without losing control | Structured visibility into agent runs |
| **Secondary: Operational Decision-Makers** | CTOs, compliance officers, ops leads                        | Minimize risk exposure                           | Governance + auditability             |
| **Tertiary: End-Approvers**                | Team leads, managers                                        | Fast clarity without reading logs                | Clear summaries + evidence            |

---

## 3️⃣ The Core Challenge

### Problem Statement

AI agents execute workflows, but:

- Reasoning is buried in technical logs
- Risky actions lack mandatory checkpoints
- Evidence is scattered
- Trust collapses when failures occur

### Market Evidence Signals

| Signal                                | Meaning                         |
| ------------------------------------- | ------------------------------- |
| Enterprise rollouts stall             | Explainability gaps             |
| Governance cited as top barrier       | Compliance pressure rising      |
| Human-in-the-loop patterns increasing | Oversight is becoming standard  |
| EU + US AI regulation expanding       | Auditability becoming mandatory |

> The constraint is not model intelligence — it is **trust + governance**.

Unreal Objects addresses that constraint directly.

---

# Vision & Mission

### 🌍 Vision

> **The world runs on autonomous systems — safe, transparent, and accountable by
> default.**

Autonomous systems will become the backbone of digital operations. Safety and
accountability must be embedded properties — not optional add-ons.

### 🎯 Mission

> **Build the accountability infrastructure for the autonomous era.**

Unreal Objects records, explains, and governs every automated decision before it
impacts the real world.

---

# Unreal Objects Architecture

Unreal Objects consists of **3 decoupled modules** that communicate via APIs.

```
┌───────────┐      API      ┌───────────┐      MCP      ┌───────────┐
│  Rule     │◄─────────────►│   MCP     │◄─────────────►│   Agent   │
│  Engine   │               │  Server   │               │           │
└───────────┘               └─────┬─────┘               └───────────┘
                                  │ API
                            ┌─────▼─────┐
                            │ Decision  │
                            │ Center    │
                            │ + Log     │
                            └─────┬─────┘
                                  │ API
                            ┌─────▼─────┐
                            │   User    │
                            │ (Approval)│
                            └───────────┘
```

> No module directly imports or depends on another module's internals. All
> inter-module communication goes through defined API contracts.

### Standardized Outcome Vocabulary

The Decision Center produces **actions**, the Decision Log records **states**:

| Decision Center (Action) | Decision Log (State) |
| ------------------------ | -------------------- |
| `APPROVE`                | `APPROVED`           |
| `REJECT`                 | `REJECTED`           |
| `ASK_FOR_APPROVAL`       | `APPROVAL_REQUIRED`  |

### Rule Evaluation Order

When multiple rules in a `business_rule_group` apply to the same action, **most
restrictive wins**:

> `REJECT` > `ASK_FOR_APPROVAL` > `APPROVE`

### Default Behavior

- **No matching rules**: The action executes **without governance**. Unreal
  Objects only governs within the scope of its business rules and must not take
  responsibility outside of them.
- **Rule Engine unreachable**: The agent **must inform the user** before
  execution starts. The user then decides to either proceed without rules or fix
  the issue first.

---

## Module 1: Rule Engine

### Purpose

The Rule Engine allows users to **create business rules** that govern autonomous
agent behavior. A business rule defines what an agent is allowed to do, must
reject, or needs human approval for.

### Business Rule Structure

Every business rule follows a strict formula:

> **Feature + Datapoints Needed + Edge Cases = Business Rule**

### Example

| Component         | Value                                                               |
| ----------------- | ------------------------------------------------------------------- |
| **Feature**       | Allow autonomous purchases until the purchase amount of 100€        |
| **Datapoints**    | `purchase`, `amount`                                                |
| **Edge Cases**    | `amount` is missing/NaN, `purchase` is missing but `amount` present |
| **Business Rule** | _(see below)_                                                       |

```
IF amount is missing/NaN OR purchase is missing but amount present
  THEN REJECT request
ELSE IF purchase > 100€
  THEN APPROVAL_REQUIRED
ELSE
  APPROVE
```

This structure — **Feature + Datapoints + Edge Cases = Business Rule** — makes
the process flexible for **all kinds of business rules**, not just purchasing.

> [!NOTE]
> This is an illustrative example. An **LLM-based hardening step** will be
> implemented to validate business rules — ensuring they don't conflict and
> behave as intended before activation.

### Grouping

Business rules are grouped by **`business_rule_group`** only.

- One `business_rule_group` can contain **several** `business_rules`
- No other grouping dimensions (no `user_id`, no `action_types` overengineering)

```
business_rule_group: "purchasing_controls"
├── rule: autonomous_purchase_limit
├── rule: restricted_vendor_check
└── rule: budget_category_validation
```

### Rule Engine API

The Rule Engine exposes its own API for CRUD operations on rules and groups.

---

## Module 2: MCP (Model Context Protocol Server)

### Purpose

The MCP module is the **sole interface** through which an AI agent consumes
business rules. No additional HTTP process is needed — the agent connects
directly via MCP.

### How It Works

1. **User connects the MCP** to their agent
2. **User tells the agent** to execute a task and specifies a
   `business_rule_group`
3. The MCP server fetches the relevant business rules from the Rule Engine
4. The agent evaluates actions against those rules via the Decision Center

### Without a Group

If the user **does not define** a `business_rule_group`, the agent processes the
task **without** business rule enforcement.

### Key Constraint

> The agent **must** consume business rules via MCP only. An additional HTTP
> process is unnecessary.

---

## Module 3: Decision Center & Decision Log

### 3a. Decision Center

The Decision Center is **how the agent takes its decisions**. Based on business
rules, every agent action has exactly **3 possible outcomes**:

| Outcome                | Agent Behavior                                                                                               |
| ---------------------- | ------------------------------------------------------------------------------------------------------------ |
| **`APPROVE`**          | Agent **autonomously continues** the process and executes the action                                         |
| **`REJECT`**           | Agent **autonomously stops** the process and rejects the action                                              |
| **`ASK_FOR_APPROVAL`** | Agent **stops and asks** the user. If user approves → execute. If user rejects → stop and reject the action. |

```
Agent Action → Evaluate Rules
     │
     ├── APPROVE ──────────► Execute Action
     ├── REJECT ───────────► Stop Action
     └── ASK_FOR_APPROVAL ─► User Review
                                ├── Approved → Execute Action
                                └── Rejected → Stop Action
```

#### Decision Center API

The Decision Center is exposed via API:

- **`GET`** — for sending information / requesting a decision
- **`POST`** — for submitting approval from the user

---

### 3b. Decision Log

The agent **logs every decision** in two complementary formats.

#### Format 1: Atomic Decision

Each individual decision is logged with full context as a single event:

```
2026_02_24 09:31:23 REQUEST: Buy 200 Paperclips
                    PURCHASE AMOUNT: 3€
                    DECISION: APPROVED

2026_02_24 09:31:23 REQUEST: Order 100 Pizza
                    PURCHASE AMOUNT: NaN
                    DECISION: REJECTED

2026_02_24 09:31:23 REQUEST: Order 100 MacBooks
                    PURCHASE AMOUNT: 19000€
                    DECISION: APPROVAL_REQUIRED
```

#### Format 2: Decision Chain

The decision chain tracks the **full lifecycle** of a request — from initial
decision through resolution:

```
────────────────────────────────────────────────────────
2026_02_24 09:31:23 REQUEST: Buy 200 Paperclips
                    PURCHASE AMOUNT: 3€
                    DECISION: APPROVED
2026_02_24 09:31:28 REQUEST_PROCESSED
────────────────────────────────────────────────────────

────────────────────────────────────────────────────────
2026_02_24 09:31:23 REQUEST: Order 100 MacBooks
                    PURCHASE AMOUNT: 19000€
                    DECISION: APPROVAL_REQUIRED
2026_02_24 09:35:30 APPROVAL_STATUS: APPROVED
2026_02_24 09:35:35 REQUEST_PROCESSED
────────────────────────────────────────────────────────
```

#### Decision Log API

Decision Logs are exposed via API for querying and retrieval.

---

## Architectural Gateway

### Decoupling Principle

The 3 modules — **Rule Engine**, **MCP**, **Decision Center & Decision Log** —
are **decoupled** and communicate exclusively via APIs.

| Module              | Exposed Via                       |
| ------------------- | --------------------------------- |
| **Rule Engine**     | API (CRUD for rules & groups)     |
| **MCP**             | MCP Server (agent-facing only)    |
| **Decision Center** | API (`GET` info, `POST` approval) |
| **Decision Log**    | API (query & retrieval)           |
