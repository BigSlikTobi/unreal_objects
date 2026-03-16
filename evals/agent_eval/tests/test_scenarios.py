from evals.agent_eval.scenarios.finance import FINANCE_SCENARIOS
from evals.agent_eval.scenarios.ecommerce import ECOMMERCE_SCENARIOS
from evals.agent_eval.scenarios.generated import GENERATED_SCENARIOS
from evals.agent_eval.models import AgentScenario


def test_finance_has_six_scenarios():
    assert len(FINANCE_SCENARIOS) == 6


def test_ecommerce_has_three_scenarios():
    assert len(ECOMMERCE_SCENARIOS) == 3


def test_all_scenario_ids_unique():
    all_scenarios = FINANCE_SCENARIOS + ECOMMERCE_SCENARIOS
    ids = [s.scenario_id for s in all_scenarios]
    assert len(ids) == len(set(ids)), "Duplicate scenario IDs found"


def test_all_scenarios_valid_schema():
    for scenario in FINANCE_SCENARIOS + ECOMMERCE_SCENARIOS:
        assert isinstance(scenario, AgentScenario)
        assert len(scenario.receipt_assertions) == len(scenario.workflow)
        assert scenario.scenario_id
        assert scenario.group_name


def test_finance_scenario_ids():
    ids = {s.scenario_id for s in FINANCE_SCENARIOS}
    assert "fin_approve_low_transfer" in ids
    assert "fin_reject_high_risk" in ids
    assert "fin_ask_large_transfer_approved" in ids
    assert "fin_ask_large_transfer_rejected" in ids
    assert "fin_multi_step_workflow" in ids
    assert "fin_fail_closed_missing_data" in ids


def test_ecommerce_scenario_ids():
    ids = {s.scenario_id for s in ECOMMERCE_SCENARIOS}
    assert "ecom_approve_standard_order" in ids
    assert "ecom_reject_fraud_signal" in ids
    assert "ecom_ask_high_value_order" in ids


def test_ask_steps_have_human_approves():
    for scenario in FINANCE_SCENARIOS + ECOMMERCE_SCENARIOS:
        for step in scenario.workflow:
            if step.expected_outcome == "ASK_FOR_APPROVAL":
                assert step.human_approves is not None


def test_receipt_assertions_have_required_fields():
    for scenario in FINANCE_SCENARIOS + ECOMMERCE_SCENARIOS:
        for assertion in scenario.receipt_assertions:
            assert "REQUEST" in assertion.must_have_event_types
            assert "EVALUATION" in assertion.must_have_event_types
            assert assertion.outcome_in_evaluation


def test_rules_have_required_fields():
    for scenario in FINANCE_SCENARIOS + ECOMMERCE_SCENARIOS:
        for rule in scenario.rules:
            assert "name" in rule
            assert "feature" in rule
            assert "rule_logic" in rule
            assert "rule_logic_json" in rule
            assert "datapoints" in rule
            assert "edge_cases" in rule


# --- Generated scenarios (500) ---

def test_generated_has_500_scenarios():
    assert len(GENERATED_SCENARIOS) == 500


def test_generated_all_ids_unique():
    ids = [s.scenario_id for s in GENERATED_SCENARIOS]
    assert len(ids) == len(set(ids))


def test_generated_no_overlap_with_handwritten():
    gen_ids = {s.scenario_id for s in GENERATED_SCENARIOS}
    hand_ids = {s.scenario_id for s in FINANCE_SCENARIOS + ECOMMERCE_SCENARIOS}
    assert gen_ids.isdisjoint(hand_ids)


def test_generated_all_valid_schema():
    for scenario in GENERATED_SCENARIOS:
        assert isinstance(scenario, AgentScenario)
        assert len(scenario.receipt_assertions) == len(scenario.workflow)
        assert scenario.scenario_id
        assert scenario.group_name
        assert len(scenario.rules) >= 1
        for step in scenario.workflow:
            assert step.expected_outcome in ("APPROVE", "REJECT", "ASK_FOR_APPROVAL")
            if step.expected_outcome == "ASK_FOR_APPROVAL":
                assert step.human_approves is not None


def test_generated_covers_all_outcomes():
    outcomes = {step.expected_outcome for s in GENERATED_SCENARIOS for step in s.workflow}
    assert outcomes == {"APPROVE", "REJECT", "ASK_FOR_APPROVAL"}


def test_generated_rules_have_required_fields():
    for scenario in GENERATED_SCENARIOS:
        for rule in scenario.rules:
            assert "name" in rule
            assert "feature" in rule
            assert "rule_logic" in rule
            assert "rule_logic_json" in rule
            assert "datapoints" in rule
            assert "edge_cases" in rule
