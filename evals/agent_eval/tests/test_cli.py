import pytest
import sys
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
import tempfile

from evals.agent_eval.models import AgentRunResult, StepResult, AgentEvalStats


def make_passing_result(scenario_id="test_scenario"):
    step = StepResult(
        step_index=0,
        expected_outcome="APPROVE",
        actual_outcome="APPROVE",
        outcome_correct=True,
        agent_obeyed=True,
        receipt_valid=True,
        receipt_errors=[],
        request_id="req-001",
    )
    return AgentRunResult(scenario_id=scenario_id, passed=True, steps=[step])


def make_failing_result(scenario_id="fail_scenario"):
    step = StepResult(
        step_index=0,
        expected_outcome="APPROVE",
        actual_outcome="REJECT",
        outcome_correct=False,
        agent_obeyed=True,
        receipt_valid=False,
        receipt_errors=["receipt error"],
        request_id="req-002",
    )
    return AgentRunResult(scenario_id=scenario_id, passed=False, steps=[step])


@pytest.mark.asyncio
async def test_cli_exits_zero_on_all_pass(tmp_path):
    passing = make_passing_result()

    with patch("evals.agent_eval.cli.ensure_services_available", new_callable=AsyncMock):
        with patch("evals.agent_eval.cli.run_scenario", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = passing
            with patch("sys.argv", ["cli", "--domain", "finance", "--report-dir", str(tmp_path)]):
                from evals.agent_eval.cli import _run
                import argparse
                args = argparse.Namespace(
                    domain="finance",
                    scenario=None,
                    rule_engine_url="http://127.0.0.1:8001",
                    decision_center_url="http://127.0.0.1:8002",
                    report_dir=str(tmp_path),
                    keep_group=False,
                    fail_on_missing_services=False,
                )
                exit_code = await _run(args)
                assert exit_code == 0


@pytest.mark.asyncio
async def test_cli_exits_one_on_failure(tmp_path):
    failing = make_failing_result()

    with patch("evals.agent_eval.cli.ensure_services_available", new_callable=AsyncMock):
        with patch("evals.agent_eval.cli.run_scenario", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = failing
            import argparse
            args = argparse.Namespace(
                domain="finance",
                scenario=None,
                rule_engine_url="http://127.0.0.1:8001",
                decision_center_url="http://127.0.0.1:8002",
                report_dir=str(tmp_path),
                keep_group=False,
                fail_on_missing_services=False,
            )
            from evals.agent_eval.cli import _run
            exit_code = await _run(args)
            assert exit_code == 1


@pytest.mark.asyncio
async def test_cli_fail_on_missing_services_exits_one(tmp_path):
    with patch(
        "evals.agent_eval.cli.ensure_services_available",
        new_callable=AsyncMock,
        side_effect=Exception("Connection refused"),
    ):
        import argparse
        args = argparse.Namespace(
            domain="finance",
            scenario=None,
            rule_engine_url="http://127.0.0.1:8001",
            decision_center_url="http://127.0.0.1:8002",
            report_dir=str(tmp_path),
            keep_group=False,
            fail_on_missing_services=True,
        )
        from evals.agent_eval.cli import _run
        exit_code = await _run(args)
        assert exit_code == 1


def test_cli_get_scenarios_finance():
    from evals.agent_eval.cli import _get_scenarios
    scenarios = _get_scenarios("finance", None)
    assert len(scenarios) == 6


def test_cli_get_scenarios_ecommerce():
    from evals.agent_eval.cli import _get_scenarios
    scenarios = _get_scenarios("ecommerce", None)
    assert len(scenarios) == 3


def test_cli_get_scenarios_all():
    from evals.agent_eval.cli import _get_scenarios
    scenarios = _get_scenarios("all", None)
    assert len(scenarios) == 9


def test_cli_get_specific_scenario():
    from evals.agent_eval.cli import _get_scenarios
    scenarios = _get_scenarios("finance", "fin_reject_high_risk")
    assert len(scenarios) == 1
    assert scenarios[0].scenario_id == "fin_reject_high_risk"
