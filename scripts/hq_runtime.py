#!/usr/bin/env python3
"""Minimal private runtime helpers for HQ sessions, probes, specs, and handoffs."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from hq_io import append_jsonl as append_jsonl_record
from hq_io import atomic_write_text, write_json
from hq_runtime_review import ALLOWED_CHANGE_SCOPES
from hq_runtime_review import derive_issue_key
from hq_runtime_review import load_reflections
from hq_runtime_review import normalize_reflection_payload
from hq_runtime_review import normalize_string_list
from hq_runtime_review import reflection_command
from hq_runtime_review import reflection_payload_from_args
from hq_runtime_review import reflections_file_for_timestamp
from hq_runtime_review import render_review_markdown
from hq_runtime_review import weekly_review_command


REPO_ROOT = Path(
    os.environ.get("HQ_RUNTIME_REPO_ROOT", Path(__file__).resolve().parents[1])
).resolve()
PRIVATE_ROOT = Path(os.environ.get("HQ_RUNTIME_PRIVATE_ROOT", REPO_ROOT / ".hq")).resolve()
RUNTIME_DIRS = {
    "handoffs": PRIVATE_ROOT / "handoffs",
    "specs": PRIVATE_ROOT / "specs",
    "logs": PRIVATE_ROOT / "logs",
    "state": PRIVATE_ROOT / "state",
    "memory": PRIVATE_ROOT / "memory",
    "journals": PRIVATE_ROOT / "journals",
    "reflections": PRIVATE_ROOT / "reflections",
    "improvements": PRIVATE_ROOT / "improvements",
    "telemetry": PRIVATE_ROOT / "telemetry",
    "evals": PRIVATE_ROOT / "evals",
    "releases": PRIVATE_ROOT / "releases",
}
CAPABILITIES_FILE = RUNTIME_DIRS["state"] / "capabilities.json"
LOCAL_STATE_DIRS = (
    REPO_ROOT / "02 Planning",
    REPO_ROOT / "03 Notes",
    REPO_ROOT / "04 Projects",
    REPO_ROOT / "05 AI Control Plane",
)


def sample_agent_registry() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": "2026-04-16",
        "roles": [
            {
                "id": "ceo",
                "display_name": "CEO",
                "role_type": "human",
                "default_autonomy_tier": "A4",
                "mission": "Approve strategy and high-risk work.",
            },
            {
                "id": "ai_operations_lead",
                "display_name": "AI Operations Lead",
                "role_type": "ai",
                "default_autonomy_tier": "A2",
                "mission": "Route work and maintain queue quality.",
                "escalates_to": "governor",
            },
            {
                "id": "delivery",
                "display_name": "Delivery",
                "role_type": "ai",
                "default_autonomy_tier": "A2",
                "mission": "Execute bounded implementation tasks.",
            },
            {
                "id": "documentation",
                "display_name": "Documentation",
                "role_type": "ai",
                "default_autonomy_tier": "A2",
                "mission": "Sync accepted decisions into shared truth.",
            },
            {
                "id": "governor",
                "display_name": "Governor",
                "role_type": "ai",
                "default_autonomy_tier": "A3",
                "mission": "Enforce risk controls and approvals.",
            },
        ],
    }


def sample_policies() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": "2026-04-16",
        "stage": "stage-2-foundation",
        "autonomy_tiers": [
            {"id": "A1", "description": "Drafts only."},
            {"id": "A2", "description": "Internal execution."},
            {"id": "A3", "description": "External action with review."},
            {"id": "A4", "description": "Human only."},
        ],
        "risk_tiers": [
            {"id": "low", "description": "Low risk.", "default_approval": "owner"},
            {"id": "medium", "description": "Medium risk.", "default_approval": "governor"},
            {"id": "high", "description": "High risk.", "default_approval": "ceo"},
        ],
        "approvals": {
            "human_only_actions": ["spend"],
            "governor_review_required_for": ["medium-risk work"],
            "default_spend_without_budget_eur": 0,
            "max_external_send_without_review": 0,
        },
        "weekly_metric_review": {
            "cadence": "weekly",
            "owner": "ai_operations_lead",
            "support": ["governor", "documentation"],
            "approver": "ceo",
            "required_metrics": [
                "autonomous_completion_rate",
                "human_escalation_rate",
                "decision_latency_hours",
                "documentation_lag_hours",
                "rework_or_rollback_rate",
            ],
        },
        "eval_policy": {
            "minimum_checks_for_repeated_work": ["task-cycle"],
            "control_plane_change_requires": ["python3 scripts/hq_control_plane.py validate"],
        },
        "metric_thresholds": [
            {
                "metric_id": "autonomous_completion_rate",
                "comparison": ">=",
                "target": 0.6,
                "owner": "ai_operations_lead",
                "escalate_to": ["governor"],
            }
        ],
    }


def sample_workflow_registry() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": "2026-04-16",
        "board_columns": [
            {"id": "intake", "title": "Intake"},
            {"id": "triage", "title": "Triage"},
            {"id": "policy_check", "title": "Policy Check"},
            {"id": "scheduled", "title": "Scheduled"},
            {"id": "this_week", "title": "This Week"},
            {"id": "done", "title": "Done"},
        ],
        "telemetry": {
            "event_types": ["intake", "route", "acceptance", "sync", "review"],
            "statuses": ["queued", "ready", "accepted", "synced", "done"],
            "event_sets": {
                "completion": ["acceptance", "sync"],
                "ready": ["route"],
                "eval": ["review"],
            },
            "status_sets": {
                "completion": ["accepted", "synced", "done"],
                "ready": ["ready"],
                "accepted": ["accepted"],
                "synced": ["synced"],
            },
        },
        "workflows": [
            {
                "id": "intake-to-execution",
                "purpose": "Route internal work.",
                "states": ["intake", "triage", "policy_check", "scheduled", "done"],
                "required_task_fields": [
                    "id",
                    "title",
                    "column",
                    "manager",
                    "owner",
                    "project",
                    "next_step",
                    "done_when",
                    "primary_update_file",
                    "accepts_result",
                    "risk_tier",
                    "autonomy_tier",
                    "workflow",
                ],
                "required_telemetry_events": ["intake", "route", "acceptance", "sync"],
                "acceptance_evidence": ["accepting role reviews outcome"],
                "transition_owners": {
                    "intake->triage": "ai_operations_lead",
                    "triage->policy_check": "governor",
                    "policy_check->scheduled": "ai_operations_lead",
                },
            }
        ],
    }


def sample_metrics_registry() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": "2026-04-16",
        "primary_metrics": [
            {
                "id": "autonomous_completion_rate",
                "definition": "Share of tasks completed without manual redo.",
                "source": [".hq/telemetry/"],
                "unit": "ratio",
                "review_cadence": "weekly",
                "review_owner": "ai_operations_lead",
                "threshold": {"comparison": ">=", "value": 0.6},
            },
            {
                "id": "human_escalation_rate",
                "definition": "Share of tasks escalated to a human reviewer.",
                "source": [".hq/telemetry/"],
                "unit": "ratio",
                "review_cadence": "weekly",
                "review_owner": "ai_operations_lead",
                "threshold": {"comparison": "<=", "value": 0.35},
            },
            {
                "id": "decision_latency_hours",
                "definition": "Hours between intake and acceptance.",
                "source": [".hq/telemetry/"],
                "unit": "hours",
                "review_cadence": "weekly",
                "review_owner": "ai_operations_lead",
                "threshold": {"comparison": "<=", "value": 24},
            },
            {
                "id": "documentation_lag_hours",
                "definition": "Hours between acceptance and documentation sync.",
                "source": [".hq/telemetry/"],
                "unit": "hours",
                "review_cadence": "weekly",
                "review_owner": "documentation",
                "threshold": {"comparison": "<=", "value": 24},
            },
            {
                "id": "rework_or_rollback_rate",
                "definition": "Share of tasks that required rollback or rework.",
                "source": [".hq/telemetry/"],
                "unit": "ratio",
                "review_cadence": "weekly",
                "review_owner": "governor",
                "threshold": {"comparison": "<=", "value": 0.2},
            },
        ],
        "secondary_metrics": [
            {
                "id": "telemetry_coverage_rate",
                "definition": "Share of governed tasks with complete telemetry.",
                "source": [".hq/telemetry/"],
                "unit": "ratio",
                "review_cadence": "weekly",
                "review_owner": "ai_operations_lead",
                "threshold": {"comparison": ">=", "value": 0.9},
            }
        ],
    }


def sample_active_work() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": "2026-04-16",
        "operating_mode": "stage-2-foundation",
        "objective": {
            "id": "local-bootstrap",
            "title": "Bootstrap a local HQ operating workspace",
            "window": {"start": "2026-04-16", "target_end": "2026-05-31"},
            "success_criteria": [
                "Local control-plane files validate successfully.",
                "Task Board.md can be rendered from active-work.json.",
            ],
        },
        "tasks": [
            {
                "id": "bootstrap-local-workspace",
                "title": "Review and customize the local HQ scaffold",
                "column": "this_week",
                "manager": "ai_operations_lead",
                "owner": "documentation",
                "project": "HQ Bootstrap",
                "support": ["governor", "delivery"],
                "next_step": "Replace sample values with your real local operating state.",
                "done_when": "The local queue, notes, and weekly plan reflect real work instead of scaffold placeholders.",
                "primary_update_file": "05 AI Control Plane/active-work.json",
                "align_files": [
                    "now.md",
                    "projects.md",
                    "02 Planning/Weekly Plan.md",
                    "03 Notes/Decisions.md",
                    "03 Notes/Open Decisions.md",
                    "04 Projects/HQ Bootstrap.md",
                ],
                "accepts_result": "ceo",
                "risk_tier": "medium",
                "autonomy_tier": "A2",
                "workflow": "intake-to-execution",
            }
        ],
    }


def local_text_files() -> dict[Path, str]:
    return {
        REPO_ROOT / "now.md": """# Now

## Current Focus

- Bootstrap the local HQ workspace.
- Replace sample operating state with real local decisions.
- Keep live operating files local and out of Git history.
""",
        REPO_ROOT / "projects.md": """# Projects

## Active

### HQ Bootstrap

- Status: active
- Goal: turn the scaffolded local HQ workspace into a real operating system for current work
- Owner: CEO
- Next step: replace sample queue and notes with live local state
""",
        REPO_ROOT / "routines.md": """# Routines

## Weekly

- Review the active queue.
- Sync accepted decisions into local notes.
- Review telemetry and runtime quality.
""",
        REPO_ROOT / "stack.md": """# Stack

## Core

- Markdown for local operating truth
- JSON control plane under `05 AI Control Plane/`
- Python scripts for validation, telemetry, and runtime helpers
""",
        REPO_ROOT / "02 Planning" / "Weekly Plan.md": """# Weekly Plan

## This Week

- Review the scaffolded queue and update it with real work.
- Run `python3 scripts/hq_control_plane.py sync` after queue changes.
""",
        REPO_ROOT / "02 Planning" / "Backlog.md": """# Backlog

- Add future work here after triage.
""",
        REPO_ROOT / "03 Notes" / "Inbox.md": """# Inbox

- Capture raw requests here before triage.
""",
        REPO_ROOT / "03 Notes" / "Decisions.md": """# Decisions

## 2026-04-16

### Local Bootstrap Created

- Decision: create a local HQ scaffold from the public bootstrap script.
- Reason: the public repository ships scripts and prompts, while live operating state stays local.
""",
        REPO_ROOT / "03 Notes" / "Open Decisions.md": """# Open Decisions

## Current

- Decide which real workflows, roles, and weekly commitments should replace the bootstrap placeholders.
""",
        REPO_ROOT / "04 Projects" / "HQ Bootstrap.md": """# HQ Bootstrap

## Goal

- Replace the scaffolded local operating files with real working state.

## Next Step

- Edit `05 AI Control Plane/active-work.json`, then run `python3 scripts/hq_control_plane.py sync`.
""",
    }


def local_json_files() -> dict[Path, dict[str, Any]]:
    return {
        REPO_ROOT / "05 AI Control Plane" / "agent-registry.json": sample_agent_registry(),
        REPO_ROOT / "05 AI Control Plane" / "operating-policies.json": sample_policies(),
        REPO_ROOT / "05 AI Control Plane" / "workflow-registry.json": sample_workflow_registry(),
        REPO_ROOT / "05 AI Control Plane" / "metrics-registry.json": sample_metrics_registry(),
        REPO_ROOT / "05 AI Control Plane" / "active-work.json": sample_active_work(),
    }


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def slugify(value: str) -> str:
    cleaned = []
    previous_dash = False
    for char in (value or "").strip().lower():
        if char.isalnum():
            cleaned.append(char)
            previous_dash = False
            continue
        if not previous_dash:
            cleaned.append("-")
            previous_dash = True
    normalized = "".join(cleaned).strip("-")
    return normalized or "session"


def ensure_private_runtime() -> dict[str, Path]:
    PRIVATE_ROOT.mkdir(parents=True, exist_ok=True)
    for path in RUNTIME_DIRS.values():
        path.mkdir(parents=True, exist_ok=True)
    return RUNTIME_DIRS


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    append_jsonl_record(path, payload)


def write_text_if_needed(path: Path, content: str, *, force: bool) -> bool:
    if path.exists() and not force:
        return False
    atomic_write_text(path, content)
    return True


def write_json_if_needed(path: Path, payload: dict[str, Any], *, force: bool) -> bool:
    if path.exists() and not force:
        return False
    write_json(path, payload)
    return True


def render_local_task_board() -> tuple[int, str]:
    env = os.environ.copy()
    env["HQ_CONTROL_PLANE_REPO_ROOT"] = str(REPO_ROOT)
    completed = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "hq_control_plane.py"), "sync"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    return completed.returncode, output.strip()


def bootstrap_command(args: argparse.Namespace) -> int:
    paths = ensure_private_runtime()
    print(f"private_root={PRIVATE_ROOT}")
    for name, path in paths.items():
        print(f"{name}={path}")

    if args.runtime_only:
        return 0

    for path in LOCAL_STATE_DIRS:
        path.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    skipped: list[str] = []

    for path, content in local_text_files().items():
        changed = write_text_if_needed(path, content, force=args.force)
        (created if changed else skipped).append(path.relative_to(REPO_ROOT).as_posix())

    for path, payload in local_json_files().items():
        changed = write_json_if_needed(path, payload, force=args.force)
        (created if changed else skipped).append(path.relative_to(REPO_ROOT).as_posix())

    exit_code, sync_output = render_local_task_board()
    if exit_code != 0:
        print(sync_output)
        return exit_code

    created.append((REPO_ROOT / "02 Planning" / "Task Board.md").relative_to(REPO_ROOT).as_posix())
    print(f"local_state_created={len(created)}")
    for item in created:
        print(f"created={item}")
    print(f"local_state_skipped={len(skipped)}")
    for item in skipped:
        print(f"skipped={item}")
    if sync_output:
        print(sync_output)
    return 0


def probe_tool(tool: str, timeout: int) -> dict[str, Any]:
    binary = shutil.which(tool)
    result: dict[str, Any] = {
        "tool": tool,
        "checked_at": utc_now(),
        "binary": binary,
        "available": False,
        "probe": "--help",
    }
    if binary is None:
        result["status"] = "missing"
        result["reason"] = "binary not found in PATH"
        return result

    try:
        completed = subprocess.run(
            [binary, "--help"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        result["status"] = "timeout"
        result["reason"] = f"timed out after {timeout}s while probing --help"
        return result
    except OSError as exc:
        result["status"] = "error"
        result["reason"] = str(exc)
        return result

    preview = (completed.stdout or completed.stderr or "").strip().splitlines()
    result["available"] = True
    result["status"] = "ready"
    result["returncode"] = completed.returncode
    if preview:
        result["preview"] = preview[0][:160]
    return result


def probe_command(args: argparse.Namespace) -> int:
    ensure_private_runtime()
    results = [probe_tool(tool, args.timeout) for tool in args.tools]
    payload = {
        "updated_at": utc_now(),
        "tools": {item["tool"]: item for item in results},
    }
    write_json(CAPABILITIES_FILE, payload)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"capabilities_file={CAPABILITIES_FILE}")
    for item in results:
        status = "ready" if item["available"] else item["status"]
        binary = item.get("binary") or "-"
        print(f"{item['tool']}: {status} ({binary})")
        preview = item.get("preview")
        if preview:
            print(f"  {preview}")
        reason = item.get("reason")
        if reason:
            print(f"  {reason}")
    return 0


def render_section(title: str, items: list[str]) -> str:
    lines = [f"## {title}"]
    if items:
        lines.extend(f"- {item}" for item in items)
    else:
        lines.append("- None")
    return "\n".join(lines)


def spec_markdown(args: argparse.Namespace, updated_at: str) -> str:
    goal = args.goal or args.task
    header = [
        "# Spec",
        "",
        f"- Task: {args.task}",
        f"- Session: {args.session}",
        f"- Updated At: {updated_at}",
        f"- Owner: {args.owner or 'Unassigned'}",
        f"- Status: {args.status}",
        f"- Goal: {goal}",
        f"- Primary Update File: {args.primary_file or 'Not set'}",
        "",
    ]
    sections = [
        render_section("Why Now", args.why),
        "",
        render_section("In Scope", args.in_scope),
        "",
        render_section("Out Of Scope", args.out_of_scope),
        "",
        render_section("Read First", args.read_file),
        "",
        render_section("Constraints", args.constraint),
        "",
        render_section("Acceptance", args.acceptance),
        "",
        render_section("Open Questions", args.question),
        "",
        render_section("Notes", args.note),
        "",
    ]
    return "\n".join(header + sections)


def spec_command(args: argparse.Namespace) -> int:
    ensure_private_runtime()
    updated_at = utc_now()
    task_slug = slugify(args.task)
    session_slug = slugify(args.session)
    task_dir = RUNTIME_DIRS["specs"] / task_slug
    task_dir.mkdir(parents=True, exist_ok=True)

    markdown = spec_markdown(args, updated_at)
    spec_path = task_dir / f"{session_slug}.md"
    latest_path = task_dir / "LATEST.md"
    manifest_path = task_dir / "manifest.json"

    atomic_write_text(spec_path, markdown)
    atomic_write_text(latest_path, markdown)
    write_json(
        manifest_path,
        {
            "task": args.task,
            "task_slug": task_slug,
            "session": args.session,
            "owner": args.owner or "",
            "status": args.status,
            "updated_at": updated_at,
            "latest_file": latest_path.relative_to(REPO_ROOT).as_posix(),
            "session_file": spec_path.relative_to(REPO_ROOT).as_posix(),
            "goal": args.goal or args.task,
            "primary_file": args.primary_file or "",
            "why": args.why,
            "in_scope": args.in_scope,
            "out_of_scope": args.out_of_scope,
            "read_first": args.read_file,
            "constraints": args.constraint,
            "acceptance": args.acceptance,
            "open_questions": args.question,
        },
    )

    print(f"spec_file={spec_path}")
    print(f"latest_file={latest_path}")
    print(f"manifest_file={manifest_path}")
    return 0


def handoff_markdown(args: argparse.Namespace, updated_at: str) -> str:
    read_first = list(dict.fromkeys(([args.spec_file] if args.spec_file else []) + args.read_first))
    header = [
        "# Handoff",
        "",
        f"- Task: {args.task}",
        f"- Session: {args.session}",
        f"- Updated At: {updated_at}",
        f"- Owner: {args.owner or 'Unassigned'}",
        f"- Status: {args.status}",
        f"- Continue From: {args.continue_from or 'Not set'}",
        f"- Spec File: {args.spec_file or 'Not set'}",
        f"- Primary Update File: {args.primary_file or 'Not set'}",
        f"- Accepting Role: {args.accepting_role or 'Not set'}",
        "",
    ]
    sections = [
        render_section("Read First", read_first),
        "",
        render_section("Done", args.done),
        "",
        render_section("Next", args.next),
        "",
        render_section("Important Files", args.important_file),
        "",
        render_section("Risks", args.risk),
        "",
        render_section("Blockers", args.blocker),
        "",
        render_section("Notes", args.note),
        "",
    ]
    return "\n".join(header + sections)


def handoff_command(args: argparse.Namespace) -> int:
    ensure_private_runtime()
    updated_at = utc_now()
    task_slug = slugify(args.task)
    session_slug = slugify(args.session)
    task_dir = RUNTIME_DIRS["handoffs"] / task_slug
    task_dir.mkdir(parents=True, exist_ok=True)

    markdown = handoff_markdown(args, updated_at)
    handoff_path = task_dir / f"{session_slug}.md"
    latest_path = task_dir / "LATEST.md"
    manifest_path = task_dir / "manifest.json"

    atomic_write_text(handoff_path, markdown)
    atomic_write_text(latest_path, markdown)
    read_first = list(dict.fromkeys(([args.spec_file] if args.spec_file else []) + args.read_first))
    write_json(
        manifest_path,
        {
            "task": args.task,
            "task_slug": task_slug,
            "session": args.session,
            "owner": args.owner or "",
            "status": args.status,
            "updated_at": updated_at,
            "latest_file": latest_path.relative_to(REPO_ROOT).as_posix(),
            "session_file": handoff_path.relative_to(REPO_ROOT).as_posix(),
            "continue_from": args.continue_from or "",
            "spec_file": args.spec_file or "",
            "primary_file": args.primary_file or "",
            "read_first": read_first,
            "important_files": args.important_file,
            "risks": args.risk,
            "blockers": args.blocker,
        },
    )

    print(f"handoff_file={handoff_path}")
    print(f"latest_file={latest_path}")
    print(f"manifest_file={manifest_path}")
    return 0


def parse_json_object(value: str) -> dict[str, Any]:
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise argparse.ArgumentTypeError("JSON payload must be an object")
    return payload


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO date: {value}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Minimal private runtime helpers for HQ.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap = subparsers.add_parser(
        "bootstrap",
        help="Create the private runtime and scaffold local HQ state if missing.",
    )
    bootstrap.add_argument(
        "--runtime-only",
        action="store_true",
        help="Create only `.hq/` runtime directories.",
    )
    bootstrap.add_argument(
        "--force",
        action="store_true",
        help="Overwrite scaffolded local state files if they already exist.",
    )
    bootstrap.set_defaults(func=bootstrap_command)

    probe = subparsers.add_parser(
        "probe",
        help="Check whether required CLI surfaces are really available.",
    )
    probe.add_argument("tools", nargs="+", help="CLI names to probe, e.g. codex claude")
    probe.add_argument(
        "--timeout",
        type=int,
        default=5,
        help="Seconds allowed for each --help probe. Defaults to 5.",
    )
    probe.add_argument(
        "--json",
        action="store_true",
        help="Print JSON instead of plain text.",
    )
    probe.set_defaults(func=probe_command)

    spec = subparsers.add_parser(
        "spec",
        help="Write a private task-scoped spec into the runtime.",
    )
    spec.add_argument("--task", required=True, help="Task or workstream identifier.")
    spec.add_argument(
        "--session",
        default=f"session-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        help="Session identifier. Defaults to a UTC timestamp.",
    )
    spec.add_argument("--owner", help="Current owner of the task slice.")
    spec.add_argument(
        "--status",
        default="draft",
        help="Spec status. Defaults to draft.",
    )
    spec.add_argument("--goal", help="Concrete outcome this spec should drive.")
    spec.add_argument(
        "--primary-file",
        help="Primary update file for the next slice.",
    )
    spec.add_argument("--why", action="append", default=[], help="Repeat for each why-now point.")
    spec.add_argument(
        "--in-scope",
        action="append",
        default=[],
        help="Repeat for each in-scope item.",
    )
    spec.add_argument(
        "--out-of-scope",
        action="append",
        default=[],
        help="Repeat for each out-of-scope item.",
    )
    spec.add_argument(
        "--read-file",
        action="append",
        default=[],
        help="Repeat for each file the next agent should read before broad scanning.",
    )
    spec.add_argument(
        "--constraint",
        action="append",
        default=[],
        help="Repeat for each constraint.",
    )
    spec.add_argument(
        "--acceptance",
        action="append",
        default=[],
        help="Repeat for each acceptance criterion.",
    )
    spec.add_argument(
        "--question",
        action="append",
        default=[],
        help="Repeat for each open question.",
    )
    spec.add_argument(
        "--note",
        action="append",
        default=[],
        help="Repeat for extra notes that should stay private.",
    )
    spec.set_defaults(func=spec_command)

    handoff = subparsers.add_parser(
        "handoff",
        help="Write a task-scoped handoff file into the private runtime.",
    )
    handoff.add_argument("--task", required=True, help="Task or workstream identifier.")
    handoff.add_argument(
        "--session",
        default=f"session-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        help="Session identifier. Defaults to a UTC timestamp.",
    )
    handoff.add_argument("--owner", help="Current owner of the task slice.")
    handoff.add_argument(
        "--status",
        default="ready_for_handoff",
        help="Current task status. Defaults to ready_for_handoff.",
    )
    handoff.add_argument(
        "--continue-from",
        help="File or place where the next agent should continue first.",
    )
    handoff.add_argument(
        "--spec-file",
        help="Private spec file that should be read before broader repo context.",
    )
    handoff.add_argument(
        "--primary-file",
        help="Primary update file for the next slice.",
    )
    handoff.add_argument(
        "--accepting-role",
        help="Role that should accept or continue the result.",
    )
    handoff.add_argument("--done", action="append", default=[], help="Repeat for each completed item.")
    handoff.add_argument("--next", action="append", default=[], help="Repeat for each next step.")
    handoff.add_argument(
        "--important-file",
        action="append",
        default=[],
        help="Repeat for each file the next agent should read.",
    )
    handoff.add_argument(
        "--read-first",
        action="append",
        default=[],
        help="Repeat for each file or artifact the next agent should read before broad scanning.",
    )
    handoff.add_argument("--risk", action="append", default=[], help="Repeat for each risk.")
    handoff.add_argument("--blocker", action="append", default=[], help="Repeat for each blocker.")
    handoff.add_argument(
        "--note",
        action="append",
        default=[],
        help="Repeat for any extra note that should stay private.",
    )
    handoff.set_defaults(func=handoff_command)

    reflection = subparsers.add_parser(
        "reflection",
        help="Write one structured JSONL reflection into the private runtime.",
    )
    reflection.add_argument("--json", type=parse_json_object, help="Inline JSON object payload.")
    reflection.add_argument("--agent", help="Agent or role name.")
    reflection.add_argument("--role", help="Optional role name.")
    reflection.add_argument("--task", help="Task or workstream identifier.")
    reflection.add_argument("--session", help="Session identifier.")
    reflection.add_argument(
        "--outcome",
        default="partial",
        choices=["success", "partial", "failed"],
        help="Outcome of the finished work. Defaults to partial.",
    )
    reflection.add_argument(
        "--category",
        default="execution",
        help="Short category label, e.g. execution, routing, context, tooling.",
    )
    reflection.add_argument(
        "--change-scope",
        default="workflow",
        choices=sorted(ALLOWED_CHANGE_SCOPES),
        help="Area where an improvement might later apply.",
    )
    reflection.add_argument("--summary", help="Short outcome summary.")
    reflection.add_argument("--observation", help="Concrete observation from the task.")
    reflection.add_argument("--issue", help="Underlying recurring issue.")
    reflection.add_argument("--lesson", help="What the agent should remember next time.")
    reflection.add_argument(
        "--proposed-rule",
        help="Optional candidate rule. This is stored separately from the observation.",
    )
    reflection.add_argument(
        "--issue-key",
        help="Stable clustering key for recurring issues. Recommended when logging similar reflections.",
    )
    reflection.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Repeat for each short tag used for grouping.",
    )
    reflection.add_argument(
        "--related-file",
        action="append",
        default=[],
        help="Repeat for any file relevant to the reflection.",
    )
    reflection.add_argument(
        "--evidence",
        action="append",
        default=[],
        help="Repeat for lightweight evidence items such as commands, errors, or artifacts.",
    )
    reflection.add_argument(
        "--metadata",
        type=parse_json_object,
        help="Optional inline JSON object with extra metadata.",
    )
    reflection.set_defaults(func=reflection_command)

    weekly_review = subparsers.add_parser(
        "weekly-review",
        aliases=["improve", "synthesize"],
        help="Aggregate reflections and emit safe candidate improvements into .hq/improvements/.",
    )
    weekly_review.add_argument(
        "--since",
        type=parse_date,
        help="Inclusive start date in ISO format, e.g. 2026-04-07.",
    )
    weekly_review.add_argument(
        "--until",
        type=parse_date,
        help="Inclusive end date in ISO format. Defaults to today.",
    )
    weekly_review.add_argument(
        "--days",
        type=int,
        default=7,
        help="If --since is omitted, review this many trailing days. Defaults to 7.",
    )
    weekly_review.add_argument(
        "--min-observations",
        type=int,
        default=2,
        help="Minimum repeated observations required before a candidate improvement is emitted.",
    )
    weekly_review.add_argument(
        "--min-unique-sessions",
        type=int,
        default=2,
        help="Minimum distinct sessions required before a candidate improvement is emitted.",
    )
    weekly_review.set_defaults(func=weekly_review_command)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
