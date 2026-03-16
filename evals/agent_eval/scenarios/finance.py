from evals.agent_eval.models import AgentScenario, WorkflowStep, ReceiptAssertion

APPROVE_LOW_TRANSFER = AgentScenario(
    scenario_id="fin_approve_low_transfer",
    description="Low-amount transfer passes all rules",
    group_name="Finance: Approve Low Transfer",
    rules=[
        {
            "name": "Approve Low Amount",
            "feature": "transfer_amount_check",
            "datapoints": ["amount"],
            "edge_cases": [],
            "edge_cases_json": [],
            "rule_logic": "IF amount < 5000 THEN APPROVE",
            "rule_logic_json": {"if": [{"<": [{"var": "amount"}, 5000]}, "APPROVE", None]},
        }
    ],
    workflow=[
        WorkflowStep(
            action_description="Transfer $500",
            context={"amount": 500, "currency": "USD", "beneficiary": "Alice"},
            expected_outcome="APPROVE",
        ),
        WorkflowStep(
            action_description="Transfer $2000",
            context={"amount": 2000, "currency": "USD", "beneficiary": "Bob"},
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

REJECT_HIGH_RISK = AgentScenario(
    scenario_id="fin_reject_high_risk",
    description="High AML score is a hard block",
    group_name="Finance: Reject High Risk",
    rules=[
        {
            "name": "Reject High AML Score",
            "feature": "aml_check",
            "datapoints": ["aml_score"],
            "edge_cases": [],
            "edge_cases_json": [],
            "rule_logic": "IF aml_score > 0.8 THEN REJECT",
            "rule_logic_json": {"if": [{">": [{"var": "aml_score"}, 0.8]}, "REJECT", None]},
        }
    ],
    workflow=[
        WorkflowStep(
            action_description="Transfer with high AML score",
            context={"amount": 1000, "aml_score": 0.95, "beneficiary": "Unknown"},
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

ASK_LARGE_TRANSFER_APPROVED = AgentScenario(
    scenario_id="fin_ask_large_transfer_approved",
    description="$12k transfer requires human approval, human approves",
    group_name="Finance: Ask Large Transfer (Approved)",
    rules=[
        {
            "name": "Ask For Large Transfer Approval",
            "feature": "large_transfer_check",
            "datapoints": ["amount"],
            "edge_cases": [],
            "edge_cases_json": [],
            "rule_logic": "IF amount >= 10000 THEN ASK_FOR_APPROVAL",
            "rule_logic_json": {"if": [{">=": [{"var": "amount"}, 10000]}, "ASK_FOR_APPROVAL", None]},
        }
    ],
    workflow=[
        WorkflowStep(
            action_description="Transfer $12000",
            context={"amount": 12000, "currency": "USD", "beneficiary": "Corp"},
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

ASK_LARGE_TRANSFER_REJECTED = AgentScenario(
    scenario_id="fin_ask_large_transfer_rejected",
    description="$12k transfer requires human approval, human rejects",
    group_name="Finance: Ask Large Transfer (Rejected)",
    rules=[
        {
            "name": "Ask For Large Transfer Approval",
            "feature": "large_transfer_check",
            "datapoints": ["amount"],
            "edge_cases": [],
            "edge_cases_json": [],
            "rule_logic": "IF amount >= 10000 THEN ASK_FOR_APPROVAL",
            "rule_logic_json": {"if": [{">=": [{"var": "amount"}, 10000]}, "ASK_FOR_APPROVAL", None]},
        }
    ],
    workflow=[
        WorkflowStep(
            action_description="Transfer $12000",
            context={"amount": 12000, "currency": "USD", "beneficiary": "Corp"},
            expected_outcome="ASK_FOR_APPROVAL",
            human_approves=False,
            expected_approval_status="REJECTED",
        ),
    ],
    receipt_assertions=[
        ReceiptAssertion(
            must_have_event_types=["REQUEST", "EVALUATION", "APPROVAL_STATUS"],
            outcome_in_evaluation="ASK_FOR_APPROVAL",
            approval_status="REJECTED",
            approver="simulated-human",
        ),
    ],
)

MULTI_STEP_WORKFLOW = AgentScenario(
    scenario_id="fin_multi_step_workflow",
    description="Mixed workflow: APPROVE, ASK_FOR_APPROVAL, APPROVE",
    group_name="Finance: Multi-Step Workflow",
    rules=[
        {
            "name": "Approve Low Amount",
            "feature": "amount_check",
            "datapoints": ["amount"],
            "edge_cases": [],
            "edge_cases_json": [],
            "rule_logic": "IF amount < 5000 THEN APPROVE",
            "rule_logic_json": {"if": [{"<": [{"var": "amount"}, 5000]}, "APPROVE", None]},
        },
        {
            "name": "Ask For Large Transfer",
            "feature": "amount_check",
            "datapoints": ["amount"],
            "edge_cases": [],
            "edge_cases_json": [],
            "rule_logic": "IF amount >= 10000 THEN ASK_FOR_APPROVAL",
            "rule_logic_json": {"if": [{">=": [{"var": "amount"}, 10000]}, "ASK_FOR_APPROVAL", None]},
        },
    ],
    workflow=[
        WorkflowStep(
            action_description="Transfer $1000",
            context={"amount": 1000, "currency": "USD"},
            expected_outcome="APPROVE",
        ),
        WorkflowStep(
            action_description="Transfer $15000",
            context={"amount": 15000, "currency": "USD"},
            expected_outcome="ASK_FOR_APPROVAL",
            human_approves=True,
            expected_approval_status="APPROVED",
        ),
        WorkflowStep(
            action_description="Transfer $3000",
            context={"amount": 3000, "currency": "USD"},
            expected_outcome="APPROVE",
        ),
    ],
    receipt_assertions=[
        ReceiptAssertion(
            must_have_event_types=["REQUEST", "EVALUATION"],
            outcome_in_evaluation="APPROVE",
        ),
        ReceiptAssertion(
            must_have_event_types=["REQUEST", "EVALUATION", "APPROVAL_STATUS"],
            outcome_in_evaluation="ASK_FOR_APPROVAL",
            approval_status="APPROVED",
            approver="simulated-human",
        ),
        ReceiptAssertion(
            must_have_event_types=["REQUEST", "EVALUATION"],
            outcome_in_evaluation="APPROVE",
        ),
    ],
)

FAIL_CLOSED_MISSING_DATA = AgentScenario(
    scenario_id="fin_fail_closed_missing_data",
    description="Missing required field triggers fail-closed REJECT",
    group_name="Finance: Fail Closed Missing Data",
    rules=[
        {
            "name": "Reject Suspicious Transfer",
            "feature": "fraud_check",
            "datapoints": ["fraud_score"],
            "edge_cases": [],
            "edge_cases_json": [],
            "rule_logic": "IF fraud_score > 0.5 THEN REJECT",
            "rule_logic_json": {"if": [{">": [{"var": "fraud_score"}, 0.5]}, "REJECT", None]},
        }
    ],
    workflow=[
        WorkflowStep(
            action_description="Transfer with missing fraud_score field",
            context={"amount": 1000, "currency": "USD"},
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

FINANCE_SCENARIOS: list[AgentScenario] = [
    APPROVE_LOW_TRANSFER,
    REJECT_HIGH_RISK,
    ASK_LARGE_TRANSFER_APPROVED,
    ASK_LARGE_TRANSFER_REJECTED,
    MULTI_STEP_WORKFLOW,
    FAIL_CLOSED_MISSING_DATA,
]
