"""Domain models for the virtual support company."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

import uuid


def _generate_id() -> str:
    return str(uuid.uuid4())


class CaseType(str, Enum):
    ACCOUNT_UPDATE = "account_update"
    REFUND_REQUEST = "refund_request"
    ESCALATION = "escalation"
    SENSITIVE_CHANGE = "sensitive_change"
    SUSPICIOUS_REQUEST = "suspicious_request"


class CaseStatus(str, Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    RESOLVED = "resolved"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CustomerTier(str, Enum):
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class SupportCase(BaseModel):
    case_id: str = Field(default_factory=_generate_id)
    case_type: CaseType
    customer_tier: CustomerTier = CustomerTier.BASIC
    priority: Priority = Priority.MEDIUM
    risk_score: float = 0.0
    requested_action: str = ""
    channel: str = "email"
    account_age_days: int = 365
    order_value: float = 0.0
    refund_amount: float = 0.0
    requires_identity_check: bool = False
    contains_policy_exception: bool = False
    expected_business_path: str = "APPROVE"
    created_at: datetime = Field(default_factory=datetime.now)

    # Optional fields for the living company extension
    customer_id: Optional[str] = None
    order_id: Optional[str] = None
    status: CaseStatus = CaseStatus.OPEN
    assigned_to: Optional[str] = None
    narrative: str = ""
    resolution: Optional[str] = None
