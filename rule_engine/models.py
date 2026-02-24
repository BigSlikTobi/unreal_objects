from pydantic import BaseModel, Field
from datetime import datetime
import uuid

def generate_id():
    return str(uuid.uuid4())

class BusinessRule(BaseModel):
    id: str = Field(default_factory=generate_id)
    name: str
    feature: str
    datapoints: list[str]
    edge_cases: list[str]
    rule_logic: str
    created_at: datetime = Field(default_factory=datetime.now)

class BusinessRuleGroup(BaseModel):
    id: str = Field(default_factory=generate_id)
    name: str
    description: str = ""
    rules: list[BusinessRule] = Field(default_factory=list)

class CreateRule(BaseModel):
    name: str
    feature: str
    datapoints: list[str]
    edge_cases: list[str]
    rule_logic: str

class CreateRuleGroup(BaseModel):
    name: str
    description: str = ""

