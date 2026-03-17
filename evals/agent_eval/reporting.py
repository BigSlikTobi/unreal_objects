from datetime import UTC, datetime
from pathlib import Path

from evals.agent_eval.models import AgentEvalStats, AgentRunResult


def next_report_path(report_dir: Path) -> Path:
    """Find the next versioned report path (agent_eval_report_v{N}.md)."""
    existing = list(report_dir.glob("agent_eval_report_v*.md"))
    versions: list[int] = []
    for p in existing:
        stem = p.stem  # e.g. "agent_eval_report_v3"
        try:
            v = int(stem.split("_v")[-1])
            versions.append(v)
        except ValueError:
            pass
    next_v = max(versions) + 1 if versions else 1
    return report_dir / f"agent_eval_report_v{next_v}.md"


def compute_stats(results: list[AgentRunResult]) -> AgentEvalStats:
    total_scenarios = len(results)
    passed_scenarios = sum(1 for r in results if r.passed)
    failed_scenarios = total_scenarios - passed_scenarios

    all_steps = [s for r in results for s in r.steps]
    total_steps = len(all_steps)

    if total_steps == 0:
        return AgentEvalStats(
            total_scenarios=total_scenarios,
            passed_scenarios=passed_scenarios,
            failed_scenarios=failed_scenarios,
            total_steps=0,
            decision_accuracy=0.0,
            obedience_rate=0.0,
            receipt_validity_rate=0.0,
            human_loop_completion_rate=0.0,
        )

    decision_accuracy = sum(1 for s in all_steps if s.outcome_correct) / total_steps
    obedience_rate = sum(1 for s in all_steps if s.agent_obeyed) / total_steps
    receipt_validity_rate = sum(1 for s in all_steps if s.receipt_valid) / total_steps

    ask_steps = [s for s in all_steps if s.expected_outcome == "ASK_FOR_APPROVAL"]
    if ask_steps:
        ask_with_approval = sum(
            1 for s in ask_steps if s.receipt_valid and not s.receipt_errors
        )
        human_loop_completion_rate = ask_with_approval / len(ask_steps)
    else:
        human_loop_completion_rate = 1.0

    return AgentEvalStats(
        total_scenarios=total_scenarios,
        passed_scenarios=passed_scenarios,
        failed_scenarios=failed_scenarios,
        total_steps=total_steps,
        decision_accuracy=decision_accuracy,
        obedience_rate=obedience_rate,
        receipt_validity_rate=receipt_validity_rate,
        human_loop_completion_rate=human_loop_completion_rate,
    )


def write_agent_eval_report(
    report_path: Path,
    results: list[AgentRunResult],
    stats: AgentEvalStats,
    *,
    domain: str,
) -> None:
    """Write a versioned markdown agent eval report."""
    scenario_rows = "\n".join(
        f"| {r.scenario_id} | {'PASS' if r.passed else 'FAIL'} | "
        f"{sum(1 for s in r.steps if s.outcome_correct)}/{len(r.steps)} steps correct |"
        f" {r.error or ''} |"
        for r in results
    )

    step_failures = []
    for r in results:
        for s in r.steps:
            if not s.outcome_correct or not s.receipt_valid:
                step_failures.append(
                    f"- `{r.scenario_id}` step {s.step_index}: "
                    f"expected={s.expected_outcome}, actual={s.actual_outcome}, "
                    f"receipt_errors={s.receipt_errors}"
                )
    failures_section = "\n".join(step_failures) or "- None"

    report = f"""# Agent Eval Report

**Date**: {datetime.now(UTC).date()}
**Domain**: {domain}

## Summary

| Metric | Value |
| --- | ---: |
| Total Scenarios | {stats.total_scenarios} |
| Passed | {stats.passed_scenarios} |
| Failed | {stats.failed_scenarios} |
| Total Steps | {stats.total_steps} |
| Decision Accuracy | {stats.decision_accuracy * 100:.1f}% |
| Agent Obedience Rate | {stats.obedience_rate * 100:.1f}% |
| Receipt Validity Rate | {stats.receipt_validity_rate * 100:.1f}% |
| Human Loop Completion | {stats.human_loop_completion_rate * 100:.1f}% |

## Scenario Results

| Scenario | Result | Steps | Error |
| --- | --- | --- | --- |
{scenario_rows}

## Step Failures

{failures_section}
"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report)
