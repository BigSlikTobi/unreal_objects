import pytest
from pathlib import Path
import tempfile

from evals.agent_eval.models import AgentRunResult, StepResult
from evals.agent_eval.reporting import (
    compute_stats,
    next_report_path,
    write_agent_eval_report,
)


def make_step_result(outcome_correct=True, agent_obeyed=True, receipt_valid=True, expected_outcome="APPROVE"):
    return StepResult(
        step_index=0,
        expected_outcome=expected_outcome,
        actual_outcome=expected_outcome if outcome_correct else "REJECT",
        outcome_correct=outcome_correct,
        agent_obeyed=agent_obeyed,
        receipt_valid=receipt_valid,
        receipt_errors=[] if receipt_valid else ["some error"],
        request_id="req-001",
    )


def make_result(scenario_id="s1", passed=True, steps=None):
    if steps is None:
        steps = [make_step_result()]
    return AgentRunResult(scenario_id=scenario_id, passed=passed, steps=steps)


def test_next_report_path_empty_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = next_report_path(Path(tmpdir))
        assert path.name == "agent_eval_report_v1.md"


def test_next_report_path_increments():
    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        (d / "agent_eval_report_v1.md").write_text("v1")
        (d / "agent_eval_report_v3.md").write_text("v3")
        path = next_report_path(d)
        assert path.name == "agent_eval_report_v4.md"


def test_compute_stats_all_pass():
    results = [make_result("s1"), make_result("s2")]
    stats = compute_stats(results)
    assert stats.total_scenarios == 2
    assert stats.passed_scenarios == 2
    assert stats.failed_scenarios == 0
    assert stats.decision_accuracy == 1.0
    assert stats.obedience_rate == 1.0
    assert stats.receipt_validity_rate == 1.0


def test_compute_stats_partial_failure():
    r1 = make_result("s1", passed=True, steps=[make_step_result()])
    r2 = make_result("s2", passed=False, steps=[make_step_result(outcome_correct=False)])
    stats = compute_stats([r1, r2])
    assert stats.passed_scenarios == 1
    assert stats.failed_scenarios == 1
    assert stats.decision_accuracy == 0.5


def test_write_report_creates_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "agent_eval_report_v1.md"
        results = [make_result()]
        stats = compute_stats(results)
        write_agent_eval_report(path, results, stats, domain="finance")
        assert path.exists()
        content = path.read_text()
        assert "Agent Eval Report" in content
        assert "finance" in content
        assert "Decision Accuracy" in content


def test_report_contains_scenario_ids():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "report.md"
        results = [make_result("my_scenario")]
        stats = compute_stats(results)
        write_agent_eval_report(path, results, stats, domain="all")
        content = path.read_text()
        assert "my_scenario" in content


def test_compute_stats_human_loop_completion():
    ask_step = make_step_result(expected_outcome="ASK_FOR_APPROVAL", receipt_valid=True)
    result = make_result("ask_test", passed=True, steps=[ask_step])
    stats = compute_stats([result])
    assert stats.human_loop_completion_rate == 1.0
