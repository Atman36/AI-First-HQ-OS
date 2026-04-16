#!/usr/bin/env python3
"""Minimal dataset-driven eval runner for repeatable HQ checks."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


REPO_ROOT = Path(os.environ.get("HQ_EVAL_REPO_ROOT", Path(__file__).resolve().parents[1])).resolve()
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

    cwd = Path(case.get("cwd") or dataset_path.parent).resolve()
    env = os.environ.copy()
    env.update(case.get("env") or {})
    timeout = float(case.get("timeout_seconds") or 30.0)

    started = time.perf_counter()
    completed = subprocess.run(
        case["command"],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
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


def build_report(dataset: dict[str, Any], dataset_path: Path) -> dict[str, Any]:
    started = time.perf_counter()
    case_reports = [run_case(case, dataset_path) for case in dataset["cases"]]
    duration = time.perf_counter() - started
    passed = sum(1 for case in case_reports if case["status"] == "passed")
    report = {
        "dataset_name": dataset["name"],
        "dataset_path": str(dataset_path),
        "generated_at": utc_now(),
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

    if args.write_report:
        output_path = args.write_report.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"report={output_path}")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"dataset={report['dataset_name']}")
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
