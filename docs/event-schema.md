# Event Schema

This document defines the required fields for Unreal Objects decision and audit
events. All governed action flows must produce events that satisfy this schema.

## Identity Model

Every authenticated governed action uses three different identifiers:

- `agent_id`: the stable identity of the software agent or agent runtime
- `credential_id`: the specific scoped credential used on this request
- `user_id`: the human or tenant-scoped principal the agent claims it is acting for

These identifiers must not be collapsed into one field.

## Core Requirements

All decision flows must record:

- a unique `request_id`
- the original `request_description`
- the structured `context`
- the decision outcome or state
- a timestamp
- the identity fields listed above
- the `effective_group_id` that governed the action

## Request Event

Created when a governed action is first submitted for evaluation.

```json
{
  "event_type": "REQUEST",
  "request_id": "req_123",
  "timestamp": "2026-03-03T10:15:00Z",
  "request_description": "Create vendor payment",
  "context": {
    "vendor": "Acme GmbH",
    "amount_eur": 12400
  },
  "agent_id": "agt_ops_01",
  "credential_id": "cred_finance_a",
  "user_id": "user_4821",
  "effective_group_id": "grp_finance_prod"
}
```

Required fields:

- `event_type`
- `request_id`
- `timestamp`
- `request_description`
- `context`
- `agent_id`
- `credential_id`
- `user_id`
- `effective_group_id`

## Evaluation Event

Created immediately after rule evaluation.

```json
{
  "event_type": "EVALUATION",
  "request_id": "req_123",
  "timestamp": "2026-03-03T10:15:00Z",
  "agent_id": "agt_ops_01",
  "credential_id": "cred_finance_a",
  "user_id": "user_4821",
  "effective_group_id": "grp_finance_prod",
  "outcome": "ASK_FOR_APPROVAL",
  "matched_rules": ["rule_high_value_payment"]
}
```

Required fields:

- `event_type`
- `request_id`
- `timestamp`
- `agent_id`
- `credential_id`
- `user_id`
- `effective_group_id`
- `outcome`
- `matched_rules`

Optional fields:

- `matched_details`

## Atomic Decision Log Entry

Created once per evaluated action.

```json
{
  "request_id": "req_123",
  "timestamp": "2026-03-03T10:15:00Z",
  "request_description": "Create vendor payment",
  "context": {
    "vendor": "Acme GmbH",
    "amount_eur": 12400
  },
  "decision": "APPROVAL_REQUIRED",
  "agent_id": "agt_ops_01",
  "credential_id": "cred_finance_a",
  "user_id": "user_4821",
  "effective_group_id": "grp_finance_prod"
}
```

Required fields:

- `request_id`
- `timestamp`
- `request_description`
- `context`
- `decision`
- `agent_id`
- `credential_id`
- `user_id`
- `effective_group_id`

## Pending Approval Entry

Created only when the evaluation outcome is `ASK_FOR_APPROVAL`.

```json
{
  "request_id": "req_123",
  "description": "Create vendor payment",
  "context": {
    "vendor": "Acme GmbH",
    "amount_eur": 12400
  },
  "agent_id": "agt_ops_01",
  "credential_id": "cred_finance_a",
  "user_id": "user_4821",
  "effective_group_id": "grp_finance_prod"
}
```

Required fields:

- `request_id`
- `description`
- `context`
- `agent_id`
- `credential_id`
- `user_id`
- `effective_group_id`

## Approval Status Event

Created when a human resolves a pending approval.

```json
{
  "event_type": "APPROVAL_STATUS",
  "request_id": "req_123",
  "timestamp": "2026-03-03T10:16:00Z",
  "agent_id": "agt_ops_01",
  "credential_id": "cred_finance_a",
  "user_id": "user_4821",
  "effective_group_id": "grp_finance_prod",
  "status": "APPROVED",
  "approver": "CFO"
}
```

Required fields:

- `event_type`
- `request_id`
- `timestamp`
- `agent_id`
- `credential_id`
- `user_id`
- `effective_group_id`
- `status`
- `approver`

## Validation Rules

- `agent_id`, `credential_id`, and `user_id` must be non-empty strings.
- `effective_group_id` must be recorded for every governed action.
- `request_id` must remain stable across request, evaluation, pending, and approval events.
- `credential_id` must identify the exact credential used, not just the parent agent.
- `user_id` is declared by the agent per request; it is part of audit context, not the authentication identity.
- Unauthenticated local development flows may omit identity fields only when auth is explicitly disabled. Production authenticated flows must always include them.
