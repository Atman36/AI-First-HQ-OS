#!/usr/bin/env python3
"""Short feedback-loop receipts for HQ execution attempts."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from hq_io import append_jsonl


REPO_ROOT = Path(
    os.environ.get(
        "HQ_FEEDBACK_LOOP_REPO_ROOT",
        os.environ.get("HQ_CONTROL_PLANE_REPO_ROOT", Path(__file__).resolve().parents[1]),
    )
).resolve()
PRIVATE_ROOT = Path(os.environ.get("HQ_RUNTIME_PRIVATE_ROOT", REPO_ROOT / ".hq")).resolve()
FEEDBACK_ROOT = PRIVATE_ROOT / "telemetry" / "feedback-loop"

STATUSES = {
    "running",
    "done",
    "checks_failed",
    "blocked_by_policy",
    "needs_approval",
    "hypothesis_failed",
    "technical_error",
    "rolled_back",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_list(values: list[str] | None) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = normalize_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        items.append(text)
    return items


def iteration_file_for_timestamp(timestamp: str) -> Path:
    return FEEDBACK_ROOT / f"{timestamp[:7]}.jsonl"


def build_iteration_payload(
    *,
    task_id: str,
    hypothesis: str,
    action: str,
    metric: str,
    status: str,
    evidence: list[str] | None,
    touched_files: list[str] | None,
    next_focus: str,
    rollback_reason: str,
    actor: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    normalized_status = normalize_text(status)
    payload = {
        "id": str(uuid.uuid4()),
        "created_at": created_at or utc_now(),
        "task_id": normalize_text(task_id),
        "actor": normalize_text(actor),
        "hypothesis": normalize_text(hypothesis),
        "action": normalize_text(action),
        "metric": normalize_text(metric),
        "status": normalized_status,
        "evidence": normalize_list(evidence),
        "touched_files": normalize_list(touched_files),
        "next_focus": normalize_text(next_focus),
        "rollback_reason": normalize_text(rollback_reason),
    }
    missing = [
        key
        for key in ("task_id", "actor", "hypothesis", "action", "metric", "status", "next_focus")
        if not payload[key]
    ]
    if missing:
        raise ValueError("missing required fields: " + ", ".join(missing))
    if normalized_status not in STATUSES:
        raise ValueError("status must be one of: " + ", ".join(sorted(STATUSES)))
    if normalized_status == "rolled_back" and not payload["rollback_reason"]:
        raise ValueError("rollback_reason is required when status is rolled_back")
    return payload


def write_iteration(payload: dict[str, Any]) -> tuple[Path, str]:
    path = iteration_file_for_timestamp(str(payload["created_at"]))
    append_jsonl(
        path,
        payload,
        max_bytes=max(1, int(os.environ.get("HQ_FEEDBACK_JSONL_MAX_BYTES", str(5 * 1024 * 1024)))),
        max_records=max(1, int(os.environ.get("HQ_FEEDBACK_JSONL_MAX_RECORDS", "5000"))),
    )
    return path, str(payload["id"])


def iter_iteration_files(private_root: Path = PRIVATE_ROOT) -> list[Path]:
    root = private_root / "telemetry" / "feedback-loop"
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.glob("*.jsonl")
        if path.is_file()
    )


def load_recent_iterations(
    private_root: Path = PRIVATE_ROOT,
    *,
    limit: int = 5,
    task_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in iter_iteration_files(private_root):
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            task_id = normalize_text(payload.get("task_id"))
            if task_ids is not None and task_id not in task_ids:
                continue
            records.append(
                {
                    "id": normalize_text(payload.get("id")),
                    "created_at": normalize_text(payload.get("created_at")),
                    "task_id": task_id,
                    "actor": normalize_text(payload.get("actor")),
                    "hypothesis": normalize_text(payload.get("hypothesis")),
                    "action": normalize_text(payload.get("action")),
                    "metric": normalize_text(payload.get("metric")),
                    "status": normalize_text(payload.get("status")),
                    "evidence": normalize_list(payload.get("evidence") if isinstance(payload.get("evidence"), list) else []),
                    "touched_files": normalize_list(
                        payload.get("touched_files") if isinstance(payload.get("touched_files"), list) else []
                    ),
                    "next_focus": normalize_text(payload.get("next_focus")),
                    "rollback_reason": normalize_text(payload.get("rollback_reason")),
                }
            )
    records.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return records[: max(0, limit)]


def load_active_task(task_id: str) -> dict[str, Any]:
    import hq_control_plane

    bundle = hq_control_plane.validate_control_plane()
    for task in bundle["active_work"].get("tasks", []) or []:
        if isinstance(task, dict) and normalize_text(task.get("id")) == task_id:
            return task
    raise ValueError(f"task not found: {task_id}")


def task_requires_explicit_approval(task: dict[str, Any]) -> bool:
    risk_tier = normalize_text(task.get("risk_tier"))
    autonomy_tier = normalize_text(task.get("autonomy_tier"))
    return risk_tier == "high" or autonomy_tier in {"A3", "A4"}


def build_payload_from_args(args: argparse.Namespace, *, status: str) -> dict[str, Any]:
    return build_iteration_payload(
        task_id=args.task_id,
        hypothesis=args.hypothesis,
        action=args.action,
        metric=args.metric,
        status=status,
        evidence=args.evidence,
        touched_files=args.touched_file,
        next_focus=args.next_focus,
        rollback_reason=getattr(args, "rollback_reason", ""),
        actor=args.actor,
    )


def before_command(args: argparse.Namespace) -> int:
    try:
        task = load_active_task(args.task_id)
        if task_requires_explicit_approval(task) and not args.confirm_approval:
            print("pre_action=blocked")
            print("reason=approval_required_for_task_risk_or_autonomy")
            print(f"task_id={args.task_id}")
            return 2
        payload = build_payload_from_args(args, status="running")
    except ValueError as exc:
        print(f"error={exc}")
        return 2
    path, iteration_id = write_iteration(payload)
    print("pre_action=ok")
    print(f"iteration_file={path}")
    print(f"iteration_id={iteration_id}")
    return 0


def after_command(args: argparse.Namespace) -> int:
    try:
        load_active_task(args.task_id)
        payload = build_payload_from_args(args, status=args.status)
    except ValueError as exc:
        print(f"error={exc}")
        return 2
    path, iteration_id = write_iteration(payload)
    print("post_action=recorded")
    print(f"iteration_file={path}")
    print(f"iteration_id={iteration_id}")
    return 0


def tail_command(args: argparse.Namespace) -> int:
    task_ids = {args.task_id} if args.task_id else None
    records = load_recent_iterations(PRIVATE_ROOT, limit=args.limit, task_ids=task_ids)
    print(json.dumps({"recent_iterations": records}, ensure_ascii=False, indent=2))
    return 0


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task-id", required=True, help="Control-plane task ID.")
    parser.add_argument("--hypothesis", required=True, help="Short hypothesis for this attempt.")
    parser.add_argument("--action", required=True, help="Action taken or about to be taken.")
    parser.add_argument("--metric", required=True, help="Signal or check used to judge the attempt.")
    parser.add_argument("--evidence", action="append", default=[], help="Evidence line, repeatable.")
    parser.add_argument("--touched-file", action="append", default=[], help="Touched path, repeatable.")
    parser.add_argument("--next-focus", required=True, help="Next best focus after this attempt.")
    parser.add_argument("--actor", default="assistant", help="Actor or role writing the receipt.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record short HQ feedback-loop receipts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    before_parser = subparsers.add_parser("before", help="Validate task context and record attempt start.")
    add_common_args(before_parser)
    before_parser.add_argument(
        "--confirm-approval",
        action="store_true",
        help="Confirm required human approval is already present for high-risk/A3+ task work.",
    )
    before_parser.set_defaults(func=before_command)

    after_parser = subparsers.add_parser("after", help="Record attempt outcome.")
    add_common_args(after_parser)
    after_parser.add_argument("--status", required=True, choices=sorted(STATUSES - {"running"}))
    after_parser.add_argument("--rollback-reason", default="", help="Required for rolled_back status.")
    after_parser.set_defaults(func=after_command)

    tail_parser = subparsers.add_parser("tail", help="Print recent feedback-loop receipts as JSON.")
    tail_parser.add_argument("--limit", type=int, default=5)
    tail_parser.add_argument("--task-id", default="")
    tail_parser.set_defaults(func=tail_command)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
