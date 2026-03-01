from datetime import UTC, datetime
from pathlib import Path

from decision_center.stress_test.models import EvaluationStats


def write_markdown_report(
    report_path: Path,
    stats: EvaluationStats,
    *,
    model_name: str,
    schema_path: str | None,
    mismatches: list[dict],
) -> None:
    schema_label = schema_path or "No schema injected"
    mismatch_lines = (
        "\n".join(
            f"- Case {item.get('index')}: expected {item.get('expected')}, actual {item.get('actual')}"
            for item in mismatches
        )
        or "- None"
    )
    report = f"""# Generative Evaluation Report

**Date**: {datetime.now(UTC).date()}
**Provider**: {stats.provider}
**Model**: {model_name}
**Schema Slug**: {stats.schema_slug}
**Schema Mode**: {stats.schema_mode}
**Schema Path**: {schema_label}

## Final Results

| Metric | Count |
| --- | ---: |
| Total Cases | {stats.total_cases} |
| Passed | {stats.passed} |
| Failed | {stats.failed} |
| Translation Errors | {stats.translation_errors} |
| Rule Upload Errors | {stats.rule_upload_errors} |
| Decision Errors | {stats.decision_errors} |
| Pass Rate | {stats.pass_rate:.1f}% |

## Artifact Locations

| Artifact | Path |
| --- | --- |
| Dataset | {stats.dataset_path} |
| Translations | {stats.translations_path} |
| Raw Eval Log | {stats.raw_eval_log_path} |
| Report | {stats.report_path} |

## Mismatch Analysis

{mismatch_lines}
"""
    report_path.write_text(report)
