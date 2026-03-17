import pytest
from pydantic import ValidationError

from evals.agent_eval.models import (
    AgentEvalStats,
    AgentRunResult,
    AgentScenario,
    ReceiptAssertion,
    StepResult,
    WorkflowStep,
)


def make_step(expected_outcome="APPROVE", human_approves=None):
    return WorkflowStep(
        action_description="test action",
        context={"amount": 100},
        expected_outcome=expected_outcome,
        human_approves=human_approves,
    )


def make_assertion(outcome="APPROVE"):
    return ReceiptAssertion(
        must_have_event_types=["REQUEST", "EVALUATION"],
        outcome_in_evaluation=outcome,
    )


# WorkflowStep validator tests

def test_step_approve_no_human_approves():
    step = make_step("APPROVE")
    assert step.human_approves is None


def test_step_reject_no_human_approves():
    step = make_step("REJECT")
    assert step.human_approves is None


def test_step_ask_requires_human_approves():
    step = WorkflowStep(
        action_description="ask",
        context={},
        expected_outcome="ASK_FOR_APPROVAL",
        human_approves=True,
    )
    assert step.human_approves is True


def test_step_ask_missing_human_approves_raises():
    with pytest.raises(ValidationError, match="human_approves must be set"):
        WorkflowStep(
            action_description="ask",
            context={},
            expected_outcome="ASK_FOR_APPROVAL",
        )


def test_step_approve_with_human_approves_raises():
    with pytest.raises(ValidationError, match="human_approves must not be set"):
        WorkflowStep(
            action_description="approve",
            context={},
            expected_outcome="APPROVE",
            human_approves=True,
        )


def test_step_reject_with_human_approves_raises():
    with pytest.raises(ValidationError, match="human_approves must not be set"):
        WorkflowStep(
            action_description="reject",
            context={},
            expected_outcome="REJECT",
            human_approves=False,
        )


# AgentScenario validator tests

def test_scenario_assertions_length_mismatch_raises():
    with pytest.raises(ValidationError, match="receipt_assertions"):
        AgentScenario(
            scenario_id="test",
            description="test",
            group_name="test group",
            rules=[],
            workflow=[make_step()],
            receipt_assertions=[],  # length 0, workflow length 1
        )


def test_scenario_valid():
    scenario = AgentScenario(
        scenario_id="test",
        description="test",
        group_name="test group",
        rules=[],
        workflow=[make_step()],
        receipt_assertions=[make_assertion()],
    )
    assert scenario.scenario_id == "test"
    assert len(scenario.workflow) == len(scenario.receipt_assertions)


# StepResult, AgentRunResult, AgentEvalStats instantiation

def test_step_result_instantiation():
    sr = StepResult(
        step_index=0,
        expected_outcome="APPROVE",
        actual_outcome="APPROVE",
        outcome_correct=True,
        agent_obeyed=True,
        receipt_valid=True,
        receipt_errors=[],
        request_id="req-123",
    )
    assert sr.outcome_correct is True


def test_agent_run_result_instantiation():
    result = AgentRunResult(scenario_id="test", passed=True, steps=[])
    assert result.passed is True
    assert result.error is None


def test_agent_eval_stats_instantiation():
    stats = AgentEvalStats(
        total_scenarios=9,
        passed_scenarios=8,
        failed_scenarios=1,
        total_steps=15,
        decision_accuracy=0.9,
        obedience_rate=1.0,
        receipt_validity_rate=0.95,
        human_loop_completion_rate=1.0,
    )
    assert stats.total_scenarios == 9
