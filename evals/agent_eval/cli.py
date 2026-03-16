"""CLI entry point for the agent eval harness.

Usage:
    python -m evals.agent_eval.cli [options]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import httpx

from decision_center.stress_test.evaluation import ensure_services_available
from evals.agent_eval.models import AgentRunResult
from evals.agent_eval.reporting import compute_stats, next_report_path, write_agent_eval_report
from evals.agent_eval.runner import run_scenario
from evals.agent_eval.scenarios.ecommerce import ECOMMERCE_SCENARIOS
from evals.agent_eval.scenarios.finance import FINANCE_SCENARIOS


def _get_scenarios(domain: str, scenario_id: str | None):
    all_scenarios = {
        "finance": FINANCE_SCENARIOS,
        "ecommerce": ECOMMERCE_SCENARIOS,
    }
    if domain == "all":
        pool = FINANCE_SCENARIOS + ECOMMERCE_SCENARIOS
    else:
        pool = all_scenarios.get(domain, [])

    if scenario_id:
        pool = [s for s in pool if s.scenario_id == scenario_id]
        if not pool:
            print(f"No scenario found with id '{scenario_id}'", file=sys.stderr)
            sys.exit(1)

    return pool


async def _run(args: argparse.Namespace) -> int:
    if args.fail_on_missing_services:
        try:
            await ensure_services_available(args.rule_engine_url, args.decision_center_url)
        except Exception as exc:
            print(f"Services unavailable: {exc}", file=sys.stderr)
            return 1
    else:
        try:
            await ensure_services_available(args.rule_engine_url, args.decision_center_url)
        except Exception as exc:
            print(f"Warning: services may be unavailable ({exc})", file=sys.stderr)

    scenarios = _get_scenarios(args.domain, getattr(args, "scenario", None))
    if not scenarios:
        print("No scenarios to run.", file=sys.stderr)
        return 1

    results: list[AgentRunResult] = []
    for scenario in scenarios:
        print(f"Running scenario: {scenario.scenario_id} ...", end=" ", flush=True)
        try:
            result = await run_scenario(
                scenario=scenario,
                rule_engine_url=args.rule_engine_url,
                decision_center_url=args.decision_center_url,
                keep_group=args.keep_group,
            )
            results.append(result)
            print("PASS" if result.passed else "FAIL")
        except Exception as exc:
            results.append(
                AgentRunResult(
                    scenario_id=scenario.scenario_id,
                    passed=False,
                    steps=[],
                    error=str(exc),
                )
            )
            print(f"ERROR: {exc}")

    stats = compute_stats(results)
    report_dir = Path(args.report_dir)
    report_path = next_report_path(report_dir)
    write_agent_eval_report(report_path, results, stats, domain=args.domain)
    print(f"\nReport written to: {report_path}")
    print(
        f"Results: {stats.passed_scenarios}/{stats.total_scenarios} scenarios passed"
    )
    print(f"  Decision Accuracy:      {stats.decision_accuracy * 100:.1f}%")
    print(f"  Agent Obedience Rate:   {stats.obedience_rate * 100:.1f}%")
    print(f"  Receipt Validity Rate:  {stats.receipt_validity_rate * 100:.1f}%")
    print(f"  Human Loop Completion:  {stats.human_loop_completion_rate * 100:.1f}%")

    if stats.failed_scenarios > 0:
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="uo-agent-eval",
        description="End-to-end simulated agent evaluation",
    )
    parser.add_argument(
        "--domain",
        choices=["finance", "ecommerce", "all"],
        default="all",
        help="Domain to evaluate (default: all)",
    )
    parser.add_argument(
        "--scenario",
        default=None,
        help="Specific scenario_id to run",
    )
    parser.add_argument(
        "--rule-engine-url",
        default="http://127.0.0.1:8001",
        dest="rule_engine_url",
    )
    parser.add_argument(
        "--decision-center-url",
        default="http://127.0.0.1:8002",
        dest="decision_center_url",
    )
    parser.add_argument(
        "--report-dir",
        default="evals",
        dest="report_dir",
    )
    parser.add_argument(
        "--keep-group",
        action="store_true",
        dest="keep_group",
        help="Do not delete rule groups after the run",
    )
    parser.add_argument(
        "--fail-on-missing-services",
        action="store_true",
        dest="fail_on_missing_services",
        help="Exit with code 1 if services are not reachable",
    )

    args = parser.parse_args()
    exit_code = asyncio.run(_run(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
