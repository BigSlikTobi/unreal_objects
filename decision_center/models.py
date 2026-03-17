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
    rule_id: Optional[str] = None
    agent_id: Optional[str] = None
    credential_id: Optional[str] = None
    user_id: Optional[str] = None

    def identity_dict(self) -> Dict[str, Any]:
        """Return a dict of identity fields for logging, suitable for ** unpacking."""
        return {
            "agent_id": self.agent_id,
            "credential_id": self.credential_id,
            "user_id": self.user_id,
            "effective_group_id": self.group_id,
        }

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
    agent_id: Optional[str] = None
    credential_id: Optional[str] = None
    user_id: Optional[str] = None
    effective_group_id: Optional[str] = None

class ApprovalSubmission(BaseModel):
    approved: bool
    approver: str

class AtomicLogEntry(BaseModel):
    request_id: str = Field(default_factory=generate_id)
    timestamp: datetime = Field(default_factory=datetime.now)
    request_description: str
    context: Dict[str, Any]
    decision: DecisionState
    agent_id: Optional[str] = None
    credential_id: Optional[str] = None
    user_id: Optional[str] = None
    effective_group_id: Optional[str] = None

class ChainEvent(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    event_type: str
    details: Dict[str, Any] = Field(default_factory=dict)

class DecisionChain(BaseModel):
    request_id: str
    events: List[ChainEvent] = Field(default_factory=list)

class LLMConnectionRequest(BaseModel):
    provider: str
    model: str
    api_key: str

class RuleTranslationRequest(BaseModel):
    natural_language: str
    feature: str
    name: str
    provider: str
    model: str
    api_key: str
    context_schema: Optional[Dict[str, Any]] = None
    datapoint_definitions: List[Dict[str, Any]] = Field(default_factory=list)

class SchemaField(BaseModel):
    name: str
    type: str
    description: str

class SchemaGenerationRequest(BaseModel):
    provider: str
    model: str
    api_key: str
    user_message: str
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)
    current_schema: Optional[Dict[str, Any]] = None

class SchemaSaveRequest(BaseModel):
    name: str
    description: str
    fields: List[SchemaField]
