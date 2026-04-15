#!/usr/bin/env python3
"""Structured telemetry logger for HQ AI-first operations."""

from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(
    os.environ.get("HQ_TELEMETRY_REPO_ROOT", Path(__file__).resolve().parents[1])
).resolve()
PRIVATE_ROOT = Path(os.environ.get("HQ_RUNTIME_PRIVATE_ROOT", REPO_ROOT / ".hq")).resolve()
TELEMETRY_ROOT = PRIVATE_ROOT / "telemetry"

ALLOWED_EVENT_TYPES = {
    "intake",
    "route",
    "policy_check",
    "start",
    "progress",
    "approval",
    "acceptance",
    "sync",
    "escalation",
    "rollback",
    "review",
}
ALLOWED_STATUSES = {
    "queued",
    "ready",
    "approved",
    "running",
    "blocked",
    "accepted",
    "synced",
    "done",
    "rolled_back",
}


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


def event_file_for_timestamp(timestamp: str) -> Path:
    day = timestamp[:10]
    month = day[:7]
    return TELEMETRY_ROOT / month / f"{day}.jsonl"


def ensure_runtime() -> None:
    TELEMETRY_ROOT.mkdir(parents=True, exist_ok=True)


def build_event_payload(args: argparse.Namespace) -> dict[str, Any]:
    event_type = str(args.event_type or "").strip()
    status = str(args.status or "").strip()
    actor = str(args.actor or "").strip()
    task_id = str(args.task_id or "").strip()
    summary = str(args.summary or "").strip()
    if event_type not in ALLOWED_EVENT_TYPES:
        raise ValueError("event_type must be one of: " + ", ".join(sorted(ALLOWED_EVENT_TYPES)))
    if status not in ALLOWED_STATUSES:
        raise ValueError("status must be one of: " + ", ".join(sorted(ALLOWED_STATUSES)))
    if not actor:
        raise ValueError("actor is required")
    if not task_id:
        raise ValueError("task_id is required")
    if not summary:
        raise ValueError("summary is required")

    created_at = utc_now()
    payload: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "created_at": created_at,
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
    return payload


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def event_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    try:
        payload = build_event_payload(args)
    except ValueError as exc:
        print(f"error={exc}")
        return 2
    path = event_file_for_timestamp(payload["created_at"])
    append_jsonl(path, payload)
    print(f"event_file={path}")
    print(f"event_id={payload['id']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write structured telemetry events for HQ.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    event = subparsers.add_parser("event", help="Write one event into .hq/telemetry.")
    event.add_argument("--event-type", required=True, choices=sorted(ALLOWED_EVENT_TYPES))
    event.add_argument("--actor", required=True, help="Actor or agent that produced the event.")
    event.add_argument("--role", help="Optional role label.")
    event.add_argument("--task-id", required=True, help="Task identifier from active-work.json.")
    event.add_argument("--status", required=True, choices=sorted(ALLOWED_STATUSES))
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
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
