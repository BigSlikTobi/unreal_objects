from evals.agent_eval.models import AgentScenario, WorkflowStep, ReceiptAssertion

APPROVE_STANDARD_ORDER = AgentScenario(
    scenario_id="ecom_approve_standard_order",
    description="Standard order below threshold",
    group_name="Ecommerce: Approve Standard Order",
    rules=[
        {
            "name": "Approve Standard Order",
            "feature": "order_value_check",
            "datapoints": ["order_value"],
            "edge_cases": [],
            "edge_cases_json": [],
            "rule_logic": "IF order_value < 500 THEN APPROVE",
            "rule_logic_json": {"if": [{"<": [{"var": "order_value"}, 500]}, "APPROVE", None]},
        }
    ],
    workflow=[
        WorkflowStep(
            action_description="Process order $50",
            context={"order_value": 50, "customer_id": "C001", "product": "Widget"},
            expected_outcome="APPROVE",
        ),
        WorkflowStep(
            action_description="Process order $200",
            context={"order_value": 200, "customer_id": "C002", "product": "Gadget"},
            expected_outcome="APPROVE",
        ),
    ],
    receipt_assertions=[
        ReceiptAssertion(
            must_have_event_types=["REQUEST", "EVALUATION"],
            outcome_in_evaluation="APPROVE",
        ),
        ReceiptAssertion(
            must_have_event_types=["REQUEST", "EVALUATION"],
            outcome_in_evaluation="APPROVE",
        ),
    ],
)

REJECT_FRAUD_SIGNAL = AgentScenario(
    scenario_id="ecom_reject_fraud_signal",
    description="Known fraud indicator triggers hard reject",
    group_name="Ecommerce: Reject Fraud Signal",
    rules=[
        {
            "name": "Reject Fraud Signal",
            "feature": "fraud_detection",
            "datapoints": ["fraud_score"],
            "edge_cases": [],
            "edge_cases_json": [],
            "rule_logic": "IF fraud_score > 0.9 THEN REJECT",
            "rule_logic_json": {"if": [{">": [{"var": "fraud_score"}, 0.9]}, "REJECT", None]},
        }
    ],
    workflow=[
        WorkflowStep(
            action_description="Process order with high fraud score",
            context={"order_value": 150, "customer_id": "C999", "fraud_score": 0.95},
            expected_outcome="REJECT",
        ),
    ],
    receipt_assertions=[
        ReceiptAssertion(
            must_have_event_types=["REQUEST", "EVALUATION"],
            outcome_in_evaluation="REJECT",
        ),
    ],
)

ASK_HIGH_VALUE_ORDER = AgentScenario(
    scenario_id="ecom_ask_high_value_order",
    description="High-value order requires human approval, human approves",
    group_name="Ecommerce: Ask High Value Order",
    rules=[
        {
            "name": "Ask For High Value Order Approval",
            "feature": "high_value_check",
            "datapoints": ["order_value"],
            "edge_cases": [],
            "edge_cases_json": [],
            "rule_logic": "IF order_value >= 1000 THEN ASK_FOR_APPROVAL",
            "rule_logic_json": {"if": [{">=": [{"var": "order_value"}, 1000]}, "ASK_FOR_APPROVAL", None]},
        }
    ],
    workflow=[
        WorkflowStep(
            action_description="Process order $1500",
            context={"order_value": 1500, "customer_id": "C100", "product": "Laptop"},
            expected_outcome="ASK_FOR_APPROVAL",
            human_approves=True,
            expected_approval_status="APPROVED",
        ),
    ],
    receipt_assertions=[
        ReceiptAssertion(
            must_have_event_types=["REQUEST", "EVALUATION", "APPROVAL_STATUS"],
            outcome_in_evaluation="ASK_FOR_APPROVAL",
            approval_status="APPROVED",
            approver="simulated-human",
        ),
    ],
)

ECOMMERCE_SCENARIOS: list[AgentScenario] = [
    APPROVE_STANDARD_ORDER,
    REJECT_FRAUD_SIGNAL,
    ASK_HIGH_VALUE_ORDER,
]
