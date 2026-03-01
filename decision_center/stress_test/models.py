from pathlib import Path
from typing import Literal

from pydantic import BaseModel


class SchemaDescriptor(BaseModel):
    slug: str
    path: Path
    display_name: str
    description: str = ""
    schema_dict: dict


class SchemaRunTarget(BaseModel):
    mode: str
    slug: str
    descriptor: SchemaDescriptor | None = None


class StressTestCase(BaseModel):
    natural_language_rule: str
    context_data: dict
    expected_outcome: Literal["APPROVE", "REJECT", "ASK_FOR_APPROVAL"]


class RunArtifacts(BaseModel):
    dataset_path: Path
    dataset_candidates_dir: Path
    dataset_manifest_path: Path
    translations_path: Path
    raw_eval_log_path: Path
    report_path: Path | None = None


class EvaluationStats(BaseModel):
    schema_slug: str
    schema_mode: Literal["schema", "none"]
    provider: str
    model: str
    total_cases: int
    processed_cases: int
    passed: int
    failed: int
    translation_errors: int
    rule_upload_errors: int
    decision_errors: int
    pass_rate: float
    dataset_path: str
    translations_path: str
    raw_eval_log_path: str
    report_path: str
