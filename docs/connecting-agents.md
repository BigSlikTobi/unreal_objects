# 🤖 Connecting Your AI Agents

Your autonomous AI agents interact with Unreal Objects exclusively through the
built-in **MCP Server**. The MCP Server is the single enforced gateway between
your agent and the real world — it does not just advise the agent, it _is_ the
only path to real actions.

---

## Starting the MCP Server

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

| Flag              | Default     | Purpose                                                                       |
| ----------------- | ----------- | ----------------------------------------------------------------------------- |
| `--transport`     | `stdio`     | `stdio`, `streamable-http`, or `sse`                                          |
| `--host`          | `127.0.0.1` | Bind address for HTTP transports                                              |
| `--port`          | `8000`      | Port for HTTP transports                                                      |
| `--group-id`      | _(none)_    | Rule group applied to all evaluations — agent cannot override this            |
| `--allowed-hosts` | auto        | Comma-separated Host headers to accept; defaults to `*` when `--host 0.0.0.0` |

> **`--group-id` is the key security flag.** When set, every `evaluate_action`
> call is evaluated against that rule group. The agent never sees, chooses, or
> influences which ruleset applies to it.

---

## How the Guardrail Works

On every `initialize` handshake the MCP Server sends a mandatory protocol
statement directly to the agent via the MCP `instructions` field. The agent is
told:

- Call `guardrail_heartbeat` on startup. Stop if the system is unhealthy.
- Call `evaluate_action` before every real-world action and obey the outcome
  absolutely.
- `APPROVE` → proceed. `REJECT` → stop and explain. `ASK_FOR_APPROVAL` → pause,
  surface to human, call `submit_approval`.

```
Agent wants to send an email
        │
        ▼
  evaluate_action("Send invoice email to client", '{"recipient": "acme@example.com"}', "user_4821")
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

---

## Available Tools

| Tool                  | Purpose                                                                                                                           |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `guardrail_heartbeat` | Checks that Rule Engine and Decision Center are reachable. Call on startup.                                                       |
| `evaluate_action`     | Evaluates a planned action against business rules. Call before every real-world action. Requires `user_id` in authenticated mode. |
| `submit_approval`     | Records a human approval decision for an `ASK_FOR_APPROVAL` outcome.                                                              |
| `list_rule_groups`    | Lists all configured rule groups.                                                                                                 |
| `get_rule_group`      | Gets a specific rule group and its rules.                                                                                         |
| `get_decision_log`    | Reads the audit log (`atomic`, `chains`, or `chain` by `request_id`).                                                             |
| `get_pending`         | Lists actions currently awaiting human approval.                                                                                  |

---

## Governing Actions — the Pattern

The governance pattern is always the same, regardless of what the agent is
doing:

```
Agent decides to act → calls evaluate_action → obeys the outcome → acts with its own tools
```

```python
# Before sending the email:
decision = await evaluate_action(
    "Send invoice email",
    '{"contact_person": "premium", "recipient": "acme@example.com"}',
    "user_4821",
)
if decision["outcome"] == "APPROVE":
    send_email(...)            # agent's own tool
elif decision["outcome"] == "ASK_FOR_APPROVAL":
    # surface to user, call submit_approval, then send if approved
elif decision["outcome"] == "REJECT":
    # explain to user, do not send
```

No special proxy tools are needed. The agent's existing action tools (email,
HTTP, file, database) stay exactly where they are. `evaluate_action` is the
single integration point.

---

## ASK_FOR_APPROVAL — Human-in-the-Loop Flow

When `evaluate_action` returns `ASK_FOR_APPROVAL`:

- The agent surfaces the request to the human.
- Once the human decides, the agent calls `submit_approval`.
  - `approved=True` → agent proceeds.
  - `approved=False` → agent stops.

The `request_id` from `evaluate_action` ties together the Decision Center audit
log entry, the `submit_approval` record, and the agent's execution — giving
operators a complete, tamper-evident chain.

---

## Agent Identity & Authenticated HTTP MCP

Unreal Objects supports authenticated HTTP MCP access for remote agents. The
permission model is:

- one stable `agent_id` per agent application or runtime
- one or more scoped credentials per agent
- one `user_id` supplied by the agent on every governed action

This lets one agent hold separate finance and support credentials without
collapsing them into one broad trust domain.

> **Current limitation:** Agent registrations are stored in memory only.
> Restarting the MCP server clears auth state.

Authenticated MCP is supported for HTTP transports only (`streamable-http`,
`sse`). `stdio` remains available for local development without auth.

The admin bootstrap surface (`/v1/admin/*`, `/v1/agents/enroll`,
`/oauth/token`, and `/instructions`) is only exposed when the MCP server starts
with `--auth-enabled`. Supplying `--admin-api-key` without `--auth-enabled`
does not turn those routes on.

### Auth Flow

1. An operator creates an agent and a one-time enrollment token through the
   admin API.
2. The agent exchanges that enrollment token once to receive a `client_id` and
   `client_secret`.
3. The agent calls `/oauth/token` with the OAuth client credentials grant.
4. The agent connects to the MCP endpoint with `Authorization: Bearer <token>`.
5. Every `evaluate_action` call includes `user_id`; `agent_id` and
   `credential_id` are derived from the bearer token.

For agents that need bootstrap help before they're authenticated, call the
public `GET /instructions` endpoint. It returns the bootstrap recipe in simple
JSON using relative paths (`/v1/agents/enroll`, `/oauth/token`, `/mcp`) so no
LAN IP needs to be hardcoded.

### Enrollment Example

```bash
curl -X POST http://127.0.0.1:8000/v1/agents/enroll \
  -H "Content-Type: application/json" \
  -d '{"enrollment_token":"enroll_123"}'
```

Response:

```json
{
    "agent_id": "agt_ops_01",
    "credential_id": "cred_finance_a",
    "client_id": "uo_client_finance_a",
    "client_secret": "uo_secret_once_only",
    "scopes": [],
    "default_group_id": "grp_finance_prod",
    "allowed_group_ids": ["grp_finance_prod"]
}
```

### OAuth Token Example

```bash
curl -X POST http://127.0.0.1:8000/oauth/token \
  -H "Content-Type: application/json" \
  -d '{
    "grant_type": "client_credentials",
    "client_id": "uo_client_finance_a",
    "client_secret": "uo_secret_once_only"
  }'
```

Response:

```json
{
    "access_token": "uo_at_abc123",
    "token_type": "Bearer",
    "expires_in": 900,
    "scope": ""
}
```

### Identity in the Audit Trail

Authenticated decisions carry these identity fields end to end:

- `agent_id`: which agent software called the MCP server
- `credential_id`: which scoped credential it used
- `user_id`: which user the agent claims it is acting for
- `effective_group_id`: which rule group actually governed the decision

---

## Operator Admin Surfaces

Two surfaces for managing agent permissions:

- **Agent Admin workspace** in the React app — create agents, issue enrollment
  tokens, revoke credentials
- **CLI** for the same tasks when operators prefer terminal workflows

The Agent Admin workspace requires:

- MCP base URL, usually `http://127.0.0.1:8000`
- admin API key configured on the MCP server

```bash
uo-agent-admin create-agent --name "Ops Agent" --description "Shared runtime"
uo-agent-admin issue-enrollment-token agt_ops_01 \
  --credential-name finance \
  --default-group-id grp_finance_prod \
  --allowed-group-id grp_finance_prod
uo-agent-admin revoke-credential cred_finance_a
```

---

## Enforcement Model and Its Limits

Unreal Objects relies on the agent calling `evaluate_action` before acting.

| Threat                                            | Stopped?                                        |
| ------------------------------------------------- | ----------------------------------------------- |
| Agent forgets to call evaluate_action             | Yes — mandatory protocol instruction            |
| User instructs agent to skip rules                | Partially — strong deterrent for aligned models |
| Jailbreak / adversarial prompt injection          | No — instructional controls only                |
| Agent has a parallel MCP tool for the same action | No — nothing prevents a direct call             |

### How to Strengthen Enforcement

- **Single-MCP deployment:** Give the agent only one MCP server (Unreal
  Objects). Any action capability the agent needs should be implemented there.
- **Operator system prompt:** Reinforce the governance requirement in your own
  system prompt.
- **Audit log monitoring:** Check `get_decision_log` regularly. Any real-world
  action with no matching evaluation entry is a signal of bypass.
