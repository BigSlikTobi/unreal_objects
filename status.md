# Deborahbot — LLM-driven worker status

> Snapshot: 2026-04-09. Tracks the journey of moving the autonomous waste-disposal worker from a hand-coded Python loop to an LLM-driven openclaw cron agent that uses MCP tools to call the Unreal Objects guardrail engine.

This document is a living log: what the bot has learned to do on its own, what we had to fix for it, what's still rough, and what to try next. Open to extension as we keep iterating.

---

## 1. Architecture today

```
        ┌──────────────────────────────┐
        │  openclaw cron               │
        │  every 30s (id=953df524…)    │
        │  agent=main, model=          │
        │  openai-codex/gpt-5.4-mini   │
        └──────────────┬───────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │  agent reads                 │
        │  WORKER_BRIEF.md             │
        │  (~/.openclaw/workspace)     │
        └──────────────┬───────────────┘
                       │
                       ▼
   ┌───────────────────────────────────────────┐
   │  Per-tick procedure                       │
   │  1. GET /api/v1/orders?status=open        │
   │  2. Claim up to 8 in parallel             │
   │  3. Build context_json with rule aliases  │
   │  4. evaluate_action × 2 rule groups       │
   │  5. Combine outcomes (most-restrictive)   │
   │  6. POST /orders/{id}/result              │
   └───────────────────┬───────────────────────┘
                       │
        ┌──────────────┴───────────────┐
        │                              │
        ▼                              ▼
  Company API                    MCP server
  (unrealobjectsinc)             (mcp-production-a4ff)
                                       │
                                       ▼
                               Decision Center
                                       │
                                       ▼
                               Rule Engine
                               (2 groups)
```

**Hybrid worker (option 2)** is also installed but **disabled**: `~/.openclaw/workspace/unreal_worker_hybrid.py` + `unreal-worker-hybrid.service`. Pure-Python fallback for when we want zero-LLM throughput. Not in active use because the goal is to test LLM-driven autonomy.

---

## 2. Decisions the bot made on its own to optimize

These were emergent — we did not pre-program them.

### 2.1 Discovered MCP via the bundled `mcporter` skill
On its very first tick the agent didn't know how to invoke the MCP tools (they aren't bound as native function calls in openclaw — they're only reachable via the `mcporter` CLI). It found the `mcporter` skill on its own, ran `mcporter list` to enumerate servers, then `mcporter list <server> --schema` to read the tool signatures. From that point on it knew the contract for `evaluate_action`, `get_rule_group`, etc.

### 2.2 Switched to python heredocs after shell-quoting failures
The agent first tried `mcporter call ...evaluate_action --args '{json}'` with the JSON inline as a shell argument. Bash tokenization broke the JSON every time — three failed attempts in a row with `Unable to parse --args: Unterminated string`. After we documented the python-heredoc pattern in `WORKER_BRIEF.md` the agent adopted it cleanly.

### 2.3 Self-corrected the `/claim` payload
The first attempt at `POST /orders/{id}/claim` used an empty body `{}`. The company API returned `422 missing bot_id`. The agent immediately retried with `{"bot_id": "deborahbot3000"}` and it worked.

### 2.4 Inferred rule-variable aliases from natural-language reasoning
The rules use idealised field names (`estimated_margin`, `quoted_revenue`, `waste_type`). The order payload uses implementation names (`baseline_margin_eur`, `offered_price_eur`, `declared_waste_type`). The brief's mapping table guided the agent, but it also **added bonus fields** the brief never mentioned — `bankruptcy_threshold_eur`, `contamination_risk`, `current_cash_balance_eur`, `hazardous_flag`, `priority` — because it judged them potentially relevant. This is exactly the autonomous reasoning we wanted.

### 2.5 Began batching orders into a single python heredoc
The brief originally said "for each order, in sequence". The agent figured out on its own to **process multiple orders inside one python script** — fetching details, claiming, and posting results in a single heredoc loop. Token-efficient, self-discovered.

### 2.6 Used openclaw's long-running `process` primitive
For commands that don't return quickly the agent started using openclaw's `process poll` / `process write` session pattern instead of blocking `exec`. Lets it keep working while a long shell command runs in the background.

---

## 3. Decisions we made for the bot

### 3.1 Stop trusting the company API for `group_id`
The company server publishes `group_id` in `/api/v1/status`, but the published value (`6a15655b…`) doesn't exist in the rule engine — every Decision Center call fail-closed to `ASK_FOR_APPROVAL`. We told the worker (and now the cron prompt) to **always use** the user-curated groups: `efb32f5b…` (operational profitability) and `7af3989c…` (environmental safety).

### 3.2 Use BOTH rule groups, combine most-restrictive-wins
The new agent identity has `allowed_group_ids` containing both groups. The cron prompt evaluates every order against both, then combines (`REJECT > ASK_FOR_APPROVAL > APPROVE`).

### 3.3 Switched the decision_center MCP token plumbing
The token refresh service originally only updated `mcporter.json`. After re-enrollment it left `openclaw.json` with the stale first-issued bearer, so openclaw's native MCP client got `401 expired` for ~15 minutes after each enrollment. Patched the refresh script + systemd unit to also rewrite `openclaw.json` on every cycle.

### 3.4 Scheduled cron with `--every 30s --thinking minimal --timeout-seconds 240`
- 30 s tick ≈ matches the legacy worker's responsiveness
- `minimal` thinking is enough for these simple business decisions
- 240 s timeout because LLM ticks can run 50–100 s with batches of 8 orders

### 3.5 Disabled and retired the legacy `unreal-worker.service`
Renamed `unreal_worker.py` → `.retired-20260409` so it's clearly out of the active set. Systemd unit stopped + disabled. Conflict directive added to the new hybrid unit so the two can never run simultaneously.

---

## 4. Things we had to fix in the rules / data

### 4.1 `Low Profit URGENT` rule used a phantom field
The rule asked for `order_status == urgent`, but the company API never sends `order_status` — orders carry `priority: standard|urgent`. The fuzzy variable mapper couldn't connect the two (no shared word parts), so the rule failed-closed on every order, escalating everything. **You edited the rule** to use `priority` instead. Approval rate dropped from 100% to ~10% afterwards.

### 4.2 `mcp.servers` token sync
See 3.3. The token refresh script now keeps `openclaw.json` and `mcporter.json` in sync with the live `client_credentials` exchange.

### 4.3 Decision Center volume removed
Earlier today: dropped Railway volume persistence on Decision Center, replaced with on-demand JSON export. Saves cost; logs reset on redeploy. PR #37 merged.

### 4.4 Rule engine volume — STILL BROKEN
The `rule_engine-volume` is mounted at `/app/data ` (literal trailing space). Writes go to ephemeral disk, every redeploy wipes all rules. Not yet fixed. Currently the rules are intact because nobody has redeployed Rule Engine since you re-created them this morning. **This is a ticking time bomb.**

---

## 5. Live numbers (rolling)

| Metric | Value |
|---|---|
| Cron tick cadence | every 30 s |
| Avg successful tick duration (post brief v2 + parallel) | ~50 s |
| Batch size | 8 orders/tick |
| Last 3 ticks | all `ok` |
| Total orders since switch | 367 |
| Completed (APPROVED + routed) | 74 |
| Blocked (APPROVAL_REQUIRED) | 9 |
| Rejected (REJECT) | 0 |
| Active containers | 38 (24 started, 32 rented) |
| Overflow events | 21 (worth investigating) |

**MCP audit trail:** Decision Center now shows entries with `agent_id=agt_kNnA22fRvaY` and `credential_id=cred_MWRgwI2Cyzk` on every evaluation. Identity is propagating end-to-end.

---

## 6. Open issues — technical

These are real bugs or rough edges that need hands-on fixes:

1. **`rule_engine-volume` mount path bug** (see 4.4). A redeploy of `rule_engine` wipes everything. Fix by detaching the volume in the Railway dashboard and re-attaching at `/app/data` (no trailing space). The 150 MB on the existing volume is empty filesystem overhead — nothing to migrate.
2. **Token refresh service unit type mismatch.** `refresh_mcp_token.service` is `Type=oneshot` but the script loops forever. Systemd reports it as `activating` indefinitely. Functionally fine, cosmetically broken. Should be `Type=simple` with `Restart=on-failure`.
3. **Cron ticks > 60 s timeout** still happen occasionally (had two 120 s timeouts before brief v2). With 240 s headroom this is under control, but at higher batch sizes it could come back.
4. **Many concurrent `claim` calls return success even if another worker already claimed the order.** Worth verifying the company API enforces idempotency on `/claim`.
5. **Overflow count climbing** (21 in the last hour). Either container rentals aren't keeping up with demand, or rentals are too small for the average order. Inspect company FE.
6. **Decision Center is in-memory** (since PR #37). On every redeploy of `decision_center` the audit trail and pending approvals reset. Snapshot via `GET /v1/logs/export` before any redeploy.

---

## 7. Open issues — yet to be discovered

These are areas where we don't yet know the failure mode but suspect there's one lurking:

1. **What happens when ChatGPT Plus rate-limits openai-codex?** Today's re-auth got us going but we haven't hit the limit yet. The cron will start failing — need to know whether systemd-style backoff kicks in or if the cron grinds to halt.
2. **What happens at 1000+ orders/day?** 50 s/tick × 30 ticks/hour = 30 LLM-agent runs/hour. If the company server starts firing 100 orders/minute we will fall behind. No back-pressure mechanism today.
3. **Long-running ticks holding the isolated session.** Cron uses `--session isolated --session-key waste-worker`, but each cron run gets a unique `runId` → fresh session. If openclaw ever switches to context-reuse, we'll need to re-test.
4. **Two simultaneous workers competing for the same orders.** The hybrid systemd unit has `Conflicts=unreal-worker.service` but does NOT block the openclaw cron. If both run at once, race conditions on `/claim`.
5. **Schema files (`schemas/*.json`) on the deployed Decision Center are ephemeral.** Custom schemas saved in the UI vanish on redeploy unless committed to git. Same class of problem as the rule engine volume but for schemas.
6. **Token-cost telemetry.** We have no metering on per-tick LLM cost. We see `dur=49s` but not `tokens=N`. Hard to budget without that.
7. **Bot ID ↔ MCP agent ID coupling.** The bot uses `bot_id=deborahbot3000` for the company API and `agent_id=agt_kNnA22fRvaY` for MCP. If you ever rotate one without the other, audit trails will diverge from operational identity.
8. **What if a rule takes >30 s to evaluate?** Decision Center's `/v1/decide` has no internal timeout that I've verified. Could deadlock the worker.

---

## 8. Improvement backlog

See section 9 for the prioritised list. Section 8 is the open superset.

- Bind MCP tools as native function-calling tools in openclaw so the agent doesn't have to shell out via `mcporter call`. Would cut 5–10 turns per tick.
- Pre-compute the action choice deterministically (Python helper) and let the LLM only verify + map fields. Cuts thinking time.
- Cache rule-variable mapping per group across ticks (hash of group's `rules` array → cached alias dict).
- Add a `--batch-eval` MCP tool that evaluates N actions in one round-trip instead of N separate `/v1/decide` calls.
- Per-rule justification template in WORKER_BRIEF.md so the agent always writes the same shape of summary, easier to render in the UI.
- Move `WORKER_BRIEF.md` into git so it's versioned + auditable.
- Move `unreal_worker_hybrid.py` into git for the same reason.
- Token usage logging: have the cron message instruct the agent to report `tokens_used: N` after each tick.

---

## 9. Recommended next steps

Ordered by effort vs. impact.

**Today / tomorrow:**
1. ⚠ **Fix `rule_engine-volume` mount path** — 5-min Railway dashboard task, eliminates the time bomb.
2. **Update `WORKER_BRIEF.md` to require justification + recommendation in `decision_summary`** for every APPROVAL_REQUIRED outcome (in progress now).
3. **Investigate the `Low positive margin GENERAL` false positive** seen in the recycling-collection screenshot (margin 48 % shouldn't trigger a < 15 % rule — likely fail-closed because the agent didn't pass `estimated_profit` consistently).

**This week:**
4. **Move WORKER_BRIEF.md and unreal_worker_hybrid.py into git** under `bots/deborahbot3000/`. Survives bot reinstalls.
5. **Add a `/v1/decide/batch` endpoint** to Decision Center so the agent can evaluate up to N actions in one HTTP call. Cuts MCP round-trips by 2× (we currently call once per group).
6. **Token telemetry**: have the cron prompt log estimated tokens, expose via `openclaw cron runs` extra fields if possible.
7. **Fix `refresh_mcp_token.service`** unit type (`Type=simple` + `Restart=on-failure`).

**This month:**
8. **Native MCP function tools in openclaw.** Either via a plugin or by upstreaming a feature request. Biggest single win for token cost.
9. **Pre-compute action choice in a Python skill**, hand the LLM a "verify + tweak" task instead of "decide from scratch". Could halve tick duration.
10. **Multi-bot mode**: run `deborahbot3000` and a second bot identity in parallel with separate group permissions, prove the auth boundary works.
11. **Backpressure**: if backlog > N, increase batch size automatically; if rate-limited by openai-codex, back off gracefully and surface the state.

---

## 10. Rollback recipes

If the LLM cron breaks badly:

```bash
# Switch to hybrid Python worker (no LLM)
openclaw cron disable 953df524-5e84-4361-a529-b5ccab62850b
sudo systemctl enable --now unreal-worker-hybrid.service

# Switch back to LLM cron
sudo systemctl disable --now unreal-worker-hybrid.service
openclaw cron enable 953df524-5e84-4361-a529-b5ccab62850b
```

The legacy `unreal-worker.service` is **disabled and deprecated** — do not re-enable it. Use the hybrid worker instead.

---

## 11. Identifiers reference

| What | Value |
|---|---|
| MCP server name (in mcporter / openclaw) | `unreal_objects_inc-live-agent-unreal-objects` |
| MCP base URL | `https://mcp-production-a4ff.up.railway.app` |
| Agent ID | `agt_kNnA22fRvaY` |
| Credential ID | `cred_MWRgwI2Cyzk` |
| Client ID | `uo_client_GriV_2LQlwM` |
| Operational rules group | `efb32f5b-58f8-45e3-a614-0c0b20b326d5` (`unreal_objects_inc`) |
| Environmental safety group | `7af3989c-0f63-4fbc-8b2b-d5a571ea38a2` (`environmental_safety_rules`) |
| Cron job ID | `953df524-5e84-4361-a529-b5ccab62850b` |
| Bot host | `deborahbot3000@192.168.178.66` |
