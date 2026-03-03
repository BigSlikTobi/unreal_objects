from pathlib import Path
import os
import subprocess
import time
import json

import pytest

from decision_center.stress_test.artifacts import (
    artifact_paths_for_slug,
    create_dataset_candidate_path,
    next_report_path,
)
from decision_center.stress_test.cli import main
from decision_center.stress_test.dataset import build_dataset_system_prompt
from decision_center.stress_test.evaluation import load_translation_results
from decision_center.stress_test.models import EvaluationStats
from decision_center.stress_test.reporting import write_markdown_report
from decision_center.stress_test.translation import build_translation_system_prompt
from decision_center.stress_test.translation import translate_cases
from decision_center.stress_test.schema_registry import (
    discover_schemas,
    expand_schema_selection,
)

def test_discover_schemas_uses_filename_stems_and_schema_body(tmp_path: Path):
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir()
    (schemas_dir / "finance.json").write_text(
        """
        {
          "name": "finance_blueprint",
          "description": "Finance test schema",
          "schema": {
            "withdrawal_amount": "number"
          }
        }
        """.strip()
    )
    (schemas_dir / "insurance.json").write_text(
        """
        {
          "schema": {
            "claim_amount": "number"
          }
        }
        """.strip()
    )

    schemas = discover_schemas(schemas_dir)

    assert [schema.slug for schema in schemas] == ["finance", "insurance"]
    assert schemas[0].display_name == "finance_blueprint"
    assert schemas[0].schema_dict == {"withdrawal_amount": "number"}
    assert schemas[1].display_name == "insurance"
    assert schemas[1].schema_dict == {"claim_amount": "number"}


def test_discover_schemas_skips_invalid_files(tmp_path: Path):
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir()
    (schemas_dir / "broken.json").write_text("{not-json")
    (schemas_dir / "empty.json").write_text('{"name":"empty"}')
    (schemas_dir / "valid.json").write_text('{"schema":{"amount":"number"}}')

    schemas = discover_schemas(schemas_dir)

    assert [schema.slug for schema in schemas] == ["valid"]


def test_expand_schema_selection_all_runs_sorted_schemas_then_none(tmp_path: Path):
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir()
    (schemas_dir / "finance.json").write_text('{"schema":{"withdrawal_amount":"number"}}')
    (schemas_dir / "ecommerce.json").write_text('{"schema":{"transaction_amount":"number"}}')

    schemas = discover_schemas(schemas_dir)

    run_targets = expand_schema_selection("all", schemas)

    assert [target.slug for target in run_targets] == ["ecommerce", "finance", "none"]
    assert [target.mode for target in run_targets] == ["schema", "schema", "none"]


def test_expand_schema_selection_rejects_unknown_slug(tmp_path: Path):
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir()
    (schemas_dir / "finance.json").write_text('{"schema":{"withdrawal_amount":"number"}}')

    schemas = discover_schemas(schemas_dir)

    with pytest.raises(ValueError, match="Unknown schema 'travel'"):
        expand_schema_selection("travel", schemas)


def test_next_report_path_increments_existing_versions(tmp_path: Path):
    report_dir = tmp_path / "evals"
    report_dir.mkdir()
    (report_dir / "generative_evaluation_report_v2.md").write_text("v2")
    (report_dir / "generative_evaluation_report_v7.md").write_text("v7")

    next_path = next_report_path(report_dir)

    assert next_path == report_dir / "generative_evaluation_report_v8.md"


def test_build_dataset_system_prompt_injects_selected_schema():
    prompt = build_dataset_system_prompt({"transaction_amount": "number"})

    assert "CRITICAL SCHEMA ENFORCEMENT" in prompt
    assert "transaction_amount" in prompt


def test_build_dataset_system_prompt_without_schema_skips_enforcement_block():
    prompt = build_dataset_system_prompt(None)

    assert "CRITICAL SCHEMA ENFORCEMENT" not in prompt


def test_build_translation_system_prompt_injects_selected_schema():
    prompt = build_translation_system_prompt({"withdrawal_amount": "number"})

    assert "CRITICAL SCHEMA ENFORCEMENT" in prompt
    assert "withdrawal_amount" in prompt


def test_build_translation_system_prompt_without_schema_skips_enforcement_block():
    prompt = build_translation_system_prompt(None)

    assert "CRITICAL SCHEMA ENFORCEMENT" not in prompt


def test_checked_in_ecommerce_schema_covers_delivery_and_fraud_relevant_fields():
    schema = json.loads(Path("schemas/ecommerce.json").read_text())["schema"]

    for key in [
        "delivery_time_days",
        "estimated_delivery_days",
        "shipping_country",
        "billing_country",
        "payment_status",
        "prior_chargeback_count",
        "refund_count_90d",
    ]:
        assert key in schema


def test_checked_in_finance_schema_covers_transfer_and_beneficiary_relevant_fields():
    schema = json.loads(Path("schemas/finance.json").read_text())["schema"]

    for key in [
        "transaction_amount",
        "transaction_type",
        "source_of_funds_verified",
        "beneficiary_account_age_days",
        "transfer_count_24h",
        "total_transfer_amount_24h",
        "account_age_days",
    ]:
        assert key in schema


def test_artifact_paths_for_slug_are_schema_scoped(tmp_path: Path):
    artifacts = artifact_paths_for_slug(tmp_path, "finance")

    assert artifacts.dataset_path == tmp_path / "finance" / "llm_test_dataset.json"
    assert artifacts.translations_path == tmp_path / "finance" / "batch_results.jsonl"
    assert artifacts.raw_eval_log_path == tmp_path / "finance" / "eval_output_raw.txt"
    assert artifacts.dataset_candidates_dir == tmp_path / "finance" / "datasets"
    assert artifacts.dataset_manifest_path == tmp_path / "finance" / "dataset_manifest.json"


def test_create_dataset_candidate_path_writes_versioned_candidate(tmp_path: Path):
    artifacts = artifact_paths_for_slug(tmp_path, "finance")

    candidate_path = create_dataset_candidate_path(artifacts)

    assert candidate_path.parent == tmp_path / "finance" / "datasets"
    assert candidate_path.name.startswith("llm_test_dataset_")
    assert candidate_path.suffix == ".json"


def test_translate_cases_skips_failed_rule_and_writes_remaining(tmp_path: Path, monkeypatch):
    output_path = tmp_path / "batch_results.jsonl"
    calls = []

    def fake_translate_rule(**kwargs):
        calls.append(kwargs["name"])
        if kwargs["name"] == "E2E Rule 0":
            raise ValueError("schema-shaped response")
        return {
            "datapoints": ["withdrawal_amount"],
            "edge_cases": [],
            "edge_cases_json": [],
            "rule_logic": "IF withdrawal_amount > 1000 THEN ASK_FOR_APPROVAL",
            "rule_logic_json": {
                "if": [{">": [{"var": "withdrawal_amount"}, 1000]}, "ASK_FOR_APPROVAL", None]
            },
        }

    monkeypatch.setattr("decision_center.stress_test.translation.translate_rule", fake_translate_rule)

    results = translate_cases(
        [
            {
                "natural_language_rule": "if withdrawal_amount > 1000 ask for approval",
                "context_data": {"withdrawal_amount": 1500},
                "expected_outcome": "ASK_FOR_APPROVAL",
            },
            {
                "natural_language_rule": "if withdrawal_amount > 1000 ask for approval",
                "context_data": {"withdrawal_amount": 1500},
                "expected_outcome": "ASK_FOR_APPROVAL",
            },
        ],
        output_path,
        provider="openai",
        model="gpt-5-mini-2025-08-07",
        api_key="fake-key",
    )

    assert calls == ["E2E Rule 0", "E2E Rule 1"]
    assert len(results) == 1
    assert "request-1" in output_path.read_text()


def test_main_auto_reuses_existing_dataset_and_shows_age(tmp_path: Path, monkeypatch, capsys):
    schemas_dir = tmp_path / "schemas"
    report_dir = tmp_path / "evals"
    artifacts_dir = report_dir / "artifacts"
    schemas_dir.mkdir()
    report_dir.mkdir()
    (schemas_dir / "finance.json").write_text('{"schema":{"withdrawal_amount":"number"}}')

    dataset_path = artifacts_dir / "finance" / "llm_test_dataset.json"
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    dataset_path.write_text("[]")
    stale_time = time.time() - 7200
    os.utime(dataset_path, (stale_time, stale_time))

    def fail_generate_dataset(*args, **kwargs):
        raise AssertionError("generate_dataset should not run when dataset exists")

    def fake_translate_cases(test_cases, output_path, **kwargs):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("")
        return []

    async def fake_ensure_services_available(*args, **kwargs):
        return None

    async def fake_evaluate_schema_run(*, run_target, artifacts, report_path, **kwargs):
        return EvaluationStats(
            schema_slug=run_target.slug,
            schema_mode=run_target.mode,
            provider="openai",
            model="gpt-5-mini-2025-08-07",
            total_cases=0,
            processed_cases=0,
            passed=0,
            failed=0,
            translation_errors=0,
            rule_upload_errors=0,
            decision_errors=0,
            pass_rate=0.0,
            dataset_path=str(artifacts.dataset_path),
            translations_path=str(artifacts.translations_path),
            raw_eval_log_path=str(artifacts.raw_eval_log_path),
            report_path=str(report_path),
        ), []

    def fake_write_report(report_path, stats, **kwargs):
        report_path.write_text("# report")

    monkeypatch.setattr("decision_center.stress_test.cli.ensure_services_available", fake_ensure_services_available)
    monkeypatch.setattr("decision_center.stress_test.cli.generate_dataset", fail_generate_dataset)
    monkeypatch.setattr("decision_center.stress_test.cli.translate_cases", fake_translate_cases)
    monkeypatch.setattr("decision_center.stress_test.cli.evaluate_schema_run", fake_evaluate_schema_run)
    monkeypatch.setattr("decision_center.stress_test.cli.write_markdown_report", fake_write_report)

    exit_code = main(
        [
            "--schema",
            "finance",
            "--schemas-dir",
            str(schemas_dir),
            "--report-dir",
            str(report_dir),
            "--artifacts-dir",
            str(artifacts_dir),
        ]
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Reusing dataset" in output
    assert "2h old" in output


def test_main_prepare_datasets_generates_candidate_only(tmp_path: Path, monkeypatch):
    schemas_dir = tmp_path / "schemas"
    report_dir = tmp_path / "evals"
    artifacts_dir = report_dir / "artifacts"
    schemas_dir.mkdir()
    report_dir.mkdir()
    (schemas_dir / "finance.json").write_text('{"schema":{"withdrawal_amount":"number"}}')

    seen = []

    async def fake_generate_dataset(output_path, schema_dict, **kwargs):
        seen.append(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("[]")
        return []

    monkeypatch.setattr("decision_center.stress_test.cli.generate_dataset", fake_generate_dataset)

    exit_code = main(
        [
            "--prepare-datasets",
            "--schema",
            "finance",
            "--schemas-dir",
            str(schemas_dir),
            "--report-dir",
            str(report_dir),
            "--artifacts-dir",
            str(artifacts_dir),
        ]
    )

    assert exit_code == 0
    assert len(seen) == 1
    assert seen[0].parent == artifacts_dir / "finance" / "datasets"
    assert not (artifacts_dir / "finance" / "llm_test_dataset.json").exists()


def test_main_promotes_latest_dataset_candidate(tmp_path: Path):
    schemas_dir = tmp_path / "schemas"
    report_dir = tmp_path / "evals"
    artifacts_dir = report_dir / "artifacts"
    schemas_dir.mkdir()
    report_dir.mkdir()
    (schemas_dir / "finance.json").write_text('{"schema":{"withdrawal_amount":"number"}}')

    artifacts = artifact_paths_for_slug(artifacts_dir, "finance")
    artifacts.dataset_candidates_dir.mkdir(parents=True, exist_ok=True)
    older = artifacts.dataset_candidates_dir / "llm_test_dataset_20260301_100000.json"
    newer = artifacts.dataset_candidates_dir / "llm_test_dataset_20260301_120000.json"
    older.write_text('[{"id":"old"}]')
    newer.write_text('[{"id":"new"}]')

    exit_code = main(
        [
            "--schema",
            "finance",
            "--promote-dataset",
            "latest",
            "--schemas-dir",
            str(schemas_dir),
            "--report-dir",
            str(report_dir),
            "--artifacts-dir",
            str(artifacts_dir),
        ]
    )

    assert exit_code == 0
    assert artifacts.dataset_path.read_text() == '[{"id":"new"}]'
    assert artifacts.dataset_manifest_path.exists()


def test_main_prepare_datasets_background_spawns_detached_process(tmp_path: Path, monkeypatch):
    schemas_dir = tmp_path / "schemas"
    report_dir = tmp_path / "evals"
    artifacts_dir = report_dir / "artifacts"
    schemas_dir.mkdir()
    report_dir.mkdir()
    (schemas_dir / "finance.json").write_text('{"schema":{"withdrawal_amount":"number"}}')

    seen = {}

    class DummyProcess:
        pid = 4242

    def fake_popen(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["kwargs"] = kwargs
        return DummyProcess()

    monkeypatch.setattr("decision_center.stress_test.cli.subprocess.Popen", fake_popen)

    exit_code = main(
        [
            "--prepare-datasets",
            "--schema",
            "finance",
            "--background",
            "--schemas-dir",
            str(schemas_dir),
            "--report-dir",
            str(report_dir),
            "--artifacts-dir",
            str(artifacts_dir),
        ]
    )

    assert exit_code == 0
    assert "--background" not in seen["cmd"]
    assert "--prepare-datasets" in seen["cmd"]
    assert seen["kwargs"]["stdout"] != subprocess.DEVNULL


def test_main_lists_baseline_and_candidate_datasets(tmp_path: Path, capsys):
    schemas_dir = tmp_path / "schemas"
    report_dir = tmp_path / "evals"
    artifacts_dir = report_dir / "artifacts"
    schemas_dir.mkdir()
    report_dir.mkdir()
    (schemas_dir / "finance.json").write_text('{"schema":{"withdrawal_amount":"number"}}')

    artifacts = artifact_paths_for_slug(artifacts_dir, "finance")
    artifacts.dataset_path.parent.mkdir(parents=True, exist_ok=True)
    artifacts.dataset_candidates_dir.mkdir(parents=True, exist_ok=True)
    artifacts.dataset_path.write_text('[{"id":"baseline"}]')
    artifacts.dataset_manifest_path.write_text(
        '{"active_dataset":"evals/artifacts/finance/llm_test_dataset.json","promoted_from":"evals/artifacts/finance/datasets/llm_test_dataset_20260301_120000.json"}'
    )
    (artifacts.dataset_candidates_dir / "llm_test_dataset_20260301_100000.json").write_text('[{"id":"older"}]')
    (artifacts.dataset_candidates_dir / "llm_test_dataset_20260301_120000.json").write_text('[{"id":"latest"}]')

    exit_code = main(
        [
            "--schema",
            "finance",
            "--list-datasets",
            "--schemas-dir",
            str(schemas_dir),
            "--report-dir",
            str(report_dir),
            "--artifacts-dir",
            str(artifacts_dir),
        ]
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Schema: finance" in output
    assert "Active baseline:" in output
    assert "llm_test_dataset.json" in output
    assert "Promoted from:" in output
    assert "Candidates:" in output
    assert "llm_test_dataset_20260301_100000.json" in output
    assert "llm_test_dataset_20260301_120000.json" in output


def test_load_translation_results_reads_jsonl_records(tmp_path: Path):
    translations_path = tmp_path / "batch_results.jsonl"
    translations_path.write_text(
        "\n".join(
            [
                '{"custom_id":"request-0","response":{"body":{"choices":[{"message":{"content":"{\\"rule_logic\\":\\"IF amount > 10 THEN REJECT\\"}"}}]}}}',
                '{"custom_id":"request-1","response":{"body":{"choices":[{"message":{"content":"{\\"rule_logic\\":\\"IF amount > 20 THEN APPROVE\\"}"}}]}}}',
            ]
        )
        + "\n"
    )

    results = load_translation_results(translations_path)

    assert results["request-0"]["rule_logic"] == "IF amount > 10 THEN REJECT"
    assert results["request-1"]["rule_logic"] == "IF amount > 20 THEN APPROVE"


def test_write_markdown_report_mentions_schema_and_artifacts(tmp_path: Path):
    report_path = tmp_path / "generative_evaluation_report_v1.md"
    stats = EvaluationStats(
        schema_slug="finance",
        schema_mode="schema",
        provider="openai",
        model="gpt-5-mini-2025-08-07",
        total_cases=20,
        processed_cases=20,
        passed=18,
        failed=1,
        translation_errors=1,
        rule_upload_errors=0,
        decision_errors=0,
        pass_rate=90.0,
        dataset_path="evals/artifacts/finance/llm_test_dataset.json",
        translations_path="evals/artifacts/finance/batch_results.jsonl",
        raw_eval_log_path="evals/artifacts/finance/eval_output_raw.txt",
        report_path=str(report_path),
    )

    write_markdown_report(
        report_path,
        stats,
        model_name="gpt-5-mini-2025-08-07",
        schema_path="schemas/finance.json",
        mismatches=[{"index": 7, "expected": "REJECT", "actual": "APPROVE"}],
    )

    report = report_path.read_text()

    assert "schema slug" in report.lower()
    assert "finance" in report
    assert "schemas/finance.json" in report
    assert "evals/artifacts/finance/llm_test_dataset.json" in report
    assert "Mismatch Analysis" in report


def test_main_runs_all_schemas_and_none_in_sequence(tmp_path: Path, monkeypatch, capsys):
    schemas_dir = tmp_path / "schemas"
    report_dir = tmp_path / "evals"
    artifacts_dir = report_dir / "artifacts"
    schemas_dir.mkdir()
    report_dir.mkdir()
    (schemas_dir / "finance.json").write_text('{"schema":{"withdrawal_amount":"number"}}')
    (schemas_dir / "ecommerce.json").write_text('{"schema":{"transaction_amount":"number"}}')

    seen = []

    async def fake_generate_dataset(output_path, schema_dict, **kwargs):
        seen.append(("dataset", output_path.parent.name, schema_dict))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("[]")
        return []

    def fake_translate_cases(test_cases, output_path, **kwargs):
        seen.append(("translate", output_path.parent.name, kwargs.get("schema_dict")))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("")
        return []

    async def fake_evaluate_schema_run(*, run_target, artifacts, report_path, **kwargs):
        seen.append(("evaluate", run_target.slug, report_path.name))
        return EvaluationStats(
            schema_slug=run_target.slug,
            schema_mode=run_target.mode,
            provider="openai",
            model="gpt-5-mini-2025-08-07",
            total_cases=0,
            processed_cases=0,
            passed=0,
            failed=0,
            translation_errors=0,
            rule_upload_errors=0,
            decision_errors=0,
            pass_rate=0.0,
            dataset_path=str(artifacts.dataset_path),
            translations_path=str(artifacts.translations_path),
            raw_eval_log_path=str(artifacts.raw_eval_log_path),
            report_path=str(report_path),
        ), []

    def fake_write_report(report_path, stats, **kwargs):
        seen.append(("report", stats.schema_slug, report_path.name))
        report_path.write_text(f"# {stats.schema_slug}")

    monkeypatch.setattr("decision_center.stress_test.cli.generate_dataset", fake_generate_dataset)
    monkeypatch.setattr("decision_center.stress_test.cli.translate_cases", fake_translate_cases)
    monkeypatch.setattr("decision_center.stress_test.cli.evaluate_schema_run", fake_evaluate_schema_run)
    monkeypatch.setattr("decision_center.stress_test.cli.write_markdown_report", fake_write_report)

    exit_code = main(
        [
            "--schema",
            "all",
            "--schemas-dir",
            str(schemas_dir),
            "--report-dir",
            str(report_dir),
            "--artifacts-dir",
            str(artifacts_dir),
        ]
    )

    assert exit_code == 0
    assert seen == [
        ("dataset", "ecommerce", {"transaction_amount": "number"}),
        ("translate", "ecommerce", {"transaction_amount": "number"}),
        ("evaluate", "ecommerce", "generative_evaluation_report_v1.md"),
        ("report", "ecommerce", "generative_evaluation_report_v1.md"),
        ("dataset", "finance", {"withdrawal_amount": "number"}),
        ("translate", "finance", {"withdrawal_amount": "number"}),
        ("evaluate", "finance", "generative_evaluation_report_v2.md"),
        ("report", "finance", "generative_evaluation_report_v2.md"),
        ("dataset", "none", None),
        ("translate", "none", None),
        ("evaluate", "none", "generative_evaluation_report_v3.md"),
        ("report", "none", "generative_evaluation_report_v3.md"),
    ]
    assert "Schema 'none'" in capsys.readouterr().out


def test_main_loads_dotenv_before_running(tmp_path: Path, monkeypatch):
    schemas_dir = tmp_path / "schemas"
    report_dir = tmp_path / "evals"
    artifacts_dir = report_dir / "artifacts"
    schemas_dir.mkdir()
    report_dir.mkdir()
    (schemas_dir / "finance.json").write_text('{"schema":{"withdrawal_amount":"number"}}')

    loaded = []

    def fake_load_dotenv():
        loaded.append(True)
        return True

    async def fake_generate_dataset(output_path, schema_dict, **kwargs):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("[]")
        return []

    def fake_translate_cases(test_cases, output_path, **kwargs):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("")
        return []

    async def fake_evaluate_schema_run(*, run_target, artifacts, report_path, **kwargs):
        return EvaluationStats(
            schema_slug=run_target.slug,
            schema_mode=run_target.mode,
            provider="openai",
            model="gpt-5-mini-2025-08-07",
            total_cases=0,
            processed_cases=0,
            passed=0,
            failed=0,
            translation_errors=0,
            rule_upload_errors=0,
            decision_errors=0,
            pass_rate=0.0,
            dataset_path=str(artifacts.dataset_path),
            translations_path=str(artifacts.translations_path),
            raw_eval_log_path=str(artifacts.raw_eval_log_path),
            report_path=str(report_path),
        ), []

    def fake_write_report(report_path, stats, **kwargs):
        report_path.write_text("# report")

    monkeypatch.setattr("decision_center.stress_test.cli.load_dotenv", fake_load_dotenv)
    monkeypatch.setattr("decision_center.stress_test.cli.generate_dataset", fake_generate_dataset)
    monkeypatch.setattr("decision_center.stress_test.cli.translate_cases", fake_translate_cases)
    monkeypatch.setattr("decision_center.stress_test.cli.evaluate_schema_run", fake_evaluate_schema_run)
    monkeypatch.setattr("decision_center.stress_test.cli.write_markdown_report", fake_write_report)

    exit_code = main(
        [
            "--schema",
            "finance",
            "--schemas-dir",
            str(schemas_dir),
            "--report-dir",
            str(report_dir),
            "--artifacts-dir",
            str(artifacts_dir),
        ]
    )

    assert exit_code == 0
    assert loaded == [True]


def test_main_warns_and_continues_when_service_check_fails_without_strict_flag(tmp_path: Path, monkeypatch, capsys):
    schemas_dir = tmp_path / "schemas"
    report_dir = tmp_path / "evals"
    artifacts_dir = report_dir / "artifacts"
    schemas_dir.mkdir()
    report_dir.mkdir()
    (schemas_dir / "finance.json").write_text('{"schema":{"withdrawal_amount":"number"}}')

    async def fake_ensure_services_available(*args, **kwargs):
        raise RuntimeError("services unavailable")

    async def fake_generate_dataset(output_path, schema_dict, **kwargs):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("[]")
        return []

    def fake_translate_cases(test_cases, output_path, **kwargs):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("")
        return []

    async def fake_evaluate_schema_run(*, run_target, artifacts, report_path, **kwargs):
        return EvaluationStats(
            schema_slug=run_target.slug,
            schema_mode=run_target.mode,
            provider="openai",
            model="gpt-5-mini-2025-08-07",
            total_cases=0,
            processed_cases=0,
            passed=0,
            failed=0,
            translation_errors=0,
            rule_upload_errors=0,
            decision_errors=0,
            pass_rate=0.0,
            dataset_path=str(artifacts.dataset_path),
            translations_path=str(artifacts.translations_path),
            raw_eval_log_path=str(artifacts.raw_eval_log_path),
            report_path=str(report_path),
        ), []

    def fake_write_report(report_path, stats, **kwargs):
        report_path.write_text("# report")

    monkeypatch.setattr("decision_center.stress_test.cli.ensure_services_available", fake_ensure_services_available)
    monkeypatch.setattr("decision_center.stress_test.cli.generate_dataset", fake_generate_dataset)
    monkeypatch.setattr("decision_center.stress_test.cli.translate_cases", fake_translate_cases)
    monkeypatch.setattr("decision_center.stress_test.cli.evaluate_schema_run", fake_evaluate_schema_run)
    monkeypatch.setattr("decision_center.stress_test.cli.write_markdown_report", fake_write_report)

    exit_code = main(
        [
            "--schema",
            "finance",
            "--schemas-dir",
            str(schemas_dir),
            "--report-dir",
            str(report_dir),
            "--artifacts-dir",
            str(artifacts_dir),
        ]
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Service check warning for schema 'finance': services unavailable" in output


def test_main_prints_banner_and_phase_markers(tmp_path: Path, monkeypatch, capsys):
    schemas_dir = tmp_path / "schemas"
    report_dir = tmp_path / "evals"
    artifacts_dir = report_dir / "artifacts"
    schemas_dir.mkdir()
    report_dir.mkdir()
    (schemas_dir / "finance.json").write_text('{"schema":{"withdrawal_amount":"number"}}')

    def fake_clear_screen():
        print("[clear-screen]")

    async def fake_ensure_services_available(*args, **kwargs):
        return None

    async def fake_generate_dataset(output_path, schema_dict, **kwargs):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("[]")
        return []

    def fake_translate_cases(test_cases, output_path, **kwargs):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("")
        return []

    async def fake_evaluate_schema_run(*, run_target, artifacts, report_path, **kwargs):
        return EvaluationStats(
            schema_slug=run_target.slug,
            schema_mode=run_target.mode,
            provider="openai",
            model="gpt-5-mini-2025-08-07",
            total_cases=0,
            processed_cases=0,
            passed=0,
            failed=0,
            translation_errors=0,
            rule_upload_errors=0,
            decision_errors=0,
            pass_rate=0.0,
            dataset_path=str(artifacts.dataset_path),
            translations_path=str(artifacts.translations_path),
            raw_eval_log_path=str(artifacts.raw_eval_log_path),
            report_path=str(report_path),
        ), []

    def fake_write_report(report_path, stats, **kwargs):
        report_path.write_text("# report")

    monkeypatch.setattr("decision_center.stress_test.cli.clear_screen", fake_clear_screen)
    monkeypatch.setattr("decision_center.stress_test.cli.ensure_services_available", fake_ensure_services_available)
    monkeypatch.setattr("decision_center.stress_test.cli.generate_dataset", fake_generate_dataset)
    monkeypatch.setattr("decision_center.stress_test.cli.translate_cases", fake_translate_cases)
    monkeypatch.setattr("decision_center.stress_test.cli.evaluate_schema_run", fake_evaluate_schema_run)
    monkeypatch.setattr("decision_center.stress_test.cli.write_markdown_report", fake_write_report)

    exit_code = main(
        [
            "--schema",
            "finance",
            "--schemas-dir",
            str(schemas_dir),
            "--report-dir",
            str(report_dir),
            "--artifacts-dir",
            str(artifacts_dir),
        ]
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "[clear-screen]" in output
    assert "UNREAL OBJECTS" in output
    assert "This run starts by generating a synthetic dataset" in output
    assert "The harness then translates those rules into JSON Logic" in output
    assert "At the end you will get versioned markdown reports" in output
    assert "Checking services" in output
    assert "Generating dataset" in output
    assert "Translating rules" in output
    assert "Running evaluation" in output
    assert "Writing report" in output
