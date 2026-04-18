#!/usr/bin/env python3
"""Validate and render the HQ AI control plane."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(
    os.environ.get("HQ_CONTROL_PLANE_REPO_ROOT", Path(__file__).resolve().parents[1])
).resolve()
CONTROL_PLANE_DIR = REPO_ROOT / "05 AI Control Plane"
ACTIVE_WORK_PATH = CONTROL_PLANE_DIR / "active-work.json"
AGENT_REGISTRY_PATH = CONTROL_PLANE_DIR / "agent-registry.json"
POLICIES_PATH = CONTROL_PLANE_DIR / "operating-policies.json"
WORKFLOW_REGISTRY_PATH = CONTROL_PLANE_DIR / "workflow-registry.json"
METRICS_REGISTRY_PATH = CONTROL_PLANE_DIR / "metrics-registry.json"
TASK_BOARD_PATH = REPO_ROOT / "02 Planning" / "Task Board.md"
SESSION_BOOTSTRAP_PATH = REPO_ROOT / ".hq" / "state" / "session-bootstrap.json"
SCHEMA_DIR = CONTROL_PLANE_DIR / "schemas"
SCHEMA_PATHS = {
    "active_work": SCHEMA_DIR / "active-work.schema.json",
    "agent_registry": SCHEMA_DIR / "agent-registry.schema.json",
    "policies": SCHEMA_DIR / "operating-policies.schema.json",
    "workflow_registry": SCHEMA_DIR / "workflow-registry.schema.json",
    "metrics_registry": SCHEMA_DIR / "metrics-registry.schema.json",
}
SPECIAL_TRANSITION_OWNERS = {"task_owner", "task_manager", "accepting_role"}
VALID_THRESHOLD_COMPARISONS = {"<", "<=", "=", ">=", ">"}
ACTIONABLE_COLUMNS = {"review", "executing", "this_week", "scheduled", "policy_check", "triage", "intake"}
STALE_PACKET_KINDS = ("spec", "handoff")
MARKDOWN_HEADING_PREFIX = "## "
DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2})?(?:Z|[+-][0-9]{2}:[0-9]{2})?)?\b")
RUNTIME_REFERENCE_PATTERN = re.compile(r"(\.hq/(?:specs|handoffs)/[^\s`'\"),:;]+)")


class ValidationError(Exception):
    """Raised when the control plane is structurally invalid."""


class ValidationIssue:
    def __init__(self, path: str, message: str) -> None:
        self.path = path
        self.message = message

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


class ValidationContext:
    def __init__(self) -> None:
        self.issues: list[ValidationIssue] = []

    def add(self, path: str, message: str) -> None:
        self.issues.append(ValidationIssue(path, message))

    def raise_if_any(self) -> None:
        if self.issues:
            message = "\n".join(str(issue) for issue in self.issues)
            raise ValidationError(message)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"missing required file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in {path}: {exc}") from exc


def normalize_text(value: Any) -> str:
    return str(value or "").strip()


def relative_display(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def ensure_file_exists(context: ValidationContext, relative_path: str, base_path: str) -> None:
    candidate = (REPO_ROOT / relative_path).resolve()
    if not candidate.exists():
        context.add(base_path, f"referenced path does not exist: {relative_path}")


def get_role_ids(agent_registry: dict[str, Any]) -> set[str]:
    return {
        normalize_text(role.get("id"))
        for role in agent_registry.get("roles", [])
        if isinstance(role, dict) and normalize_text(role.get("id"))
    }


def get_workflows(workflow_registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    workflows: dict[str, dict[str, Any]] = {}
    for item in workflow_registry.get("workflows", []):
        if isinstance(item, dict):
            workflow_id = normalize_text(item.get("id"))
            if workflow_id:
                workflows[workflow_id] = item
    return workflows


def get_policy_sets(policies: dict[str, Any]) -> tuple[set[str], set[str]]:
    autonomy_tiers = {
        normalize_text(item.get("id"))
        for item in policies.get("autonomy_tiers", [])
        if isinstance(item, dict) and normalize_text(item.get("id"))
    }
    risk_tiers = {
        normalize_text(item.get("id"))
        for item in policies.get("risk_tiers", [])
        if isinstance(item, dict) and normalize_text(item.get("id"))
    }
    return autonomy_tiers, risk_tiers


def get_metric_ids(metrics: dict[str, Any]) -> set[str]:
    metric_ids: set[str] = set()
    for collection_name in ("primary_metrics", "secondary_metrics"):
        for item in metrics.get(collection_name, []) or []:
            if isinstance(item, dict):
                metric_id = normalize_text(item.get("id"))
                if metric_id:
                    metric_ids.add(metric_id)
    return metric_ids


def format_issue_path(root: str, parts: list[Any]) -> str:
    path = root
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}"
    return path


def validate_schema(
    payload: dict[str, Any],
    schema_path: Path,
    root_label: str,
    context: ValidationContext,
) -> None:
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path)):
        context.add(format_issue_path(root_label, list(error.absolute_path)), error.message)


def get_board_columns(workflow_registry: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    ordered_columns: list[str] = []
    column_titles: dict[str, str] = {}
    for item in workflow_registry.get("board_columns", []) or []:
        if not isinstance(item, dict):
            continue
        column_id = normalize_text(item.get("id"))
        if not column_id:
            continue
        ordered_columns.append(column_id)
        column_titles[column_id] = normalize_text(item.get("title")) or column_id.title()
    return ordered_columns, column_titles


def get_telemetry_contract(workflow_registry: dict[str, Any]) -> tuple[set[str], set[str]]:
    telemetry = workflow_registry.get("telemetry", {})
    if not isinstance(telemetry, dict):
        return set(), set()
    event_types = {
        normalize_text(item)
        for item in telemetry.get("event_types", []) or []
        if normalize_text(item)
    }
    statuses = {
        normalize_text(item)
        for item in telemetry.get("statuses", []) or []
        if normalize_text(item)
    }
    return event_types, statuses


def validate_role_registry(agent_registry: dict[str, Any], context: ValidationContext) -> None:
    roles = agent_registry.get("roles")
    if not isinstance(roles, list):
        return

    seen: set[str] = set()
    for index, role in enumerate(roles):
        path = f"agent-registry.json.roles[{index}]"
        if not isinstance(role, dict):
            context.add(path, "role must be an object")
            continue
        role_id = normalize_text(role.get("id"))
        if not role_id:
            context.add(path, "role id is required")
        elif role_id in seen:
            context.add(path, f"duplicate role id: {role_id}")
        else:
            seen.add(role_id)
        if normalize_text(role.get("role_type")) not in {"human", "ai"}:
            context.add(path, "role_type must be 'human' or 'ai'")
        if not normalize_text(role.get("mission")):
            context.add(path, "mission is required")
        owns = role.get("owns")
        if owns is not None and not isinstance(owns, list):
            context.add(path, "owns must be a list when provided")

    for index, role in enumerate(roles):
        if not isinstance(role, dict):
            continue
        escalate_target = normalize_text(role.get("escalates_to"))
        if escalate_target and escalate_target not in seen:
            context.add(
                f"agent-registry.json.roles[{index}].escalates_to",
                f"unknown escalation role: {escalate_target}",
            )


def validate_metrics(
    metrics: dict[str, Any],
    agent_registry: dict[str, Any],
    context: ValidationContext,
) -> None:
    role_ids = get_role_ids(agent_registry)
    primary = metrics.get("primary_metrics")
    if not isinstance(primary, list):
        return
    if len(primary) < 5:
        context.add("metrics-registry.json", "primary_metrics should contain at least 5 metrics")
    for collection_name in ("primary_metrics", "secondary_metrics"):
        collection = metrics.get(collection_name, []) or []
        if not isinstance(collection, list):
            continue
        seen_ids: set[str] = set()
        for index, metric in enumerate(collection):
            path = f"metrics-registry.json.{collection_name}[{index}]"
            if not isinstance(metric, dict):
                context.add(path, "metric must be an object")
                continue
            metric_id = normalize_text(metric.get("id"))
            if not metric_id:
                context.add(path, "metric id is required")
            elif metric_id in seen_ids:
                context.add(path, f"duplicate metric id: {metric_id}")
            else:
                seen_ids.add(metric_id)
            if not normalize_text(metric.get("definition")):
                context.add(path, "definition is required")
            sources = metric.get("source")
            if not isinstance(sources, list) or not sources:
                context.add(path, "source must be a non-empty list")
            review_owner = normalize_text(metric.get("review_owner"))
            if review_owner and review_owner not in role_ids:
                context.add(path, f"unknown review_owner role: {review_owner}")
            threshold = metric.get("threshold")
            if threshold is not None:
                if not isinstance(threshold, dict):
                    context.add(path, "threshold must be an object when provided")
                else:
                    comparison = normalize_text(threshold.get("comparison"))
                    if comparison not in VALID_THRESHOLD_COMPARISONS:
                        context.add(
                            f"{path}.threshold.comparison",
                            "threshold comparison must be one of <, <=, =, >=, >",
                        )
                    if not isinstance(threshold.get("value"), (int, float)):
                        context.add(f"{path}.threshold.value", "threshold value must be numeric")


def validate_workflows(
    workflow_registry: dict[str, Any],
    agent_registry: dict[str, Any],
    context: ValidationContext,
) -> None:
    ordered_columns, _ = get_board_columns(workflow_registry)
    allowed_columns = set(ordered_columns)
    seen_columns: set[str] = set()
    for index, item in enumerate(workflow_registry.get("board_columns", []) or []):
        if not isinstance(item, dict):
            continue
        column_id = normalize_text(item.get("id"))
        if column_id in seen_columns:
            context.add(f"workflow-registry.json.board_columns[{index}]", f"duplicate board column id: {column_id}")
        elif column_id:
            seen_columns.add(column_id)

    allowed_event_types, allowed_statuses = get_telemetry_contract(workflow_registry)
    telemetry = workflow_registry.get("telemetry", {})
    if isinstance(telemetry, dict):
        for set_name, items in (telemetry.get("event_sets", {}) or {}).items():
            for index, item in enumerate(items or []):
                event_type = normalize_text(item)
                if event_type and event_type not in allowed_event_types:
                    context.add(
                        f"workflow-registry.json.telemetry.event_sets.{set_name}[{index}]",
                        f"unknown telemetry event type: {event_type}",
                    )
        for set_name, items in (telemetry.get("status_sets", {}) or {}).items():
            for index, item in enumerate(items or []):
                status = normalize_text(item)
                if status and status not in allowed_statuses:
                    context.add(
                        f"workflow-registry.json.telemetry.status_sets.{set_name}[{index}]",
                        f"unknown telemetry status: {status}",
                    )

    workflows = workflow_registry.get("workflows")
    if not isinstance(workflows, list):
        return

    role_ids = get_role_ids(agent_registry)
    seen: set[str] = set()
    for index, workflow in enumerate(workflows):
        path = f"workflow-registry.json.workflows[{index}]"
        if not isinstance(workflow, dict):
            context.add(path, "workflow must be an object")
            continue
        workflow_id = normalize_text(workflow.get("id"))
        if not workflow_id:
            context.add(path, "workflow id is required")
        elif workflow_id in seen:
            context.add(path, f"duplicate workflow id: {workflow_id}")
        else:
            seen.add(workflow_id)
        states = workflow.get("states", []) or []
        if not isinstance(states, list):
            states = []
        if states:
            state_set = {normalize_text(item) for item in states if normalize_text(item)}
            if len(state_set) != len(states):
                context.add(path, "states must not contain duplicates")
            if allowed_columns and state_set & allowed_columns and not state_set <= allowed_columns:
                missing = sorted(state_set - allowed_columns)
                context.add(path, f"workflow states mix board and non-board states: {', '.join(missing)}")
        transition_owners = workflow.get("transition_owners")
        if isinstance(transition_owners, dict):
            for transition, owner in transition_owners.items():
                owner_id = normalize_text(owner)
                if owner_id not in role_ids and owner_id not in SPECIAL_TRANSITION_OWNERS:
                    context.add(
                        f"{path}.transition_owners[{transition}]",
                        f"unknown transition owner: {owner_id}",
                    )
        for key in ("required_telemetry_events", "acceptance_evidence"):
            value = workflow.get(key)
            if value is None:
                continue
            if not isinstance(value, list) or not value:
                context.add(f"{path}.{key}", f"{key} must be a non-empty list when provided")
                continue
            if key == "required_telemetry_events":
                for event_index, event_type in enumerate(value):
                    normalized = normalize_text(event_type)
                    if normalized and normalized not in allowed_event_types:
                        context.add(
                            f"{path}.{key}[{event_index}]",
                            f"unknown telemetry event type: {normalized}",
                        )


def validate_policies(
    policies: dict[str, Any],
    agent_registry: dict[str, Any],
    metrics: dict[str, Any],
    context: ValidationContext,
) -> None:
    role_ids = get_role_ids(agent_registry)
    metric_ids = get_metric_ids(metrics)

    weekly_review = policies.get("weekly_metric_review")
    if weekly_review is not None:
        if not isinstance(weekly_review, dict):
            context.add("operating-policies.json.weekly_metric_review", "weekly_metric_review must be an object")
        else:
            owner = normalize_text(weekly_review.get("owner"))
            approver = normalize_text(weekly_review.get("approver"))
            if owner and owner not in role_ids:
                context.add("operating-policies.json.weekly_metric_review.owner", f"unknown role: {owner}")
            if approver and approver not in role_ids:
                context.add(
                    "operating-policies.json.weekly_metric_review.approver",
                    f"unknown role: {approver}",
                )
            for index, support_role in enumerate(weekly_review.get("support", []) or []):
                support_id = normalize_text(support_role)
                if support_id and support_id not in role_ids:
                    context.add(
                        f"operating-policies.json.weekly_metric_review.support[{index}]",
                        f"unknown role: {support_id}",
                    )
            for index, metric_id in enumerate(weekly_review.get("required_metrics", []) or []):
                metric_text = normalize_text(metric_id)
                if metric_text and metric_text not in metric_ids:
                    context.add(
                        f"operating-policies.json.weekly_metric_review.required_metrics[{index}]",
                        f"unknown metric id: {metric_text}",
                    )

    runtime_governance = policies.get("runtime_governance")
    if runtime_governance is not None:
        if not isinstance(runtime_governance, dict):
            context.add("operating-policies.json.runtime_governance", "runtime_governance must be an object")
        else:
            policy_surface = runtime_governance.get("policy_surface")
            if not isinstance(policy_surface, dict):
                context.add(
                    "operating-policies.json.runtime_governance.policy_surface",
                    "policy_surface must be an object",
                )
            else:
                script_path = normalize_text(policy_surface.get("script"))
                schema_path = normalize_text(policy_surface.get("policy_schema"))
                if script_path:
                    ensure_file_exists(
                        context,
                        script_path,
                        "operating-policies.json.runtime_governance.policy_surface.script",
                    )
                if schema_path:
                    ensure_file_exists(
                        context,
                        schema_path,
                        "operating-policies.json.runtime_governance.policy_surface.policy_schema",
                    )
            hook_events = runtime_governance.get("hook_events")
            if not isinstance(hook_events, list) or not hook_events:
                context.add(
                    "operating-policies.json.runtime_governance.hook_events",
                    "hook_events must be a non-empty list",
                )

    metric_thresholds = policies.get("metric_thresholds", []) or []
    if metric_thresholds and not isinstance(metric_thresholds, list):
        context.add("operating-policies.json.metric_thresholds", "metric_thresholds must be a list")
    for index, threshold in enumerate(metric_thresholds if isinstance(metric_thresholds, list) else []):
        path = f"operating-policies.json.metric_thresholds[{index}]"
        if not isinstance(threshold, dict):
            context.add(path, "metric threshold must be an object")
            continue
        metric_id = normalize_text(threshold.get("metric_id"))
        if metric_id and metric_id not in metric_ids:
            context.add(f"{path}.metric_id", f"unknown metric id: {metric_id}")
        comparison = normalize_text(threshold.get("comparison"))
        if comparison not in VALID_THRESHOLD_COMPARISONS:
            context.add(f"{path}.comparison", "comparison must be one of <, <=, =, >=, >")
        if not isinstance(threshold.get("target"), (int, float)):
            context.add(f"{path}.target", "target must be numeric")
        owner = normalize_text(threshold.get("owner"))
        if owner and owner not in role_ids:
            context.add(f"{path}.owner", f"unknown role: {owner}")
        for role_index, escalate_role in enumerate(threshold.get("escalate_to", []) or []):
            escalate_id = normalize_text(escalate_role)
            if escalate_id and escalate_id not in role_ids:
                context.add(f"{path}.escalate_to[{role_index}]", f"unknown role: {escalate_id}")


def validate_active_work(
    active_work: dict[str, Any],
    agent_registry: dict[str, Any],
    policies: dict[str, Any],
    workflow_registry: dict[str, Any],
    context: ValidationContext,
) -> None:
    tasks = active_work.get("tasks")
    if not isinstance(tasks, list):
        return

    role_ids = get_role_ids(agent_registry)
    autonomy_tiers, risk_tiers = get_policy_sets(policies)
    workflows = get_workflows(workflow_registry)
    ordered_columns, _ = get_board_columns(workflow_registry)
    allowed_columns = set(ordered_columns)

    seen_task_ids: set[str] = set()
    for index, task in enumerate(tasks):
        path = f"active-work.json.tasks[{index}]"
        if not isinstance(task, dict):
            context.add(path, "task must be an object")
            continue

        task_id = normalize_text(task.get("id"))
        if not task_id:
            context.add(path, "task id is required")
        elif task_id in seen_task_ids:
            context.add(path, f"duplicate task id: {task_id}")
        else:
            seen_task_ids.add(task_id)

        workflow_id = normalize_text(task.get("workflow"))
        workflow = workflows.get(workflow_id)
        if not workflow:
            context.add(path, f"unknown workflow: {workflow_id or '<empty>'}")
            required_fields: list[str] = []
        else:
            required_fields = [
                normalize_text(item)
                for item in workflow.get("required_task_fields", [])
                if normalize_text(item)
            ]

        for field in required_fields:
            value = task.get(field)
            if value is None:
                context.add(f"{path}.{field}", "required field is missing")
                continue
            if isinstance(value, str) and not value.strip():
                context.add(f"{path}.{field}", "required field must not be empty")

        manager = normalize_text(task.get("manager"))
        owner = normalize_text(task.get("owner"))
        accepts_result = normalize_text(task.get("accepts_result"))
        if manager and manager not in role_ids:
            context.add(f"{path}.manager", f"unknown role: {manager}")
        if owner and owner not in role_ids:
            context.add(f"{path}.owner", f"unknown role: {owner}")
        if accepts_result and accepts_result not in role_ids:
            context.add(f"{path}.accepts_result", f"unknown role: {accepts_result}")

        for support_index, support_role in enumerate(task.get("support", []) or []):
            support_id = normalize_text(support_role)
            if support_id and support_id not in role_ids:
                context.add(f"{path}.support[{support_index}]", f"unknown role: {support_id}")

        risk_tier = normalize_text(task.get("risk_tier"))
        autonomy_tier = normalize_text(task.get("autonomy_tier"))
        if risk_tier and risk_tier not in risk_tiers:
            context.add(f"{path}.risk_tier", f"unknown risk tier: {risk_tier}")
        if autonomy_tier and autonomy_tier not in autonomy_tiers:
            context.add(f"{path}.autonomy_tier", f"unknown autonomy tier: {autonomy_tier}")

        column = normalize_text(task.get("column"))
        if column not in allowed_columns:
            context.add(f"{path}.column", f"unsupported column: {column}")

        primary_update_file = normalize_text(task.get("primary_update_file"))
        if primary_update_file:
            ensure_file_exists(context, primary_update_file, f"{path}.primary_update_file")
        for align_index, align_path in enumerate(task.get("align_files", []) or []):
            align_text = normalize_text(align_path)
            if align_text:
                ensure_file_exists(context, align_text, f"{path}.align_files[{align_index}]")
def load_control_plane() -> dict[str, Any]:
    return {
        "active_work": load_json(ACTIVE_WORK_PATH),
        "agent_registry": load_json(AGENT_REGISTRY_PATH),
        "policies": load_json(POLICIES_PATH),
        "workflow_registry": load_json(WORKFLOW_REGISTRY_PATH),
        "metrics_registry": load_json(METRICS_REGISTRY_PATH),
    }


def validate_control_plane() -> dict[str, Any]:
    bundle = load_control_plane()
    context = ValidationContext()
    for key, root_label in (
        ("active_work", "active-work.json"),
        ("agent_registry", "agent-registry.json"),
        ("policies", "operating-policies.json"),
        ("workflow_registry", "workflow-registry.json"),
        ("metrics_registry", "metrics-registry.json"),
    ):
        validate_schema(bundle[key], SCHEMA_PATHS[key], root_label, context)
    validate_role_registry(bundle["agent_registry"], context)
    validate_metrics(bundle["metrics_registry"], bundle["agent_registry"], context)
    validate_workflows(bundle["workflow_registry"], bundle["agent_registry"], context)
    validate_policies(
        bundle["policies"],
        bundle["agent_registry"],
        bundle["metrics_registry"],
        context,
    )
    validate_active_work(
        bundle["active_work"],
        bundle["agent_registry"],
        bundle["policies"],
        bundle["workflow_registry"],
        context,
    )
    context.raise_if_any()
    return bundle


def checkbox_for_column(column: str) -> str:
    return "x" if column == "done" else " "


def task_lines(task: dict[str, Any]) -> list[str]:
    checkbox = checkbox_for_column(normalize_text(task.get("column")))
    lines = [f"- [{checkbox}] {normalize_text(task.get('title'))}"]
    lines.append(
        "  - ID: {id} | Manager: {manager} | Owner: {owner} | Accepts: {accepts} | Risk: {risk} | Autonomy: {autonomy}".format(
            id=normalize_text(task.get("id")),
            manager=normalize_text(task.get("manager")),
            owner=normalize_text(task.get("owner")),
            accepts=normalize_text(task.get("accepts_result")),
            risk=normalize_text(task.get("risk_tier")),
            autonomy=normalize_text(task.get("autonomy_tier")),
        )
    )
    lines.append(f"  - Project: {normalize_text(task.get('project'))}")
    if task.get("support"):
        lines.append(f"  - Support: {', '.join(str(item) for item in task.get('support', []))}")
    lines.append(f"  - Next: {normalize_text(task.get('next_step'))}")
    lines.append(f"  - Done when: {normalize_text(task.get('done_when'))}")
    lines.append(f"  - Primary update file: `{normalize_text(task.get('primary_update_file'))}`")
    align_files = [normalize_text(item) for item in task.get("align_files", []) or [] if normalize_text(item)]
    if align_files:
        lines.append("  - Align: " + ", ".join(f"`{item}`" for item in align_files))
    completed_at = normalize_text(task.get("completed_at"))
    if completed_at:
        lines.append(f"  - Completed at: {completed_at}")
    return lines


def render_board(active_work: dict[str, Any], workflow_registry: dict[str, Any]) -> str:
    objective = active_work.get("objective", {})
    column_order, column_titles = get_board_columns(workflow_registry)
    lines = [
        "# Task Board",
        "",
        "> Generated from `05 AI Control Plane/active-work.json`. Do not edit this board by hand; run `python3 scripts/hq_control_plane.py sync` after queue changes.",
        "",
        f"- Updated At: {normalize_text(active_work.get('updated_at'))}",
        f"- Operating Mode: {normalize_text(active_work.get('operating_mode'))}",
        f"- Objective: {normalize_text(objective.get('title'))}",
        "",
        "## Success Criteria",
    ]
    criteria = objective.get("success_criteria", []) or []
    if criteria:
        lines.extend(f"- {item}" for item in criteria)
    else:
        lines.append("- None")

    tasks = active_work.get("tasks", [])
    for column in column_order:
        column_tasks = [task for task in tasks if normalize_text(task.get("column")) == column]
        if not column_tasks:
            continue
        lines.extend(["", f"## {column_titles.get(column, column.title())}"])
        for task in column_tasks:
            lines.extend(task_lines(task))
    return "\n".join(lines) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_datetime(value: str) -> datetime | None:
    text = normalize_text(value)
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    for candidate in (normalized, normalized.split("T", 1)[0]):
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def packet_task_slug(task: dict[str, Any]) -> str:
    return normalize_text(task.get("id"))


def packet_path(task: dict[str, Any], kind: str) -> Path:
    root_name = "specs" if kind == "spec" else "handoffs"
    return REPO_ROOT / ".hq" / root_name / packet_task_slug(task) / "LATEST.md"


def normalize_runtime_reference(path_text: str) -> Path | None:
    candidate = (REPO_ROOT / path_text).resolve()
    if candidate.is_dir():
        latest = candidate / "LATEST.md"
        if latest.exists():
            return latest
        return None
    return candidate


def packet_candidates(task: dict[str, Any], kind: str) -> list[Path]:
    references: list[Path] = []
    scanned_values = [
        normalize_text(task.get("next_step")),
        normalize_text(task.get("primary_update_file")),
        *(normalize_text(item) for item in task.get("align_files", []) or []),
    ]
    for value in scanned_values:
        for match in RUNTIME_REFERENCE_PATTERN.findall(value):
            candidate = normalize_runtime_reference(match)
            parts = Path(match).parts
            if kind == "spec" and len(parts) >= 3 and parts[1] == "handoffs":
                inferred_spec = REPO_ROOT / ".hq" / "specs" / parts[2] / "LATEST.md"
                if inferred_spec.exists():
                    references.append(inferred_spec)
            if candidate is None:
                continue
            if f"/{kind}s/" not in candidate.as_posix():
                continue
            references.append(candidate)
    if not references:
        return [packet_path(task, kind)]
    deduplicated: list[Path] = []
    seen: set[str] = set()
    for item in references:
        key = item.as_posix()
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(item)
    return deduplicated


def extract_section_items(path: Path, heading: str) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    items: list[str] = []
    in_section = False
    expected_heading = heading.strip().lower()
    for line in lines:
        if line.startswith(MARKDOWN_HEADING_PREFIX):
            current_heading = line[len(MARKDOWN_HEADING_PREFIX) :].strip().lower()
            if in_section:
                break
            in_section = current_heading == expected_heading
            continue
        if not in_section:
            continue
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")):
            items.append(stripped[2:].strip())
            continue
        match = re.match(r"^\d+\.\s+(.*)$", stripped)
        if match:
            items.append(match.group(1).strip())
    return items


def packet_updated_at(path: Path) -> str:
    manifest_path = path.parent / "manifest.json"
    if manifest_path.exists():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        updated_at = normalize_text(payload.get("updated_at"))
        if updated_at:
            return updated_at
    if not path.exists():
        return ""
    content = path.read_text(encoding="utf-8")
    matches = DATE_PATTERN.findall("\n".join(content.splitlines()[:80]))
    parsed_matches = [parse_datetime(item) for item in matches]
    parsed = [item for item in parsed_matches if item is not None]
    if not parsed:
        return ""
    latest = max(parsed)
    return latest.date().isoformat()


def sort_tasks(
    tasks: list[dict[str, Any]],
    workflow_registry: dict[str, Any],
) -> list[dict[str, Any]]:
    column_order, _ = get_board_columns(workflow_registry)
    priority = {column: index for index, column in enumerate(column_order)}
    return sorted(
        tasks,
        key=lambda task: (
            priority.get(normalize_text(task.get("column")), len(priority)),
            normalize_text(task.get("project")),
            normalize_text(task.get("title")),
        ),
    )


def project_live_task(task: dict[str, Any]) -> dict[str, str]:
    return {
        "id": normalize_text(task.get("id")),
        "title": normalize_text(task.get("title")),
        "project": normalize_text(task.get("project")),
        "owner": normalize_text(task.get("owner")),
        "manager": normalize_text(task.get("manager")),
        "column": normalize_text(task.get("column")),
        "next_step": normalize_text(task.get("next_step")),
        "primary_update_file": normalize_text(task.get("primary_update_file")),
        "accepts_result": normalize_text(task.get("accepts_result")),
    }


def blocked_reason(task: dict[str, Any]) -> str:
    handoff = packet_path(task, "handoff")
    blockers = extract_section_items(handoff, "Blockers")
    if blockers:
        return " ".join(blockers[:2])
    next_step = normalize_text(task.get("next_step"))
    if next_step:
        return next_step
    return "No blocker note found in the current control surface."


def collect_stale_items(tasks: list[dict[str, Any]], queue_updated_at: str) -> list[dict[str, str]]:
    queue_updated = parse_datetime(queue_updated_at)
    stale_items: list[dict[str, str]] = []
    for task in tasks:
        task_id = normalize_text(task.get("id"))
        task_title = normalize_text(task.get("title"))
        for kind in STALE_PACKET_KINDS:
            for current_path in packet_candidates(task, kind):
                relative_path = relative_display(current_path)
                if not current_path.exists():
                    stale_items.append(
                        {
                            "task_id": task_id,
                            "task_title": task_title,
                            "kind": kind,
                            "status": "missing",
                            "path": relative_path,
                            "reason": f"Missing {kind} packet for live task.",
                        }
                    )
                    continue
                packet_updated = parse_datetime(packet_updated_at(current_path))
                if queue_updated and packet_updated and packet_updated.date() < queue_updated.date():
                    stale_items.append(
                        {
                            "task_id": task_id,
                            "task_title": task_title,
                            "kind": kind,
                            "status": "stale",
                            "path": relative_path,
                            "updated_at": packet_updated.date().isoformat(),
                            "reason": f"{kind} packet predates active-work.json updated_at.",
                        }
                    )
    return stale_items


def recommended_next_command(active_tasks: list[dict[str, Any]]) -> str:
    if any(normalize_text(task.get("column")) in ACTIONABLE_COLUMNS for task in active_tasks):
        return "python3 scripts/hq_runtime.py route-next-slice"
    return "python3 scripts/hq_control_plane.py validate"


def build_status_payload(
    active_work: dict[str, Any],
    workflow_registry: dict[str, Any],
) -> dict[str, Any]:
    live_tasks = [
        task
        for task in active_work.get("tasks", []) or []
        if isinstance(task, dict) and normalize_text(task.get("column")) != "done"
    ]
    ordered_live_tasks = sort_tasks(live_tasks, workflow_registry)
    blocked_tasks = [
        {
            "id": normalize_text(task.get("id")),
            "title": normalize_text(task.get("title")),
            "project": normalize_text(task.get("project")),
            "owner": normalize_text(task.get("owner")),
            "column": normalize_text(task.get("column")),
            "reason": blocked_reason(task),
            "next_step": normalize_text(task.get("next_step")),
        }
        for task in ordered_live_tasks
        if normalize_text(task.get("column")) == "blocked"
    ]
    payload = {
        "generated_at": utc_now(),
        "updated_at": normalize_text(active_work.get("updated_at")),
        "objective": normalize_text(active_work.get("objective", {}).get("title")),
        "active_tasks": [project_live_task(task) for task in ordered_live_tasks],
        "blocked": blocked_tasks,
        "stale_items": collect_stale_items(ordered_live_tasks, normalize_text(active_work.get("updated_at"))),
        "recommended_next_command": recommended_next_command(ordered_live_tasks),
    }
    return payload


def render_status_text(payload: dict[str, Any]) -> str:
    lines = [
        "Session Bootstrap",
        f"Objective: {payload.get('objective') or '-'}",
        f"Updated At: {payload.get('updated_at') or '-'}",
        f"Bootstrap File: {relative_display(SESSION_BOOTSTRAP_PATH)}",
        "",
        "Active Tasks",
    ]
    active_tasks = payload.get("active_tasks", []) or []
    if active_tasks:
        for task in active_tasks:
            lines.append(
                f"- {task['id']} [{task['column']}] {task['title']} ({task['owner']}) | next_step: {task['next_step'] or '-'}"
            )
    else:
        lines.append("- None")

    lines.extend(["", "Blocked Tasks"])
    blocked = payload.get("blocked", []) or []
    if blocked:
        for task in blocked:
            lines.append(f"- {task['id']} [{task['column']}] {task['title']} | reason: {task['reason']}")
    else:
        lines.append("- None")

    lines.extend(["", "Stale Items"])
    stale_items = payload.get("stale_items", []) or []
    if stale_items:
        for item in stale_items:
            updated_at = f" | updated_at: {item['updated_at']}" if item.get("updated_at") else ""
            lines.append(
                f"- {item['task_id']} {item['kind']} [{item['status']}] {item['path']}{updated_at} | {item['reason']}"
            )
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "Recommended Next Command",
            f"- {payload.get('recommended_next_command') or '-'}",
        ]
    )
    return "\n".join(lines) + "\n"


def status_command(args: argparse.Namespace) -> int:
    bundle = validate_control_plane()
    payload = build_status_payload(bundle["active_work"], bundle["workflow_registry"])
    SESSION_BOOTSTRAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    SESSION_BOOTSTRAP_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_status_text(payload), end="")
    return 0


def validate_command(_: argparse.Namespace) -> int:
    bundle = validate_control_plane()
    print(f"validation=ok")
    print(f"tasks={len(bundle['active_work'].get('tasks', []))}")
    print(f"board={relative_display(TASK_BOARD_PATH)}")
    return 0


def sync_command(_: argparse.Namespace) -> int:
    bundle = validate_control_plane()
    TASK_BOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    TASK_BOARD_PATH.write_text(
        render_board(bundle["active_work"], bundle["workflow_registry"]),
        encoding="utf-8",
    )
    print(f"validation=ok")
    print(f"board_written={TASK_BOARD_PATH}")
    return 0


def render_board_command(_: argparse.Namespace) -> int:
    bundle = validate_control_plane()
    print(render_board(bundle["active_work"], bundle["workflow_registry"]), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and render the HQ control plane.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate JSON control-plane structure and references.")
    validate_parser.set_defaults(func=validate_command)

    sync_parser = subparsers.add_parser("sync", help="Validate and render Task Board.md from active-work.json.")
    sync_parser.set_defaults(func=sync_command)

    render_parser = subparsers.add_parser("render-board", help="Print the rendered task board to stdout.")
    render_parser.set_defaults(func=render_board_command)

    status_parser = subparsers.add_parser(
        "status",
        help="Write and print a compact session bootstrap view from the live control plane.",
    )
    status_parser.add_argument("--json", action="store_true", help="Print the session bootstrap as JSON.")
    status_parser.set_defaults(func=status_command)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except ValidationError as exc:
        print(f"validation=failed")
        print(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
