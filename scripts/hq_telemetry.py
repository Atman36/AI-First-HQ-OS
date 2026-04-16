#!/usr/bin/env python3
"""Structured telemetry logger and weekly metric review for HQ AI-first operations."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from hq_telemetry_review import build_review_payload
from hq_telemetry_review import build_task_cycle_report
from hq_telemetry_review import build_telemetry_contract
from hq_telemetry_review import render_review_markdown
from hq_telemetry_store import append_event
from hq_telemetry_store import ensure_runtime
from hq_telemetry_store import event_file_for_timestamp
from hq_telemetry_store import load_json
from hq_telemetry_store import write_review_artifacts


REPO_ROOT = Path(
    os.environ.get("HQ_TELEMETRY_REPO_ROOT", Path(__file__).resolve().parents[1])
).resolve()
PRIVATE_ROOT = Path(os.environ.get("HQ_RUNTIME_PRIVATE_ROOT", REPO_ROOT / ".hq")).resolve()
CONTROL_PLANE_DIR = REPO_ROOT / "05 AI Control Plane"
TELEMETRY_SCHEMA_PATH = CONTROL_PLANE_DIR / "schemas" / "telemetry-event.schema.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_json_object(value: str) -> dict[str, Any]:
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise argparse.ArgumentTypeError("metadata must be a JSON object")
    return payload


def normalize_list(values: list[str] | None) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        items.append(text)
    return items


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid date: {value}") from exc


def validate_event_payload(payload: dict[str, Any]) -> None:
    schema = load_json(TELEMETRY_SCHEMA_PATH)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path))
    if errors:
        error = errors[0]
        path = ".".join(str(item) for item in error.absolute_path)
        raise ValueError(f"event payload failed schema validation at {path or '<root>'}: {error.message}")


def build_event_payload(args: argparse.Namespace) -> dict[str, Any]:
    contract = build_telemetry_contract()
    event_type = str(args.event_type or "").strip()
    status = str(args.status or "").strip()
    actor = str(args.actor or "").strip()
    task_id = str(args.task_id or "").strip()
    summary = str(args.summary or "").strip()
    if event_type not in contract["event_types"]:
        raise ValueError("event_type must be one of: " + ", ".join(sorted(contract["event_types"])))
    if status not in contract["statuses"]:
        raise ValueError("status must be one of: " + ", ".join(sorted(contract["statuses"])))
    if not actor:
        raise ValueError("actor is required")
    if not task_id:
        raise ValueError("task_id is required")
    if not summary:
        raise ValueError("summary is required")

    payload: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "created_at": utc_now(),
        "event_type": event_type,
        "agent": actor,
        "role": str(args.role or "").strip(),
        "task_id": task_id,
        "status": status,
        "summary": summary,
        "workflow": str(args.workflow or "").strip(),
        "risk_tier": str(args.risk_tier or "").strip(),
        "autonomy_tier": str(args.autonomy_tier or "").strip(),
        "touched_files": normalize_list(args.touched_file),
        "metadata": args.metadata or {},
    }
    validate_event_payload(payload)
    return payload


def event_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    try:
        payload = build_event_payload(args)
    except ValueError as exc:
        print(f"error={exc}")
        return 2
    path = event_file_for_timestamp(payload["created_at"])
    archive_path = append_event(path, payload)
    if archive_path:
        print(f"archived_event_file={archive_path}")
    print(f"event_file={path}")
    print(f"event_id={payload['id']}")
    return 0


def weekly_metrics_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    if args.days < 1:
        print("error=days must be at least 1")
        return 2
    until = args.until or date.today()
    since = args.since or (until - timedelta(days=args.days - 1))
    if since > until:
        print("error=since must be earlier than or equal to until")
        return 2
    review = build_review_payload(since, until)
    review_markdown = render_review_markdown(review)
    json_path, md_path = write_review_artifacts(review, review_markdown)
    print(f"review_json={json_path}")
    print(f"review_md={md_path}")
    print(f"breached_metrics={len(review['breached_metrics'])}")
    return 0


def task_cycle_command(args: argparse.Namespace) -> int:
    if args.since and args.until and args.since > args.until:
        print("error=since must be earlier than or equal to until")
        return 2
    try:
        report = build_task_cycle_report(args.task_id, since=args.since, until=args.until)
    except ValueError as exc:
        print(f"error={exc}")
        return 2
    print(f"task_id={report['task_id']}")
    print(f"workflow={report['workflow']}")
    print(f"column={report['column']}")
    print(f"queue_state_ok={str(report['queue_state_ok']).lower()}")
    print(f"required_events={','.join(report['required_events'])}")
    print(f"seen_event_types={','.join(report['seen_event_types'])}")
    print(
        "missing_required_events="
        + (",".join(report["missing_required_events"]) if report["missing_required_events"] else "none")
    )
    print(f"events_seen={report['events_seen']}")
    print(
        "actor_failures="
        + ("; ".join(report["actor_failures"]) if report["actor_failures"] else "none")
    )
    print(f"status={report['status']}")
    return 0 if report["status"] == "ok" else 1


def build_parser() -> argparse.ArgumentParser:
    contract = build_telemetry_contract()
    parser = argparse.ArgumentParser(description="Write structured telemetry events for HQ.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    event = subparsers.add_parser("event", help="Write one event into .hq/telemetry.")
    event.add_argument("--event-type", required=True, choices=sorted(contract["event_types"]))
    event.add_argument("--actor", required=True, help="Actor or agent that produced the event.")
    event.add_argument("--role", help="Optional role label.")
    event.add_argument("--task-id", required=True, help="Task identifier from active-work.json.")
    event.add_argument("--status", required=True, choices=sorted(contract["statuses"]))
    event.add_argument("--summary", required=True, help="Short event summary.")
    event.add_argument("--workflow", help="Workflow identifier.")
    event.add_argument("--risk-tier", help="Optional risk tier.")
    event.add_argument("--autonomy-tier", help="Optional autonomy tier.")
    event.add_argument(
        "--touched-file",
        action="append",
        default=[],
        help="Repeat for each file touched or affected by the event.",
    )
    event.add_argument(
        "--metadata",
        type=parse_json_object,
        help="Optional inline JSON object with extra event metadata.",
    )
    event.set_defaults(func=event_command)

    weekly_metrics = subparsers.add_parser(
        "weekly-metrics",
        help="Generate the weekly telemetry-backed metrics review.",
    )
    weekly_metrics.add_argument(
        "--since",
        type=parse_date,
        help="Inclusive start date in ISO format, e.g. 2026-04-07.",
    )
    weekly_metrics.add_argument(
        "--until",
        type=parse_date,
        help="Inclusive end date in ISO format. Defaults to today.",
    )
    weekly_metrics.add_argument(
        "--days",
        type=int,
        default=7,
        help="If --since is omitted, review this many trailing days. Defaults to 7.",
    )
    weekly_metrics.set_defaults(func=weekly_metrics_command)

    task_cycle = subparsers.add_parser(
        "task-cycle",
        help="Verify one live task completed the full governed telemetry cycle locally.",
    )
    task_cycle.add_argument("--task-id", required=True, help="Task identifier from active-work.json.")
    task_cycle.add_argument(
        "--since",
        type=parse_date,
        help="Optional inclusive start date in ISO format.",
    )
    task_cycle.add_argument(
        "--until",
        type=parse_date,
        help="Optional inclusive end date in ISO format.",
    )
    task_cycle.set_defaults(func=task_cycle_command)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
