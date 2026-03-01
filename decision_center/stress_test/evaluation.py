import json
from pathlib import Path

import httpx

from decision_center.stress_test.models import EvaluationStats, RunArtifacts, SchemaRunTarget


def load_translation_results(translations_path: Path) -> dict[str, dict]:
    results: dict[str, dict] = {}
    for line in translations_path.read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        custom_id = record.get("custom_id")
        content = record["response"]["body"]["choices"][0]["message"]["content"]
        results[custom_id] = json.loads(content)
    return results


async def ensure_services_available(rule_engine_url: str, decision_center_url: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        group_resp = await client.get(f"{rule_engine_url}/v1/groups")
        group_resp.raise_for_status()
        decision_resp = await client.get(
            f"{decision_center_url}/v1/decide",
            params={"request_description": "healthcheck", "context": "{}", "group_id": "missing"},
        )
        if decision_resp.status_code not in {200, 404, 422, 500}:
            decision_resp.raise_for_status()


async def evaluate_schema_run(
    *,
    run_target: SchemaRunTarget,
    artifacts: RunArtifacts,
    report_path: Path,
    rule_engine_url: str,
    decision_center_url: str,
    provider: str,
    model: str,
    group_prefix: str,
    keep_group: bool = False,
) -> tuple[EvaluationStats, list[dict]]:
    test_cases = json.loads(artifacts.dataset_path.read_text())
    batch_results = load_translation_results(artifacts.translations_path)
    mismatches: list[dict] = []
    raw_log_lines = [f"Evaluating schema '{run_target.slug}'"]
    stats = {
        "passed": 0,
        "failed": 0,
        "translation_errors": 0,
        "rule_upload_errors": 0,
        "decision_errors": 0,
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            f"{rule_engine_url}/v1/groups",
            json={
                "name": f"{group_prefix} {run_target.slug}",
                "description": f"Stress test group for schema '{run_target.slug}'",
            },
        )
        resp.raise_for_status()
        group_id = resp.json()["id"]

        try:
            for index, case in enumerate(test_cases):
                custom_id = f"request-{index}"
                translated = batch_results.get(custom_id)
                if not translated:
                    stats["translation_errors"] += 1
                    mismatches.append({"index": index, "error": "missing_translation"})
                    raw_log_lines.append(f"[{index}] missing translation")
                    continue

                translated_payload = dict(translated)
                translated_payload["name"] = f"E2E Rule {index}"
                translated_payload["feature"] = f"stress_test_{run_target.slug}"

                rule_resp = await client.post(
                    f"{rule_engine_url}/v1/groups/{group_id}/rules",
                    json=translated_payload,
                )
                if rule_resp.status_code != 201:
                    stats["rule_upload_errors"] += 1
                    mismatches.append(
                        {
                            "index": index,
                            "error": "rule_upload_failed",
                            "status_code": rule_resp.status_code,
                            "body": rule_resp.text,
                        }
                    )
                    raw_log_lines.append(f"[{index}] rule upload failed {rule_resp.status_code}")
                    continue

                rule_id = rule_resp.json()["id"]
                try:
                    dec_resp = await client.get(
                        f"{decision_center_url}/v1/decide",
                        params={
                            "request_description": f"Stress test {index}",
                            "context": json.dumps(case["context_data"]),
                            "group_id": group_id,
                        },
                    )
                    if dec_resp.status_code != 200:
                        stats["decision_errors"] += 1
                        mismatches.append(
                            {
                                "index": index,
                                "error": "decision_failed",
                                "status_code": dec_resp.status_code,
                                "body": dec_resp.text,
                            }
                        )
                        raw_log_lines.append(f"[{index}] decision failed {dec_resp.status_code}")
                        continue

                    decision_data = dec_resp.json()
                    actual = decision_data.get("outcome")
                    expected = case["expected_outcome"]
                    if actual == expected:
                        stats["passed"] += 1
                        raw_log_lines.append(f"[{index}] pass {actual}")
                    else:
                        stats["failed"] += 1
                        mismatch = {
                            "index": index,
                            "natural_language_rule": case["natural_language_rule"],
                            "expected": expected,
                            "actual": actual,
                            "matched_details": decision_data.get("matched_details", []),
                        }
                        mismatches.append(mismatch)
                        raw_log_lines.append(f"[{index}] mismatch expected={expected} actual={actual}")
                finally:
                    await client.delete(f"{rule_engine_url}/v1/groups/{group_id}/rules/{rule_id}")
        finally:
            artifacts.raw_eval_log_path.parent.mkdir(parents=True, exist_ok=True)
            artifacts.raw_eval_log_path.write_text("\n".join(raw_log_lines) + "\n")
            if not keep_group:
                await client.delete(f"{rule_engine_url}/v1/groups/{group_id}")

    total_cases = len(test_cases)
    processed_cases = stats["passed"] + stats["failed"]
    pass_rate = (stats["passed"] / total_cases * 100.0) if total_cases else 0.0
    evaluation_stats = EvaluationStats(
        schema_slug=run_target.slug,
        schema_mode=run_target.mode,
        provider=provider,
        model=model,
        total_cases=total_cases,
        processed_cases=processed_cases,
        passed=stats["passed"],
        failed=stats["failed"],
        translation_errors=stats["translation_errors"],
        rule_upload_errors=stats["rule_upload_errors"],
        decision_errors=stats["decision_errors"],
        pass_rate=pass_rate,
        dataset_path=str(artifacts.dataset_path),
        translations_path=str(artifacts.translations_path),
        raw_eval_log_path=str(artifacts.raw_eval_log_path),
        report_path=str(report_path),
    )
    return evaluation_stats, mismatches
