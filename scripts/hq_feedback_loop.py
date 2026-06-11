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


# Adverse = any closed outcome that is not a clean success; these warrant an
# immediate review. Cadence reviews fire after a batch of clean successes.
ADVERSE_STATUSES = STATUSES - {"running", "done"}
DEFAULT_REVIEW_CADENCE = 5
REVIEW_MARKER_PATH = PRIVATE_ROOT / "state" / "feedback-review-marker.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_text(value: Any) -> str:
    return str(value or "").strip()


DIRECTIONS = {"higher", "lower"}


def normalize_direction(value: Any) -> str:
    text = normalize_text(value).lower()
    return text if text in DIRECTIONS else ""


def coerce_metric_value(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = normalize_text(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


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
    metric_value: Any = None,
    metric_direction: str = "",
    parent_id: str = "",
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
        "metric_value": coerce_metric_value(metric_value),
        "metric_direction": normalize_direction(metric_direction),
        "status": normalized_status,
        "evidence": normalize_list(evidence),
        "touched_files": normalize_list(touched_files),
        "next_focus": normalize_text(next_focus),
        "rollback_reason": normalize_text(rollback_reason),
        "parent_id": normalize_text(parent_id),
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
    raw_direction = normalize_text(metric_direction)
    if raw_direction and not payload["metric_direction"]:
        raise ValueError("metric_direction must be one of: " + ", ".join(sorted(DIRECTIONS)))
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


def normalize_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": normalize_text(payload.get("id")),
        "created_at": normalize_text(payload.get("created_at")),
        "task_id": normalize_text(payload.get("task_id")),
        "actor": normalize_text(payload.get("actor")),
        "hypothesis": normalize_text(payload.get("hypothesis")),
        "action": normalize_text(payload.get("action")),
        "metric": normalize_text(payload.get("metric")),
        "metric_value": coerce_metric_value(payload.get("metric_value")),
        "metric_direction": normalize_direction(payload.get("metric_direction")),
        "status": normalize_text(payload.get("status")),
        "evidence": normalize_list(payload.get("evidence") if isinstance(payload.get("evidence"), list) else []),
        "touched_files": normalize_list(
            payload.get("touched_files") if isinstance(payload.get("touched_files"), list) else []
        ),
        "next_focus": normalize_text(payload.get("next_focus")),
        "rollback_reason": normalize_text(payload.get("rollback_reason")),
        "parent_id": normalize_text(payload.get("parent_id")),
    }


def load_iterations(
    private_root: Path = PRIVATE_ROOT,
    *,
    task_ids: set[str] | None = None,
    collapse_running: bool = True,
) -> list[dict[str, Any]]:
    """Load all normalized receipts, dropping running attempts that already closed.

    A ``before`` receipt writes a ``running`` row; the matching ``after`` receipt
    references it via ``parent_id``. Once closed, the running row is superseded and
    must not pollute recent views or status counts. Truly open attempts (no closing
    receipt yet) are kept so in-flight work stays visible.
    """
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
            record = normalize_record(payload)
            if task_ids is not None and record["task_id"] not in task_ids:
                continue
            records.append(record)
    if collapse_running:
        closed_parent_ids = {r["parent_id"] for r in records if r["parent_id"]}
        records = [
            r for r in records if not (r["status"] == "running" and r["id"] in closed_parent_ids)
        ]
    return records


def load_recent_iterations(
    private_root: Path = PRIVATE_ROOT,
    *,
    limit: int = 5,
    task_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    records = load_iterations(private_root, task_ids=task_ids)
    records.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return records[: max(0, limit)]


SUCCESS_STATUS = "done"


def summarize_iterations(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate receipts into a loop view: counts, baseline, best, latest delta."""
    chrono = sorted(records, key=lambda r: r.get("created_at") or "")
    status_counts: dict[str, int] = {}
    for record in chrono:
        status = record["status"] or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1

    numeric = [r for r in chrono if r["metric_value"] is not None]
    direction = next((r["metric_direction"] for r in numeric if r["metric_direction"]), "higher")

    baseline = numeric[0] if numeric else None
    latest = numeric[-1] if numeric else None
    successes = [r for r in numeric if r["status"] == SUCCESS_STATUS]
    if successes:
        best = max(successes, key=lambda r: r["metric_value"]) if direction == "higher" else min(
            successes, key=lambda r: r["metric_value"]
        )
    else:
        best = None

    def delta_pct(value: float | None) -> float | None:
        if value is None or baseline is None or not baseline["metric_value"]:
            return None
        base = baseline["metric_value"]
        return round((value - base) / base * 100, 1)

    def point(record: dict[str, Any] | None) -> dict[str, Any] | None:
        if record is None:
            return None
        return {
            "metric": record["metric"],
            "metric_value": record["metric_value"],
            "created_at": record["created_at"],
            "task_id": record["task_id"],
        }

    return {
        "total": len(records),
        "status_counts": status_counts,
        "metric_direction": direction,
        "baseline": point(baseline),
        "best": point(best),
        "latest": point(latest),
        "latest_delta_pct": delta_pct(latest["metric_value"]) if latest else None,
        "open_attempts": sum(1 for r in records if r["status"] == "running"),
    }


def build_open_next_steps(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Latest non-empty next_focus per task — a backlog that survives compaction."""
    latest_by_task: dict[str, dict[str, Any]] = {}
    for record in sorted(records, key=lambda r: r.get("created_at") or ""):
        if not record["next_focus"]:
            continue
        latest_by_task[record["task_id"]] = record
    steps = [
        {
            "task_id": record["task_id"],
            "next_focus": record["next_focus"],
            "status": record["status"],
            "created_at": record["created_at"],
        }
        for record in latest_by_task.values()
    ]
    steps.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return steps


def build_feedback_summary(
    private_root: Path = PRIVATE_ROOT,
    *,
    task_ids: set[str] | None = None,
) -> dict[str, Any]:
    records = load_iterations(private_root, task_ids=task_ids)
    by_task: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_task.setdefault(record["task_id"], []).append(record)
    return {
        "overall": summarize_iterations(records),
        "tasks": {task_id: summarize_iterations(items) for task_id, items in by_task.items()},
        "open_next_steps": build_open_next_steps(records),
    }


def review_cadence_batch_size() -> int:
    try:
        value = int(os.environ.get("HQ_FEEDBACK_REVIEW_CADENCE", str(DEFAULT_REVIEW_CADENCE)))
    except ValueError:
        return DEFAULT_REVIEW_CADENCE
    return max(1, value)


def marker_task_key(task_id: str) -> str:
    text = normalize_text(task_id)
    safe = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in text)
    return safe.strip("-_") or "task"


def review_marker_path(private_root: Path = PRIVATE_ROOT, *, task_id: str = "") -> Path:
    if task_id:
        return private_root / "state" / f"feedback-review-marker.{marker_task_key(task_id)}.json"
    return private_root / "state" / "feedback-review-marker.json"


def marker_task_id(task_ids: set[str] | None) -> str:
    if task_ids is None:
        return ""
    normalized = sorted(normalize_text(item) for item in task_ids if normalize_text(item))
    return normalized[0] if len(normalized) == 1 else ""


def load_review_marker(
    private_root: Path = PRIVATE_ROOT,
    *,
    task_ids: set[str] | None = None,
) -> dict[str, Any]:
    task_id = marker_task_id(task_ids)
    path = review_marker_path(private_root, task_id=task_id)
    if not path.exists():
        return {"last_reviewed_created_at": "", "last_reviewed_id": "", "task_id": task_id}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"last_reviewed_created_at": "", "last_reviewed_id": "", "task_id": task_id}
    if not isinstance(payload, dict):
        return {"last_reviewed_created_at": "", "last_reviewed_id": "", "task_id": task_id}
    return {
        "last_reviewed_created_at": normalize_text(payload.get("last_reviewed_created_at")),
        "last_reviewed_id": normalize_text(payload.get("last_reviewed_id")),
        "task_id": normalize_text(payload.get("task_id")) or task_id,
    }


def records_since_marker(
    records: list[dict[str, Any]], marker: dict[str, Any]
) -> list[dict[str, Any]]:
    chrono = sorted(records, key=lambda r: (r.get("created_at") or "", r.get("id") or ""))
    last_id = normalize_text(marker.get("last_reviewed_id"))
    if last_id:
        for index, record in enumerate(chrono):
            if record["id"] == last_id:
                return chrono[index + 1 :]
    last_at = normalize_text(marker.get("last_reviewed_created_at"))
    if last_at:
        return [record for record in chrono if (record.get("created_at") or "") > last_at]
    return chrono


def evaluate_review_signal(
    records: list[dict[str, Any]],
    *,
    batch_size: int,
    marker: dict[str, Any],
) -> dict[str, Any]:
    """Decide whether a review is due from receipts not yet acknowledged.

    Immediate when any adverse outcome appears; cadence when a batch of clean
    successes accrues. Mirrors the trigger/cadence policy from the claw project.
    """
    pending = [r for r in records_since_marker(records, marker) if r["status"] != "running"]
    adverse = [r for r in pending if r["status"] in ADVERSE_STATUSES]
    successes = [r for r in pending if r["status"] == SUCCESS_STATUS]
    immediate_due = bool(adverse)
    cadence_due = len(successes) >= batch_size
    if immediate_due:
        reason = "adverse_outcomes:" + ",".join(sorted({r["status"] for r in adverse}))
    elif cadence_due:
        reason = f"cadence:{len(successes)}_successful_since_review"
    else:
        reason = ""
    return {
        "review_due": immediate_due or cadence_due,
        "reason": reason,
        "adverse_since_review": len(adverse),
        "successful_since_review": len(successes),
        "batch_size": batch_size,
        "last_reviewed_created_at": normalize_text(marker.get("last_reviewed_created_at")),
    }


def build_review_signal(
    private_root: Path = PRIVATE_ROOT,
    *,
    task_ids: set[str] | None = None,
) -> dict[str, Any]:
    records = load_iterations(private_root, task_ids=task_ids)
    return evaluate_review_signal(
        records,
        batch_size=review_cadence_batch_size(),
        marker=load_review_marker(private_root, task_ids=task_ids),
    )


def mark_reviewed(
    private_root: Path = PRIVATE_ROOT,
    *,
    task_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Advance the review marker to the latest receipt (resets the cadence)."""
    records = load_iterations(private_root, task_ids=task_ids)
    chrono = sorted(records, key=lambda r: (r.get("created_at") or "", r.get("id") or ""))
    latest = chrono[-1] if chrono else None
    task_id = marker_task_id(task_ids)
    marker = {
        "last_reviewed_created_at": latest["created_at"] if latest else "",
        "last_reviewed_id": latest["id"] if latest else "",
        "task_id": task_id,
        "reviewed_at": utc_now(),
        "reviewed_through_count": len(chrono),
    }
    path = review_marker_path(private_root, task_id=task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return marker


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
        metric_value=getattr(args, "metric_value", None),
        metric_direction=getattr(args, "metric_direction", ""),
        parent_id=getattr(args, "iteration_id", ""),
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


def summary_command(args: argparse.Namespace) -> int:
    task_ids = {args.task_id} if args.task_id else None
    summary = build_feedback_summary(PRIVATE_ROOT, task_ids=task_ids)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def review_status_command(args: argparse.Namespace) -> int:
    task_ids = {args.task_id} if args.task_id else None
    signal = build_review_signal(PRIVATE_ROOT, task_ids=task_ids)
    print(json.dumps(signal, ensure_ascii=False, indent=2))
    return 0


def mark_reviewed_command(args: argparse.Namespace) -> int:
    task_ids = {args.task_id} if args.task_id else None
    marker = mark_reviewed(PRIVATE_ROOT, task_ids=task_ids)
    print(json.dumps(marker, ensure_ascii=False, indent=2))
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
    parser.add_argument(
        "--metric-value",
        type=float,
        default=None,
        help="Numeric metric reading for this attempt (enables baseline/best/delta).",
    )
    parser.add_argument(
        "--metric-direction",
        choices=sorted(DIRECTIONS),
        default="",
        help="Which direction of metric_value is better.",
    )


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
    after_parser.add_argument(
        "--iteration-id",
        default="",
        help="ID returned by the matching `before` receipt; closes that running attempt.",
    )
    after_parser.set_defaults(func=after_command)

    tail_parser = subparsers.add_parser("tail", help="Print recent feedback-loop receipts as JSON.")
    tail_parser.add_argument("--limit", type=int, default=5)
    tail_parser.add_argument("--task-id", default="")
    tail_parser.set_defaults(func=tail_command)

    summary_parser = subparsers.add_parser(
        "summary", help="Print aggregated loop summary (counts, baseline, best, next steps)."
    )
    summary_parser.add_argument("--task-id", default="")
    summary_parser.set_defaults(func=summary_command)

    review_status_parser = subparsers.add_parser(
        "review-status", help="Print whether a review is due (immediate or cadence)."
    )
    review_status_parser.add_argument("--task-id", default="")
    review_status_parser.set_defaults(func=review_status_command)

    mark_reviewed_parser = subparsers.add_parser(
        "mark-reviewed", help="Advance the review marker to the latest receipt (resets cadence)."
    )
    mark_reviewed_parser.add_argument("--task-id", default="")
    mark_reviewed_parser.set_defaults(func=mark_reviewed_command)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
