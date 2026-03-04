# ⚙️ Rule Engine & Decision Center

## How Decisions Are Made

When an AI agent requests to take an action (e.g., spending company money,
sending an email), the Decision Center funnels that request through a 3-step
pipeline governed by the Rule Engine's stored groups.

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

- **Fail-Closed by Default:** Any missing data, type mismatches, or evaluation
  timeouts instantly hard-fail to `ASK_FOR_APPROVAL` or `REJECT`.
- **JSON Logic Engine:** Rules are compiled into strictly auditable AST
  representations using [JsonLogic](http://jsonlogic.com/).
- **Rule lifecycle:** Rules are never required to be deleted to retire them.
  Mark a rule inactive to skip it during evaluation while keeping it visible for
  audit history.

---

## What Rules Are (and Aren't)

Rules describe **conditions on an action the agent has already chosen to take.**

| Rule                                                   | What it means                                                         |
| ------------------------------------------------------ | --------------------------------------------------------------------- |
| `IF contact_person == 'premium' THEN ASK_FOR_APPROVAL` | When agent sends to a premium contact, pause and get a human sign-off |
| `IF transfer_amount > 10000 THEN REJECT`               | Block any transfer above this threshold, unconditionally              |
| `IF file_path CONTAINS '/etc/' THEN REJECT`            | Agent cannot write to system directories, ever                        |

Rules that **prescribe what the agent should do** are process instructions, not
governance rules. They do not belong here:

| Rule                                             | Why it's wrong                                        |
| ------------------------------------------------ | ----------------------------------------------------- |
| `IF contact_person == 'premium' THEN send_email` | This tells the agent to act — that is the agent's job |
| `IF order_value > 500 THEN notify_customer`      | This is a business process step, not a guardrail      |

> **The agent decides what to do. Unreal Objects decides whether, and under what
> conditions, that decision is allowed to execute.**

---

## 📐 Schema Blueprints

When the LLM translates a rule into JSON Logic it has to choose variable names.
Without guidance it invents them freely — the same concept might become `amount`
in one rule, `transaction_amount` in the next. **Schemas lock the LLM to a
pre-approved vocabulary** so all rules stay consistent.

| Schema         | Use when your rules are about…                                             |
| -------------- | -------------------------------------------------------------------------- |
| **No schema**  | Custom domains, or when your variable names are already decided            |
| **E-Commerce** | Orders, payments, cart contents, shipping, delivery timing, user accounts  |
| **Finance**    | Withdrawals, transfers, balances, loans, KYC verification, AML risk scores |

### Semantic Concept Validation (3 layers)

1. **Pre-translation candidate ranking** — before calling the LLM, the system
   scores every schema field against the rule text. Top 3 best-matching fields
   are injected into the prompt as a ranked hint list.

2. **Post-translation candidate alignment check** — after translation, every
   variable the LLM used is scored against the original rule text. If a variable
   scores below 50% of the best available field's score, the translation is
   rejected.

3. **Schema variable validation** — every `{"var": ...}` reference in the JSON
   Logic AST is verified to exist in the active schema. Off-schema variables are
   rejected.

### Interactive Datapoint Editing

After translation, **both UI and CLI let you swap extracted datapoints**:

- **UI:** Click any datapoint badge → dropdown shows schema fields ranked by
  name + "Create new field" option. Selecting a field instantly updates the rule
  logic, JSON Logic AST, and edge cases.

- **CLI:** After showing extracted datapoints, prompts to change by number.
  Shows schema fields ranked by relevance to the original rule text. Option `N`
  creates a custom field name.

The swap utility (`swap_variable_in_result`) replaces the old variable
throughout `datapoints`, `rule_logic`, `rule_logic_json`, and `edge_cases` so
the entire translation stays internally consistent.
