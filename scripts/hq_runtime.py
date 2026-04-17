#!/usr/bin/env python3
"""Private runtime helpers for HQ sessions, minimal-demo bootstrap, specs, and handoffs."""

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

DEFAULT_REPO_ROOT = Path(
    os.environ.get("HQ_RUNTIME_REPO_ROOT", Path(__file__).resolve().parents[1])
).resolve()
os.environ.setdefault("HQ_MISSION_RUNTIME_REPO_ROOT", str(DEFAULT_REPO_ROOT))
os.environ.setdefault("HQ_TELEMETRY_REPO_ROOT", str(DEFAULT_REPO_ROOT))

from hq_io import append_jsonl as append_jsonl_record
from hq_io import atomic_write_text, write_json
import hq_mission_runtime
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


REPO_ROOT = DEFAULT_REPO_ROOT
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
                "mission": "Maintain the delegated-work queue and route execution.",
                "escalates_to": "governor",
            },
            {
                "id": "governor",
                "display_name": "Governor",
                "role_type": "ai",
                "default_autonomy_tier": "A3",
                "mission": "Enforce risk controls and approvals.",
                "escalates_to": "ceo",
            },
            {
                "id": "documentation",
                "display_name": "Documentation",
                "role_type": "ai",
                "default_autonomy_tier": "A2",
                "mission": "Sync accepted decisions into shared truth.",
            },
            {
                "id": "delivery",
                "display_name": "Delivery",
                "role_type": "ai",
                "default_autonomy_tier": "A2",
                "mission": "Execute bounded implementation tasks.",
                "escalates_to": "ai_operations_lead",
            },
            {
                "id": "finance",
                "display_name": "Finance",
                "role_type": "ai",
                "default_autonomy_tier": "A1",
                "mission": "Surface money impact and route commercial constraints.",
                "escalates_to": "ceo",
            },
            {
                "id": "growth",
                "display_name": "Growth",
                "role_type": "ai",
                "default_autonomy_tier": "A1",
                "mission": "Package offers and target the first revenue slice.",
                "escalates_to": "ceo",
            },
            {
                "id": "research",
                "display_name": "Research",
                "role_type": "ai",
                "default_autonomy_tier": "A1",
                "mission": "Provide evidence and counter-case support.",
                "escalates_to": "ai_operations_lead",
            },
        ],
    }


def sample_policies() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": "2026-04-16",
        "stage": "stage-2-minimal-demo-scaffold",
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
        "operating_mode": "stage-2-minimal-demo-scaffold",
        "objective": {
            "id": "minimal-demo-bootstrap",
            "title": "Bootstrap a minimal-demo HQ operating workspace",
            "window": {"start": "2026-04-16", "target_end": "2026-05-31"},
            "success_criteria": [
                "Local control-plane files validate successfully.",
                "Task Board.md can be rendered from active-work.json.",
            ],
        },
        "tasks": [
            {
                "id": "review-minimal-demo-scaffold",
                "title": "Review and replace the minimal-demo HQ scaffold",
                "column": "this_week",
                "manager": "ai_operations_lead",
                "owner": "documentation",
                "project": "HQ Minimal Demo Scaffold",
                "support": ["governor", "delivery", "finance", "growth", "research"],
                "next_step": "Replace minimal-demo values with your real local operating state before treating the scaffold as live HQ truth.",
                "done_when": "The local queue, notes, and weekly plan reflect real work instead of minimal-demo placeholders.",
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

- Bootstrap the local HQ minimal-demo workspace.
- Replace minimal-demo operating state with real local decisions.
- Keep live operating files local and out of Git history.
""",
        REPO_ROOT / "projects.md": """# Projects

## Active

### HQ Minimal Demo Scaffold

- Status: active
- Goal: turn the minimal-demo HQ scaffold into a real operating system for current work
- Owner: CEO
- Next step: replace minimal-demo queue and notes with live local state
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

- Review the minimal-demo queue and update it with real work.
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

### Minimal Demo Bootstrap Created

- Decision: create a minimal-demo local HQ scaffold from the public bootstrap script.
- Reason: the public repository ships scripts and prompts, while live operating state stays local and must replace the demo before real use.
""",
        REPO_ROOT / "03 Notes" / "Open Decisions.md": """# Open Decisions

## Current

- Decide which real workflows, roles, and weekly commitments should replace the minimal-demo placeholders.
""",
        REPO_ROOT / "04 Projects" / "HQ Bootstrap.md": """# HQ Bootstrap

## Goal

- Replace the minimal-demo local operating files with real working state.

## Next Step

- Edit `05 AI Control Plane/active-work.json`, then run `python3 scripts/hq_control_plane.py sync`.
- Do not treat the bootstrap scaffold as live company truth until the placeholders are replaced.
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
    print("scaffold_mode=stage-2-minimal-demo-scaffold")
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


def relative_runtime_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sync_thread_packet(
    *,
    thread_id: str | None,
    spec_path: Path | None = None,
    handoff_path: Path | None = None,
    status: str | None = None,
) -> None:
    if not thread_id:
        return
    hq_mission_runtime.ensure_runtime()
    hq_mission_runtime.update_thread_context(
        thread_id,
        spec_path=relative_runtime_path(spec_path) if spec_path else None,
        handoff_path=relative_runtime_path(handoff_path) if handoff_path else None,
        resume_packet_path=relative_runtime_path(handoff_path or spec_path) if (handoff_path or spec_path) else None,
        status=status,
    )


def spec_markdown(args: argparse.Namespace, updated_at: str) -> str:
    goal = args.goal or args.task
    header = [
        "# Spec",
        "",
        f"- Task: {args.task}",
        f"- Session: {args.session}",
        f"- Updated At: {updated_at}",
        f"- Thread ID: {args.thread_id or 'Not set'}",
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
            "thread_id": args.thread_id or "",
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
    sync_thread_packet(thread_id=args.thread_id, spec_path=latest_path, status="active")

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
        f"- Thread ID: {args.thread_id or 'Not set'}",
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
    hq_mission_runtime.ensure_runtime()
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
    handoff_record = None
    if args.thread_id:
        try:
            handoff_record = hq_mission_runtime.create_handoff_record(
                thread_id=args.thread_id,
                task=args.task,
                session=args.session,
                handoff_file=latest_path.relative_to(REPO_ROOT).as_posix(),
                owner=args.owner or "",
                status=args.status,
                accepting_role=args.accepting_role or "",
                continue_from=args.continue_from or "",
                spec_file=args.spec_file or "",
                primary_file=args.primary_file or "",
                read_first=read_first,
                done_items=args.done,
                next_steps=args.next,
                important_files=args.important_file,
                risks=args.risk,
                blockers=args.blocker,
                notes=args.note,
            )
        except ValueError as exc:
            print(f"error={exc}")
            return 2
    write_json(
        manifest_path,
        {
            "task": args.task,
            "task_slug": task_slug,
            "session": args.session,
            "thread_id": args.thread_id or "",
            "owner": args.owner or "",
            "status": args.status,
            "updated_at": updated_at,
            "latest_file": latest_path.relative_to(REPO_ROOT).as_posix(),
            "session_file": handoff_path.relative_to(REPO_ROOT).as_posix(),
            "handoff_id": handoff_record["id"] if handoff_record else "",
            "continue_from": args.continue_from or "",
            "spec_file": args.spec_file or "",
            "primary_file": args.primary_file or "",
            "read_first": read_first,
            "important_files": args.important_file,
            "risks": args.risk,
            "blockers": args.blocker,
        },
    )
    if not handoff_record:
        sync_thread_packet(
            thread_id=args.thread_id,
            handoff_path=latest_path,
            status="paused" if args.blocker else "active",
        )

    print(f"handoff_file={handoff_path}")
    print(f"latest_file={latest_path}")
    print(f"manifest_file={manifest_path}")
    if handoff_record:
        print(f"handoff_id={handoff_record['id']}")
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


def normalize_cli_list(values: list[str] | None) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        items.append(text)
    return items


def mission_runtime_command(args: argparse.Namespace) -> int:
    ensure_private_runtime()
    hq_mission_runtime.ensure_runtime()
    if not args.mission_args:
        print("error=mission-runtime requires a subcommand")
        return 2
    mission_parser = hq_mission_runtime.build_parser()
    try:
        mission_args = mission_parser.parse_args(args.mission_args)
    except SystemExit as exc:
        return int(exc.code)
    return int(mission_args.func(mission_args))


def founder_inbox_markdown(
    *,
    review_date: str,
    review_summary: str,
    routes: list[str],
    approvals: list[str],
    blockers: list[str],
    policy_exceptions: list[str],
    kpi_drifts: list[str],
    run_id: str,
) -> str:
    lines = [
        "# Founder Weekly Operating Review",
        "",
        f"- Review Date: {review_date}",
        f"- Run ID: {run_id}",
        "",
        "## Review Summary",
        f"- {review_summary or 'Weekly operating review recorded.'}",
        "",
        "## Mission Routes",
    ]
    if routes:
        lines.extend(f"- {item}" for item in routes)
    else:
        lines.append("- None")

    sections = [
        ("Approvals", approvals),
        ("Blockers", blockers),
        ("Policy Exceptions", policy_exceptions),
        ("KPI Drift", kpi_drifts),
    ]
    for title, items in sections:
        lines.extend(["", f"## {title}"])
        if items:
            lines.extend(f"- {item}" for item in items)
        else:
            lines.append("- None")

    lines.extend(["", "## Founder Review Scope"])
    if approvals or blockers or policy_exceptions or kpi_drifts:
        lines.append("- Founder review required on the narrow operational surface above.")
    else:
        lines.append("- No founder review items.")
    lines.append("")
    return "\n".join(lines)


def write_founder_inbox_artifact(session: str, content: str) -> Path:
    inbox_dir = RUNTIME_DIRS["handoffs"] / "founder-weekly-operating-review"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    session_path = inbox_dir / f"{slugify(session)}.md"
    latest_path = inbox_dir / "LATEST.md"
    atomic_write_text(session_path, content)
    atomic_write_text(latest_path, content)
    return session_path


def founder_weekly_review_command(args: argparse.Namespace) -> int:
    ensure_private_runtime()
    hq_mission_runtime.ensure_runtime()
    routes = normalize_cli_list(args.route)
    approvals = normalize_cli_list(args.approval)
    blockers = normalize_cli_list(args.blocker)
    policy_exceptions = normalize_cli_list(args.policy_exception)
    kpi_drifts = normalize_cli_list(args.kpi_drift)
    founder_attention_required = bool(
        approvals or blockers or policy_exceptions or kpi_drifts or args.force_founder_review
    )
    if args.founder_decision and not founder_attention_required:
        print("error=founder-decision requires founder review items or --force-founder-review")
        return 2

    mission = hq_mission_runtime.create_mission(
        argparse.Namespace(
            title=args.mission_title or f"Founder Weekly Operating Review {args.review_date}",
            goal=args.goal or "Review weekly operating state and route the next mission slice.",
            workflow="founder-weekly-operating-review",
            project=args.project or "Founder Weekly Operating Review",
            owner=args.owner,
            manager=args.manager,
            accepts_result=args.accepts_result,
            source_task_id=args.source_task_id,
            thread_id="",
            thread_title="",
            metadata={
                "routes": routes,
                "approvals": approvals,
                "blockers": blockers,
                "policy_exceptions": policy_exceptions,
                "kpi_drifts": kpi_drifts,
            },
        )
    )
    run = hq_mission_runtime.start_run(
        argparse.Namespace(
            mission_id=mission["id"],
            actor=args.actor,
            loop="weekly_operating_review->mission_routing->policy_gate",
            metadata={"review_date": args.review_date},
        )
    )
    hq_mission_runtime.checkpoint_step(
        argparse.Namespace(
            run_id=run["id"],
            key="weekly_operating_review",
            actor=args.actor,
            status="completed",
            summary=args.review_summary or "Weekly operating review completed.",
            evidence=[],
            metadata={"review_date": args.review_date},
        )
    )
    policy_summary = (
        "Founder inbox requires review for approvals, blockers, policy exceptions, or KPI drift."
        if founder_attention_required
        else "No founder-only items detected during the weekly operating review."
    )
    routing_step = hq_mission_runtime.checkpoint_step(
        argparse.Namespace(
            run_id=run["id"],
            key="mission_routing",
            actor=args.actor,
            status="completed",
            summary=(
                f"Prepared {len(routes)} mission route(s) for follow-up."
                if routes
                else "No new mission routes were queued in this review."
            ),
            evidence=[],
            metadata={"route_count": len(routes)},
        )
    )
    policy_step = hq_mission_runtime.checkpoint_step(
        argparse.Namespace(
            run_id=run["id"],
            key="policy_gate",
            actor=args.governor,
            status="waiting_approval" if founder_attention_required else "completed",
            summary=policy_summary,
            evidence=[],
            metadata={
                "approval_count": len(approvals),
                "blocker_count": len(blockers),
                "policy_exception_count": len(policy_exceptions),
                "kpi_drift_count": len(kpi_drifts),
            },
        )
    )
    inbox_path = write_founder_inbox_artifact(
        args.session,
        founder_inbox_markdown(
            review_date=args.review_date,
            review_summary=args.review_summary or "Weekly operating review completed.",
            routes=routes,
            approvals=approvals,
            blockers=blockers,
            policy_exceptions=policy_exceptions,
            kpi_drifts=kpi_drifts,
            run_id=run["id"],
        ),
    )
    artifact = hq_mission_runtime.attach_artifact(
        argparse.Namespace(
            run_id=run["id"],
            step_id=policy_step["id"],
            kind="founder_inbox",
            path=inbox_path.relative_to(REPO_ROOT).as_posix(),
            summary="Founder weekly operating review inbox.",
            metadata={"route_count": len(routes), "review_date": args.review_date},
        )
    )

    approval = None
    if founder_attention_required:
        approval = hq_mission_runtime.request_approval(
            argparse.Namespace(
                run_id=run["id"],
                step_id=policy_step["id"],
                requested_by=args.governor,
                requested_for="founder",
                policy_action="pause_for_founder_approval",
                summary=policy_summary,
                metadata={"artifact_id": artifact["id"]},
            )
        )
        if args.founder_decision:
            hq_mission_runtime.decide_approval(
                argparse.Namespace(
                    approval_id=approval["id"],
                    decision=args.founder_decision,
                    decided_by=args.accepts_result,
                    rationale=args.founder_rationale or "Founder weekly operating review decision recorded.",
                )
            )
            hq_mission_runtime.finish_run(
                argparse.Namespace(
                    run_id=run["id"],
                    status="completed" if args.founder_decision == "approved" else "blocked",
                )
            )
    else:
        hq_mission_runtime.finish_run(
            argparse.Namespace(
                run_id=run["id"],
                status="completed",
            )
        )

    current_run = hq_mission_runtime.require_file(
        hq_mission_runtime.run_path(run["id"]),
        "run",
        "run",
    )
    print(f"mission_id={mission['id']}")
    print(f"run_id={run['id']}")
    print(f"routing_step_id={routing_step['id']}")
    print(f"policy_step_id={policy_step['id']}")
    print(f"founder_inbox={inbox_path}")
    if approval:
        print(f"approval_id={approval['id']}")
    print(f"status={current_run['status']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Private runtime helpers for HQ, including a minimal-demo bootstrap scaffold."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap = subparsers.add_parser(
        "bootstrap",
        help="Create the private runtime and scaffold minimal-demo local HQ state if missing.",
    )
    bootstrap.add_argument(
        "--runtime-only",
        action="store_true",
        help="Create only `.hq/` runtime directories.",
    )
    bootstrap.add_argument(
        "--force",
        action="store_true",
        help="Overwrite minimal-demo scaffold files if they already exist.",
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
    spec.add_argument("--thread-id", help="Durable execution thread identifier.")
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
    handoff.add_argument("--thread-id", help="Durable execution thread identifier.")
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

    mission_runtime = subparsers.add_parser(
        "mission-runtime",
        aliases=["mission"],
        help="Forward commands to the additive mission runtime nucleus.",
    )
    mission_runtime.add_argument(
        "mission_args",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded to scripts/hq_mission_runtime.py.",
    )
    mission_runtime.set_defaults(func=mission_runtime_command)

    founder_weekly_review = subparsers.add_parser(
        "founder-weekly-review",
        aliases=["weekly-operating-review"],
        help="Run the Founder Weekly Operating Review + Mission Routing pilot on Mission/Run/Step state.",
    )
    founder_weekly_review.add_argument(
        "--session",
        default=f"session-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        help="Session identifier for the generated founder inbox artifact.",
    )
    founder_weekly_review.add_argument(
        "--review-date",
        default=date.today().isoformat(),
        help="Review date in ISO format. Defaults to today.",
    )
    founder_weekly_review.add_argument(
        "--mission-title",
        help="Optional custom mission title.",
    )
    founder_weekly_review.add_argument(
        "--goal",
        help="Optional explicit goal override for the mission.",
    )
    founder_weekly_review.add_argument(
        "--project",
        help="Optional project label override.",
    )
    founder_weekly_review.add_argument(
        "--source-task-id",
        default="founder-weekly-operating-review",
        help="Task identifier used for telemetry lineage. Defaults to founder-weekly-operating-review.",
    )
    founder_weekly_review.add_argument(
        "--owner",
        default="ai_operations_lead",
        help="Mission owner. Defaults to ai_operations_lead.",
    )
    founder_weekly_review.add_argument(
        "--manager",
        default="ceo",
        help="Mission manager. Defaults to ceo.",
    )
    founder_weekly_review.add_argument(
        "--accepts-result",
        default="ceo",
        help="Accepting role for the mission. Defaults to ceo.",
    )
    founder_weekly_review.add_argument(
        "--actor",
        default="ai_operations_lead",
        help="Actor running the weekly review. Defaults to ai_operations_lead.",
    )
    founder_weekly_review.add_argument(
        "--governor",
        default="governor",
        help="Actor applying the policy gate. Defaults to governor.",
    )
    founder_weekly_review.add_argument(
        "--review-summary",
        help="Short review summary.",
    )
    founder_weekly_review.add_argument(
        "--route",
        action="append",
        default=[],
        help="Repeat for each mission route produced by the weekly review.",
    )
    founder_weekly_review.add_argument(
        "--approval",
        action="append",
        default=[],
        help="Repeat for each approval item that must surface in the founder inbox.",
    )
    founder_weekly_review.add_argument(
        "--blocker",
        action="append",
        default=[],
        help="Repeat for each blocker that must surface in the founder inbox.",
    )
    founder_weekly_review.add_argument(
        "--policy-exception",
        action="append",
        default=[],
        help="Repeat for each policy exception that must surface in the founder inbox.",
    )
    founder_weekly_review.add_argument(
        "--kpi-drift",
        action="append",
        default=[],
        help="Repeat for each KPI drift item that must surface in the founder inbox.",
    )
    founder_weekly_review.add_argument(
        "--force-founder-review",
        action="store_true",
        help="Force a founder approval pause even if the narrow founder surface is empty.",
    )
    founder_weekly_review.add_argument(
        "--founder-decision",
        choices=["approved", "rejected", "blocked"],
        help="Optional founder decision to close the approval in the same command.",
    )
    founder_weekly_review.add_argument(
        "--founder-rationale",
        help="Optional rationale for --founder-decision.",
    )
    founder_weekly_review.set_defaults(func=founder_weekly_review_command)

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
