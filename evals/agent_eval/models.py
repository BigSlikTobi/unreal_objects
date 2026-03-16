from typing import Literal
from pydantic import BaseModel, model_validator


class WorkflowStep(BaseModel):
    action_description: str
    context: dict
    expected_outcome: Literal["APPROVE", "REJECT", "ASK_FOR_APPROVAL"]
    human_approves: bool | None = None
    expected_approval_status: Literal["APPROVED", "REJECTED"] | None = None

    @model_validator(mode="after")
    def validate_human_approves(self) -> "WorkflowStep":
        if self.expected_outcome == "ASK_FOR_APPROVAL":
            if self.human_approves is None:
                raise ValueError("human_approves must be set when expected_outcome == ASK_FOR_APPROVAL")
        else:
            if self.human_approves is not None:
                raise ValueError(
                    "human_approves must not be set when expected_outcome != ASK_FOR_APPROVAL"
                )
        return self


class ReceiptAssertion(BaseModel):
    must_have_event_types: list[str]
    outcome_in_evaluation: str
    approval_status: str | None = None
    approver: str | None = None


class AgentScenario(BaseModel):
    scenario_id: str
    description: str
    group_name: str
    rules: list[dict]
    workflow: list[WorkflowStep]
    receipt_assertions: list[ReceiptAssertion]

    @model_validator(mode="after")
    def validate_assertions_match_workflow(self) -> "AgentScenario":
        if len(self.receipt_assertions) != len(self.workflow):
            raise ValueError(
                f"receipt_assertions length ({len(self.receipt_assertions)}) must equal "
                f"workflow length ({len(self.workflow)})"
            )
        return self


class StepResult(BaseModel):
    step_index: int
    expected_outcome: str
    actual_outcome: str | None
    outcome_correct: bool
    agent_obeyed: bool
    receipt_valid: bool
    receipt_errors: list[str]
    request_id: str | None = None


class AgentRunResult(BaseModel):
    scenario_id: str
    passed: bool
    steps: list[StepResult]
    error: str | None = None


class AgentEvalStats(BaseModel):
    total_scenarios: int
    passed_scenarios: int
    failed_scenarios: int
    total_steps: int
    decision_accuracy: float
    obedience_rate: float
    receipt_validity_rate: float
    human_loop_completion_rate: float
