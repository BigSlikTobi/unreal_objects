from pydantic import BaseModel, Field
from datetime import datetime
import uuid

def generate_id():
    return str(uuid.uuid4())

class DatapointDefinition(BaseModel):
    name: str
    type: str  # "text" | "number" | "boolean" | "enum"
    values: list[str] = []

class BusinessRule(BaseModel):
    id: str = Field(default_factory=generate_id)
    name: str
    feature: str
    datapoints: list[str]
    edge_cases: list[str]
    edge_cases_json: list[dict] = Field(default_factory=list)
    rule_logic: str
    rule_logic_json: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)

class BusinessRuleGroup(BaseModel):
    id: str = Field(default_factory=generate_id)
    name: str
    description: str = ""
    rules: list[BusinessRule] = Field(default_factory=list)
    datapoint_definitions: list[DatapointDefinition] = Field(default_factory=list)

class CreateRule(BaseModel):
    name: str
    feature: str
    datapoints: list[str]
    edge_cases: list[str]
    edge_cases_json: list[dict] = Field(default_factory=list)
    rule_logic: str
    rule_logic_json: dict = Field(default_factory=dict)

class CreateRuleGroup(BaseModel):
    name: str
    description: str = ""

