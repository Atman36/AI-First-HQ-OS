#!/usr/bin/env python3
"""Minimal dataset-driven eval runner for repeatable HQ checks."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

REPO_ROOT = Path(os.environ.get("HQ_EVAL_REPO_ROOT", Path(__file__).resolve().parents[1])).resolve()
os.environ.setdefault("HQ_TELEMETRY_REPO_ROOT", str(REPO_ROOT))
os.environ.setdefault("HQ_RUNTIME_PRIVATE_ROOT", str(REPO_ROOT / ".hq"))

from hq_io import write_json
from hq_telemetry import build_trace_contract
from hq_telemetry import write_event_payload


PRIVATE_ROOT = Path(os.environ.get("HQ_RUNTIME_PRIVATE_ROOT", REPO_ROOT / ".hq")).resolve()
EVAL_ROOT = PRIVATE_ROOT / "evals"
SCHEMA_DIR = REPO_ROOT / "05 AI Control Plane" / "schemas"
DATASET_SCHEMA_PATH = SCHEMA_DIR / "eval-dataset.schema.json"
REPORT_SCHEMA_PATH = SCHEMA_DIR / "eval-report.schema.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_payload(payload: dict[str, Any], schema_path: Path, label: str) -> None:
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path))
    if errors:
        error = errors[0]
        path = ".".join(str(item) for item in error.absolute_path)
        raise ValueError(f"{label} failed schema validation at {path or '<root>'}: {error.message}")


def load_dataset(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    validate_payload(payload, DATASET_SCHEMA_PATH, "dataset")
    return payload


def slugify(value: str) -> str:
    chunks: list[str] = []
    current: list[str] = []
    for char in value.lower().strip():
        if char.isalnum():
            current.append(char)
            continue
        if current:
            chunks.append("".join(current))
            current = []
    if current:
        chunks.append("".join(current))
    return "-".join(chunks) or "eval"


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str = ""


def _contains_check(haystack: str, needle: str, label: str) -> CheckResult:
    passed = needle in haystack
    details = f"expected {label} to contain {needle!r}" if not passed else ""
    return CheckResult(name=f"{label}_contains", passed=passed, details=details)


def _not_contains_check(haystack: str, needle: str, label: str) -> CheckResult:
    passed = needle not in haystack
    details = f"expected {label} to not contain {needle!r}" if not passed else ""
    return CheckResult(name=f"{label}_not_contains", passed=passed, details=details)


def run_case(case: dict[str, Any], dataset_path: Path) -> dict[str, Any]:
    if case["kind"] != "command":
        raise ValueError(f"unsupported case kind: {case['kind']}")

    cwd_value = str(case.get("cwd") or "").strip()
    if cwd_value:
        cwd_path = Path(cwd_value)
        if not cwd_path.is_absolute():
            cwd_path = dataset_path.parent / cwd_path
    else:
        cwd_path = dataset_path.parent
    cwd = cwd_path.resolve()
    env = os.environ.copy()
    env.update(case.get("env") or {})
    timeout = float(case.get("timeout_seconds") or 30.0)

    started = time.perf_counter()
    try:
        completed = subprocess.run(
            case["command"],
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.perf_counter() - started
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        return {
            "id": case["id"],
            "status": "failed",
            "duration_seconds": round(duration, 6),
            "exit_code": -1,
            "checks": [
                {
                    "name": "timeout",
                    "passed": False,
                    "details": f"command exceeded timeout of {timeout} seconds",
                }
            ],
            "stdout": stdout,
            "stderr": stderr,
        }
    duration = time.perf_counter() - started

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    expectations = case["expectations"]
    checks: list[CheckResult] = [
        CheckResult(
            name="exit_code",
            passed=completed.returncode == expectations["exit_code"],
            details=(
                ""
                if completed.returncode == expectations["exit_code"]
                else f"expected exit code {expectations['exit_code']}, got {completed.returncode}"
            ),
        )
    ]

    for needle in expectations.get("stdout_contains", []):
        checks.append(_contains_check(stdout, needle, "stdout"))
    for needle in expectations.get("stderr_contains", []):
        checks.append(_contains_check(stderr, needle, "stderr"))
    for needle in expectations.get("stdout_not_contains", []):
        checks.append(_not_contains_check(stdout, needle, "stdout"))
    for needle in expectations.get("stderr_not_contains", []):
        checks.append(_not_contains_check(stderr, needle, "stderr"))

    passed = all(check.passed for check in checks)
    return {
        "id": case["id"],
        "status": "passed" if passed else "failed",
        "duration_seconds": round(duration, 6),
        "exit_code": completed.returncode,
        "checks": [
            {
                "name": check.name,
                "passed": check.passed,
                **({"details": check.details} if check.details else {}),
            }
            for check in checks
        ],
        "stdout": stdout,
        "stderr": stderr,
    }


def make_eval_run_id(dataset_name: str) -> str:
    return f"eval-{slugify(dataset_name)}-{uuid.uuid4().hex[:8]}"


def build_report(dataset: dict[str, Any], dataset_path: Path) -> dict[str, Any]:
    started = time.perf_counter()
    case_reports = [run_case(case, dataset_path) for case in dataset["cases"]]
    duration = time.perf_counter() - started
    passed = sum(1 for case in case_reports if case["status"] == "passed")
    telemetry = dataset.get("telemetry", {}) if isinstance(dataset.get("telemetry"), dict) else {}
    task_id = str(telemetry.get("task_id") or f"eval-{slugify(dataset['name'])}").strip()
    run_id = make_eval_run_id(dataset["name"])
    report = {
        "version": 1,
        "run_id": run_id,
        "status": "passed" if passed == len(case_reports) else "failed",
        "dataset_version": dataset["version"],
        "dataset_name": dataset["name"],
        "dataset_path": str(dataset_path),
        "generated_at": utc_now(),
        "task_id": task_id,
        "trace": {
            "trace_contract_version": build_trace_contract()["version"],
            "trace_entity": "run",
            "trace_id": run_id,
            "task_id": task_id,
            "mission_id": str(telemetry.get("mission_id") or "").strip(),
            "subject_run_id": str(telemetry.get("subject_run_id") or "").strip(),
        },
        "summary": {
            "total": len(case_reports),
            "passed": passed,
            "failed": len(case_reports) - passed,
            "duration_seconds": round(duration, 6),
        },
        "cases": case_reports,
    }
    validate_payload(report, REPORT_SCHEMA_PATH, "report")
    return report


def build_default_report_paths(dataset_name: str, run_id: str) -> tuple[Path, Path]:
    dataset_dir = EVAL_ROOT / slugify(dataset_name)
    return dataset_dir / "runs" / f"{run_id}.json", dataset_dir / "LATEST.json"


def write_report_artifacts(report: dict[str, Any], write_report: Path | None = None) -> tuple[dict[str, Any], Path]:
    report_path, latest_path = build_default_report_paths(report["dataset_name"], report["run_id"])
    report_with_paths = dict(report)
    report_with_paths["report_path"] = str(report_path)
    validate_payload(report_with_paths, REPORT_SCHEMA_PATH, "report")
    write_json(report_path, report_with_paths)
    write_json(latest_path, report_with_paths)
    if write_report:
        write_json(write_report, report_with_paths)
    return report_with_paths, report_path


def emit_eval_telemetry(dataset: dict[str, Any], report: dict[str, Any]) -> tuple[Path, str, Path | None]:
    telemetry = dataset.get("telemetry", {}) if isinstance(dataset.get("telemetry"), dict) else {}
    trace_contract = build_trace_contract()
    payload = {
        "id": str(uuid.uuid4()),
        "created_at": report["generated_at"],
        "event_type": "eval",
        "agent": str(telemetry.get("actor") or "hq_eval").strip(),
        "role": str(telemetry.get("role") or "Eval Runner").strip(),
        "task_id": str(telemetry.get("task_id") or report["task_id"]).strip(),
        "mission_id": str(telemetry.get("mission_id") or report["trace"].get("mission_id") or "").strip(),
        "run_id": report["run_id"],
        "status": "reviewed",
        "summary": (
            f"Eval dataset '{report['dataset_name']}' {report['status']} "
            f"({report['summary']['passed']}/{report['summary']['total']} passed)."
        ),
        "workflow": str(telemetry.get("workflow") or "eval-foundation").strip(),
        "risk_tier": str(telemetry.get("risk_tier") or "").strip(),
        "autonomy_tier": str(telemetry.get("autonomy_tier") or "").strip(),
        "metadata": {
            "outcome": report["status"],
            "dataset_name": report["dataset_name"],
            "dataset_version": report["dataset_version"],
            "report_path": report["report_path"],
            "cases_total": report["summary"]["total"],
            "cases_passed": report["summary"]["passed"],
            "cases_failed": report["summary"]["failed"],
            "trace_contract_version": trace_contract["version"],
            "observation_type": "eval",
            "observation_level": "dataset",
            **(telemetry.get("metadata") or {}),
        },
    }
    payload = {key: value for key, value in payload.items() if value != "" or key == "metadata"}
    return write_event_payload(payload)


def validate_command(args: argparse.Namespace) -> int:
    try:
        load_dataset(args.dataset.resolve())
    except ValueError as exc:
        print(f"error={exc}")
        return 2
    print(f"dataset={args.dataset.resolve()}")
    print("status=ok")
    return 0


def run_command(args: argparse.Namespace) -> int:
    try:
        dataset_path = args.dataset.resolve()
        dataset = load_dataset(dataset_path)
        report = build_report(dataset, dataset_path)
    except ValueError as exc:
        print(f"error={exc}")
        return 2

    custom_report_path = args.write_report.resolve() if args.write_report else None
    report, report_path = write_report_artifacts(report, custom_report_path)
    print(f"report={report_path}")
    print(f"report_latest={(report_path.parent.parent / 'LATEST.json')}")
    if custom_report_path:
        print(f"report_copy={custom_report_path}")

    event_path, event_id, archived_event_path = emit_eval_telemetry(dataset, report)
    if archived_event_path:
        print(f"archived_event_file={archived_event_path}")
    print(f"event_file={event_path}")
    print(f"event_id={event_id}")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"dataset={report['dataset_name']}")
        print(f"run_id={report['run_id']}")
        print(f"status={report['status']}")
        print(f"cases_total={report['summary']['total']}")
        print(f"cases_passed={report['summary']['passed']}")
        print(f"cases_failed={report['summary']['failed']}")
        for case in report["cases"]:
            print(f"case={case['id']} status={case['status']} exit_code={case['exit_code']}")
            for check in case["checks"]:
                suffix = f" details={check['details']}" if "details" in check else ""
                print(f"check={check['name']} passed={str(check['passed']).lower()}{suffix}")
    return 0 if report["summary"]["failed"] == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run lightweight HQ eval datasets.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate an eval dataset against the schema.")
    validate_parser.add_argument("--dataset", type=Path, required=True)
    validate_parser.set_defaults(func=validate_command)

    run_parser = subparsers.add_parser("run", help="Run an eval dataset and emit a report.")
    run_parser.add_argument("--dataset", type=Path, required=True)
    run_parser.add_argument("--json", action="store_true", help="Print the full JSON report.")
    run_parser.add_argument("--write-report", type=Path, help="Optional JSON report output path.")
    run_parser.set_defaults(func=run_command)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
