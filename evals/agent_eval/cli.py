"""CLI entry point for the agent eval harness.

Usage:
    python -m evals.agent_eval.cli [options]
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

from decision_center.stress_test.evaluation import ensure_services_available
from evals.agent_eval.models import AgentRunResult
from evals.agent_eval.reporting import compute_stats, next_report_path, write_agent_eval_report
from evals.agent_eval.runner import run_scenario
from evals.agent_eval.scenarios.ecommerce import ECOMMERCE_SCENARIOS
from evals.agent_eval.scenarios.finance import FINANCE_SCENARIOS
from evals.agent_eval.scenarios.generated import GENERATED_SCENARIOS, generate_scenarios


def _start_services(rule_engine_url: str, decision_center_url: str) -> list[subprocess.Popen]:
    """Start Rule Engine and Decision Center as background processes."""
    re_parsed = urlparse(rule_engine_url)
    dc_parsed = urlparse(decision_center_url)

    re_port = re_parsed.port
    dc_port = dc_parsed.port

    for name, url, port in (
        ("rule_engine_url", rule_engine_url, re_port),
        ("decision_center_url", decision_center_url, dc_port),
    ):
        if port is None:
            raise ValueError(f"{name} must include an explicit port (got {url!r})")
        if not isinstance(port, int) or not (0 < port < 65536):
            raise ValueError(f"Invalid port {port!r} extracted from {name}={url!r}")

    procs = [
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "rule_engine.app:app", "--port", str(re_port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ),
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "decision_center.app:app", "--port", str(dc_port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ),
    ]

    # Wait for services to become available
    max_wait = 10
    start = time.monotonic()
    while time.monotonic() - start < max_wait:
        try:
            with httpx.Client(timeout=2.0) as c:
                c.get(f"{rule_engine_url}/v1/groups").raise_for_status()
                c.get(f"{decision_center_url}/v1/decide", params={
                    "request_description": "healthcheck",
                    "context": "{}",
                    "group_id": "missing",
                })
            return procs
        except Exception:
            # Check if either process died
            for p in procs:
                if p.poll() is not None:
                    _stop_services(procs)
                    raise RuntimeError(f"Service process exited with code {p.returncode}")
            time.sleep(0.5)

    _stop_services(procs)
    raise RuntimeError(f"Services did not become available within {max_wait}s")


def _stop_services(procs: list[subprocess.Popen]) -> None:
    for p in procs:
        p.terminate()
    for p in procs:
        p.wait(timeout=5)


def _get_scenarios(domain: str, scenario_id: str | None, seed: int = 42):
    generated = generate_scenarios(500, seed=seed) if seed != 42 else GENERATED_SCENARIOS
    all_scenarios = {
        "finance": FINANCE_SCENARIOS,
        "ecommerce": ECOMMERCE_SCENARIOS,
        "generated": generated,
    }
    if domain == "all":
        pool = FINANCE_SCENARIOS + ECOMMERCE_SCENARIOS
    elif domain == "generated":
        pool = generated
    elif domain == "full":
        pool = FINANCE_SCENARIOS + ECOMMERCE_SCENARIOS + generated
    else:
        pool = all_scenarios.get(domain, [])

    if scenario_id:
        pool = [s for s in pool if s.scenario_id == scenario_id]
        if not pool:
            print(f"No scenario found with id '{scenario_id}'", file=sys.stderr)
            sys.exit(1)

    return pool


async def _run(args: argparse.Namespace) -> int:
    managed_procs: list[subprocess.Popen] = []
    try:
        await ensure_services_available(args.rule_engine_url, args.decision_center_url)
    except Exception:
        if args.fail_on_missing_services:
            print("Services unavailable and --fail-on-missing-services is set.", file=sys.stderr)
            return 1
        print("Services not running — starting them automatically ...", flush=True)
        try:
            managed_procs = _start_services(args.rule_engine_url, args.decision_center_url)
            print("Services started.")
        except RuntimeError as exc:
            print(f"Failed to start services: {exc}", file=sys.stderr)
            return 1

    try:
        scenarios = _get_scenarios(args.domain, getattr(args, "scenario", None), seed=args.seed)
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
    finally:
        if managed_procs:
            print("Stopping services ...")
            _stop_services(managed_procs)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="uo-agent-eval",
        description="End-to-end simulated agent evaluation",
    )
    parser.add_argument(
        "--domain",
        choices=["finance", "ecommerce", "generated", "full", "all"],
        default="all",
        help="Domain to evaluate: finance, ecommerce, generated (500 scenarios), full (all + generated), all (finance+ecommerce only)",
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
    parser.add_argument(
        "--seed",
        default="42",
        help="Seed for generated scenarios. Use 'random' for a new set each run, or an integer for reproducibility (default: 42)",
    )

    args = parser.parse_args()
    if args.seed.lower() == "random":
        import random as _random
        args.seed = _random.randint(0, 2**31)
        print(f"Using random seed: {args.seed}")
    else:
        args.seed = int(args.seed)
    exit_code = asyncio.run(_run(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
