#!/usr/bin/env python3
"""Validate and render the HQ AI control plane."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from hq_feedback_loop import load_recent_iterations

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ModuleNotFoundError:  # pragma: no cover - local bootstrap fallback
    Draft202012Validator = None
    FormatChecker = None

REPO_ROOT = Path(
    os.environ.get("HQ_CONTROL_PLANE_REPO_ROOT", Path(__file__).resolve().parents[1])
).resolve()
CONTROL_PLANE_DIR = REPO_ROOT / "05 AI Control Plane"
ACTIVE_WORK_PATH = CONTROL_PLANE_DIR / "active-work.json"
AGENT_REGISTRY_PATH = CONTROL_PLANE_DIR / "agent-registry.json"
POLICIES_PATH = CONTROL_PLANE_DIR / "operating-policies.json"
WORKFLOW_REGISTRY_PATH = CONTROL_PLANE_DIR / "workflow-registry.json"
METRICS_REGISTRY_PATH = CONTROL_PLANE_DIR / "metrics-registry.json"
EXECUTION_CONFIG_PATH = CONTROL_PLANE_DIR / "execution-config.json"
TASK_TEMPLATES_JSON_PATH = CONTROL_PLANE_DIR / "task-templates.json"
TASK_TEMPLATES_MD_PATH = CONTROL_PLANE_DIR / "task-templates.md"
TASK_BOARD_PATH = REPO_ROOT / "02 Planning" / "Task Board.md"
SESSION_BOOTSTRAP_PATH = REPO_ROOT / ".hq" / "state" / "session-bootstrap.json"
MEMORY_INDEX_PATH = REPO_ROOT / ".hq" / "state" / "memory-index.json"
ARCHIVED_TASKS_PATH = REPO_ROOT / ".hq" / "state" / "archived-tasks.json"
QUICK_CONTEXT_PATH = REPO_ROOT / ".hq" / "state" / "QUICK_CONTEXT.md"
PRIVATE_ROOT = Path(os.environ.get("HQ_RUNTIME_PRIVATE_ROOT", REPO_ROOT / ".hq")).resolve()
WORKFLOW_ARTIFACT_PATH = PRIVATE_ROOT / "state" / "WORKFLOW.generated.md"
TELEMETRY_ROOT = PRIVATE_ROOT / "telemetry"
TELEMETRY_REVIEW_PATH = TELEMETRY_ROOT / "reviews" / "LATEST.json"
MISSION_RUNTIME_ROOT = PRIVATE_ROOT / "state" / "mission-runtime"
MISSION_RUNTIME_RUNS_DIR = MISSION_RUNTIME_ROOT / "runs"
MISSION_RUNTIME_RESUME_STATUS_DIR = MISSION_RUNTIME_ROOT / "resume-status"
SCHEMA_DIR = CONTROL_PLANE_DIR / "schemas"
FOUNDER_WEEKLY_REVIEW_BRIDGE_SCHEMA_PATH = (
    SCHEMA_DIR / "founder-weekly-review-bridge.schema.json"
)
EXECUTION_CONFIG_SCHEMA_PATH = SCHEMA_DIR / "execution-config.schema.json"
SCHEMA_PATHS = {
    "active_work": SCHEMA_DIR / "active-work.schema.json",
    "agent_registry": SCHEMA_DIR / "agent-registry.schema.json",
    "policies": SCHEMA_DIR / "operating-policies.schema.json",
    "workflow_registry": SCHEMA_DIR / "workflow-registry.schema.json",
    "metrics_registry": SCHEMA_DIR / "metrics-registry.schema.json",
}
PERMISSION_GRANTS_PATH = CONTROL_PLANE_DIR / "permission-grants.json"
PERMISSION_GRANTS_SCHEMA_PATH = SCHEMA_DIR / "permission-grants.schema.json"
SPECIAL_TRANSITION_OWNERS = {"task_owner", "task_manager", "accepting_role"}
VALID_THRESHOLD_COMPARISONS = {"<", "<=", "=", ">=", ">"}
ACTIONABLE_COLUMNS = {"review", "executing", "this_week", "scheduled", "policy_check", "triage", "intake"}
STALE_PACKET_KINDS = ("spec", "handoff")
RECENT_ITERATION_LIMIT = 5
MARKDOWN_HEADING_PREFIX = "## "
DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2})?(?:Z|[+-][0-9]{2}:[0-9]{2})?)?\b")
RUNTIME_REFERENCE_PATTERN = re.compile(r"(\.hq/(?:specs|handoffs)/[^\s`'\"),:;]+)")
NEXT_STEP_SOFT_LIMIT = 120
NON_ACTIONABLE_PREFIXES = {
    "background",
    "context",
    "none",
    "note",
    "notes",
    "n/a",
    "na",
    "status",
    "summary",
    "tbd",
    "todo",
}
EXECUTION_PRESETS: dict[str, dict[str, Any]] = {
    "light": {
        "description": "Low-friction local execution with lighter review defaults.",
        "workflow_mode": "light",
        "approvals": {
            "default_internal_change_approval": "owner_or_accepting_role",
            "require_governor_for_medium_risk": False,
            "require_governor_for_control_plane_changes": True,
            "require_human_for_external_actions": True,
            "require_human_for_high_risk": True,
        },
        "execution_profile": {
            "preflight_required": False,
            "auto_scaffold_packets": True,
            "auto_generate_workflow_artifact": True,
            "verification_depth": "minimal",
            "runner_model_selection": "explicit_required",
        },
    },
    "normal": {
        "description": "Balanced default for governed internal execution.",
        "workflow_mode": "normal",
        "approvals": {
            "default_internal_change_approval": "governor_or_accepting_role",
            "require_governor_for_medium_risk": True,
            "require_governor_for_control_plane_changes": True,
            "require_human_for_external_actions": True,
            "require_human_for_high_risk": True,
        },
        "execution_profile": {
            "preflight_required": True,
            "auto_scaffold_packets": True,
            "auto_generate_workflow_artifact": True,
            "verification_depth": "standard",
            "runner_model_selection": "explicit_required",
        },
    },
    "strict": {
        "description": "Tighter review posture with strict preflight and verification.",
        "workflow_mode": "strict",
        "approvals": {
            "default_internal_change_approval": "governor_or_accepting_role",
            "require_governor_for_medium_risk": True,
            "require_governor_for_control_plane_changes": True,
            "require_human_for_external_actions": True,
            "require_human_for_high_risk": True,
        },
        "execution_profile": {
            "preflight_required": True,
            "auto_scaffold_packets": True,
            "auto_generate_workflow_artifact": True,
            "verification_depth": "strict",
            "runner_model_selection": "explicit_required",
        },
    },
}
DEFAULT_EXECUTION_PRESET = "normal"
DEFAULT_UNSAFE_ACTIONS = {
    "allow_external_writes": False,
    "allow_destructive_tracked_delete": False,
    "allow_unreviewed_publish": False,
    "allow_implicit_runner_model": False,
}


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
        self.warnings: list[ValidationIssue] = []

    def add(self, path: str, message: str) -> None:
        self.issues.append(ValidationIssue(path, message))

    def warn(self, path: str, message: str) -> None:
        self.warnings.append(ValidationIssue(path, message))

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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def normalize_text(value: Any) -> str:
    return str(value or "").strip()


def relative_display(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json_object_safe(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "missing"
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"
    if not isinstance(payload, dict):
        return None, "expected JSON object"
    return payload, ""


def resolve_runtime_path(path_text: str) -> Path:
    candidate = Path(path_text)
    if candidate.is_absolute():
        return candidate.resolve()
    return (REPO_ROOT / candidate).resolve()


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


def bool_text(value: Any) -> str:
    return "true" if bool(value) else "false"


def build_execution_config_from_preset(
    preset_id: str,
    active_work: dict[str, Any],
    policies: dict[str, Any],
    *,
    source: str,
) -> dict[str, Any]:
    normalized_preset = normalize_text(preset_id) or DEFAULT_EXECUTION_PRESET
    if normalized_preset not in EXECUTION_PRESETS:
        allowed = ", ".join(sorted(EXECUTION_PRESETS))
        raise ValidationError(f"unsupported execution preset '{normalized_preset}' (expected one of: {allowed})")

    preset = EXECUTION_PRESETS[normalized_preset]
    return {
        "version": 1,
        "updated_at": utc_today(),
        "profile": normalized_preset,
        "profile_source": source,
        "profile_description": preset["description"],
        "operating_mode": normalize_text(active_work.get("operating_mode")) or normalize_text(policies.get("stage")),
        "policy_stage": normalize_text(policies.get("stage")),
        "workflow_mode": preset["workflow_mode"],
        "approvals": dict(preset["approvals"]),
        "execution_profile": dict(preset["execution_profile"]),
        "unsafe_actions": dict(DEFAULT_UNSAFE_ACTIONS),
    }


def load_or_infer_execution_config(
    active_work: dict[str, Any],
    policies: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    if not EXECUTION_CONFIG_PATH.exists():
        return (
            build_execution_config_from_preset(
                DEFAULT_EXECUTION_PRESET,
                active_work,
                policies,
                source="inferred",
            ),
            "inferred",
        )

    payload = load_json(EXECUTION_CONFIG_PATH)
    if not isinstance(payload, dict):
        raise ValidationError(f"invalid JSON in {EXECUTION_CONFIG_PATH}: expected object")

    context = ValidationContext()
    validate_schema(payload, EXECUTION_CONFIG_SCHEMA_PATH, "execution-config.json", context)
    context.raise_if_any()
    return payload, "materialized"


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
    if Draft202012Validator is None or FormatChecker is None:
        context.warn(root_label, "jsonschema is not installed; skipping JSON Schema validation")
        return
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

    capability_routes = agent_registry.get("capability_routing", []) or []
    if capability_routes and not isinstance(capability_routes, list):
        context.add("agent-registry.json.capability_routing", "capability_routing must be a list")
        return
    seen_routes: set[str] = set()
    for index, route in enumerate(capability_routes):
        path = f"agent-registry.json.capability_routing[{index}]"
        if not isinstance(route, dict):
            context.add(path, "capability route must be an object")
            continue
        route_id = normalize_text(route.get("id"))
        if not route_id:
            context.add(path, "capability route id is required")
        elif route_id in seen_routes:
            context.add(path, f"duplicate capability route id: {route_id}")
        else:
            seen_routes.add(route_id)
        for field in ("primary_role", "manager"):
            role_id = normalize_text(route.get(field))
            if role_id and role_id not in seen:
                context.add(f"{path}.{field}", f"unknown role: {role_id}")
        support_roles = route.get("support_roles", []) or []
        if not isinstance(support_roles, list):
            context.add(f"{path}.support_roles", "support_roles must be a list when provided")
            continue
        for support_index, support_role in enumerate(support_roles):
            support_id = normalize_text(support_role)
            if support_id and support_id not in seen:
                context.add(f"{path}.support_roles[{support_index}]", f"unknown role: {support_id}")


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
        review_gates = workflow.get("review_gates", []) or []
        if review_gates and not isinstance(review_gates, list):
            context.add(f"{path}.review_gates", "review_gates must be a list when provided")
            continue
        seen_review_gates: set[str] = set()
        for gate_index, gate in enumerate(review_gates):
            gate_path = f"{path}.review_gates[{gate_index}]"
            if not isinstance(gate, dict):
                context.add(gate_path, "review gate must be an object")
                continue
            gate_id = normalize_text(gate.get("id"))
            if not gate_id:
                context.add(gate_path, "review gate id is required")
            elif gate_id in seen_review_gates:
                context.add(gate_path, f"duplicate review gate id: {gate_id}")
            else:
                seen_review_gates.add(gate_id)
            owner_id = normalize_text(gate.get("owner"))
            if owner_id and owner_id not in role_ids:
                context.add(f"{gate_path}.owner", f"unknown role: {owner_id}")
            telemetry_event = normalize_text(gate.get("telemetry_event"))
            if telemetry_event and telemetry_event not in allowed_event_types:
                context.add(
                    f"{gate_path}.telemetry_event",
                    f"unknown telemetry event type: {telemetry_event}",
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

    review_pipeline = policies.get("review_pipeline")
    if review_pipeline is not None:
        if not isinstance(review_pipeline, dict):
            context.add("operating-policies.json.review_pipeline", "review_pipeline must be an object")
        else:
            owner = normalize_text(review_pipeline.get("owner"))
            if owner and owner not in role_ids:
                context.add("operating-policies.json.review_pipeline.owner", f"unknown role: {owner}")
            for order_index, gate_role in enumerate(review_pipeline.get("default_order", []) or []):
                gate_id = normalize_text(gate_role)
                if gate_id and gate_id not in role_ids:
                    context.add(
                        f"operating-policies.json.review_pipeline.default_order[{order_index}]",
                        f"unknown role: {gate_id}",
                    )
            gate_selection = review_pipeline.get("gate_selection", []) or []
            if gate_selection and not isinstance(gate_selection, list):
                context.add(
                    "operating-policies.json.review_pipeline.gate_selection",
                    "gate_selection must be a list when provided",
                )
            for gate_index, gate in enumerate(gate_selection if isinstance(gate_selection, list) else []):
                gate_path = f"operating-policies.json.review_pipeline.gate_selection[{gate_index}]"
                if not isinstance(gate, dict):
                    context.add(gate_path, "gate selection must be an object")
                    continue
                gate_id = normalize_text(gate.get("gate"))
                if gate_id and gate_id not in role_ids:
                    context.add(f"{gate_path}.gate", f"unknown role: {gate_id}")
            learning_loop = review_pipeline.get("learning_loop")
            if isinstance(learning_loop, dict):
                learning_owner = normalize_text(learning_loop.get("owner"))
                if learning_owner and learning_owner not in role_ids:
                    context.add(
                        "operating-policies.json.review_pipeline.learning_loop.owner",
                        f"unknown role: {learning_owner}",
                    )

    subagent_context_protocol = policies.get("subagent_context_protocol")
    if subagent_context_protocol is not None:
        if not isinstance(subagent_context_protocol, dict):
            context.add(
                "operating-policies.json.subagent_context_protocol",
                "subagent_context_protocol must be an object",
            )
        else:
            owner = normalize_text(subagent_context_protocol.get("owner"))
            if owner and owner not in role_ids:
                context.add(
                    "operating-policies.json.subagent_context_protocol.owner",
                    f"unknown role: {owner}",
                )
            applies_to_roles = subagent_context_protocol.get("applies_to_roles")
            if not isinstance(applies_to_roles, list) or not applies_to_roles:
                context.add(
                    "operating-policies.json.subagent_context_protocol.applies_to_roles",
                    "applies_to_roles must be a non-empty list",
                )
            else:
                for index, role in enumerate(applies_to_roles):
                    role_id = normalize_text(role)
                    if role_id and role_id not in role_ids:
                        context.add(
                            f"operating-policies.json.subagent_context_protocol.applies_to_roles[{index}]",
                            f"unknown role: {role_id}",
                        )
            child_session_defaults = subagent_context_protocol.get("child_session_defaults")
            if not isinstance(child_session_defaults, dict):
                context.add(
                    "operating-policies.json.subagent_context_protocol.child_session_defaults",
                    "child_session_defaults must be an object",
                )
            else:
                blocked_tool_classes = child_session_defaults.get("blocked_tool_classes")
                if not isinstance(blocked_tool_classes, list) or not blocked_tool_classes:
                    context.add(
                        "operating-policies.json.subagent_context_protocol.child_session_defaults.blocked_tool_classes",
                        "blocked_tool_classes must be a non-empty list",
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
    queue_updated_at = normalize_text(active_work.get("updated_at"))

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
        for warning in lint_next_step(normalize_text(task.get("next_step"))):
            context.warn(f"{path}.next_step", warning)
        for warning in lint_role_conflicts(task):
            context.warn(path, warning)
        for warning in check_stale_telemetry(task, queue_updated_at):
            context.warn(path, warning)

    live_tasks = [
        task
        for task in tasks
        if isinstance(task, dict) and normalize_text(task.get("column")) != "done"
    ]
    for item in collect_stale_items(live_tasks, queue_updated_at):
        context.warn("active-work.json.runtime_packets", format_stale_item_warning(item))


def lint_next_step(next_step: str) -> list[str]:
    text = normalize_text(next_step)
    if not text:
        return []

    warnings: list[str] = []
    if "\n" in text:
        warnings.append("keep next_step to one line; move extra context into .hq/specs/ or .hq/handoffs/")

    sentences = [item for item in re.split(r"(?<=[.!?])\s+", text) if item.strip()]
    if len(sentences) > 1:
        warnings.append("keep next_step to one sentence; move narrative context into .hq/specs/ or .hq/handoffs/")

    if len(text) > NEXT_STEP_SOFT_LIMIT:
        warnings.append(
            f"keep next_step short and actionable (recommended <= {NEXT_STEP_SOFT_LIMIT} chars)"
        )

    first_token = text.split()[0].strip(" :").lower() if text.split() else ""
    if first_token in NON_ACTIONABLE_PREFIXES:
        warnings.append("start next_step with an action verb, not a narrative label")

    return warnings


def lint_role_conflicts(task: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    owner = normalize_text(task.get("owner"))
    manager = normalize_text(task.get("manager"))
    accepts_result = normalize_text(task.get("accepts_result"))

    if owner and owner == manager:
        warnings.append(f"owner and manager are the same role: {owner}")
    if owner and owner == accepts_result:
        warnings.append(f"owner and accepts_result are the same role: {owner}")

    return warnings


def validate_permission_grants(
    permission_grants: dict[str, Any] | None,
    agent_registry: dict[str, Any],
    context: ValidationContext,
) -> None:
    if permission_grants is None:
        return
    role_ids = get_role_ids(agent_registry)
    for collection in ("grants", "denies"):
        rows = permission_grants.get(collection, []) or []
        if not isinstance(rows, list):
            context.add(f"permission-grants.json.{collection}", f"{collection} must be a list")
            continue
        for index, row in enumerate(rows):
            path = f"permission-grants.json.{collection}[{index}]"
            if not isinstance(row, dict):
                context.add(path, "entry must be an object")
                continue
            role_id = normalize_text(row.get("role_id"))
            if role_id and role_id != "*" and role_id not in role_ids:
                context.add(f"{path}.role_id", f"unknown role: {role_id}")


def load_control_plane() -> dict[str, Any]:
    bundle = {
        "active_work": load_json(ACTIVE_WORK_PATH),
        "agent_registry": load_json(AGENT_REGISTRY_PATH),
        "policies": load_json(POLICIES_PATH),
        "workflow_registry": load_json(WORKFLOW_REGISTRY_PATH),
        "metrics_registry": load_json(METRICS_REGISTRY_PATH),
    }
    if PERMISSION_GRANTS_PATH.exists():
        bundle["permission_grants"] = load_json(PERMISSION_GRANTS_PATH)
    return bundle


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
    if "permission_grants" in bundle:
        validate_schema(
            bundle["permission_grants"],
            PERMISSION_GRANTS_SCHEMA_PATH,
            "permission-grants.json",
            context,
        )
        validate_permission_grants(
            bundle["permission_grants"], bundle["agent_registry"], context
        )
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
    execution_config, execution_config_state = load_or_infer_execution_config(
        bundle["active_work"],
        bundle["policies"],
    )
    stale_warnings = stale_runtime_packet_warnings(bundle["active_work"])
    if is_strict_execution(execution_config) and stale_warnings:
        raise ValidationError(
            "strict execution profile requires fresh runtime packets:\n"
            + "\n".join(f"- {warning}" for warning in stale_warnings)
        )
    bundle["execution_config"] = execution_config
    bundle["execution_config_state"] = execution_config_state
    bundle["validation_warnings"] = [str(item) for item in context.warnings]
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
    lines.extend(owner_gate_lines(task))
    completed_at = normalize_text(task.get("completed_at"))
    if completed_at:
        lines.append(f"  - Completed at: {completed_at}")
    return lines




def owner_gate_lines(task: dict[str, Any], indent: str = "  - ") -> list[str]:
    owner_gate = task.get("owner_gate")
    if not isinstance(owner_gate, dict) or not owner_gate:
        return []
    labels = [
        ("current_hypothesis", "Current Hypothesis"),
        ("next_founder_decision_gate", "Next Founder Decision Gate"),
        ("allowed_ai_actions", "Allowed AI Actions"),
        ("required_founder_approval_before_external_sends", "Required Founder Approval Before External Sends"),
        ("success_signal", "Success Signal"),
        ("kill_criteria", "Kill Criteria"),
    ]
    lines = [f"{indent}Owner Gate:"]
    nested_indent = indent + "  "
    for key, label in labels:
        value = owner_gate.get(key)
        if isinstance(value, list):
            items = [normalize_text(item) for item in value if normalize_text(item)]
            if not items:
                continue
            lines.append(f"{nested_indent}- {label}:")
            lines.extend(f"{nested_indent}  - {item}" for item in items)
        else:
            text = normalize_text(value)
            if text:
                lines.append(f"{nested_indent}- {label}: {text}")
    for key, label in (
        ("timeout_wait", "Timeout Wait"),
        ("timeout_minutes", "Timeout Minutes"),
        ("partial_handoff_rule", "Partial Handoff Rule"),
    ):
        text = normalize_text(task.get(key))
        if text:
            lines.append(f"{nested_indent}- {label}: {text}")
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


def write_task_board(active_work: dict[str, Any], workflow_registry: dict[str, Any]) -> None:
    TASK_BOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    TASK_BOARD_PATH.write_text(render_board(active_work, workflow_registry), encoding="utf-8")


def render_workflow_artifact(
    active_work: dict[str, Any],
    workflow_registry: dict[str, Any],
    policies: dict[str, Any],
    execution_config: dict[str, Any],
    execution_config_state: str,
) -> str:
    objective = active_work.get("objective", {})
    status_payload = build_status_payload(active_work, workflow_registry)
    column_order, column_titles = get_board_columns(workflow_registry)
    workflow_lookup = get_workflows(workflow_registry)
    tasks = [
        task
        for task in active_work.get("tasks", []) or []
        if isinstance(task, dict)
    ]
    used_workflow_ids: list[str] = []
    seen_workflow_ids: set[str] = set()
    for task in tasks:
        workflow_id = normalize_text(task.get("workflow"))
        if workflow_id and workflow_id not in seen_workflow_ids:
            seen_workflow_ids.add(workflow_id)
            used_workflow_ids.append(workflow_id)

    lines = [
        "# Workflow Artifact",
        "",
        "> Generated from the HQ control plane. Do not edit by hand; regenerate via `python3 scripts/hq_control_plane.py sync` or `status`.",
        "",
        f"- Generated At: {utc_now()}",
        f"- Objective: {normalize_text(objective.get('title')) or '-'}",
        f"- Operating Mode: {normalize_text(active_work.get('operating_mode')) or '-'}",
        f"- Policy Stage: {normalize_text(policies.get('stage')) or '-'}",
        f"- Execution Config: {relative_display(EXECUTION_CONFIG_PATH)} ({execution_config_state})",
        f"- Workflow Artifact: {relative_display(WORKFLOW_ARTIFACT_PATH)}",
        "",
        "## Sources",
        f"- active_work: {relative_display(ACTIVE_WORK_PATH)}",
        f"- workflow_registry: {relative_display(WORKFLOW_REGISTRY_PATH)}",
        f"- operating_policies: {relative_display(POLICIES_PATH)}",
    ]
    if execution_config_state == "materialized":
        lines.append(f"- execution_config: {relative_display(EXECUTION_CONFIG_PATH)}")
    else:
        lines.append(
            f"- execution_config: inferred `{DEFAULT_EXECUTION_PRESET}` baseline until `{relative_display(EXECUTION_CONFIG_PATH)}` is materialized"
        )

    startup_focus = status_payload.get("startup_focus") or {}
    lines.extend(
        [
            "",
            "## Execution Defaults",
            f"- Profile: {normalize_text(execution_config.get('profile')) or '-'}",
            f"- Profile Source: {normalize_text(execution_config.get('profile_source')) or execution_config_state}",
            f"- Workflow Mode: {normalize_text(execution_config.get('workflow_mode')) or '-'}",
            f"- Default Internal Change Approval: {normalize_text((execution_config.get('approvals') or {}).get('default_internal_change_approval')) or '-'}",
            f"- Governor Review For Medium Risk: {bool_text((execution_config.get('approvals') or {}).get('require_governor_for_medium_risk'))}",
            f"- Governor Review For Control Plane Changes: {bool_text((execution_config.get('approvals') or {}).get('require_governor_for_control_plane_changes'))}",
            f"- Human Review For External Actions: {bool_text((execution_config.get('approvals') or {}).get('require_human_for_external_actions'))}",
            f"- Preflight Required: {bool_text((execution_config.get('execution_profile') or {}).get('preflight_required'))}",
            f"- Verification Depth: {normalize_text((execution_config.get('execution_profile') or {}).get('verification_depth')) or '-'}",
            f"- Runner Model Selection: {normalize_text((execution_config.get('execution_profile') or {}).get('runner_model_selection')) or '-'}",
            f"- Allow External Writes: {bool_text((execution_config.get('unsafe_actions') or {}).get('allow_external_writes'))}",
            f"- Allow Destructive Tracked Delete: {bool_text((execution_config.get('unsafe_actions') or {}).get('allow_destructive_tracked_delete'))}",
            f"- Allow Unreviewed Publish: {bool_text((execution_config.get('unsafe_actions') or {}).get('allow_unreviewed_publish'))}",
            f"- Allow Implicit Runner Model: {bool_text((execution_config.get('unsafe_actions') or {}).get('allow_implicit_runner_model'))}",
            "",
            "## Queue Snapshot",
            f"- Updated At: {normalize_text(active_work.get('updated_at')) or '-'}",
            f"- Live Tasks: {len(status_payload.get('active_tasks', []) or [])}",
            f"- Blocked Tasks: {len(status_payload.get('blocked', []) or [])}",
            f"- Startup Focus: {startup_focus.get('id') or '-'} | {startup_focus.get('title') or '-'}",
            f"- Recent Iterations: {len(status_payload.get('recent_iterations', []) or [])}",
            f"- Recommended Next Command: {status_payload.get('recommended_next_command') or '-'}",
        ]
    )

    recent_iterations = status_payload.get("recent_iterations", []) or []
    lines.extend(["", "## Recent Feedback Loop"])
    if recent_iterations:
        for item in recent_iterations:
            lines.append(
                "- {created_at} | {task_id} [{status}] hypothesis={hypothesis} | next_focus={next_focus}".format(
                    created_at=normalize_text(item.get("created_at")) or "-",
                    task_id=normalize_text(item.get("task_id")) or "-",
                    status=normalize_text(item.get("status")) or "-",
                    hypothesis=normalize_text(item.get("hypothesis")) or "-",
                    next_focus=normalize_text(item.get("next_focus")) or "-",
                )
            )
    else:
        lines.append("- None")

    for column in column_order:
        column_tasks = [task for task in tasks if normalize_text(task.get("column")) == column]
        if not column_tasks:
            continue
        lines.extend(["", f"## Column: {column_titles.get(column, column.title())}"])
        for task in column_tasks:
            lines.append(
                "- {id} | owner={owner} | accepts={accepts} | workflow={workflow} | next_step={next_step}".format(
                    id=normalize_text(task.get("id")) or "-",
                    owner=normalize_text(task.get("owner")) or "-",
                    accepts=normalize_text(task.get("accepts_result")) or "-",
                    workflow=normalize_text(task.get("workflow")) or "-",
                    next_step=normalize_text(task.get("next_step")) or "-",
                )
            )
            lines.extend(owner_gate_lines(task, indent="  - "))

    lines.extend(["", "## Workflow Contracts"])
    if used_workflow_ids:
        for workflow_id in used_workflow_ids:
            workflow = workflow_lookup.get(workflow_id)
            if not workflow:
                lines.append(f"- {workflow_id}: missing from workflow-registry.json")
                continue
            lines.extend(
                [
                    f"- Workflow: {workflow_id}",
                    f"  purpose: {normalize_text(workflow.get('purpose')) or '-'}",
                    "  states: " + ", ".join(normalize_text(item) for item in workflow.get("states", []) or []),
                    "  required_task_fields: "
                    + ", ".join(
                        normalize_text(item) for item in workflow.get("required_task_fields", []) or []
                    ),
                    "  required_telemetry_events: "
                    + ", ".join(
                        normalize_text(item)
                        for item in workflow.get("required_telemetry_events", []) or []
                    ),
                ]
            )
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Policy Surface",
            "- human_only_actions:",
        ]
    )
    for item in (policies.get("approvals", {}) or {}).get("human_only_actions", []) or []:
        lines.append(f"  - {normalize_text(item)}")
    lines.append("- governor_review_required_for:")
    for item in (policies.get("approvals", {}) or {}).get("governor_review_required_for", []) or []:
        lines.append(f"  - {normalize_text(item)}")
    lines.append(
        "- telemetry_event_types: "
        + ", ".join(
            normalize_text(item)
            for item in ((workflow_registry.get("telemetry", {}) or {}).get("event_types", []) or [])
        )
    )
    lines.append(
        "- telemetry_statuses: "
        + ", ".join(
            normalize_text(item)
            for item in ((workflow_registry.get("telemetry", {}) or {}).get("statuses", []) or [])
        )
    )
    return "\n".join(lines) + "\n"


def write_workflow_artifact(
    active_work: dict[str, Any],
    workflow_registry: dict[str, Any],
    policies: dict[str, Any],
    execution_config: dict[str, Any],
    execution_config_state: str,
) -> None:
    write_text(
        WORKFLOW_ARTIFACT_PATH,
        render_workflow_artifact(
            active_work,
            workflow_registry,
            policies,
            execution_config,
            execution_config_state,
        ),
    )


def normalize_generated_artifact_content(path: Path, content: str) -> str:
    if path == WORKFLOW_ARTIFACT_PATH:
        lines = [
            line
            for line in content.splitlines()
            if not line.startswith("- Generated At:")
        ]
        return "\n".join(lines).rstrip() + "\n"
    return content


def generated_artifact_check_issues(bundle: dict[str, Any]) -> list[str]:
    expected_artifacts = [
        (TASK_BOARD_PATH, render_board(bundle["active_work"], bundle["workflow_registry"])),
        (
            WORKFLOW_ARTIFACT_PATH,
            render_workflow_artifact(
                bundle["active_work"],
                bundle["workflow_registry"],
                bundle["policies"],
                bundle["execution_config"],
                bundle["execution_config_state"],
            ),
        ),
    ]
    issues: list[str] = []
    for path, expected in expected_artifacts:
        if not path.exists():
            issues.append(f"missing generated artifact: {relative_display(path)}")
            continue
        actual = path.read_text(encoding="utf-8")
        if normalize_generated_artifact_content(path, actual) != normalize_generated_artifact_content(path, expected):
            issues.append(f"stale generated artifact: {relative_display(path)}")
    return issues


def generated_check_command(_: argparse.Namespace) -> int:
    bundle = validate_control_plane()
    issues = generated_artifact_check_issues(bundle)
    if issues:
        print("generated_check=failed")
        print(f"issues={len(issues)}")
        for issue in issues:
            print(f"- {issue}")
        print("recommended_next_command=python3 scripts/hq_control_plane.py sync")
        return 1
    print("generated_check=ok")
    print("issues=0")
    return 0


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


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


def parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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
    candidates: list[datetime] = []
    manifest_path = path.parent / "manifest.json"
    if manifest_path.exists():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        updated_at = normalize_text(payload.get("updated_at"))
        if updated_at:
            parsed_manifest = parse_datetime(updated_at)
            if parsed_manifest is not None:
                candidates.append(parsed_manifest)
    if not path.exists():
        return max(candidates).date().isoformat() if candidates else ""
    content = path.read_text(encoding="utf-8")
    matches = DATE_PATTERN.findall("\n".join(content.splitlines()[:80]))
    parsed_matches = [parse_datetime(item) for item in matches]
    candidates.extend(item for item in parsed_matches if item is not None)
    if not candidates:
        return ""
    latest = max(candidates)
    return latest.date().isoformat()


def sort_tasks(
    tasks: list[dict[str, Any]],
    workflow_registry: dict[str, Any],
) -> list[dict[str, Any]]:
    column_order, _ = get_board_columns(workflow_registry)
    priority = {column: index for index, column in enumerate(column_order)}
    return [
        task
        for _, task in sorted(
            enumerate(tasks),
            key=lambda item: (
                priority.get(normalize_text(item[1].get("column")), len(priority)),
                item[0],
            ),
        )
    ]


def project_live_task(task: dict[str, Any]) -> dict[str, Any]:
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
        "owner_gate": task.get("owner_gate") if isinstance(task.get("owner_gate"), dict) else {},
    }


def project_workflow_input_task(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": normalize_text(task.get("id")),
        "title": normalize_text(task.get("title")),
        "project": normalize_text(task.get("project")),
        "owner": normalize_text(task.get("owner")),
        "manager": normalize_text(task.get("manager")),
        "column": normalize_text(task.get("column")),
        "next_step": normalize_text(task.get("next_step")),
        "done_when": normalize_text(task.get("done_when")),
        "primary_update_file": normalize_text(task.get("primary_update_file")),
        "accepts_result": normalize_text(task.get("accepts_result")),
        "risk_tier": normalize_text(task.get("risk_tier")),
        "autonomy_tier": normalize_text(task.get("autonomy_tier")),
        "workflow": normalize_text(task.get("workflow")),
        "support": [
            normalize_text(item)
            for item in task.get("support", []) or []
            if normalize_text(item)
        ],
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


def format_stale_item_warning(item: dict[str, str]) -> str:
    task_id = normalize_text(item.get("task_id")) or "<unknown>"
    kind = normalize_text(item.get("kind")) or "packet"
    status = normalize_text(item.get("status"))
    path = normalize_text(item.get("path"))
    reason = normalize_text(item.get("reason"))
    if status == "missing":
        return f"missing {kind} packet: {path} (task={task_id})"
    if status == "stale":
        updated_at = normalize_text(item.get("updated_at"))
        detail = f", updated_at={updated_at}" if updated_at else ""
        return f"stale {kind} packet: {path} (task={task_id}{detail}; {reason})"
    return f"{status or 'stale'} {kind} packet: {path} (task={task_id}; {reason})"


def stale_runtime_packet_warnings(active_work: dict[str, Any]) -> list[str]:
    tasks = [
        task
        for task in active_work.get("tasks", []) or []
        if isinstance(task, dict) and normalize_text(task.get("column")) != "done"
    ]
    return [
        format_stale_item_warning(item)
        for item in collect_stale_items(tasks, normalize_text(active_work.get("updated_at")))
    ]


def is_strict_execution(execution_config: dict[str, Any]) -> bool:
    execution_profile = execution_config.get("execution_profile") or {}
    return (
        normalize_text(execution_config.get("profile")) == "strict"
        or normalize_text(execution_config.get("workflow_mode")) == "strict"
        or normalize_text(execution_profile.get("verification_depth")) == "strict"
    )


def telemetry_metric_label(metric: Any) -> str:
    if isinstance(metric, str):
        return normalize_text(metric)
    if isinstance(metric, dict):
        metric_id = normalize_text(metric.get("metric_id")) or normalize_text(metric.get("id")) or "unknown_metric"
        action = normalize_text(metric.get("action"))
        return " | ".join(part for part in (metric_id, action) if part)
    return "unknown_metric"


def load_breached_metrics() -> list[str]:
    if not TELEMETRY_REVIEW_PATH.exists():
        return []
    payload = load_json(TELEMETRY_REVIEW_PATH)
    if not isinstance(payload, dict):
        return []
    breached_metrics = payload.get("breached_metrics", []) or []
    if not isinstance(breached_metrics, list):
        return []
    return [
        telemetry_metric_label(metric)
        for metric in breached_metrics
        if telemetry_metric_label(metric)
    ]


def workflow_requirements(workflow_registry: dict[str, Any]) -> dict[str, list[str]]:
    requirements: dict[str, list[str]] = {}
    for workflow in workflow_registry.get("workflows", []) or []:
        if not isinstance(workflow, dict):
            continue
        workflow_id = normalize_text(workflow.get("id"))
        if not workflow_id:
            continue
        requirements[workflow_id] = [
            normalize_text(item)
            for item in workflow.get("required_task_fields", []) or []
            if normalize_text(item)
        ]
    return requirements


def founder_weekly_review_contract_policy() -> dict[str, Any]:
    return {
        "policy_version": 1,
        "contract_name": "founder_weekly_review_snapshot",
        "schema_path": relative_display(FOUNDER_WEEKLY_REVIEW_BRIDGE_SCHEMA_PATH),
        "schema_version": 1,
        "versioning": {
            "current_version": 1,
            "minimum_consumer_version": 1,
            "maximum_consumer_version": 1,
            "additive_change_rule": "New fields must remain optional within a contract version.",
            "breaking_change_rule": (
                "Renamed, removed, or newly required fields require a contract_version bump."
            ),
        },
    }


def validate_founder_weekly_review_input(payload: dict[str, Any]) -> None:
    context = ValidationContext()
    validate_schema(
        payload,
        FOUNDER_WEEKLY_REVIEW_BRIDGE_SCHEMA_PATH,
        "workflow_inputs.founder_weekly_review",
        context,
    )
    context.raise_if_any()


def build_founder_weekly_review_input(
    active_work: dict[str, Any],
    workflow_registry: dict[str, Any],
) -> dict[str, Any]:
    tasks = [
        task
        for task in active_work.get("tasks", []) or []
        if isinstance(task, dict)
    ]
    live_tasks = [
        task for task in tasks if normalize_text(task.get("column")) != "done"
    ]
    ordered_live_tasks = sort_tasks(live_tasks, workflow_registry)
    actionable_count = sum(
        1 for task in ordered_live_tasks if normalize_text(task.get("column")) in ACTIONABLE_COLUMNS
    )
    founder_review_count = sum(
        1
        for task in ordered_live_tasks
        if normalize_text(task.get("accepts_result")) == "ceo"
        and (
            normalize_text(task.get("risk_tier")) == "high"
            or normalize_text(task.get("column")) == "review"
        )
    )
    payload = {
        "contract_version": 1,
        "contract_policy": founder_weekly_review_contract_policy(),
        "source_files": {
            "active_work": relative_display(ACTIVE_WORK_PATH),
            "workflow_registry": relative_display(WORKFLOW_REGISTRY_PATH),
            "operating_policies": relative_display(POLICIES_PATH),
            "telemetry_review": relative_display(TELEMETRY_REVIEW_PATH)
            if TELEMETRY_REVIEW_PATH.exists()
            else "",
        },
        "active_tasks": [project_workflow_input_task(task) for task in ordered_live_tasks],
        "workflow_requirements": workflow_requirements(workflow_registry),
        "breached_metrics": load_breached_metrics(),
        "metadata": {
            "total_tasks": len(tasks),
            "active_tasks": len(ordered_live_tasks),
            "actionable_tasks": actionable_count,
            "founder_review_tasks": founder_review_count,
        },
    }
    validate_founder_weekly_review_input(payload)
    return payload


def scaffolded_packet_stale_items(
    tasks: list[dict[str, Any]],
    created_packets: list[dict[str, str]] | None,
) -> list[dict[str, str]]:
    if not created_packets:
        return []
    task_lookup = {
        normalize_text(task.get("id")): task
        for task in tasks
        if normalize_text(task.get("id"))
    }
    stale_items: list[dict[str, str]] = []
    for item in created_packets:
        task_id = normalize_text(item.get("task_id"))
        kind = normalize_text(item.get("kind"))
        path = normalize_text(item.get("path"))
        task = task_lookup.get(task_id, {})
        stale_items.append(
            {
                "task_id": task_id,
                "task_title": normalize_text(task.get("title")),
                "kind": kind,
                "status": "stale",
                "path": path,
                "reason": f"Placeholder {kind} packet was scaffolded during status and still needs real content.",
            }
        )
    return stale_items


def summarize_stale_items(stale_items: list[dict[str, str]]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    for item in stale_items:
        status = normalize_text(item.get("status")) or "unknown"
        kind = normalize_text(item.get("kind")) or "unknown"
        by_status[status] = by_status.get(status, 0) + 1
        by_kind[kind] = by_kind.get(kind, 0) + 1
    return {
        "total": len(stale_items),
        "by_status": by_status,
        "by_kind": by_kind,
    }


def build_memory_index(status_payload: dict[str, Any]) -> dict[str, Any]:
    active_tasks = status_payload.get("active_tasks", []) or []
    blocked_tasks = status_payload.get("blocked", []) or []
    runtime_recovery = status_payload.get("runtime_recovery") or {}
    runtime_recovery_items = runtime_recovery.get("items", []) or []
    recent_iterations = status_payload.get("recent_iterations", []) or []
    return {
        "generated_at": status_payload.get("generated_at") or "",
        "updated_at": status_payload.get("updated_at") or "",
        "objective": status_payload.get("objective") or "",
        "startup_focus": status_payload.get("startup_focus") or {},
        "support_tracks": status_payload.get("support_tracks", []) or [],
        "recent_iterations": recent_iterations,
        "stale_summary": status_payload.get("stale_summary") or {},
        "runtime_recovery": {
            "summary": runtime_recovery.get("summary") or {},
            "first_run": runtime_recovery_items[0] if runtime_recovery_items else {},
        },
        "recommended_next_command": status_payload.get("recommended_next_command") or "",
        "counts": {
            "active_tasks": len(active_tasks),
            "blocked_tasks": len(blocked_tasks),
        },
    }


def runtime_recovery_command(runtime_recovery: dict[str, Any] | None) -> str:
    items = (runtime_recovery or {}).get("items", []) or []
    for item in items:
        command = normalize_text(item.get("recommended_next_command"))
        if command:
            return command
    return ""


def runtime_recovery_sort_key(item: dict[str, Any]) -> tuple[int, float, str]:
    if item.get("safe_to_resume"):
        priority = 0
    elif item.get("resumable"):
        priority = 1
    elif normalize_text(item.get("run_status")) == "interrupted":
        priority = 2
    else:
        priority = 3
    updated_at = parse_datetime(normalize_text(item.get("updated_at")))
    timestamp = updated_at.timestamp() if updated_at is not None else 0.0
    return (priority, -timestamp, normalize_text(item.get("run_id")))


def summarize_runtime_recovery(items: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total": len(items),
        "interrupted": sum(1 for item in items if normalize_text(item.get("run_status")) == "interrupted"),
        "resumable": sum(1 for item in items if bool(item.get("resumable"))),
        "safe_to_resume": sum(1 for item in items if bool(item.get("safe_to_resume"))),
        "needs_handoff_refresh": sum(1 for item in items if bool(item.get("needs_handoff_refresh"))),
        "missing_resume_status": sum(
            1 for item in items if normalize_text(item.get("resume_status_state")) == "missing"
        ),
        "invalid_resume_status": sum(
            1 for item in items if normalize_text(item.get("resume_status_state")) == "invalid"
        ),
    }


def build_runtime_recovery_payload() -> dict[str, Any]:
    if not MISSION_RUNTIME_RUNS_DIR.exists():
        items: list[dict[str, Any]] = []
        return {"summary": summarize_runtime_recovery(items), "items": items}

    items: list[dict[str, Any]] = []
    for run_file in sorted(MISSION_RUNTIME_RUNS_DIR.glob("*.json")):
        run, run_error = load_json_object_safe(run_file)
        if run is None:
            items.append(
                {
                    "run_id": run_file.stem,
                    "mission_id": "",
                    "thread_id": "",
                    "run_status": "unknown",
                    "updated_at": "",
                    "resumable": False,
                    "safe_to_resume": False,
                    "needs_handoff_refresh": False,
                    "resume_reason": "",
                    "resume_epoch": 0,
                    "latest_checkpoint_id": "",
                    "latest_checkpoint_path": "",
                    "resume_status_path": "",
                    "resume_status_state": "invalid",
                    "stale_inputs": [],
                    "error": run_error,
                    "recommended_next_command": "",
                }
            )
            continue

        run_id = normalize_text(run.get("id")) or run_file.stem
        run_status = normalize_text(run.get("status"))
        resume_status_path_text = normalize_text(run.get("resume_status_path"))
        if resume_status_path_text:
            resume_status_file = resolve_runtime_path(resume_status_path_text)
        else:
            resume_status_file = MISSION_RUNTIME_RESUME_STATUS_DIR / f"{run_id}.json"
            if resume_status_file.exists():
                resume_status_path_text = relative_display(resume_status_file)
        has_resume_status_reference = bool(resume_status_path_text) or resume_status_file.exists()

        resume_status, resume_error = load_json_object_safe(resume_status_file)
        if resume_status is None and resume_error == "missing":
            resume_status_state = "missing"
        elif resume_status is None:
            resume_status_state = "invalid"
        else:
            resume_status_state = "ok"
            if not resume_status_path_text:
                resume_status_path_text = relative_display(resume_status_file)

        resumable = bool(resume_status.get("resumable")) if resume_status else False
        safe_to_resume = bool(resume_status.get("safe_to_resume")) if resume_status else False
        needs_handoff_refresh = bool(resume_status.get("needs_handoff_refresh")) if resume_status else False
        stale_inputs = resume_status.get("stale_inputs") if isinstance(resume_status, dict) else []
        stale_inputs = stale_inputs if isinstance(stale_inputs, list) else []
        resume_reason = ""
        if resume_status is not None:
            resume_reason = normalize_text(resume_status.get("resume_reason"))
        elif run_status == "interrupted":
            resume_reason = "resume-status missing for interrupted run"
        latest_checkpoint_id = normalize_text(
            (resume_status or {}).get("latest_checkpoint_id") or run.get("latest_checkpoint_id")
        )
        latest_checkpoint_path = normalize_text(
            (resume_status or {}).get("latest_checkpoint_path") or run.get("latest_checkpoint_path")
        )
        item = {
            "run_id": run_id,
            "mission_id": normalize_text(run.get("mission_id")),
            "thread_id": normalize_text(run.get("thread_id")),
            "run_status": run_status,
            "updated_at": normalize_text((resume_status or {}).get("updated_at") or run.get("updated_at")),
            "resumable": resumable,
            "safe_to_resume": safe_to_resume,
            "needs_handoff_refresh": needs_handoff_refresh,
            "resume_reason": resume_reason,
            "resume_epoch": parse_int((resume_status or {}).get("resume_epoch", 0), 0),
            "latest_checkpoint_id": latest_checkpoint_id,
            "latest_checkpoint_path": latest_checkpoint_path,
            "resume_status_path": resume_status_path_text,
            "resume_status_state": resume_status_state,
            "stale_inputs": [normalize_text(value) for value in stale_inputs if normalize_text(value)],
            "error": resume_error if resume_status is None else "",
            "recommended_next_command": (
                f"python3 scripts/hq_mission_runtime.py export-recovery-bundle --run-id {run_id}"
                if run_id
                else ""
            ),
        }
        should_include = run_status == "interrupted"
        if has_resume_status_reference and (
            resume_status_state != "ok" or resumable or safe_to_resume or needs_handoff_refresh
        ):
            should_include = True
        if should_include:
            items.append(item)

    items = sorted(items, key=runtime_recovery_sort_key)
    return {
        "summary": summarize_runtime_recovery(items),
        "items": items,
    }


def recommended_next_command(
    active_tasks: list[dict[str, Any]],
    runtime_recovery: dict[str, Any] | None = None,
) -> str:
    recovery_command = runtime_recovery_command(runtime_recovery)
    if recovery_command:
        return recovery_command
    if any(normalize_text(task.get("column")) in ACTIONABLE_COLUMNS for task in active_tasks):
        return "python3 scripts/hq_runtime.py route-next-slice"
    return "python3 scripts/hq_control_plane.py validate"


def packet_heading(kind: str) -> str:
    return "Spec" if kind == "spec" else "Handoff"


def placeholder_packet_markdown(task: dict[str, Any], kind: str, updated_at: str) -> str:
    title = normalize_text(task.get("title")) or normalize_text(task.get("id")) or "Untitled task"
    task_id = normalize_text(task.get("id"))
    owner = normalize_text(task.get("owner")) or "Unassigned"
    primary_update_file = normalize_text(task.get("primary_update_file")) or "Not set"
    next_step = normalize_text(task.get("next_step")) or "Not set"
    if kind == "spec":
        sections = [
            "## Why Now",
            "",
            "## In Scope",
            "",
            "## Out Of Scope",
            "",
            "## Acceptance",
            "",
            "## Notes",
            "",
        ]
    else:
        sections = [
            "## Done",
            "",
            "## Next",
            "",
            "## Blockers",
            "",
            "## Notes",
            "",
        ]
    return "\n".join(
        [
            f"# {packet_heading(kind)}",
            "",
            f"- Task ID: {task_id or '-'}",
            f"- Task: {title}",
            f"- Updated At: {updated_at}",
            f"- Owner: {owner}",
            f"- Primary Update File: {primary_update_file}",
            f"- Queue Next Step: {next_step}",
            "",
            *sections,
        ]
    )


def placeholder_packet_manifest(task: dict[str, Any], kind: str, packet_path_value: Path, updated_at: str) -> dict[str, str]:
    relative_packet = relative_display(packet_path_value)
    return {
        "task": normalize_text(task.get("title")) or normalize_text(task.get("id")),
        "task_slug": packet_task_slug(task),
        "kind": kind,
        "owner": normalize_text(task.get("owner")),
        "updated_at": updated_at,
        "latest_file": relative_packet,
        "session_file": relative_packet,
        "primary_file": normalize_text(task.get("primary_update_file")),
    }


def ensure_task_packet(task: dict[str, Any], kind: str) -> bool:
    current_path = packet_path(task, kind)
    manifest_path = current_path.parent / "manifest.json"
    if current_path.exists() and manifest_path.exists():
        return False

    updated_at = utc_now()
    if not current_path.exists():
        write_text(current_path, placeholder_packet_markdown(task, kind, updated_at))
    if not manifest_path.exists():
        write_json(manifest_path, placeholder_packet_manifest(task, kind, current_path, updated_at))
    return True


def ensure_task_packets(tasks: list[dict[str, Any]]) -> list[str]:
    created: list[dict[str, str]] = []
    for task in tasks:
        task_id = normalize_text(task.get("id"))
        for kind in STALE_PACKET_KINDS:
            if ensure_task_packet(task, kind):
                created.append(
                    {
                        "task_id": task_id,
                        "kind": kind,
                        "path": relative_display(packet_path(task, kind)),
                    }
                )
    return created


def find_task(active_work: dict[str, Any], task_id: str) -> dict[str, Any] | None:
    for task in active_work.get("tasks", []) or []:
        if isinstance(task, dict) and normalize_text(task.get("id")) == task_id:
            return task
    return None


def has_meaningful_items(items: list[str]) -> bool:
    return any(normalize_text(item).lower() not in {"", "none", "none.", "n/a", "na"} for item in items)


def task_packet_paths(task: dict[str, Any]) -> dict[str, Path]:
    return {kind: packet_path(task, kind) for kind in STALE_PACKET_KINDS}


def task_packet_summary(task: dict[str, Any]) -> dict[str, str]:
    paths = task_packet_paths(task)
    return {
        "id": normalize_text(task.get("id")),
        "title": normalize_text(task.get("title")),
        "column": normalize_text(task.get("column")),
        "spec": relative_display(paths["spec"]),
        "handoff": relative_display(paths["handoff"]),
    }


def minimal_read_first(task: dict[str, Any]) -> list[str]:
    items = [normalize_text(task.get("primary_update_file"))]
    items.extend(relative_display(path) for path in task_packet_paths(task).values())
    normalized = [item for item in items if item]
    return list(dict.fromkeys(normalized))


def startup_focus_projection(task: dict[str, Any] | None) -> dict[str, Any]:
    if not task:
        return {}
    return {
        "id": normalize_text(task.get("id")),
        "title": normalize_text(task.get("title")),
        "column": normalize_text(task.get("column")),
        "owner": normalize_text(task.get("owner")),
        "manager": normalize_text(task.get("manager")),
        "project": normalize_text(task.get("project")),
        "next_step": normalize_text(task.get("next_step")),
        "primary_update_file": normalize_text(task.get("primary_update_file")),
        "minimal_read_first": minimal_read_first(task),
        "recommended_next_command": recommended_task_command(task, task_missing_for_safe_continue(task)),
    }


def support_track_projection(tasks: list[dict[str, Any]], startup_task: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not startup_task:
        return []
    support_tracks: list[dict[str, Any]] = []
    for task in choose_parallel_support_tasks(startup_task, tasks, limit=2):
        support_tracks.append(
            {
                "id": normalize_text(task.get("id")),
                "title": normalize_text(task.get("title")),
                "column": normalize_text(task.get("column")),
                "owner": normalize_text(task.get("owner")),
                "project": normalize_text(task.get("project")),
                "next_step": normalize_text(task.get("next_step")),
                "minimal_read_first": minimal_read_first(task),
                "recommended_next_command": recommended_task_command(task, task_missing_for_safe_continue(task)),
            }
        )
        if len(support_tracks) == 2:
            break
    return support_tracks


def startup_focus_task(tasks: list[dict[str, Any]]) -> dict[str, Any] | None:
    for preferred_column in ("executing", "review", "this_week", "scheduled", "policy_check", "triage", "intake"):
        for task in tasks:
            if normalize_text(task.get("column")) == preferred_column:
                return task
    return tasks[0] if tasks else None


def choose_parallel_support_tasks(
    primary: dict[str, Any],
    tasks: list[dict[str, Any]],
    *,
    limit: int = 2,
) -> list[dict[str, Any]]:
    primary_id = normalize_text(primary.get("id"))
    primary_column = normalize_text(primary.get("column"))
    primary_project = normalize_text(primary.get("project"))
    same_project_preferred: list[dict[str, Any]] = []
    cross_project_preferred: list[dict[str, Any]] = []
    same_project_fallback: list[dict[str, Any]] = []
    cross_project_fallback: list[dict[str, Any]] = []

    for task in tasks:
        task_id = normalize_text(task.get("id"))
        if task_id == primary_id:
            continue
        task_column = normalize_text(task.get("column"))
        if task_column in {"blocked", "waiting", "accepted", "synced", "done"}:
            continue
        task_project = normalize_text(task.get("project"))
        same_project = bool(primary_project and task_project == primary_project)

        is_preferred = False
        if primary_column == "review" and task_column == "executing":
            is_preferred = True
        elif primary_column == "executing" and task_column in {"executing", "review", "this_week"}:
            is_preferred = True
        elif primary_column == "this_week" and task_column in {"executing", "review", "this_week"}:
            is_preferred = True

        if same_project and is_preferred:
            same_project_preferred.append(task)
        elif is_preferred:
            cross_project_preferred.append(task)
        elif same_project:
            same_project_fallback.append(task)
        else:
            cross_project_fallback.append(task)

    ordered = same_project_preferred + cross_project_preferred + same_project_fallback + cross_project_fallback
    return ordered[:limit]


def task_missing_for_safe_continue(task: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    paths = task_packet_paths(task)
    spec_path = paths["spec"]
    handoff_path = paths["handoff"]

    if not spec_path.exists():
        missing.append(f"spec packet missing: {relative_display(spec_path)}")
    if not handoff_path.exists():
        missing.append(f"handoff packet missing: {relative_display(handoff_path)}")

    if spec_path.exists() and not has_meaningful_items(extract_section_items(spec_path, "Acceptance")):
        missing.append("spec acceptance is still empty")
    if handoff_path.exists() and not has_meaningful_items(extract_section_items(handoff_path, "Next")):
        missing.append("handoff next steps are still empty")
    if handoff_path.exists() and has_meaningful_items(extract_section_items(handoff_path, "Blockers")):
        missing.append("handoff still lists blockers")

    primary_update_file = normalize_text(task.get("primary_update_file"))
    if primary_update_file and not (REPO_ROOT / primary_update_file).exists():
        missing.append(f"primary update file is missing: {primary_update_file}")
    if not normalize_text(task.get("done_when")):
        missing.append("done_when is missing from the task contract")
    return missing


def can_auto_closeout(task: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if normalize_text(task.get("risk_tier")) not in {"low", "medium"}:
        reasons.append("closeout only supports low/medium risk tasks")
    if normalize_text(task.get("autonomy_tier")) == "A1":
        reasons.append("founder acceptance is still required for A1 work")
    if normalize_text(task.get("accepts_result")) == "ceo":
        reasons.append("founder acceptance is still required for this task")
    if normalize_text(task.get("column")) in {"blocked", "review", "done"}:
        reasons.append(f"task is currently in '{normalize_text(task.get('column'))}' and is not on the happy path")
    return not reasons, reasons


def write_closeout_telemetry(task: dict[str, Any], completed_at: str) -> int:
    """Write minimal acceptance + sync telemetry events for a closeout.

    Returns the number of events written.  Telemetry is stored as JSONL
    under TELEMETRY_ROOT, mirroring the layout used by hq_telemetry_store.
    """
    task_id = normalize_text(task.get("id"))
    day = completed_at[:10]
    month = day[:7]
    telemetry_dir = TELEMETRY_ROOT / month
    telemetry_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = telemetry_dir / f"{day}.jsonl"

    events = []
    for event_type in ("acceptance", "sync"):
        events.append(
            {
                "id": str(uuid.uuid4()),
                "created_at": completed_at,
                "event_type": event_type,
                "agent": "hq_control_plane",
                "task_id": task_id,
                "status": "ok",
                "workflow": normalize_text(task.get("workflow")),
                "risk_tier": normalize_text(task.get("risk_tier")),
                "autonomy_tier": normalize_text(task.get("autonomy_tier")),
                "summary": f"Auto-closeout {event_type} for task {task_id}.",
            }
        )

    with jsonl_path.open("a", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    return len(events)


def task_summary_lines(task: dict[str, Any]) -> list[str]:
    lines = [
        f"- Task ID: {normalize_text(task.get('id'))}",
        f"- Title: {normalize_text(task.get('title'))}",
        f"- Project: {normalize_text(task.get('project'))}",
        f"- Column: {normalize_text(task.get('column'))}",
        f"- Owner: {normalize_text(task.get('owner'))}",
        f"- Manager: {normalize_text(task.get('manager'))}",
        f"- Accepts Result: {normalize_text(task.get('accepts_result'))}",
        f"- Risk / Autonomy: {normalize_text(task.get('risk_tier'))} / {normalize_text(task.get('autonomy_tier'))}",
        f"- Done When: {normalize_text(task.get('done_when')) or '-'}",
    ]
    lines.extend(owner_gate_lines(task, indent="- "))
    return lines


def render_recommended_next_command(command: str) -> str:
    return "\n".join(["", "Recommended Next Command", f"- {command}"])


def recommended_task_command(task: dict[str, Any], missing: list[str]) -> str:
    task_id = normalize_text(task.get("id"))
    if not missing:
        closeout_ready, closeout_reasons = can_auto_closeout(task)
        if closeout_ready and not closeout_reasons:
            return f"python3 scripts/hq_control_plane.py closeout --task-id {task_id}"
    return "python3 scripts/hq_control_plane.py status"


def quick_context_markdown(task: dict[str, Any], missing: list[str]) -> str:
    paths = task_packet_paths(task)
    lines = [
        "# QUICK_CONTEXT",
        "",
        "> Projection only. Source of truth remains `05 AI Control Plane/active-work.json` and the current `.hq/specs/` / `.hq/handoffs/` packets.",
        "",
        "## Task Contract Summary",
        *task_summary_lines(task),
        "",
        "## Current Packets",
        f"- Spec: {relative_display(paths['spec'])}",
        f"- Handoff: {relative_display(paths['handoff'])}",
        "",
        "## Current Next Step",
        f"- {normalize_text(task.get('next_step')) or '-'}",
        "",
        "## Missing For Safe Continue",
    ]
    if missing:
        lines.extend(f"- {item}" for item in missing)
    else:
        lines.append("- None")
    lines.extend(["", "## Recommended Next Command", f"- {recommended_task_command(task, missing)}", ""])
    return "\n".join(lines)


def write_quick_context(task: dict[str, Any], missing: list[str]) -> None:
    write_text(QUICK_CONTEXT_PATH, quick_context_markdown(task, missing))


def render_resume_text(task: dict[str, Any], missing: list[str]) -> str:
    paths = task_packet_paths(task)
    lines = [
        "Resume Task",
        *task_summary_lines(task),
        "",
        "Current Packets",
        f"- Spec: {relative_display(paths['spec'])}",
        f"- Handoff: {relative_display(paths['handoff'])}",
        "",
        "Current Next Step",
        f"- {normalize_text(task.get('next_step')) or '-'}",
        "",
        "Missing For Safe Continue",
    ]
    if missing:
        lines.extend(f"- {item}" for item in missing)
    else:
        lines.append("- None")
    lines.append(render_recommended_next_command(recommended_task_command(task, missing)))
    return "\n".join(lines) + "\n"


def git_status_lines() -> list[str]:
    try:
        completed = subprocess.run(
            ["git", "status", "--short", "--branch"],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )
        output = (completed.stdout or "").strip().splitlines()
        return output or ["clean"]
    except subprocess.CalledProcessError as exc:
        output = (exc.stdout or exc.stderr or "").strip().splitlines()
        return output or ["git failure"]


def load_archived_tasks() -> dict[str, Any]:
    if not ARCHIVED_TASKS_PATH.exists():
        return {"generated_at": "", "source_updated_at": "", "tasks": []}
    payload = load_json(ARCHIVED_TASKS_PATH)
    if not isinstance(payload, dict):
        raise ValidationError(f"invalid archive payload in {relative_display(ARCHIVED_TASKS_PATH)}: expected object")
    tasks = payload.get("tasks", [])
    if tasks is None:
        tasks = []
    if not isinstance(tasks, list):
        raise ValidationError(f"invalid archive payload in {relative_display(ARCHIVED_TASKS_PATH)}: tasks must be a list")
    return {
        "generated_at": normalize_text(payload.get("generated_at")),
        "source_updated_at": normalize_text(payload.get("source_updated_at")),
        "tasks": [task for task in tasks if isinstance(task, dict)],
    }


def merge_archived_tasks(existing: list[dict[str, Any]], new: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for task in existing:
        task_id = normalize_text(task.get("id"))
        if not task_id or task_id in merged:
            continue
        order.append(task_id)
        merged[task_id] = task
    for task in new:
        task_id = normalize_text(task.get("id"))
        if not task_id:
            continue
        if task_id not in merged:
            order.append(task_id)
        merged[task_id] = task
    return [merged[task_id] for task_id in order]


def archive_projection(active_work: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    tasks = [task for task in active_work.get("tasks", []) or [] if isinstance(task, dict)]
    done_tasks = [task for task in tasks if normalize_text(task.get("column")) == "done"]
    live_tasks = [task for task in tasks if normalize_text(task.get("column")) != "done"]
    archived_at = utc_now()
    archived_tasks = [{**task, "archived_at": archived_at} for task in done_tasks]
    existing_archive = load_archived_tasks()
    archive_payload = {
        "generated_at": archived_at,
        "source_updated_at": normalize_text(active_work.get("updated_at")),
        "tasks": merge_archived_tasks(existing_archive.get("tasks", []), archived_tasks),
    }
    return done_tasks, live_tasks, archive_payload


def build_status_payload(
    active_work: dict[str, Any],
    workflow_registry: dict[str, Any],
    *,
    created_packets: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    live_tasks = [
        task
        for task in active_work.get("tasks", []) or []
        if isinstance(task, dict) and normalize_text(task.get("column")) != "done"
    ]
    ordered_live_tasks = sort_tasks(live_tasks, workflow_registry)
    startup_task = startup_focus_task(ordered_live_tasks)
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
    stale_items = collect_stale_items(ordered_live_tasks, normalize_text(active_work.get("updated_at")))
    stale_items.extend(scaffolded_packet_stale_items(ordered_live_tasks, created_packets))
    runtime_recovery = build_runtime_recovery_payload()
    live_task_ids = {
        normalize_text(task.get("id"))
        for task in ordered_live_tasks
        if normalize_text(task.get("id"))
    }
    recent_iterations = load_recent_iterations(
        PRIVATE_ROOT,
        limit=RECENT_ITERATION_LIMIT,
        task_ids=live_task_ids or None,
    )
    payload = {
        "generated_at": utc_now(),
        "updated_at": normalize_text(active_work.get("updated_at")),
        "objective": normalize_text(active_work.get("objective", {}).get("title")),
        "startup_focus": startup_focus_projection(startup_task),
        "runtime_recovery": runtime_recovery,
        "recent_iterations": recent_iterations,
        "support_tracks": support_track_projection(ordered_live_tasks, startup_task),
        "active_tasks": [project_live_task(task) for task in ordered_live_tasks],
        "current_packets": [task_packet_summary(task) for task in ordered_live_tasks],
        "minimal_read_first": minimal_read_first(startup_task) if startup_task else [],
        "blocked": blocked_tasks,
        "stale_items": stale_items,
        "stale_summary": summarize_stale_items(stale_items),
        "workflow_inputs": {
            "founder_weekly_review": build_founder_weekly_review_input(
                active_work,
                workflow_registry,
            )
        },
        "recommended_next_command": recommended_next_command(
            ordered_live_tasks,
            runtime_recovery,
        ),
    }
    return payload


def write_session_bootstrap(
    active_work: dict[str, Any],
    workflow_registry: dict[str, Any],
    *,
    created_packets: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    payload = build_status_payload(
        active_work,
        workflow_registry,
        created_packets=created_packets,
    )
    SESSION_BOOTSTRAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    SESSION_BOOTSTRAP_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    MEMORY_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_INDEX_PATH.write_text(
        json.dumps(build_memory_index(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def render_status_text(payload: dict[str, Any]) -> str:
    lines = [
        "Session Bootstrap",
        f"Objective: {payload.get('objective') or '-'}",
        f"Updated At: {payload.get('updated_at') or '-'}",
        f"Bootstrap File: {relative_display(SESSION_BOOTSTRAP_PATH)}",
        f"Workflow Artifact: {relative_display(WORKFLOW_ARTIFACT_PATH)}",
    ]
    startup_focus = payload.get("startup_focus") or {}
    if startup_focus:
        lines.extend(
            [
                "",
                "Startup Focus",
                (
                    f"- {startup_focus.get('id') or '-'} [{startup_focus.get('column') or '-'}] "
                    f"{startup_focus.get('title') or '-'} ({startup_focus.get('owner') or '-'})"
                ),
                f"- next_step: {startup_focus.get('next_step') or '-'}",
                f"- primary_update_file: {startup_focus.get('primary_update_file') or '-'}",
                f"- task_command: {startup_focus.get('recommended_next_command') or '-'}",
            ]
        )
        task = find_task({"tasks": payload.get("active_tasks", []) or []}, startup_focus.get("id") or "")
        if task:
            lines.extend(owner_gate_lines(task))
    lines.extend(["", "Recovery Queue"])
    runtime_recovery = payload.get("runtime_recovery") or {}
    recovery_items = runtime_recovery.get("items", []) or []
    recovery_summary = runtime_recovery.get("summary") or {}
    if recovery_items:
        summary_parts = [f"total={recovery_summary.get('total', len(recovery_items))}"]
        for key in (
            "interrupted",
            "resumable",
            "safe_to_resume",
            "needs_handoff_refresh",
            "missing_resume_status",
            "invalid_resume_status",
        ):
            value = recovery_summary.get(key, 0)
            if value:
                summary_parts.append(f"{key}={value}")
        lines.append("- " + " | ".join(summary_parts))
        for item in recovery_items[:5]:
            reason = item.get("resume_reason") or item.get("error") or "-"
            lines.append(
                f"- {item['run_id']} [{item['run_status'] or '-'}] mission={item['mission_id'] or '-'} | "
                f"safe_to_resume={str(bool(item.get('safe_to_resume'))).lower()} | "
                f"resume_epoch={item.get('resume_epoch', 0)} | reason: {reason} | "
                f"command: {item.get('recommended_next_command') or '-'}"
            )
        if len(recovery_items) > 5:
            lines.append(f"- ... {len(recovery_items) - 5} more recovery items hidden")
    else:
        lines.append("- None")

    lines.extend(["", "Recent Iterations"])
    recent_iterations = payload.get("recent_iterations", []) or []
    if recent_iterations:
        for item in recent_iterations:
            evidence = item.get("evidence") or []
            evidence_text = f" | evidence: {evidence[0]}" if evidence else ""
            lines.append(
                f"- {item.get('task_id') or '-'} [{item.get('status') or '-'}] "
                f"{item.get('hypothesis') or '-'} | next: {item.get('next_focus') or '-'}{evidence_text}"
            )
    else:
        lines.append("- None")

    lines.extend(["", "Support Tracks"])
    support_tracks = payload.get("support_tracks", []) or []
    if support_tracks:
        for task in support_tracks:
            lines.append(
                f"- {task['id']} [{task['column']}] {task['title']} ({task['owner']}) | next_step: {task['next_step'] or '-'}"
            )
    else:
        lines.append("- None")
    lines.extend(["", "Active Tasks"])
    active_tasks = payload.get("active_tasks", []) or []
    if active_tasks:
        for task in active_tasks:
            lines.append(
                f"- {task['id']} [{task['column']}] {task['title']} ({task['owner']}) | next_step: {task['next_step'] or '-'}"
            )
    else:
        lines.append("- None")

    lines.extend(["", "Current Packets"])
    current_packets = payload.get("current_packets", []) or []
    if current_packets:
        for item in current_packets:
            lines.append(
                f"- {item['id']} [{item['column']}] | spec: {item['spec']} | handoff: {item['handoff']}"
            )
    else:
        lines.append("- None")

    lines.extend(["", "Minimal Read First"])
    minimal_read = payload.get("minimal_read_first", []) or []
    if minimal_read:
        lines.extend(f"- {item}" for item in minimal_read)
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
    stale_summary = payload.get("stale_summary") or {}
    if stale_items:
        summary_parts: list[str] = []
        total = stale_summary.get("total")
        if isinstance(total, int):
            summary_parts.append(f"total={total}")
        by_status = stale_summary.get("by_status")
        if isinstance(by_status, dict) and by_status:
            summary_parts.append(
                "status=" + ", ".join(f"{key}:{value}" for key, value in sorted(by_status.items()))
            )
        by_kind = stale_summary.get("by_kind")
        if isinstance(by_kind, dict) and by_kind:
            summary_parts.append(
                "kind=" + ", ".join(f"{key}:{value}" for key, value in sorted(by_kind.items()))
            )
        if summary_parts:
            lines.append("- " + " | ".join(summary_parts))
        for item in stale_items[:5]:
            updated_at = f" | updated_at: {item['updated_at']}" if item.get("updated_at") else ""
            lines.append(
                f"- {item['task_id']} {item['kind']} [{item['status']}] {item['path']}{updated_at} | {item['reason']}"
            )
        if len(stale_items) > 5:
            lines.append(f"- ... {len(stale_items) - 5} more stale items hidden")
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
    live_tasks = [
        task
        for task in bundle["active_work"].get("tasks", []) or []
        if isinstance(task, dict) and normalize_text(task.get("column")) != "done"
    ]
    created_packets = ensure_task_packets(live_tasks)
    payload = write_session_bootstrap(
        bundle["active_work"],
        bundle["workflow_registry"],
        created_packets=created_packets,
    )
    write_workflow_artifact(
        bundle["active_work"],
        bundle["workflow_registry"],
        bundle["policies"],
        bundle["execution_config"],
        bundle["execution_config_state"],
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_status_text(payload), end="")
    return 0


def load_task_templates() -> tuple[Path, list[dict[str, str]]]:
    if TASK_TEMPLATES_JSON_PATH.exists():
        payload = load_json(TASK_TEMPLATES_JSON_PATH)
        templates: list[dict[str, str]] = []
        for item in payload.get("templates", []) or []:
            if not isinstance(item, dict):
                continue
            templates.append(
                {
                    "id": normalize_text(item.get("id")),
                    "title_pattern": normalize_text(item.get("title_pattern")),
                    "workflow": normalize_text(item.get("workflow")),
                    "default_owner": normalize_text(item.get("default_owner")),
                    "risk_tier": normalize_text(item.get("risk_tier")),
                    "autonomy_tier": normalize_text(item.get("autonomy_tier")),
                    "done_when_stub": normalize_text(item.get("done_when_stub")),
                }
            )
        return TASK_TEMPLATES_JSON_PATH, templates

    if TASK_TEMPLATES_MD_PATH.exists():
        templates: list[dict[str, str]] = []
        current: dict[str, str] | None = None
        for raw_line in TASK_TEMPLATES_MD_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line.startswith("## "):
                if current:
                    templates.append(current)
                current = {
                    "id": line.removeprefix("## ").strip().lower().replace(" ", "-"),
                    "title_pattern": "",
                    "workflow": "",
                    "default_owner": "",
                }
                continue
            if not current or not line.startswith("- "):
                continue
            key, _, value = line.removeprefix("- ").partition(":")
            normalized_key = key.strip().replace(" ", "_").lower()
            if normalized_key in current:
                current[normalized_key] = value.strip()
        if current:
            templates.append(current)
        return TASK_TEMPLATES_MD_PATH, templates

    raise ValidationError(
        "missing task templates file: expected 05 AI Control Plane/task-templates.json or task-templates.md"
    )


def templates_command(_: argparse.Namespace) -> int:
    path, templates = load_task_templates()
    print("templates=ok")
    print(f"path={relative_display(path)}")
    print(f"count={len(templates)}")
    for template in templates:
        print(
            "template="
            f"{template.get('id') or '-'}"
            f" owner={template.get('default_owner') or '-'}"
            f" workflow={template.get('workflow') or '-'}"
            f" title_pattern={template.get('title_pattern') or '-'}"
        )
    return 0


def slugify_task_id(title: str) -> str:
    """Generate a kebab-case task ID from a title."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:60] if slug else f"task-{utc_today().replace('-', '')}"


def create_task_command(args: argparse.Namespace) -> int:
    bundle = validate_control_plane()
    title = normalize_text(args.title)
    project = normalize_text(args.project)
    owner = normalize_text(args.owner) if args.owner else ""
    manager = normalize_text(args.manager) if args.manager else ""
    accepts_result = normalize_text(args.accepts_result) if args.accepts_result else ""
    workflow_id = normalize_text(args.workflow) if args.workflow else "intake-to-execution"
    risk_tier = normalize_text(args.risk_tier) if args.risk_tier else "medium"
    autonomy_tier = normalize_text(args.autonomy_tier) if args.autonomy_tier else "A2"
    done_when = normalize_text(args.done_when) if args.done_when else ""
    next_step = normalize_text(args.next_step) if args.next_step else "Triage and route."
    primary_update_file = normalize_text(args.primary_update_file) if args.primary_update_file else ""
    template_id = normalize_text(args.template) if args.template else ""
    task_id = normalize_text(args.task_id) if args.task_id else slugify_task_id(title)

    # Apply template defaults if requested
    if template_id:
        try:
            _, templates = load_task_templates()
        except ValidationError:
            templates = []
        template = next((t for t in templates if t.get("id") == template_id), None)
        if template:
            if not owner:
                owner = template.get("default_owner", "")
            if not workflow_id or workflow_id == "intake-to-execution":
                workflow_id = template.get("workflow", workflow_id) or workflow_id
            risk_tier = template.get("risk_tier", risk_tier) or risk_tier
            autonomy_tier = template.get("autonomy_tier", autonomy_tier) or autonomy_tier
            if not done_when:
                done_when = template.get("done_when_stub", "")

    # Validate roles
    role_ids = {
        normalize_text(role.get("id"))
        for role in bundle["agent_registry"].get("roles", []) or []
        if isinstance(role, dict)
    }
    errors: list[str] = []
    if owner and owner not in role_ids:
        errors.append(f"owner '{owner}' is not in agent-registry.json")
    if manager and manager not in role_ids:
        errors.append(f"manager '{manager}' is not in agent-registry.json")
    if accepts_result and accepts_result not in role_ids:
        errors.append(f"accepts_result '{accepts_result}' is not in agent-registry.json")

    # Check for duplicate task_id
    existing = find_task(bundle["active_work"], task_id)
    if existing is not None:
        errors.append(f"task_id '{task_id}' already exists in active-work.json")

    if errors:
        print("create_task=failed")
        print(f"reasons={len(errors)}")
        for err in errors:
            print(f"- {err}")
        return 1

    new_task: dict[str, Any] = {
        "id": task_id,
        "title": title,
        "column": "intake",
        "project": project,
        "owner": owner,
        "manager": manager,
        "accepts_result": accepts_result,
        "risk_tier": risk_tier,
        "autonomy_tier": autonomy_tier,
        "workflow": workflow_id,
        "next_step": next_step,
        "done_when": done_when,
        "primary_update_file": primary_update_file,
    }

    active_work = dict(bundle["active_work"])
    tasks = list(active_work.get("tasks", []) or [])
    tasks.append(new_task)
    active_work["tasks"] = tasks
    active_work["updated_at"] = utc_today()
    write_json(ACTIVE_WORK_PATH, active_work)

    ensure_task_packets([new_task])
    write_task_board(active_work, bundle["workflow_registry"])
    write_workflow_artifact(
        active_work,
        bundle["workflow_registry"],
        bundle["policies"],
        bundle["execution_config"],
        bundle["execution_config_state"],
    )

    print("create_task=ok")
    print(f"task_id={task_id}")
    print("column=intake")
    print(f"board_written={relative_display(TASK_BOARD_PATH)}")
    print(f"workflow_artifact_written={relative_display(WORKFLOW_ARTIFACT_PATH)}")
    print(render_recommended_next_command(f"python3 scripts/hq_control_plane.py resume --task-id {task_id}"))
    return 0


def init_profile_command(args: argparse.Namespace) -> int:
    bundle = validate_control_plane()
    profile = normalize_text(args.preset) or DEFAULT_EXECUTION_PRESET

    if EXECUTION_CONFIG_PATH.exists() and not args.force:
        print("init_profile=failed")
        print(f"profile={profile}")
        print(f"reason={relative_display(EXECUTION_CONFIG_PATH)} already exists; rerun with --force to overwrite")
        return 1

    payload = build_execution_config_from_preset(
        profile,
        bundle["active_work"],
        bundle["policies"],
        source="materialized",
    )
    write_json(EXECUTION_CONFIG_PATH, payload)
    write_workflow_artifact(
        bundle["active_work"],
        bundle["workflow_registry"],
        bundle["policies"],
        payload,
        "materialized",
    )

    print("init_profile=ok")
    print(f"profile={profile}")
    print(f"config_written={relative_display(EXECUTION_CONFIG_PATH)}")
    print(f"workflow_artifact_written={relative_display(WORKFLOW_ARTIFACT_PATH)}")
    if args.force:
        print("mode=overwrite")
    else:
        print("mode=create")
    print(render_recommended_next_command("python3 scripts/hq_control_plane.py status"))
    return 0


def validate_command(_: argparse.Namespace) -> int:
    bundle = validate_control_plane()
    print("validation=ok")
    print(f"warnings={len(bundle['validation_warnings'])}")
    for warning in bundle["validation_warnings"]:
        print(f"warning: {warning}")
    print(f"tasks={len(bundle['active_work'].get('tasks', []))}")
    print(f"board={relative_display(TASK_BOARD_PATH)}")
    print(
        "execution_config={path} state={state}".format(
            path=relative_display(EXECUTION_CONFIG_PATH),
            state=bundle["execution_config_state"],
        )
    )
    return 0


def sync_command(args: argparse.Namespace) -> int:
    bundle = validate_control_plane()
    if args.check:
        return generated_check_command(args)
    live_tasks = [
        task
        for task in bundle["active_work"].get("tasks", []) or []
        if isinstance(task, dict) and normalize_text(task.get("column")) != "done"
    ]
    ensure_task_packets(live_tasks)
    write_task_board(bundle["active_work"], bundle["workflow_registry"])
    write_workflow_artifact(
        bundle["active_work"],
        bundle["workflow_registry"],
        bundle["policies"],
        bundle["execution_config"],
        bundle["execution_config_state"],
    )
    print("validation=ok")
    print(f"board_written={TASK_BOARD_PATH}")
    print(f"workflow_artifact_written={relative_display(WORKFLOW_ARTIFACT_PATH)}")
    print(render_recommended_next_command("python3 scripts/hq_control_plane.py status"))
    return 0


def render_board_command(_: argparse.Namespace) -> int:
    bundle = validate_control_plane()
    print(render_board(bundle["active_work"], bundle["workflow_registry"]), end="")
    return 0


def archive_command(args: argparse.Namespace) -> int:
    bundle = validate_control_plane()
    done_tasks, live_tasks, archive_payload = archive_projection(bundle["active_work"])

    if not args.dry_run:
        write_json(ARCHIVED_TASKS_PATH, archive_payload)
        active_work = dict(bundle["active_work"])
        active_work["tasks"] = live_tasks
        if done_tasks:
            active_work["updated_at"] = utc_today()
            write_json(ACTIVE_WORK_PATH, active_work)
            write_task_board(active_work, bundle["workflow_registry"])
            write_workflow_artifact(
                active_work,
                bundle["workflow_registry"],
                bundle["policies"],
                bundle["execution_config"],
                bundle["execution_config_state"],
            )

    print("validation=ok")
    print(f"archive={relative_display(ARCHIVED_TASKS_PATH)}")
    print(f"archived={len(done_tasks)}")
    print(f"archived_total={len(archive_payload['tasks'])}")
    print(f"live_tasks={len(live_tasks)}")
    if args.dry_run:
        print("dry_run=true")
    return 0


def resume_command(args: argparse.Namespace) -> int:
    bundle = validate_control_plane()
    task_id = normalize_text(args.task_id)
    task = find_task(bundle["active_work"], task_id)
    if task is None:
        print("resume=failed")
        print(f"reason=task '{task_id}' not found in active-work.json")
        return 1

    ensure_task_packets([task])
    missing = task_missing_for_safe_continue(task)
    write_quick_context(task, missing)
    print(render_resume_text(task, missing), end="")
    return 0


def closeout_command(args: argparse.Namespace) -> int:
    bundle = validate_control_plane()
    task_id = normalize_text(args.task_id)
    task = find_task(bundle["active_work"], task_id)
    if task is None:
        print("closeout=failed")
        print(f"reason=task '{task_id}' not found in active-work.json")
        return 1

    ensure_task_packets([task])
    missing = task_missing_for_safe_continue(task)
    closeout_ready, closeout_reasons = can_auto_closeout(task)
    reasons = [*closeout_reasons, *missing]
    if not closeout_ready or missing:
        print("closeout=not_ready")
        print(f"task_id={task_id}")
        if reasons:
            print(f"reasons={len(reasons)}")
            for reason in reasons:
                print(f"- {reason}")
        print(render_recommended_next_command(f"python3 scripts/hq_control_plane.py resume --task-id {task_id}"))
        return 1

    active_work = dict(bundle["active_work"])
    updated_tasks: list[dict[str, Any]] = []
    for current in active_work.get("tasks", []) or []:
        if not isinstance(current, dict):
            updated_tasks.append(current)
            continue
        if normalize_text(current.get("id")) != task_id:
            updated_tasks.append(current)
            continue
        closed_task = dict(current)
        closed_task["column"] = "done"
        closed_task["completed_at"] = utc_today()
        updated_tasks.append(closed_task)
    active_work["tasks"] = updated_tasks
    active_work["updated_at"] = utc_today()
    write_json(ACTIVE_WORK_PATH, active_work)
    write_task_board(active_work, bundle["workflow_registry"])
    write_workflow_artifact(
        active_work,
        bundle["workflow_registry"],
        bundle["policies"],
        bundle["execution_config"],
        bundle["execution_config_state"],
    )

    telemetry_count = write_closeout_telemetry(task, utc_now())

    print("closeout=done")
    print(f"task_id={task_id}")
    print(f"completed_at={utc_today()}")
    print(f"telemetry={telemetry_count}")
    print(f"board_written={relative_display(TASK_BOARD_PATH)}")
    print(f"workflow_artifact_written={relative_display(WORKFLOW_ARTIFACT_PATH)}")
    print(render_recommended_next_command("python3 scripts/hq_control_plane.py status"))
    return 0


def health_command(args: argparse.Namespace) -> int:
    bundle = validate_control_plane()
    live_tasks = [
        task
        for task in bundle["active_work"].get("tasks", []) or []
        if isinstance(task, dict) and normalize_text(task.get("column")) != "done"
    ]
    ensure_task_packets(live_tasks)
    status_payload = build_status_payload(bundle["active_work"], bundle["workflow_registry"])
    write_workflow_artifact(
        bundle["active_work"],
        bundle["workflow_registry"],
        bundle["policies"],
        bundle["execution_config"],
        bundle["execution_config_state"],
    )

    if getattr(args, "json", False):
        payload = {
            "validation": {
                "status": "ok",
                "warnings": [str(w) for w in bundle["validation_warnings"]],
                "warning_count": len(bundle["validation_warnings"]),
                "execution_config_state": bundle["execution_config_state"],
            },
            "status": status_payload,
            "git_status": git_status_lines(),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    lines = [
        "HQ Health",
        "",
        "Validation",
        "- validation=ok",
        f"- warnings={len(bundle['validation_warnings'])}",
    ]
    if bundle["validation_warnings"]:
        lines.extend(f"- warning: {warning}" for warning in bundle["validation_warnings"])
    lines.extend(
        [
            "",
            "Status Snapshot",
            render_status_text(status_payload).rstrip(),
            "",
            "Git Status",
        ]
    )
    lines.extend(f"- {line}" for line in git_status_lines())
    lines.append(render_recommended_next_command(status_payload["recommended_next_command"]))
    print("\n".join(lines) + "\n")
    return 0


def check_role_conflict(task: dict[str, Any], role_id: str, role_ids: set[str]) -> list[str]:
    """Check for role conflicts in task assignment."""
    issues: list[str] = []
    owner = normalize_text(task.get("owner"))
    manager = normalize_text(task.get("manager"))
    accepts_result = normalize_text(task.get("accepts_result"))
    support = {normalize_text(item) for item in task.get("support", []) or [] if normalize_text(item)}
    
    if role_id not in role_ids:
        issues.append(f"role '{role_id}' is not registered in agent-registry.json")
    
    if role_id not in {manager, owner} and role_id not in support:
        issues.append(f"role '{role_id}' is not the manager, owner, or in support list")
    
    if owner == manager and owner:
        issues.append(f"owner and manager are the same role: {owner}")
    
    if owner == accepts_result and owner:
        issues.append(f"owner and accepts_result are the same role: {owner}")
    
    return issues


def check_task_completeness(task: dict[str, Any], workflow: dict[str, Any] | None) -> list[str]:
    """Check if task has all required fields filled."""
    issues: list[str] = []
    
    if not workflow:
        return issues
    
    required_fields = [
        normalize_text(item)
        for item in workflow.get("required_task_fields", [])
        if normalize_text(item)
    ]
    
    for field in required_fields:
        value = task.get(field)
        if value is None:
            issues.append(f"required field '{field}' is missing")
        elif isinstance(value, str) and not value.strip():
            issues.append(f"required field '{field}' is empty")
    
    return issues


def check_policy_compliance(
    task: dict[str, Any],
    autonomy_tiers: set[str],
    risk_tiers: set[str],
) -> list[str]:
    """Check if task risk and autonomy tiers are valid."""
    issues: list[str] = []
    
    risk_tier = normalize_text(task.get("risk_tier"))
    autonomy_tier = normalize_text(task.get("autonomy_tier"))
    
    if risk_tier and risk_tier not in risk_tiers:
        issues.append(f"unknown risk_tier: {risk_tier}")
    
    if autonomy_tier and autonomy_tier not in autonomy_tiers:
        issues.append(f"unknown autonomy_tier: {autonomy_tier}")
    
    return issues


def check_stale_telemetry(task: dict[str, Any], queue_updated_at: str) -> list[str]:
    """Check for stale telemetry or missing closeout signals."""
    warnings: list[str] = []
    column = normalize_text(task.get("column"))
    
    # Check for done tasks without completion signal
    if column == "done":
        completed_at = normalize_text(task.get("completed_at"))
        if not completed_at:
            warnings.append("task is done but missing completed_at timestamp")
    
    # Check for executing tasks without recent updates
    if column == "executing":
        queue_updated = parse_datetime(queue_updated_at)
        if queue_updated:
            # Check if handoff exists and is recent
            handoff_path = packet_path(task, "handoff")
            if handoff_path.exists():
                handoff_updated = parse_datetime(packet_updated_at(handoff_path))
                if handoff_updated and queue_updated:
                    days_stale = (queue_updated.date() - handoff_updated.date()).days
                    if days_stale > 3:
                        warnings.append(f"executing task has stale handoff ({days_stale} days old)")
    
    # Check for accepted tasks without sync
    if column == "accepted":
        queue_updated = parse_datetime(queue_updated_at)
        if queue_updated:
            handoff_path = packet_path(task, "handoff")
            if handoff_path.exists():
                handoff_updated = parse_datetime(packet_updated_at(handoff_path))
                if handoff_updated and queue_updated:
                    days_stale = (queue_updated.date() - handoff_updated.date()).days
                    if days_stale > 2:
                        warnings.append(f"accepted task without recent sync ({days_stale} days old)")
    
    return warnings


def preflight_check(
    task_id: str,
    role_id: str,
    bundle: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Run preflight checks for a task before starting work."""
    failures: list[str] = []
    warnings: list[str] = []
    
    active_work = bundle["active_work"]
    agent_registry = bundle["agent_registry"]
    policies = bundle["policies"]
    workflow_registry = bundle["workflow_registry"]
    
    # Find the task
    tasks = [t for t in active_work.get("tasks", []) if normalize_text(t.get("id")) == task_id]
    if not tasks:
        failures.append(f"task '{task_id}' not found in active-work.json")
        return failures, warnings
    
    task = tasks[0]
    column = normalize_text(task.get("column"))
    
    # Check if task is done
    if column == "done":
        failures.append(f"task '{task_id}' is already done")
    
    # Get reference data
    role_ids = get_role_ids(agent_registry)
    workflows = get_workflows(workflow_registry)
    autonomy_tiers, risk_tiers = get_policy_sets(policies)
    
    # Check workflow exists
    workflow_id = normalize_text(task.get("workflow"))
    workflow = workflows.get(workflow_id)
    if not workflow:
        failures.append(f"task workflow '{workflow_id}' not found in workflow-registry.json")
    
    # Check role conflicts
    role_issues = check_role_conflict(task, role_id, role_ids)
    for issue in role_issues:
        if "not registered" in issue or "not the manager, owner, or in support list" in issue:
            failures.append(issue)
        else:
            warnings.append(issue)
    
    # Check task completeness
    completeness_issues = check_task_completeness(task, workflow)
    failures.extend(completeness_issues)
    
    # Check policy compliance
    policy_issues = check_policy_compliance(task, autonomy_tiers, risk_tiers)
    failures.extend(policy_issues)
    
    # Check for stale state
    queue_updated_at = normalize_text(active_work.get("updated_at"))
    stale_warnings = check_stale_telemetry(task, queue_updated_at)
    warnings.extend(stale_warnings)
    
    packet_warnings = [
        format_stale_item_warning(item)
        for item in collect_stale_items([task], queue_updated_at)
    ]
    if is_strict_execution(bundle.get("execution_config") or {}) and packet_warnings:
        failures.append("strict execution profile requires fresh runtime packets")
        failures.extend(packet_warnings)
    else:
        warnings.extend(packet_warnings)
    
    return failures, warnings


def preflight_command(args: argparse.Namespace) -> int:
    """Run preflight checks before starting work on a task."""
    try:
        bundle = validate_control_plane()
    except ValidationError as exc:
        print("preflight=failed")
        print("reason=control_plane_validation_failed")
        print(str(exc))
        return 2
    
    task_id = normalize_text(args.task_id)
    role_id = normalize_text(args.role)
    
    if not task_id:
        print("preflight=failed")
        print("reason=task_id is required")
        return 2
    
    if not role_id:
        print("preflight=failed")
        print("reason=role is required")
        return 2
    
    failures, warnings = preflight_check(task_id, role_id, bundle)
    
    if failures:
        print("preflight=failed")
        print(f"task_id={task_id}")
        print(f"role={role_id}")
        print(f"failures={len(failures)}")
        for failure in failures:
            print(f"fail: {failure}")
        if warnings:
            print(f"warnings={len(warnings)}")
            for warning in warnings:
                print(f"warn: {warning}")
        return 1
    
    print("preflight=ok")
    print(f"task_id={task_id}")
    print(f"role={role_id}")
    if warnings:
        print(f"warnings={len(warnings)}")
        for warning in warnings:
            print(f"warn: {warning}")
    else:
        print("warnings=0")
    
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and render the HQ control plane.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate JSON control-plane structure and references.")
    validate_parser.set_defaults(func=validate_command)

    sync_parser = subparsers.add_parser("sync", help="Validate and render Task Board.md from active-work.json.")
    sync_parser.add_argument("--check", action="store_true", help="Check generated artifacts without writing files.")
    sync_parser.set_defaults(func=sync_command)

    generated_check_parser = subparsers.add_parser(
        "generated-check",
        help="Check generated artifacts without writing files.",
    )
    generated_check_parser.set_defaults(func=generated_check_command)

    render_parser = subparsers.add_parser("render-board", help="Print the rendered task board to stdout.")
    render_parser.set_defaults(func=render_board_command)

    archive_parser = subparsers.add_parser(
        "archive",
        help="Archive done tasks into .hq/state/archived-tasks.json and remove them from active-work.json.",
    )
    archive_parser.add_argument("--dry-run", action="store_true", help="Show archive counts without writing files.")
    archive_parser.set_defaults(func=archive_command)

    status_parser = subparsers.add_parser(
        "status",
        help="Write and print a compact session bootstrap view from the live control plane.",
    )
    status_parser.add_argument("--json", action="store_true", help="Print the session bootstrap as JSON.")
    status_parser.set_defaults(func=status_command)

    health_parser = subparsers.add_parser(
        "health",
        help="Print one report combining validation, status, stale packets, warnings, and git status.",
    )
    health_parser.add_argument("--json", action="store_true", help="Print the health report as JSON.")
    health_parser.set_defaults(func=health_command)

    templates_parser = subparsers.add_parser(
        "templates",
        help="List locally available task templates for shaping new work.",
    )
    templates_parser.set_defaults(func=templates_command)

    init_profile_parser = subparsers.add_parser(
        "init-profile",
        help="Materialize a local execution-config preset without adding a new task runtime.",
    )
    init_profile_parser.add_argument(
        "--preset",
        default=DEFAULT_EXECUTION_PRESET,
        choices=sorted(EXECUTION_PRESETS),
        help="Execution strictness preset.",
    )
    init_profile_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing execution-config.json baseline.",
    )
    init_profile_parser.set_defaults(func=init_profile_command)

    create_task_parser = subparsers.add_parser(
        "create-task",
        help="Create a new task in active-work.json with spec/handoff packets.",
    )
    create_task_parser.add_argument("--title", required=True, help="Task title.")
    create_task_parser.add_argument("--project", required=True, help="Project name.")
    create_task_parser.add_argument("--owner", default="", help="Owner role (must exist in agent-registry).")
    create_task_parser.add_argument("--manager", default="", help="Manager role.")
    create_task_parser.add_argument("--accepts-result", default="", help="Role that accepts the result.")
    create_task_parser.add_argument("--workflow", default="intake-to-execution", help="Workflow ID.")
    create_task_parser.add_argument("--risk-tier", default="medium", help="Risk tier (low/medium/high).")
    create_task_parser.add_argument("--autonomy-tier", default="A2", help="Autonomy tier (A1/A2/A3).")
    create_task_parser.add_argument("--done-when", default="", help="Done-when criteria.")
    create_task_parser.add_argument("--next-step", default="Triage and route.", help="Initial next step.")
    create_task_parser.add_argument("--primary-update-file", default="", help="Primary update file path.")
    create_task_parser.add_argument("--template", default="", help="Template ID for defaults.")
    create_task_parser.add_argument("--task-id", default="", help="Override auto-generated task ID.")
    create_task_parser.set_defaults(func=create_task_command)

    resume_parser = subparsers.add_parser(
        "resume",
        help="Render a queue-level continuation summary for one task and refresh QUICK_CONTEXT.",
    )
    resume_parser.add_argument("--task-id", required=True, help="Task ID to resume.")
    resume_parser.set_defaults(func=resume_command)

    closeout_parser = subparsers.add_parser(
        "closeout",
        help="Close low/medium internal work from the queue happy path when required signals are present.",
    )
    closeout_parser.add_argument("--task-id", required=True, help="Task ID to close out.")
    closeout_parser.set_defaults(func=closeout_command)

    preflight_parser = subparsers.add_parser(
        "preflight",
        help="Run preflight checks before starting work on a task.",
    )
    preflight_parser.add_argument("--task-id", required=True, help="Task ID to check.")
    preflight_parser.add_argument("--role", required=True, help="Role that will execute the task.")
    preflight_parser.set_defaults(func=preflight_command)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except ValidationError as exc:
        print("validation=failed")
        print(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
