#!/usr/bin/env python3
"""Structured telemetry logger and weekly metric review for HQ AI-first operations."""

from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(
    os.environ.get("HQ_TELEMETRY_REPO_ROOT", Path(__file__).resolve().parents[1])
).resolve()
PRIVATE_ROOT = Path(os.environ.get("HQ_RUNTIME_PRIVATE_ROOT", REPO_ROOT / ".hq")).resolve()
TELEMETRY_ROOT = PRIVATE_ROOT / "telemetry"
CONTROL_PLANE_DIR = REPO_ROOT / "05 AI Control Plane"
ACTIVE_WORK_PATH = CONTROL_PLANE_DIR / "active-work.json"
AGENT_REGISTRY_PATH = CONTROL_PLANE_DIR / "agent-registry.json"
METRICS_REGISTRY_PATH = CONTROL_PLANE_DIR / "metrics-registry.json"
WORKFLOW_REGISTRY_PATH = CONTROL_PLANE_DIR / "workflow-registry.json"

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
    "eval",
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
    "reviewed",
}
VALID_COMPARISONS = {"<", "<=", "=", ">=", ">"}


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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid date: {value}") from exc


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def round_metric(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 4)


def median_hours(samples: list[float]) -> float | None:
    if not samples:
        return None
    ordered = sorted(samples)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return round_metric(ordered[middle])
    return round_metric((ordered[middle - 1] + ordered[middle]) / 2)


def ratio_result(metric_id: str, numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "id": metric_id,
        "value": round_metric(numerator / denominator) if denominator else None,
        "numerator": numerator,
        "denominator": denominator,
    }


def hours_result(metric_id: str, samples: list[float]) -> dict[str, Any]:
    return {
        "id": metric_id,
        "value": median_hours(samples),
        "sample_size": len(samples),
    }


def scalar_result(metric_id: str, value: float | int | None) -> dict[str, Any]:
    return {"id": metric_id, "value": round_metric(float(value)) if value is not None else None}


def load_events(since: date, until: date) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not TELEMETRY_ROOT.exists():
        return events
    for path in sorted(TELEMETRY_ROOT.glob("**/*.jsonl")):
        if "reviews" in path.parts:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            created_at = str(payload.get("created_at") or "").strip()
            if not created_at:
                continue
            created_date = parse_timestamp(created_at).date()
            if since <= created_date <= until:
                events.append(payload)
    events.sort(key=lambda item: str(item.get("created_at") or ""))
    return events


def load_task_events(
    task_id: str,
    since: date | None = None,
    until: date | None = None,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not TELEMETRY_ROOT.exists():
        return events
    for path in sorted(TELEMETRY_ROOT.glob("**/*.jsonl")):
        if "reviews" in path.parts:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if str(payload.get("task_id") or "").strip() != task_id:
                continue
            created_at = str(payload.get("created_at") or "").strip()
            if not created_at:
                continue
            created_date = parse_timestamp(created_at).date()
            if since and created_date < since:
                continue
            if until and created_date > until:
                continue
            events.append(payload)
    events.sort(key=lambda item: str(item.get("created_at") or ""))
    return events


def build_role_types() -> dict[str, str]:
    registry = load_json(AGENT_REGISTRY_PATH)
    return {
        str(role.get("id") or "").strip(): str(role.get("role_type") or "").strip()
        for role in registry.get("roles", [])
        if isinstance(role, dict)
    }


def build_active_tasks() -> dict[str, dict[str, Any]]:
    active_work = load_json(ACTIVE_WORK_PATH)
    tasks = active_work.get("tasks", []) or []
    return {
        str(task.get("id") or "").strip(): task
        for task in tasks
        if isinstance(task, dict) and str(task.get("id") or "").strip()
    }


def is_current_active_task(task: dict[str, Any]) -> bool:
    return str(task.get("column") or "").strip() != "done"


def build_metric_registry() -> list[dict[str, Any]]:
    metrics = load_json(METRICS_REGISTRY_PATH)
    items: list[dict[str, Any]] = []
    for collection_name in ("primary_metrics", "secondary_metrics"):
        for item in metrics.get(collection_name, []) or []:
            if isinstance(item, dict):
                items.append(item)
    return items


def build_workflow_registry() -> dict[str, dict[str, Any]]:
    registry = load_json(WORKFLOW_REGISTRY_PATH)
    workflows: dict[str, dict[str, Any]] = {}
    for item in registry.get("workflows", []) or []:
        if not isinstance(item, dict):
            continue
        workflow_id = str(item.get("id") or "").strip()
        if workflow_id:
            workflows[workflow_id] = item
    return workflows


def bool_from_metadata(metadata: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        if metadata.get(key):
            return True
    return False


def numeric_from_metadata(metadata: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return None


def task_risk(task_id: str, grouped_events: dict[str, list[dict[str, Any]]], active_tasks: dict[str, dict[str, Any]]) -> str:
    task = active_tasks.get(task_id) or {}
    risk = str(task.get("risk_tier") or "").strip()
    if risk:
        return risk
    for event in grouped_events.get(task_id, []):
        risk = str(event.get("risk_tier") or "").strip()
        if risk:
            return risk
    return ""


def is_completed_event(event: dict[str, Any]) -> bool:
    event_type = str(event.get("event_type") or "").strip()
    status = str(event.get("status") or "").strip()
    return event_type in {"acceptance", "sync"} or status in {"accepted", "synced", "done"}


def is_ready_event(event: dict[str, Any]) -> bool:
    event_type = str(event.get("event_type") or "").strip()
    status = str(event.get("status") or "").strip()
    return event_type in {"policy_check", "approval", "start"} or status in {"ready", "approved", "running"}


def is_eval_signal(event: dict[str, Any]) -> bool:
    metadata = event.get("metadata", {}) if isinstance(event.get("metadata"), dict) else {}
    return str(event.get("event_type") or "").strip() in {"review", "eval"} or bool_from_metadata(
        metadata,
        "acceptance_check",
        "eval_id",
        "review_id",
        "review_type",
    )


def is_repeated_internal_task(task: dict[str, Any]) -> bool:
    return (
        bool(task.get("task_cycle_required"))
        and str(task.get("column") or "").strip() == "done"
        and str(task.get("workflow") or "").strip() == "intake-to-execution"
        and str(task.get("owner") or "").strip() == "ai_operations_lead"
        and str(task.get("autonomy_tier") or "").strip() == "A2"
        and str(task.get("risk_tier") or "").strip() in {"low", "medium"}
    )


def repeated_internal_task_ids(active_tasks: dict[str, dict[str, Any]]) -> set[str]:
    return {
        task_id
        for task_id, task in active_tasks.items()
        if is_repeated_internal_task(task)
    }


def evaluate_threshold(value: float | None, threshold: dict[str, Any] | None) -> str:
    if not threshold:
        return "no_threshold"
    if value is None:
        return "insufficient_data"
    comparison = str(threshold.get("comparison") or "").strip()
    expected = threshold.get("value")
    if comparison not in VALID_COMPARISONS or not isinstance(expected, (int, float)):
        return "invalid_threshold"
    if comparison == "<":
        passed = value < expected
    elif comparison == "<=":
        passed = value <= expected
    elif comparison == "=":
        passed = value == expected
    elif comparison == ">=":
        passed = value >= expected
    else:
        passed = value > expected
    return "ok" if passed else "breached"


def format_metric_value(value: float | None, unit: str) -> str:
    if value is None:
        return "n/a"
    if unit == "ratio":
        return f"{value * 100:.1f}%"
    if unit == "hours":
        return f"{value:.2f}h"
    return f"{value:.2f}"


def build_review_payload(since: date, until: date) -> dict[str, Any]:
    active_tasks = build_active_tasks()
    current_active_tasks = {
        task_id: task for task_id, task in active_tasks.items() if is_current_active_task(task)
    }
    role_types = build_role_types()
    metric_registry = build_metric_registry()
    events = load_events(since, until)
    grouped_events: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        task_id = str(event.get("task_id") or "").strip()
        if not task_id:
            continue
        grouped_events.setdefault(task_id, []).append(event)

    completed_task_ids = {
        task_id
        for task_id, task_events in grouped_events.items()
        if any(is_completed_event(event) for event in task_events)
    }
    eligible_autonomous_tasks = {
        task_id
        for task_id in completed_task_ids
        if task_risk(task_id, grouped_events, active_tasks) in {"low", "medium"}
    }
    autonomous_without_rework = {
        task_id
        for task_id in eligible_autonomous_tasks
        if not any(
            str(event.get("event_type") or "").strip() == "rollback"
            or bool_from_metadata(
                event.get("metadata", {}) if isinstance(event.get("metadata"), dict) else {},
                "human_rework",
                "reopened",
            )
            for event in grouped_events.get(task_id, [])
        )
    }
    escalated_tasks = {
        task_id
        for task_id, task_events in grouped_events.items()
        if any(
            str(event.get("event_type") or "").strip() == "escalation"
            or bool_from_metadata(
                event.get("metadata", {}) if isinstance(event.get("metadata"), dict) else {},
                "human_escalation",
                "required_human_review",
            )
            for event in task_events
        )
    }
    rollback_tasks = {
        task_id
        for task_id, task_events in grouped_events.items()
        if any(
            str(event.get("event_type") or "").strip() == "rollback"
            or bool_from_metadata(
                event.get("metadata", {}) if isinstance(event.get("metadata"), dict) else {},
                "human_rework",
                "reopened",
            )
            for event in task_events
        )
    }

    decision_latency_samples: list[float] = []
    documentation_lag_samples: list[float] = []
    founder_hours = 0.0
    founder_hours_seen: set[str] = set()
    eval_covered_tasks: set[str] = set()
    repeated_internal_ids = repeated_internal_task_ids(active_tasks)
    repeated_internal_completed_in_window = repeated_internal_ids & completed_task_ids
    repeated_internal_task_cycle_reports: list[dict[str, Any]] = []
    repeated_internal_task_cycle_ok: set[str] = set()

    for task_id, task_events in grouped_events.items():
        intake_time: datetime | None = None
        ready_time: datetime | None = None
        acceptance_time: datetime | None = None
        sync_time: datetime | None = None
        for event in task_events:
            timestamp = parse_timestamp(str(event.get("created_at") or ""))
            if str(event.get("event_type") or "").strip() == "intake" and intake_time is None:
                intake_time = timestamp
            if is_ready_event(event) and ready_time is None:
                ready_time = timestamp
            if str(event.get("event_type") or "").strip() == "acceptance" or str(event.get("status") or "").strip() == "accepted":
                if acceptance_time is None:
                    acceptance_time = timestamp
            if str(event.get("event_type") or "").strip() == "sync" or str(event.get("status") or "").strip() == "synced":
                if sync_time is None:
                    sync_time = timestamp
            if is_eval_signal(event):
                eval_covered_tasks.add(task_id)
            metadata = event.get("metadata", {}) if isinstance(event.get("metadata"), dict) else {}
            if task_id not in founder_hours_seen:
                founder_value = numeric_from_metadata(
                    metadata,
                    "founder_hours_recovered",
                    "founder_hours_saved",
                    "estimated_founder_hours_saved",
                )
                if founder_value is not None:
                    founder_hours += founder_value
                    founder_hours_seen.add(task_id)
        if intake_time and ready_time and ready_time >= intake_time:
            decision_latency_samples.append((ready_time - intake_time).total_seconds() / 3600)
        if acceptance_time and sync_time and sync_time >= acceptance_time:
            documentation_lag_samples.append((sync_time - acceptance_time).total_seconds() / 3600)

    for task_id in sorted(repeated_internal_completed_in_window):
        report = build_task_cycle_report(task_id, since=since, until=until)
        repeated_internal_task_cycle_reports.append(report)
        if report["status"] == "ok":
            repeated_internal_task_cycle_ok.add(task_id)
            eval_covered_tasks.add(task_id)

    ai_owned_active_tasks = sum(
        1
        for task in current_active_tasks.values()
        if role_types.get(str(task.get("owner") or "").strip()) == "ai"
    )
    active_tasks_with_telemetry = sum(1 for task_id in current_active_tasks if task_id in grouped_events)

    computed: dict[str, dict[str, Any]] = {
        "autonomous_completion_rate": ratio_result(
            "autonomous_completion_rate",
            len(autonomous_without_rework),
            len(eligible_autonomous_tasks),
        ),
        "human_escalation_rate": ratio_result(
            "human_escalation_rate",
            len(escalated_tasks),
            len(grouped_events),
        ),
        "decision_latency_hours": hours_result("decision_latency_hours", decision_latency_samples),
        "documentation_lag_hours": hours_result("documentation_lag_hours", documentation_lag_samples),
        "rework_or_rollback_rate": ratio_result(
            "rework_or_rollback_rate",
            len(rollback_tasks & completed_task_ids),
            len(completed_task_ids),
        ),
        "founder_hours_recovered": scalar_result("founder_hours_recovered", founder_hours),
        "ai_handled_task_share": ratio_result(
            "ai_handled_task_share",
            ai_owned_active_tasks,
            len(current_active_tasks),
        ),
        "telemetry_coverage_rate": ratio_result(
            "telemetry_coverage_rate",
            active_tasks_with_telemetry,
            len(current_active_tasks),
        ),
        "eval_coverage_rate": ratio_result(
            "eval_coverage_rate",
            len(eval_covered_tasks & completed_task_ids),
            len(completed_task_ids),
        ),
        "repeated_internal_task_cycle_rate": ratio_result(
            "repeated_internal_task_cycle_rate",
            len(repeated_internal_task_cycle_ok),
            len(repeated_internal_completed_in_window),
        ),
    }

    metrics_payload: list[dict[str, Any]] = []
    breached: list[str] = []
    for metric in metric_registry:
        metric_id = str(metric.get("id") or "").strip()
        result = computed.get(metric_id, {"id": metric_id, "value": None})
        threshold = metric.get("threshold") if isinstance(metric.get("threshold"), dict) else None
        threshold_status = evaluate_threshold(result.get("value"), threshold)
        payload = {
            "id": metric_id,
            "definition": metric.get("definition"),
            "unit": str(metric.get("unit") or "").strip(),
            "review_owner": str(metric.get("review_owner") or "").strip(),
            "value": result.get("value"),
            "threshold": threshold,
            "threshold_status": threshold_status,
            "action_if_breached": metric.get("action_if_breached", ""),
        }
        for key in ("numerator", "denominator", "sample_size"):
            if key in result:
                payload[key] = result[key]
        if threshold_status == "breached":
            breached.append(metric_id)
        metrics_payload.append(payload)

    event_type_counts: dict[str, int] = {}
    for event in events:
        event_type = str(event.get("event_type") or "").strip() or "unknown"
        event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1

    missing_telemetry = sorted(task_id for task_id in current_active_tasks if task_id not in grouped_events)
    repeated_internal_missing_task_cycle = sorted(
        task_id for task_id in repeated_internal_completed_in_window if task_id not in repeated_internal_task_cycle_ok
    )

    return {
        "generated_at": utc_now(),
        "window": {"since": since.isoformat(), "until": until.isoformat()},
        "total_events": len(events),
        "tasks_seen_in_telemetry": len(grouped_events),
        "active_tasks": len(current_active_tasks),
        "missing_telemetry_task_ids": missing_telemetry,
        "breached_metrics": breached,
        "event_type_counts": event_type_counts,
        "metrics": metrics_payload,
        "repeated_internal_work": {
            "required_task_cycle_task_ids": sorted(repeated_internal_completed_in_window),
            "task_cycle_ok_task_ids": sorted(repeated_internal_task_cycle_ok),
            "task_cycle_missing_task_ids": repeated_internal_missing_task_cycle,
            "task_cycle_reports": repeated_internal_task_cycle_reports,
        },
    }


def render_review_markdown(review: dict[str, Any]) -> str:
    lines = [
        "# Weekly Telemetry Metrics Review",
        "",
        f"- Generated At: {review['generated_at']}",
        f"- Window: {review['window']['since']} -> {review['window']['until']}",
        f"- Total events: {review['total_events']}",
        f"- Tasks seen in telemetry: {review['tasks_seen_in_telemetry']}",
        f"- Active tasks: {review['active_tasks']}",
        f"- Breached metrics: {', '.join(review['breached_metrics']) if review['breached_metrics'] else 'none'}",
        "",
        "## Metrics",
    ]
    for metric in review["metrics"]:
        value = format_metric_value(metric.get("value"), str(metric.get("unit") or "").strip())
        status = metric.get("threshold_status")
        threshold = metric.get("threshold") or {}
        threshold_text = ""
        if threshold:
            threshold_text = f" | Threshold: {threshold.get('comparison')} {threshold.get('value')}"
        lines.append(f"- {metric['id']}: {value} | Status: {status}{threshold_text}")
        action = str(metric.get("action_if_breached") or "").strip()
        if action and status == "breached":
            lines.append(f"  Action: {action}")

    lines.extend(["", "## Coverage"])
    if review["missing_telemetry_task_ids"]:
        lines.append("- Missing telemetry on active tasks: " + ", ".join(review["missing_telemetry_task_ids"]))
    else:
        lines.append("- Missing telemetry on active tasks: none")

    repeated_internal = review.get("repeated_internal_work", {}) or {}
    required_task_cycle = repeated_internal.get("required_task_cycle_task_ids", []) or []
    lines.extend(["", "## Repeated Internal Work"])
    if required_task_cycle:
        lines.append("- Repeated internal tasks requiring task-cycle: " + ", ".join(required_task_cycle))
        missing_task_cycle = repeated_internal.get("task_cycle_missing_task_ids", []) or []
        if missing_task_cycle:
            lines.append("- Missing or failing task-cycle: " + ", ".join(missing_task_cycle))
        else:
            lines.append("- Missing or failing task-cycle: none")
    else:
        lines.append("- Repeated internal tasks requiring task-cycle: none")

    lines.extend(["", "## Event Types"])
    if not review["event_type_counts"]:
        lines.append("- No telemetry events in this window.")
    else:
        for event_type, count in sorted(review["event_type_counts"].items()):
            lines.append(f"- {event_type}: {count}")
    return "\n".join(lines) + "\n"


def write_review_artifacts(review: dict[str, Any]) -> tuple[Path, Path]:
    review_slug = f"{review['window']['since']}_to_{review['window']['until']}"
    review_dir = TELEMETRY_ROOT / "reviews" / review_slug
    review_dir.mkdir(parents=True, exist_ok=True)
    json_path = review_dir / "metrics-review.json"
    md_path = review_dir / "metrics-review.md"
    json_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_review_markdown(review), encoding="utf-8")
    latest_dir = TELEMETRY_ROOT / "reviews"
    (latest_dir / "LATEST.json").write_text(
        json.dumps(review, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (latest_dir / "LATEST.md").write_text(render_review_markdown(review), encoding="utf-8")
    return json_path, md_path


def event_actor(event: dict[str, Any] | None) -> str:
    if not isinstance(event, dict):
        return ""
    return str(event.get("agent") or "").strip()


def build_task_cycle_report(
    task_id: str,
    since: date | None = None,
    until: date | None = None,
) -> dict[str, Any]:
    active_tasks = build_active_tasks()
    task = active_tasks.get(task_id)
    if not task:
        raise ValueError(f"unknown task_id: {task_id}")

    workflow_id = str(task.get("workflow") or "").strip()
    workflow = build_workflow_registry().get(workflow_id)
    if not workflow:
        raise ValueError(f"unknown workflow for task {task_id}: {workflow_id or '<empty>'}")

    events = load_task_events(task_id, since=since, until=until)
    first_by_type: dict[str, dict[str, Any]] = {}
    seen_event_types: list[str] = []
    for event in events:
        event_type = str(event.get("event_type") or "").strip()
        if not event_type:
            continue
        if event_type not in first_by_type:
            first_by_type[event_type] = event
        if event_type not in seen_event_types:
            seen_event_types.append(event_type)

    required_events = [
        str(item).strip()
        for item in workflow.get("required_telemetry_events", []) or []
        if str(item).strip()
    ]
    missing_required_events = [item for item in required_events if item not in first_by_type]

    expected_actor_map = {
        "route": ["ai_operations_lead"],
        "policy_check": ["governor"],
        "start": normalize_list(
            [
                str(task.get("owner") or "").strip(),
                *[str(item) for item in task.get("support", []) or []],
            ]
        ),
        "acceptance": [str(task.get("accepts_result") or "").strip()],
        "sync": ["documentation"],
    }
    actor_checks: list[dict[str, Any]] = []
    actor_failures: list[str] = []
    for event_type, expected_actors in expected_actor_map.items():
        if not expected_actors:
            continue
        event = first_by_type.get(event_type)
        actual_actor = event_actor(event)
        passed = bool(event) and actual_actor in expected_actors
        actor_checks.append(
            {
                "event_type": event_type,
                "expected_actors": expected_actors,
                "actual_actor": actual_actor,
                "ok": passed,
            }
        )
        if not passed:
            actor_failures.append(
                f"{event_type}:{actual_actor or '<missing>'} expected {'/'.join(expected_actors)}"
            )

    queue_state_ok = str(task.get("column") or "").strip() == "done" and bool(
        str(task.get("completed_at") or "").strip()
    )
    if not queue_state_ok:
        actor_failures.append(
            "queue_state:{column} expected done with completed_at".format(
                column=str(task.get("column") or "").strip() or "<empty>"
            )
        )

    status = "ok" if not missing_required_events and not actor_failures else "failed"
    return {
        "task_id": task_id,
        "task_title": str(task.get("title") or "").strip(),
        "workflow": workflow_id,
        "column": str(task.get("column") or "").strip(),
        "completed_at": str(task.get("completed_at") or "").strip(),
        "queue_state_ok": queue_state_ok,
        "required_events": required_events,
        "seen_event_types": seen_event_types,
        "missing_required_events": missing_required_events,
        "actor_checks": actor_checks,
        "actor_failures": actor_failures,
        "events_seen": len(events),
        "status": status,
        "window": {
            "since": since.isoformat() if since else "",
            "until": until.isoformat() if until else "",
        },
    }


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
    json_path, md_path = write_review_artifacts(review)
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
