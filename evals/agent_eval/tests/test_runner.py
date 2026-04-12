import pytest
import httpx
from httpx import ASGITransport

import decision_center.evaluator as evaluator_module
from decision_center.app import app as dc_app, store as dc_store
from rule_engine.app import app as re_app, store as re_store

from evals.agent_eval.runner import run_scenario
from evals.agent_eval.models import AgentScenario, WorkflowStep, ReceiptAssertion


@pytest.fixture(autouse=True)
def reset_stores():
    """Reset in-memory stores before each test."""
    re_store.groups.clear()
    dc_store.data.atomic_logs.clear()
    dc_store.data.chains.clear()
    dc_store.data.pending.clear()
    yield
    re_store.groups.clear()
    dc_store.data.atomic_logs.clear()
    dc_store.data.chains.clear()
    dc_store.data.pending.clear()


@pytest.fixture
async def clients(monkeypatch):
    """Provide in-process ASGI clients for rule engine and decision center."""
    re_transport = ASGITransport(app=re_app)
    dc_transport = ASGITransport(app=dc_app)

    re_client = httpx.AsyncClient(transport=re_transport, base_url="http://test-re")
    dc_client = httpx.AsyncClient(transport=dc_transport, base_url="http://test-dc")

    # Patch _fetch_group to use in-process rule engine
    async def mock_fetch_group(group_id: str):
        return await re_client.get(f"/v1/groups/{group_id}")

    monkeypatch.setattr(evaluator_module, "_fetch_group", mock_fetch_group)

    yield re_client, dc_client

    await re_client.aclose()
    await dc_client.aclose()


def make_simple_scenario(scenario_id="test_approve", expected_outcome="APPROVE"):
    rules = [
        {
            "name": "Approve Low Amount",
            "feature": "test",
            "datapoints": ["amount"],
            "edge_cases": [],
            "edge_cases_json": [],
            "rule_logic": "IF amount < 5000 THEN APPROVE",
            "rule_logic_json": {"if": [{"<": [{"var": "amount"}, 5000]}, "APPROVE", None]},
        }
    ]
    step = WorkflowStep(
        action_description="Transfer $100",
        context={"amount": 100},
        expected_outcome=expected_outcome,
    )
    assertion = ReceiptAssertion(
        must_have_event_types=["REQUEST", "EVALUATION"],
        outcome_in_evaluation=expected_outcome,
    )
    return AgentScenario(
        scenario_id=scenario_id,
        description="Simple test scenario",
        group_name=f"Test Group {scenario_id}",
        rules=rules,
        workflow=[step],
        receipt_assertions=[assertion],
    )


@pytest.mark.asyncio
async def test_group_created_and_deleted(clients):
    re_client, dc_client = clients
    scenario = make_simple_scenario()

    result = await run_scenario(
        scenario,
        rule_engine_url="http://test-re",
        decision_center_url="http://test-dc",
        re_client=re_client,
        dc_client=dc_client,
    )

    assert result.scenario_id == "test_approve"
    # Group should be deleted
    groups_resp = await re_client.get("/v1/groups")
    groups = groups_resp.json()
    assert len(groups) == 0


@pytest.mark.asyncio
async def test_keep_group_flag(clients):
    re_client, dc_client = clients
    scenario = make_simple_scenario("test_keep")

    await run_scenario(
        scenario,
        rule_engine_url="http://test-re",
        decision_center_url="http://test-dc",
        keep_group=True,
        re_client=re_client,
        dc_client=dc_client,
    )

    groups_resp = await re_client.get("/v1/groups")
    groups = groups_resp.json()
    assert len(groups) == 1


@pytest.mark.asyncio
async def test_correct_outcome_passes(clients):
    re_client, dc_client = clients
    scenario = make_simple_scenario("test_pass", expected_outcome="APPROVE")

    result = await run_scenario(
        scenario,
        rule_engine_url="http://test-re",
        decision_center_url="http://test-dc",
        re_client=re_client,
        dc_client=dc_client,
    )

    assert result.passed is True
    assert len(result.steps) == 1
    assert result.steps[0].outcome_correct is True
    assert result.steps[0].agent_obeyed is True
    assert result.steps[0].receipt_valid is True


@pytest.mark.asyncio
async def test_wrong_expected_outcome_fails(clients):
    re_client, dc_client = clients
    # Scenario expects REJECT but rule gives APPROVE
    scenario = make_simple_scenario("test_fail", expected_outcome="REJECT")

    result = await run_scenario(
        scenario,
        rule_engine_url="http://test-re",
        decision_center_url="http://test-dc",
        re_client=re_client,
        dc_client=dc_client,
    )

    assert result.passed is False
    assert result.steps[0].outcome_correct is False


@pytest.mark.asyncio
async def test_ask_for_approval_workflow(clients, monkeypatch):
    re_client, dc_client = clients
    rules = [
        {
            "name": "Ask Large Transfer",
            "feature": "test",
            "datapoints": ["amount"],
            "edge_cases": [],
            "edge_cases_json": [],
            "rule_logic": "IF amount >= 10000 THEN ASK_FOR_APPROVAL",
            "rule_logic_json": {"if": [{">=": [{"var": "amount"}, 10000]}, "ASK_FOR_APPROVAL", None]},
        }
    ]
    step = WorkflowStep(
        action_description="Transfer $12000",
        context={"amount": 12000},
        expected_outcome="ASK_FOR_APPROVAL",
        human_approves=True,
        expected_approval_status="APPROVED",
    )
    assertion = ReceiptAssertion(
        must_have_event_types=["REQUEST", "EVALUATION", "APPROVAL_STATUS"],
        outcome_in_evaluation="ASK_FOR_APPROVAL",
        approval_status="APPROVED",
        approver="simulated-human",
    )
    scenario = AgentScenario(
        scenario_id="test_ask",
        description="ASK scenario",
        group_name="Test Ask Group",
        rules=rules,
        workflow=[step],
        receipt_assertions=[assertion],
    )

    result = await run_scenario(
        scenario,
        rule_engine_url="http://test-re",
        decision_center_url="http://test-dc",
        re_client=re_client,
        dc_client=dc_client,
    )

    assert result.passed is True
    assert result.steps[0].outcome_correct is True
    assert result.steps[0].receipt_valid is True
