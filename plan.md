# Plan: Real-Bot Support Company Stress Test on Unreal Objects

## Summary

Build a realistic support-operations simulation that generates inbound business cases, routes them to your real Open Claw bot, and requires every bot action to pass through Unreal Objects before execution. The goal of v1 is not raw scale; it is proving a believable end-to-end workflow where a real bot handles realistic support requests, Unreal Objects governs each action, and a human operator resolves approval-required steps.

This should be implemented as a new scenario runner on top of the existing stack, not by stretching the current eval CLIs beyond their purpose. The existing `uo-agent-eval` harness is useful as a model for outcome validation and receipts, but your new runner should add a company simulator, a live bot adapter, and manual approval handling.

## Implementation Changes

### 1. Add a "virtual support company" simulator

- Create a support-company domain model that emits realistic inbound cases rather than synthetic rule-only test cases.
- Each case should include:
  - `case_id`
  - `case_type`
  - `customer_tier`
  - `priority`
  - `risk_score`
  - `requested_action`
  - `channel`
  - `account_age_days`
  - `order_value` or `refund_amount` when relevant
  - `requires_identity_check`
  - `contains_policy_exception`
  - `expected_business_path`
- Support at least 5 realistic case families:
  - Standard account update
  - Refund request
  - Escalation / complaint
  - Sensitive account change
  - Suspicious / high-risk request
- Generate a case queue with a controllable mix of easy, approval-required, and hard-reject work so the run exercises all three outcomes: `APPROVE`, `ASK_FOR_APPROVAL`, `REJECT`.

### 2. Define a governed action contract between the simulator and the bot

- Introduce a clear action schema that the bot must use for all executable work.
- The first version should assume the bot performs HTTP/API-style actions only.
- Every bot action should be represented as:
  - `action_name`
  - `case_id`
  - `action_payload`
  - `business_reason`
  - `user_id`
- Require the bot adapter to call Unreal Objects before each real action.
- The governed action lifecycle should be:
  1. Simulator creates a support case.
  2. Bot reads the case and decides the next action.
  3. Bot sends `evaluate_action` to Unreal Objects with the action description and structured context.
  4. If `APPROVE`, bot performs the action through its API/tool.
  5. If `REJECT`, bot records the refusal and stops that action path.
  6. If `ASK_FOR_APPROVAL`, bot pauses and exposes the request for a real human reviewer.
  7. Human reviewer approves or rejects through the existing approval flow.
  8. Bot resumes or stops accordingly.
- This action contract is the main public interface addition for the new test harness. It should be documented and treated as stable.

### 3. Add a real-bot adapter layer for Open Claw

- Do not hardwire simulator logic directly into Open Claw-specific code.
- Add a narrow adapter boundary that translates:
  - simulator case -> bot input
  - bot proposed action -> Unreal Objects `evaluate_action`
  - approved action -> executable HTTP/API call
  - approval-needed action -> manual review item
- The adapter should own:
  - bot session startup
  - case submission
  - action interception
  - result capture
  - timeout / retry policy
- The plan should assume the bot connects through MCP where possible, because that matches the existing Unreal Objects enforcement model.
- If Open Claw cannot natively emit a structured "proposed action" event, add a thin wrapper process that sits between the bot and its outbound tools and forces all executable calls through the governed action contract.

### 4. Create a dedicated "support-company stress run" CLI

- Add a new CLI instead of overloading `uo-stress-test` or `uo-agent-eval`.
- The CLI should support:
  - case count
  - case mix profile
  - concurrency
  - seed
  - approval reviewer mode
  - bot endpoint / bot config
  - Unreal Objects service URLs
  - report output path
- The CLI should:
  - provision or select a rule group
  - generate a run-specific case batch
  - dispatch cases to the bot
  - wait for completion or timeout
  - collect decision logs and execution results
  - write a versioned report
- The report should include:
  - total cases
  - total governed actions
  - outcome counts by `APPROVE` / `ASK_FOR_APPROVAL` / `REJECT`
  - percentage of bot actions that were governed
  - approval turnaround stats
  - execution success/failure after approval
  - any unguided or bypassed actions
  - per-case timeline samples

### 5. Add a manual review operator surface

- v1 should use real human review for `ASK_FOR_APPROVAL`, not simulated approval.
- Reuse existing approval APIs and pending-decision endpoints.
- Provide a minimal operator workflow:
  - list pending approvals for the run
  - inspect case + requested action + matched rules
  - approve or reject
- If the current UI is sufficient, use it.
- If not, add a minimal run-focused review surface rather than a broad UI redesign.

### 6. Define the initial rule pack for the support company

- Create one reusable support-company rule group with realistic coverage.
- Include rules such as:
  - low-risk standard account updates -> `APPROVE`
  - medium-risk refunds above threshold -> `ASK_FOR_APPROVAL`
  - sensitive identity or payout changes -> `ASK_FOR_APPROVAL`
  - high-risk / fraud-like requests -> `REJECT`
  - missing required identity data -> fail closed
- The rule pack should be stable and hand-authored for v1. Do not depend on LLM rule generation for this effort.
- This keeps the stress test focused on bot behavior under guardrails, not translation accuracy.

## Public APIs / Interfaces / Types

- Add a `SupportCase` type for simulator-produced work items.
- Add a `GovernedBotAction` type for actions proposed by the bot before execution.
- Add a `StressRunResult` / report model for run-level metrics and per-case traces.
- Add a new CLI entrypoint for live support-company stress runs.
- Reuse existing Unreal Objects APIs:
  - `POST /v1/decide`
  - `POST /v1/decide/{request_id}/approve`
  - `GET /v1/pending`
  - `GET /v1/logs/chains/{request_id}`
- Keep the simulator-to-bot adapter as a separate internal interface so Open Claw-specific logic can change without affecting the rest of the harness.

## Test Plan

- Unit tests for support case generation:
  - generated cases always include required fields
  - case mix controls produce the expected distribution
  - seeded runs are reproducible
- Unit tests for action interception:
  - every executable bot action becomes a `GovernedBotAction`
  - no action can execute without an Unreal Objects decision
  - `REJECT` and `ASK_FOR_APPROVAL` paths block execution correctly
- Integration tests against local Rule Engine + Decision Center:
  - approved support action executes and logs correctly
  - rejected support action never executes
  - approval-required action pauses until a human resolves it
  - approval rejection ends the action cleanly
  - audit chain contains request, evaluation, and approval events when applicable
- End-to-end stress scenarios:
  - low-risk mixed case batch with mostly approvals
  - high-risk batch with meaningful reject volume
  - approval-heavy batch to test the human review queue
  - partial bot/tool failure batch to verify reporting and recovery behavior
  - concurrency run that confirms no bypass under load
- Acceptance criteria:
  - 100% of executed bot actions have a matching Unreal Objects decision record
  - 0 bypassed actions in the report
  - approval-required actions remain paused until reviewed
  - per-case traces can reconstruct what happened and why
  - the run report clearly separates business failures from guardrail failures

## Assumptions And Defaults

- The first version targets your real Open Claw bot, not only an in-repo simulator.
- The virtual company is a realistic support company, because that best matches your preference for case/request work.
- The bot acts through HTTP/API-style tools in v1.
- Human approvals are real manual approvals, not simulated.
- The stress objective is business realism first, with throughput as a secondary metric.
- Hand-authored rules are preferred for v1 so the exercise measures guardrail enforcement and bot obedience rather than LLM rule translation quality.
- Existing `uo-agent-eval` logic should be reused conceptually for receipts and result structure, but the new runner should be separate because it needs live bot integration and human review.
