import argparse
import asyncio
import json
from pathlib import Path
import shutil
import subprocess
import sys
from time import time

from dotenv import load_dotenv

from decision_center.stress_test.artifacts import (
    artifact_paths_for_slug,
    create_dataset_candidate_path,
    list_dataset_candidates,
    next_report_path,
    resolve_dataset_candidate,
    write_dataset_manifest,
)
from decision_center.stress_test.dataset import generate_dataset
from decision_center.stress_test.evaluation import ensure_services_available, evaluate_schema_run
from decision_center.stress_test.reporting import write_markdown_report
from decision_center.stress_test.schema_registry import discover_schemas, expand_schema_selection
from decision_center.stress_test.translation import translate_cases

ASCII_ART = r"""
 ██    ██  ███   ██  ██████▒   ████████    ▒██▒    ██                   ░████░   ██████▒      █████  ████████    ▒████▒  ████████   ▒████▒  
 ██    ██  ███   ██  ███████▓  ████████    ▓██▓    ██                   ██████   ███████▓     █████  ████████   ▓██████  ████████  ▒██████  
 ██    ██  ███▒  ██  ██   ▒██  ██          ████    ██                  ▒██  ██▒  ██   ▒██        ██  ██        ▒██▒  ░█     ██     ██▒  ▒█  
 ██    ██  ████  ██  ██    ██  ██          ████    ██                  ██▒  ▒██  ██    ██        ██  ██        ██▓          ██     ██       
 ██    ██  ██▒█▒ ██  ██   ▒██  ██         ▒█▓▓█▒   ██                  ██    ██  ██   ▒██        ██  ██        ██░          ██     ███▒     
 ██    ██  ██ ██ ██  ███████▒  ███████    ▓█▒▒█▓   ██                  ██    ██  ███████░        ██  ███████   ██           ██     ▒█████▒  
 ██    ██  ██ ██ ██  ██████▓   ███████    ██  ██   ██                  ██    ██  ███████░        ██  ███████   ██           ██      ░█████▒ 
 ██    ██  ██ ▒█▒██  ██  ▓██░  ██         ██████   ██                  ██    ██  ██   ▒██        ██  ██        ██░          ██         ▒███ 
 ██    ██  ██  ████  ██   ██▓  ██        ░██████░  ██                  ██▒  ▒██  ██    ██        ██  ██        ██▓          ██           ██ 
 ██▓  ▓██  ██  ▒███  ██   ▒██  ██        ▒██  ██▒  ██                  ▒██  ██▒  ██   ▒██  █▒   ▒██  ██        ▒██▒  ░█     ██     █▒░  ▒██ 
 ▒██████▒  ██   ███  ██    ██▒ ████████  ███  ███  ████████             ██████   ████████  ███████▓  ████████   ▓██████     ██     ███████▒ 
  ▒████▒   ██   ███  ██    ███ ████████  ██▒  ▒██  ████████             ░████░   ██████▓   ░█████▒   ████████    ▒████▒     ██     ░█████▒  
                                                                                          
                                ▗▄▄▄▖▗▖ ▗▖  ▄  ▗▖   ▗▖ ▗▖  ▄  ▗▄▄▄▖ ▄▄▄  ▗▄▖ ▗▄ ▗▖       ▄▄ ▗▄▄▄▖▗▄ ▗▖▗▄▄▄▖▗▄▄▄▖▗▄▄▖      
                                ▐▛▀▀▘▝█ █▘ ▐█▌ ▐▌   ▐▌ ▐▌ ▐█▌ ▝▀█▀▘ ▀█▀  █▀█ ▐█ ▐▌      █▀▀▌▐▛▀▀▘▐█ ▐▌▝▀█▀▘▐▛▀▀▘▐▛▀▜▌     
                                ▐▌    █ █  ▐█▌ ▐▌   ▐▌ ▐▌ ▐█▌   █    █  ▐▌ ▐▌▐▛▌▐▌     ▐▛   ▐▌   ▐▛▌▐▌  █  ▐▌   ▐▌ ▐▌     
                                ▐███  █ █  █ █ ▐▌   ▐▌ ▐▌ █ █   █    █  ▐▌ ▐▌▐▌█▐▌     ▐▌   ▐███ ▐▌█▐▌  █  ▐███ ▐███      
                                ▐▌    ▐█▌  ███ ▐▌   ▐▌ ▐▌ ███   █    █  ▐▌ ▐▌▐▌▐▟▌     ▐▙   ▐▌   ▐▌▐▟▌  █  ▐▌   ▐▌▝█▖     
                                ▐▙▄▄▖ ▐█▌ ▗█ █▖▐▙▄▄▖▝█▄█▘▗█ █▖  █   ▄█▄  █▄█ ▐▌ █▌      █▄▄▌▐▙▄▄▖▐▌ █▌  █  ▐▙▄▄▖▐▌ ▐▌     
                                ▝▀▀▀▘ ▝▀▘ ▝▘ ▝▘▝▀▀▀▘ ▝▀▘ ▝▘ ▝▘  ▀   ▀▀▀  ▝▀▘ ▝▘ ▀▘       ▀▀ ▝▀▀▀▘▝▘ ▀▘  ▀  ▝▀▀▀▘▝▘ ▝▀                                                                                                                                                                                     
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the generative stress-test pipeline.")
    parser.add_argument("--schema", required=True, help="Schema slug, 'none', or 'all'.")
    parser.add_argument("--provider", default="openai")
    parser.add_argument("--model", default="gpt-5-mini-2025-08-07")
    parser.add_argument("--dataset-batches", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=50)
    parser.add_argument("--reuse-dataset", action="store_true")
    parser.add_argument("--refresh-dataset", action="store_true")
    parser.add_argument("--reuse-translations", action="store_true")
    parser.add_argument("--prepare-datasets", action="store_true")
    parser.add_argument("--background", action="store_true")
    parser.add_argument("--promote-dataset")
    parser.add_argument("--list-datasets", action="store_true")
    parser.add_argument("--schemas-dir", default="schemas")
    parser.add_argument("--artifacts-dir", default="evals/artifacts")
    parser.add_argument("--report-dir", default="evals")
    parser.add_argument("--rule-engine-url", default="http://127.0.0.1:8001")
    parser.add_argument("--decision-center-url", default="http://127.0.0.1:8002")
    parser.add_argument("--group-prefix", default="E2E Stress Test")
    parser.add_argument("--fail-on-missing-services", action="store_true")
    parser.add_argument("--keep-group", action="store_true")
    return parser


def clear_screen() -> None:
    print("\033[2J\033[H", end="")


def print_banner() -> None:
    print(ASCII_ART)
    print("UNREAL OBJECTS")
    print("Autonomy with Receipts: Generative Stress Test\n")


def print_intro() -> None:
    print(
        "This run starts by generating a synthetic dataset of business rules and "
        "matching context payloads. That first phase can take a bit because the "
        "CLI is asking the model to create a broad, realistic test corpus before "
        "anything is evaluated."
    )
    print(
        "The harness then translates those rules into JSON Logic, loads them into "
        "the Rule Engine, and asks the Decision Center to evaluate each case "
        "against the expected outcome. This is useful because it measures the "
        "full pipeline end to end instead of only testing translation or rule "
        "execution in isolation."
    )
    print(
        "At the end you will get versioned markdown reports in evals/ and raw "
        "artifacts under evals/artifacts/<schema>/ so you can inspect the "
        "dataset, translations, and evaluation output.\n"
    )


def print_phase(title: str, detail: str = "") -> None:
    suffix = f" - {detail}" if detail else ""
    print(f"[phase] {title}{suffix}")


def format_artifact_age(path: Path) -> str:
    age_seconds = max(0, int(time() - path.stat().st_mtime))
    if age_seconds < 60:
        return f"{age_seconds}s old"
    if age_seconds < 3600:
        return f"{age_seconds // 60}m old"
    if age_seconds < 86400:
        return f"{age_seconds // 3600}h old"
    return f"{age_seconds // 86400}d old"


def build_background_command(argv: list[str]) -> list[str]:
    return [
        sys.executable,
        "-m",
        "decision_center.stress_test.cli",
        *[arg for arg in argv if arg != "--background"],
    ]


def launch_background_prepare(argv: list[str], artifacts_dir: Path) -> int:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    log_path = artifacts_dir / "prepare_datasets_background.log"
    log_handle = log_path.open("a")
    process = subprocess.Popen(
        build_background_command(argv),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    print(f"Background dataset preparation started. PID: {process.pid}. Log: {log_path}")
    return 0


def prepare_datasets(args, run_targets, artifacts_dir: Path) -> int:
    for run_target in run_targets:
        artifacts = artifact_paths_for_slug(artifacts_dir, run_target.slug)
        artifacts.dataset_candidates_dir.mkdir(parents=True, exist_ok=True)
        schema_dict = run_target.descriptor.schema_dict if run_target.descriptor else None
        candidate_path = create_dataset_candidate_path(artifacts)
        print_phase("Generating dataset candidate", str(candidate_path))
        asyncio.run(
            generate_dataset(
                candidate_path,
                schema_dict,
                model_name=args.model,
                batch_count=args.dataset_batches,
                batch_size=args.batch_size,
            )
        )
        print(f"Dataset candidate created for schema '{run_target.slug}': {candidate_path}")
    return 0


def promote_dataset(artifacts_dir: Path, run_target, selector: str) -> int:
    artifacts = artifact_paths_for_slug(artifacts_dir, run_target.slug)
    artifacts.dataset_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_path = resolve_dataset_candidate(artifacts, selector)
    shutil.copyfile(candidate_path, artifacts.dataset_path)
    write_dataset_manifest(artifacts, active_dataset=artifacts.dataset_path, promoted_from=candidate_path)
    print(f"Promoted dataset for schema '{run_target.slug}': {candidate_path} -> {artifacts.dataset_path}")
    return 0


def list_datasets(artifacts_dir: Path, run_targets) -> int:
    for run_target in run_targets:
        if run_target.slug == "none":
            continue
        artifacts = artifact_paths_for_slug(artifacts_dir, run_target.slug)
        print(f"Schema: {run_target.slug}")
        if artifacts.dataset_path.exists():
            print(f"Active baseline: {artifacts.dataset_path}")
        else:
            print("Active baseline: (none)")

        if artifacts.dataset_manifest_path.exists():
            manifest = json.loads(artifacts.dataset_manifest_path.read_text())
            promoted_from = manifest.get("promoted_from")
            if promoted_from:
                print(f"Promoted from: {promoted_from}")

        candidates = list_dataset_candidates(artifacts)
        if candidates:
            print("Candidates:")
            for candidate in candidates:
                print(f"- {candidate}")
        else:
            print("Candidates: (none)")
        print("")
    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    clear_screen()
    print_banner()
    print_intro()
    argv = argv or sys.argv[1:]
    args = build_parser().parse_args(argv)
    schemas_dir = Path(args.schemas_dir)
    report_dir = Path(args.report_dir)
    artifacts_dir = Path(args.artifacts_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    schemas = discover_schemas(schemas_dir)
    run_targets = expand_schema_selection(args.schema, schemas)

    if args.background:
        if not args.prepare_datasets:
            print("--background is only supported with --prepare-datasets")
            return 1
        return launch_background_prepare(argv, artifacts_dir)

    if args.prepare_datasets:
        return prepare_datasets(args, run_targets, artifacts_dir)

    if args.promote_dataset:
        if len(run_targets) != 1 or run_targets[0].slug == "none":
            print("--promote-dataset requires one concrete schema slug")
            return 1
        return promote_dataset(artifacts_dir, run_targets[0], args.promote_dataset)

    if args.list_datasets:
        return list_datasets(artifacts_dir, run_targets)

    failures = 0
    for run_target in run_targets:
        artifacts = artifact_paths_for_slug(artifacts_dir, run_target.slug)
        artifacts.dataset_path.parent.mkdir(parents=True, exist_ok=True)
        schema_dict = run_target.descriptor.schema_dict if run_target.descriptor else None
        schema_path = str(run_target.descriptor.path) if run_target.descriptor else None

        try:
            print_phase("Checking services", run_target.slug)
            asyncio.run(ensure_services_available(args.rule_engine_url, args.decision_center_url))

            should_reuse_dataset = not args.refresh_dataset and artifacts.dataset_path.exists()
            if args.reuse_dataset or should_reuse_dataset:
                dataset_age = format_artifact_age(artifacts.dataset_path)
                print_phase("Reusing dataset", f"{artifacts.dataset_path} ({dataset_age})")
                test_cases = json.loads(artifacts.dataset_path.read_text())
            else:
                print_phase("Generating dataset", run_target.slug)
                test_cases = asyncio.run(
                    generate_dataset(
                        artifacts.dataset_path,
                        schema_dict,
                        model_name=args.model,
                        batch_count=args.dataset_batches,
                        batch_size=args.batch_size,
                    )
                )

            if args.reuse_translations:
                print_phase("Reusing translations", str(artifacts.translations_path))
                _ = artifacts.translations_path.read_text()
            else:
                print_phase("Translating rules", run_target.slug)
                translate_cases(
                    test_cases,
                    artifacts.translations_path,
                    provider=args.provider,
                    model=args.model,
                    schema_dict=schema_dict,
                )

            report_path = next_report_path(report_dir)
            print_phase("Running evaluation", run_target.slug)
            stats, mismatches = asyncio.run(
                evaluate_schema_run(
                    run_target=run_target,
                    artifacts=artifacts,
                    report_path=report_path,
                    rule_engine_url=args.rule_engine_url,
                    decision_center_url=args.decision_center_url,
                    provider=args.provider,
                    model=args.model,
                    group_prefix=args.group_prefix,
                    keep_group=args.keep_group,
                )
            )
            print_phase("Writing report", report_path.name)
            write_markdown_report(
                report_path,
                stats,
                model_name=args.model,
                schema_path=schema_path,
                mismatches=mismatches,
            )
            print(
                f"Schema '{run_target.slug}': {stats.passed}/{stats.total_cases} passed. "
                f"Report: {report_path}"
            )
        except Exception as exc:
            failures += 1
            print(f"Schema '{run_target.slug}' failed: {exc}")
            if args.fail_on_missing_services:
                return 1

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
