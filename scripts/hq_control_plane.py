#!/usr/bin/env python3
"""Validate and render the HQ AI control plane."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

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

COLUMN_ORDER = [
    "intake",
    "triage",
    "policy_check",
    "scheduled",
    "this_week",
    "executing",
    "review",
    "blocked",
    "waiting",
    "accepted",
    "synced",
    "done",
]
COLUMN_TITLES = {
    "intake": "Intake",
    "triage": "Triage",
    "policy_check": "Policy Check",
    "scheduled": "Scheduled",
    "this_week": "This Week",
    "executing": "Executing",
    "review": "Review",
    "blocked": "Blocked",
    "waiting": "Waiting",
    "accepted": "Accepted",
    "synced": "Synced",
    "done": "Done",
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


def validate_role_registry(agent_registry: dict[str, Any], context: ValidationContext) -> None:
    roles = agent_registry.get("roles")
    if not isinstance(roles, list) or not roles:
        context.add("agent-registry.json", "roles must be a non-empty list")
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


def validate_metrics(metrics: dict[str, Any], context: ValidationContext) -> None:
    primary = metrics.get("primary_metrics")
    if not isinstance(primary, list) or len(primary) < 3:
        context.add("metrics-registry.json", "primary_metrics should contain at least 3 metrics")
        return
    for index, metric in enumerate(primary):
        path = f"metrics-registry.json.primary_metrics[{index}]"
        if not isinstance(metric, dict):
            context.add(path, "metric must be an object")
            continue
        if not normalize_text(metric.get("id")):
            context.add(path, "metric id is required")
        if not normalize_text(metric.get("definition")):
            context.add(path, "definition is required")


def validate_active_work(
    active_work: dict[str, Any],
    agent_registry: dict[str, Any],
    policies: dict[str, Any],
    workflow_registry: dict[str, Any],
    context: ValidationContext,
) -> None:
    tasks = active_work.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        context.add("active-work.json", "tasks must be a non-empty list")
        return

    role_ids = get_role_ids(agent_registry)
    autonomy_tiers, risk_tiers = get_policy_sets(policies)
    workflows = get_workflows(workflow_registry)
    objective = active_work.get("objective")
    if not isinstance(objective, dict):
        context.add("active-work.json.objective", "objective must be an object")
    else:
        if not normalize_text(objective.get("id")):
            context.add("active-work.json.objective", "objective.id is required")
        if not normalize_text(objective.get("title")):
            context.add("active-work.json.objective", "objective.title is required")

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

        owner = normalize_text(task.get("owner"))
        accepts_result = normalize_text(task.get("accepts_result"))
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
        if column not in COLUMN_ORDER:
            context.add(f"{path}.column", f"unsupported column: {column}")
        if column == "done" and not normalize_text(task.get("completed_at")):
            context.add(f"{path}.completed_at", "done tasks must include completed_at")

        primary_update_file = normalize_text(task.get("primary_update_file"))
        if primary_update_file:
            ensure_file_exists(context, primary_update_file, f"{path}.primary_update_file")
        for align_index, align_path in enumerate(task.get("align_files", []) or []):
            align_text = normalize_text(align_path)
            if align_text:
                ensure_file_exists(context, align_text, f"{path}.align_files[{align_index}]")


        if not normalize_text(task.get("done_when")):
            context.add(f"{path}.done_when", "done_when must not be empty")
        if not normalize_text(task.get("next_step")):
            context.add(f"{path}.next_step", "next_step must not be empty")


        project = normalize_text(task.get("project"))
        if not project:
            context.add(f"{path}.project", "project is required")


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
    validate_role_registry(bundle["agent_registry"], context)
    validate_metrics(bundle["metrics_registry"], context)
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
        "  - ID: {id} | Owner: {owner} | Accepts: {accepts} | Risk: {risk} | Autonomy: {autonomy}".format(
            id=normalize_text(task.get("id")),
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


def render_board(active_work: dict[str, Any]) -> str:
    objective = active_work.get("objective", {})
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
    for column in COLUMN_ORDER:
        column_tasks = [task for task in tasks if normalize_text(task.get("column")) == column]
        if not column_tasks:
            continue
        lines.extend(["", f"## {COLUMN_TITLES.get(column, column.title())}"])
        for task in column_tasks:
            lines.extend(task_lines(task))
    return "\n".join(lines) + "\n"


def validate_command(_: argparse.Namespace) -> int:
    bundle = validate_control_plane()
    print(f"validation=ok")
    print(f"tasks={len(bundle['active_work'].get('tasks', []))}")
    print(f"board={relative_display(TASK_BOARD_PATH)}")
    return 0


def sync_command(_: argparse.Namespace) -> int:
    bundle = validate_control_plane()
    TASK_BOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    TASK_BOARD_PATH.write_text(render_board(bundle["active_work"]), encoding="utf-8")
    print(f"validation=ok")
    print(f"board_written={TASK_BOARD_PATH}")
    return 0


def render_board_command(_: argparse.Namespace) -> int:
    bundle = validate_control_plane()
    print(render_board(bundle["active_work"]), end="")
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
