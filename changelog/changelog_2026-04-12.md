# Changelog — 2026-04-12

## Summary

Operational day: onboarded a second LLM-driven bot (Phil) for proactive container management alongside the existing deborahbot3000 waste-disposal worker, and tuned deborahbot's batch size to prevent Pi queue buildup. No code changes were committed to the repo today — the session's code fix (MCP memory leak, PR #38) landed on 2026-04-10.

## Changes

### Bot operations (on-device, not repo changes)

- **Phil onboarded** (`phil@192.168.178.61`): new openclaw LLM-driven cron bot for proactive container management
  - Enrolled in MCP server, synced gateway tokens, configured `mcporter` and `openclaw.json`
  - Authored `WORKER_BRIEF.md` for container management procedure (scan containers, evaluate early empties via `evaluate_action`)
  - Fought and resolved openclaw 2026.4.9 pairing issues: read-only scopes, gateway token mismatch, slow Pi init (~2.5 min)
  - Fixed by: reinstalling openclaw, syncing gateway tokens, waiting for full initialization
  - Created `container-manager` cron job (every 5 min, batch 6, 240 s timeout)
  - First tick completed successfully in 122 s

- **deborahbot3000 tuned**: reduced batch size from 8 → 5 orders per tick and added explicit "finish before claiming more" instruction to `WORKER_BRIEF.md` to prevent queue buildup on the Raspberry Pi

### Documentation

- **`status.md` added to repo root**: comprehensive operational status document covering both bot architectures, identifiers, open issues, improvement backlog, rollback recipes, and live metrics (snapshot date: 2026-04-09, updated with current state)

### Carryover from branch `fix/mcp-memory-leak` (PR #38, merged 2026-04-10)

- MCP `stateless_http=True` fix and `_prune_expired_tokens()` addition are already in `main` via the merged PR

## Files Modified

- `status.md` — new file; comprehensive operational status document for the bot ecosystem
- `changelog/changelog_2026-04-12.md` — this file

## Code Quality Notes

- **Tests**: 306 passed, 5 pre-existing errors in `evals/agent_eval/tests/test_runner.py` (`dc_store.atomic_logs.clear()` — pre-existing API mismatch, not introduced today)
- **Linting**: UI files not changed today; pre-existing ESLint baseline unchanged (2 errors + 2 warnings in `ChatInterface.tsx` and `AgentAdminPanel.tsx`)
- No new code was introduced today — no new lint or test issues

## Open Items / Carry-over

- **Rule Engine volume mount bug** — trailing space in Railway mount path (`/app/data `) causes rules to write to ephemeral disk; a Railway redeploy wipes all rules. Fix: detach and re-attach volume at `/app/data` (no trailing space). Time bomb.
- **`refresh_mcp_token.service` unit type mismatch** — `Type=oneshot` but script loops forever; should be `Type=simple` with `Restart=on-failure`
- **Token usage optimization** — no per-tick LLM cost telemetry; company server acceleration reduced to 2x as interim measure
- **Decision Center in-memory** — audit log + pending approvals reset on every Railway redeploy; export via `GET /v1/logs/export` before any deploy
- **Schema files ephemeral** — `schemas/*.json` saved in UI vanish on redeploy unless committed to git
- **WORKER_BRIEF.md and hybrid worker not in git** — Phil's and deborahbot's briefs live on the Pi, not versioned
- **Overflow count** — 21 overflow events on deborahbot in last tracked hour; container rentals may not be keeping up with demand
