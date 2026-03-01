import re
from datetime import UTC, datetime
import json
from pathlib import Path

from decision_center.stress_test.models import RunArtifacts

REPORT_PATTERN = re.compile(r"generative_evaluation_report_v(\d+)\.md$")


def next_report_path(report_dir: Path) -> Path:
    highest_version = 0
    for path in report_dir.glob("generative_evaluation_report_v*.md"):
        match = REPORT_PATTERN.match(path.name)
        if match:
            highest_version = max(highest_version, int(match.group(1)))
    return report_dir / f"generative_evaluation_report_v{highest_version + 1}.md"


def artifact_paths_for_slug(artifacts_dir: Path, slug: str) -> RunArtifacts:
    base_dir = artifacts_dir / slug
    return RunArtifacts(
        dataset_path=base_dir / "llm_test_dataset.json",
        dataset_candidates_dir=base_dir / "datasets",
        dataset_manifest_path=base_dir / "dataset_manifest.json",
        translations_path=base_dir / "batch_results.jsonl",
        raw_eval_log_path=base_dir / "eval_output_raw.txt",
    )


def create_dataset_candidate_path(artifacts: RunArtifacts) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return artifacts.dataset_candidates_dir / f"llm_test_dataset_{timestamp}.json"


def list_dataset_candidates(artifacts: RunArtifacts) -> list[Path]:
    return sorted(artifacts.dataset_candidates_dir.glob("llm_test_dataset_*.json"))


def resolve_dataset_candidate(artifacts: RunArtifacts, selector: str) -> Path:
    if selector == "latest":
        candidates = list_dataset_candidates(artifacts)
        if not candidates:
            raise FileNotFoundError(f"No dataset candidates found for schema artifacts at {artifacts.dataset_candidates_dir}")
        return candidates[-1]

    candidate_path = Path(selector)
    if not candidate_path.exists():
        raise FileNotFoundError(f"Dataset candidate not found: {candidate_path}")
    return candidate_path


def write_dataset_manifest(artifacts: RunArtifacts, *, active_dataset: Path, promoted_from: Path | None = None) -> None:
    payload = {
        "active_dataset": str(active_dataset),
        "promoted_from": str(promoted_from) if promoted_from else None,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    artifacts.dataset_manifest_path.write_text(json.dumps(payload, indent=2))
