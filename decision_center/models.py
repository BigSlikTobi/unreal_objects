from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime
import uuid
from typing import Optional, List, Dict, Any

def generate_id():
    return str(uuid.uuid4())

class DecisionOutcome(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ASK_FOR_APPROVAL = "ASK_FOR_APPROVAL"

class DecisionState(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"

class EvaluateRequest(BaseModel):
    request_description: str
    context: Dict[str, Any]
    group_id: Optional[str] = None

class MatchedRuleInfo(BaseModel):
    rule_id: str
    rule_name: str
    hit_type: str
    trigger_expression: str

class DecisionResult(BaseModel):
    request_id: str
    outcome: DecisionOutcome
    matched_rules: List[str]
    matched_details: List[MatchedRuleInfo] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)

class ApprovalSubmission(BaseModel):
    approved: bool
    approver: str

class AtomicLogEntry(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    request_description: str
    context: Dict[str, Any]
    decision: DecisionState

class ChainEvent(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    event_type: str
    details: Dict[str, Any] = Field(default_factory=dict)

class DecisionChain(BaseModel):
    request_id: str
    events: List[ChainEvent] = Field(default_factory=list)

