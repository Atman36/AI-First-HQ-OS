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
os.environ.setdefault("HQ_CONTROL_PLANE_REPO_ROOT", str(DEFAULT_REPO_ROOT))

from hq_io import append_jsonl as append_jsonl_record
from hq_io import atomic_write_text, write_json
import hq_control_plane
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
        "subagent_context_protocol": {
            "owner": "ai_operations_lead",
            "applies_to_roles": ["ceo", "ai_operations_lead", "governor"],
            "inherit_parent_history": False,
            "require_explicit_context_packet": True,
            "require_original_source_material": True,
            "context_packet_sections": [
                "task_contract",
                "constraints_and_decisions",
                "prior_agent_outputs",
                "original_source_material",
                "write_scope",
                "verification_and_acceptance",
            ],
            "required_packet_fields": [
                "task",
                "done_when",
                "source_paths",
                "relevant_outputs",
                "write_scope",
                "verification_commands",
                "accepting_role",
            ],
            "return_handoff_requirements": [
                "outcome_summary",
                "evidence_or_verification",
                "files_touched",
                "open_questions",
                "recommended_next_step",
            ],
            "child_session_defaults": {
                "scope": "child_isolated",
                "blocked_tool_classes": [
                    "delegation",
                    "user_interaction",
                    "shared_memory_write",
                    "external_side_effect",
                ],
            },
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
        except (ValueError, RuntimeError) as exc:
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


AUTOPILOT_COLUMN_PRIORITY = (
    "review",
    "executing",
    "this_week",
    "scheduled",
    "policy_check",
    "triage",
    "intake",
)


def load_active_work_payload() -> dict[str, Any]:
    active_work_path = REPO_ROOT / "05 AI Control Plane" / "active-work.json"
    if not active_work_path.exists():
        raise FileNotFoundError(f"active work file not found: {active_work_path}")
    payload = json.loads(active_work_path.read_text(encoding="utf-8"))
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("active-work.json must contain a tasks array")
    return payload


def actionable_tasks(
    tasks: list[dict[str, Any]],
    *,
    project: str = "",
) -> list[dict[str, Any]]:
    priority = {column: index for index, column in enumerate(AUTOPILOT_COLUMN_PRIORITY)}
    filtered: list[dict[str, Any]] = []
    for task in tasks:
        column = str(task.get("column") or "").strip()
        task_project = str(task.get("project") or "").strip()
        if project and task_project != project:
            continue
        if column in {"blocked", "waiting", "accepted", "synced", "done"}:
            continue
        filtered.append(task)
    return sorted(
        filtered,
        key=lambda task: (
            priority.get(str(task.get("column") or "").strip(), len(priority)),
            str(task.get("project") or "").strip(),
            str(task.get("title") or "").strip(),
        ),
    )


def founder_attention_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for task in tasks:
        if str(task.get("column") or "").strip() != "review":
            continue
        accepts_result = str(task.get("accepts_result") or "").strip()
        risk_tier = str(task.get("risk_tier") or "").strip()
        autonomy_tier = str(task.get("autonomy_tier") or "").strip()
        if accepts_result == "ceo" or risk_tier == "high" or autonomy_tier == "A1":
            items.append(task)
    return items


def choose_parallel_support_task(
    primary: dict[str, Any],
    tasks: list[dict[str, Any]],
) -> dict[str, Any] | None:
    primary_id = str(primary.get("id") or "").strip()
    primary_column = str(primary.get("column") or "").strip()
    for task in tasks:
        if str(task.get("id") or "").strip() == primary_id:
            continue
        if primary_column == "review" and str(task.get("column") or "").strip() == "executing":
            return task
    for task in tasks:
        if str(task.get("id") or "").strip() != primary_id:
            return task
    return None


def relative_read_first_for_task(task: dict[str, Any]) -> list[str]:
    items = ["05 AI Control Plane/active-work.json"]
    primary_file = str(task.get("primary_update_file") or "").strip()
    if primary_file:
        items.append(primary_file)
    for align_file in task.get("align_files") or []:
        text = str(align_file).strip()
        if text:
            items.append(text)
    project_name = str(task.get("project") or "").strip()
    if project_name:
        candidate = REPO_ROOT / "04 Projects" / f"{project_name}.md"
        if candidate.exists():
            items.append(candidate.relative_to(REPO_ROOT).as_posix())
    return normalize_cli_list(items)


def task_route_line(label: str, task: dict[str, Any]) -> str:
    return (
        f"{label}: [{task.get('project')}] {task.get('title')} "
        f"({task.get('owner')} / {task.get('column')}) -> {task.get('next_step')}"
    )


def route_next_slice_command(args: argparse.Namespace) -> int:
    ensure_private_runtime()
    try:
        payload = load_active_work_payload()
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    tasks = actionable_tasks(payload["tasks"], project=args.project or "")
    if not tasks:
        if args.project:
            print(f"error=no actionable tasks for project '{args.project}'")
        else:
            print("error=no actionable tasks in active-work.json")
        return 2

    primary = tasks[0]
    support = choose_parallel_support_task(primary, tasks)
    founder_items = founder_attention_tasks(payload["tasks"])
    founder_lines = [task_route_line("Founder review", task) for task in founder_items]
    spec_task_name = args.task_name or "Route next slice"
    session = args.session or f"session-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    read_first = relative_read_first_for_task(primary)
    if support:
        read_first.extend(relative_read_first_for_task(support))
        read_first = normalize_cli_list(read_first)

    spec_args = argparse.Namespace(
        task=spec_task_name,
        session=session,
        owner=args.owner or "AI Operations Lead",
        thread_id=args.thread_id or "",
        status="ready",
        goal=(
            f"Keep HQ moving without a manual 'what next' prompt by routing the next slice from "
            f"active-work.json. Current primary task: {primary.get('title')}."
        ),
        primary_file=str(primary.get("primary_update_file") or "").strip(),
        why=[
            "The founder should not need to relaunch Codex and restate the next move.",
            f"The highest-priority actionable task is currently '{primary.get('title')}' in column "
            f"'{primary.get('column')}'.",
            (
                f"Founder-only review is pending on {len(founder_items)} item(s)."
                if founder_items
                else "No founder-only review items are currently queued."
            ),
        ],
        in_scope=[
            task_route_line("Primary move", primary),
            (
                task_route_line("Parallel support", support)
                if support
                else "No separate parallel support track is currently available."
            ),
            "Refresh this private packet before handing control back.",
        ],
        out_of_scope=[
            "Do not introduce a new general multi-agent framework.",
            "Do not move private runtime state into tracked repo files.",
        ],
        read_file=read_first,
        constraint=[
            "Keep runtime artifacts private under .hq/.",
            "Use active-work.json as the queue source of truth before ad hoc chat memory.",
            "Surface founder-only review items explicitly instead of burying them in narrative.",
        ],
        acceptance=[
            "A future wake-up can identify the primary move, one support track, and founder-only review items from this packet alone.",
            "The selected task aligns with the highest-priority actionable column ordering.",
        ],
        question=[
            "Should the heartbeat stay daily or move to a tighter interval after the loop proves stable?"
        ],
        note=founder_lines or ["No founder-only review lines were generated from the current queue."],
    )
    spec_exit = spec_command(spec_args)
    if spec_exit != 0:
        return spec_exit

    spec_latest = (
        RUNTIME_DIRS["specs"] / slugify(spec_task_name) / "LATEST.md"
    ).relative_to(REPO_ROOT).as_posix()
    handoff_args = argparse.Namespace(
        task=spec_task_name,
        session=session,
        owner=args.owner or str(primary.get("owner") or "AI Operations Lead").strip(),
        thread_id=args.thread_id or "",
        status="ready_for_handoff",
        continue_from=str(primary.get("primary_update_file") or "").strip(),
        spec_file=spec_latest,
        primary_file=str(primary.get("primary_update_file") or "").strip(),
        accepting_role=str(primary.get("accepts_result") or "").strip(),
        done=[
            "Reviewed the active-work queue and selected the next slice automatically.",
            f"Primary task locked: {primary.get('id')}.",
        ],
        next=[
            task_route_line("Continue now", primary),
            (
                task_route_line("Move in parallel", support)
                if support
                else "No parallel support track is currently available."
            ),
            "Refresh `.hq/handoffs/route-next-slice/LATEST.md` before ending the session.",
        ],
        important_file=read_first,
        read_first=[spec_latest],
        risk=founder_lines,
        blocker=[],
        note=[
            f"Queue updated_at: {payload.get('updated_at', '')}",
            (
                "Founder review is pending on narrow operational surfaces."
                if founder_items
                else "No founder-only review items are pending from the queue snapshot."
            ),
        ],
    )
    handoff_exit = handoff_command(handoff_args)
    if handoff_exit != 0:
        return handoff_exit

    print(f"primary_task_id={primary.get('id')}")
    if support:
        print(f"parallel_task_id={support.get('id')}")
    print(f"founder_review_items={len(founder_items)}")
    return 0


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


def resolve_mastra_sidecar_root(value: str | None) -> Path | None:
    candidate = (value or os.environ.get("HQ_MASTRA_SIDECAR_ROOT") or "").strip()
    if not candidate:
        return None
    return Path(candidate).expanduser().resolve()


def mastra_sidecar_ready(path: Path | None) -> bool:
    if path is None:
        return False
    if not path.is_dir():
        return False
    package_path = path / "package.json"
    if not package_path.exists():
        return False
    try:
        package_payload = json.loads(package_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    scripts = package_payload.get("scripts", {})
    return isinstance(scripts, dict) and isinstance(scripts.get("run:weekly-review"), str)


def refresh_session_bootstrap() -> Path:
    bundle = hq_control_plane.validate_control_plane()
    live_tasks = [
        task
        for task in bundle["active_work"].get("tasks", []) or []
        if isinstance(task, dict) and hq_control_plane.normalize_text(task.get("column")) != "done"
    ]
    created_packets = hq_control_plane.ensure_task_packets(live_tasks)
    hq_control_plane.write_session_bootstrap(
        bundle["active_work"],
        bundle["workflow_registry"],
        created_packets=created_packets,
    )
    return hq_control_plane.SESSION_BOOTSTRAP_PATH


def mastra_founder_weekly_review_command(args: argparse.Namespace) -> list[str]:
    npm_binary = shutil.which("npm")
    if not npm_binary:
        raise RuntimeError("npm is required to run the optional Mastra sidecar")
    status_path = refresh_session_bootstrap()

    command = [
        npm_binary,
        "run",
        "run:weekly-review",
        "--",
        "--hq-root",
        str(REPO_ROOT),
        "--hq-status-file",
        str(status_path),
        "--review-date",
        args.review_date,
        "--session",
        args.session,
        "--max-routes",
        str(args.max_routes),
    ]
    if args.force_founder_review:
        command.append("--force-founder-review")
    if args.dry_run:
        command.append("--dry-run")
    if args.founder_decision:
        command.extend(["--approve", args.founder_decision])
    if args.founder_rationale:
        command.extend(["--rationale", args.founder_rationale])
    return command


def parse_mastra_weekly_review_output(stdout: str) -> dict[str, Any]:
    text = (stdout or "").strip()
    if not text:
        raise ValueError("Mastra sidecar returned empty output")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Mastra sidecar output did not contain parseable JSON")
        payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("Mastra sidecar output must be a JSON object")
    return payload


def normalize_founder_weekly_review_artifact_paths(paths: dict[str, Any] | None) -> list[str]:
    if not isinstance(paths, dict):
        return []
    normalized: list[str] = []
    for key in ("json", "markdown", "latestJson", "latestMarkdown"):
        value = str(paths.get(key) or "").strip()
        if not value or value in normalized:
            continue
        normalized.append(value)
    return normalized


def load_mastra_review_artifact_payload(artifact_paths: list[str]) -> dict[str, Any]:
    for relative_path in artifact_paths:
        if not relative_path.endswith(".json"):
            continue
        candidate = (REPO_ROOT / relative_path).resolve()
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def emit_founder_weekly_review_telemetry(
    *,
    event_type: str,
    status: str,
    summary: str,
    actor: str,
    mission: dict[str, Any],
    run: dict[str, Any],
    step_id: str,
    metadata: dict[str, Any],
) -> None:
    hq_mission_runtime.emit_runtime_telemetry(
        event_type=event_type,
        status=status,
        summary=summary,
        actor=actor,
        thread_id=run["thread_id"],
        mission_id=mission["id"],
        source_task_id=mission["source_task_id"],
        workflow=mission["workflow"],
        run_id=run["id"],
        step_id=step_id,
        metadata=metadata,
    )


def persist_founder_weekly_review_runtime(
    *,
    args: argparse.Namespace,
    runner: str,
    review_summary: str,
    routes: list[str],
    approvals: list[str],
    blockers: list[str],
    policy_exceptions: list[str],
    kpi_drifts: list[str],
    founder_attention_required: bool,
    approval_status: str,
    founder_rationale: str,
    evidence_paths: list[str],
    artifact_paths: list[str],
    sidecar_status: str = "",
) -> dict[str, Any]:
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
                "runner": runner,
                "routes": routes,
                "approvals": approvals,
                "blockers": blockers,
                "policy_exceptions": policy_exceptions,
                "kpi_drifts": kpi_drifts,
                "sidecar_status": sidecar_status,
                "artifact_paths": artifact_paths,
            },
        )
    )
    run = hq_mission_runtime.start_run(
        argparse.Namespace(
            mission_id=mission["id"],
            actor=args.actor,
            loop="weekly_operating_review->mission_routing->policy_gate",
            metadata={"review_date": args.review_date, "runner": runner, "sidecar_status": sidecar_status},
        )
    )
    review_step = hq_mission_runtime.checkpoint_step(
        argparse.Namespace(
            run_id=run["id"],
            key="weekly_operating_review",
            actor=args.actor,
            status="completed",
            summary=review_summary,
            evidence=evidence_paths,
            metadata={"review_date": args.review_date, "runner": runner, "sidecar_status": sidecar_status},
        )
    )
    review_event_metadata = {
        "review_type": "founder_weekly_review",
        "review_date": args.review_date,
        "runner": runner,
        "founder_attention_required": founder_attention_required,
        "route_count": len(routes),
        "approval_count": len(approvals),
        "blocker_count": len(blockers),
        "policy_exception_count": len(policy_exceptions),
        "kpi_drift_count": len(kpi_drifts),
        "artifact_paths": artifact_paths,
        "sidecar_status": sidecar_status,
    }
    emit_founder_weekly_review_telemetry(
        event_type="review",
        status="reviewed",
        summary=review_summary,
        actor=args.actor,
        mission=mission,
        run=run,
        step_id=review_step["id"],
        metadata=review_event_metadata,
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
            evidence=evidence_paths,
            metadata={"route_count": len(routes), "runner": runner},
        )
    )
    policy_step = hq_mission_runtime.checkpoint_step(
        argparse.Namespace(
            run_id=run["id"],
            key="policy_gate",
            actor=args.governor,
            status="waiting_approval" if founder_attention_required and approval_status == "" else "completed",
            summary=policy_summary,
            evidence=evidence_paths,
            metadata={
                "approval_count": len(approvals),
                "blocker_count": len(blockers),
                "policy_exception_count": len(policy_exceptions),
                "kpi_drift_count": len(kpi_drifts),
                "runner": runner,
                "sidecar_status": sidecar_status,
            },
        )
    )

    attached_artifacts: list[dict[str, Any]] = []
    for path in artifact_paths:
        suffix = Path(path).suffix.lower()
        kind = "review_artifact"
        if runner == "builtin" and suffix == ".md":
            kind = "founder_inbox"
        elif suffix == ".json":
            kind = "founder_weekly_review_json"
        elif suffix == ".md":
            kind = "founder_weekly_review_markdown"
        attached_artifacts.append(
            hq_mission_runtime.attach_artifact(
                argparse.Namespace(
                    run_id=run["id"],
                    step_id=review_step["id"],
                    kind=kind,
                    path=path,
                    summary=f"Founder weekly review artifact from {runner} runner.",
                    metadata={"review_date": args.review_date, "runner": runner},
                )
            )
        )

    approval = None
    verification_evidence = list(dict.fromkeys([*evidence_paths, *artifact_paths]))
    verification_metadata = {
        "artifact_ids": [item["id"] for item in attached_artifacts],
        "review_date": args.review_date,
        "runner": runner,
        "review_type": "founder_weekly_review",
        "acceptance_check": True,
        "sidecar_status": sidecar_status,
    }
    if founder_attention_required:
        approval = hq_mission_runtime.request_approval(
            argparse.Namespace(
                run_id=run["id"],
                step_id=policy_step["id"],
                requested_by=args.governor,
                requested_for="founder",
                policy_action="pause_for_founder_approval",
                summary=policy_summary,
                metadata={"artifact_ids": verification_metadata["artifact_ids"], "runner": runner},
            )
        )
        if approval_status:
            hq_mission_runtime.decide_approval(
                argparse.Namespace(
                    approval_id=approval["id"],
                    decision=approval_status,
                    decided_by=args.accepts_result,
                    rationale=founder_rationale or "Founder weekly operating review decision recorded.",
                )
            )
            if approval_status == "approved":
                verified_run = hq_mission_runtime.verify_run(
                    argparse.Namespace(
                        run_id=run["id"],
                        actor=args.accepts_result,
                        status="verified",
                        summary="Founder-approved weekly review outputs passed verification.",
                        evidence=verification_evidence,
                        metadata=verification_metadata,
                    )
                )
                emit_founder_weekly_review_telemetry(
                    event_type="acceptance",
                    status="accepted",
                    summary="Founder-approved weekly review outputs passed verification.",
                    actor=args.accepts_result,
                    mission=mission,
                    run=run,
                    step_id=verified_run["verification_state"]["step_id"],
                    metadata=verification_metadata,
                )
            hq_mission_runtime.finish_run(
                argparse.Namespace(
                    run_id=run["id"],
                    status="completed" if approval_status == "approved" else "blocked",
                )
            )
    else:
        verified_run = hq_mission_runtime.verify_run(
            argparse.Namespace(
                run_id=run["id"],
                actor=args.accepts_result,
                status="verified",
                summary="Weekly review outputs passed verification without founder escalation.",
                evidence=verification_evidence,
                metadata=verification_metadata,
            )
        )
        emit_founder_weekly_review_telemetry(
            event_type="acceptance",
            status="accepted",
            summary="Weekly review outputs passed verification without founder escalation.",
            actor=args.accepts_result,
            mission=mission,
            run=run,
            step_id=verified_run["verification_state"]["step_id"],
            metadata=verification_metadata,
        )
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
    return {
        "mission": mission,
        "run": current_run,
        "routing_step": routing_step,
        "policy_step": policy_step,
        "approval": approval,
        "artifacts": attached_artifacts,
    }


def maybe_run_mastra_founder_weekly_review(args: argparse.Namespace) -> int | None:
    sidecar_root = resolve_mastra_sidecar_root(args.mastra_sidecar_root)
    wants_mastra = args.runner in {"mastra", "auto"}
    if not wants_mastra:
        return None
    if not mastra_sidecar_ready(sidecar_root):
        if args.runner == "auto":
            return None
        print(
            "error=Mastra sidecar is not configured. "
            "Pass --mastra-sidecar-root or set HQ_MASTRA_SIDECAR_ROOT to a local at-masta checkout."
        )
        return 2

    try:
        command = mastra_founder_weekly_review_command(args)
    except RuntimeError as exc:
        print(f"error={exc}")
        return 2

    env = os.environ.copy()
    env.setdefault("HQ_ROOT", str(REPO_ROOT))
    completed = subprocess.run(
        command,
        cwd=sidecar_root,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    print("runner=mastra")
    if completed.stdout.strip():
        print(completed.stdout.strip())
    if completed.stderr.strip():
        print(completed.stderr.strip())
    if completed.returncode != 0:
        return completed.returncode or 1
    try:
        sidecar_output = parse_mastra_weekly_review_output(completed.stdout)
    except ValueError as exc:
        print(f"error={exc}")
        return 2

    artifact_paths = normalize_founder_weekly_review_artifact_paths(sidecar_output.get("artifactPaths"))
    artifact_payload = load_mastra_review_artifact_payload(artifact_paths)
    evidence_paths = list(dict.fromkeys([hq_control_plane.relative_display(hq_control_plane.SESSION_BOOTSTRAP_PATH), *artifact_paths]))
    persisted = persist_founder_weekly_review_runtime(
        args=args,
        runner="mastra",
        review_summary=str(
            artifact_payload.get("summary")
            or sidecar_output.get("summary")
            or "Weekly operating review completed."
        ),
        routes=normalize_cli_list(artifact_payload.get("routes"))
        if isinstance(artifact_payload.get("routes"), list)
        else [],
        approvals=normalize_cli_list(artifact_payload.get("approvals"))
        if isinstance(artifact_payload.get("approvals"), list)
        else [],
        blockers=normalize_cli_list(artifact_payload.get("blockers"))
        if isinstance(artifact_payload.get("blockers"), list)
        else [],
        policy_exceptions=normalize_cli_list(artifact_payload.get("policyExceptions"))
        if isinstance(artifact_payload.get("policyExceptions"), list)
        else [],
        kpi_drifts=normalize_cli_list(artifact_payload.get("kpiDrifts"))
        if isinstance(artifact_payload.get("kpiDrifts"), list)
        else [],
        founder_attention_required=bool(
            artifact_payload.get("founderAttentionRequired", sidecar_output.get("founderAttentionRequired"))
        ),
        approval_status=str(sidecar_output.get("approvalStatus") or "").strip().replace("not_required", ""),
        founder_rationale=str(
            artifact_payload.get("founderRationale") or sidecar_output.get("founderRationale") or args.founder_rationale or ""
        ).strip(),
        evidence_paths=evidence_paths,
        artifact_paths=artifact_paths,
        sidecar_status=str(sidecar_output.get("status") or "").strip(),
    )
    print(f"mission_id={persisted['mission']['id']}")
    print(f"run_id={persisted['run']['id']}")
    print(f"routing_step_id={persisted['routing_step']['id']}")
    print(f"policy_step_id={persisted['policy_step']['id']}")
    if persisted["approval"]:
        print(f"approval_id={persisted['approval']['id']}")
    print(f"status={persisted['run']['status']}")
    return 0


def founder_weekly_review_command(args: argparse.Namespace) -> int:
    ensure_private_runtime()
    hq_mission_runtime.ensure_runtime()
    mastra_exit = maybe_run_mastra_founder_weekly_review(args)
    if mastra_exit is not None:
        return mastra_exit
    print("runner=builtin")
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
            run_id="pending-runtime-record",
        ),
    )
    persisted = persist_founder_weekly_review_runtime(
        args=args,
        runner="builtin",
        review_summary=args.review_summary or "Weekly operating review completed.",
        routes=routes,
        approvals=approvals,
        blockers=blockers,
        policy_exceptions=policy_exceptions,
        kpi_drifts=kpi_drifts,
        founder_attention_required=founder_attention_required,
        approval_status=args.founder_decision or "",
        founder_rationale=args.founder_rationale or "",
        evidence_paths=[inbox_path.relative_to(REPO_ROOT).as_posix()],
        artifact_paths=[inbox_path.relative_to(REPO_ROOT).as_posix()],
    )
    atomic_write_text(
        inbox_path,
        founder_inbox_markdown(
            review_date=args.review_date,
            review_summary=args.review_summary or "Weekly operating review completed.",
            routes=routes,
            approvals=approvals,
            blockers=blockers,
            policy_exceptions=policy_exceptions,
            kpi_drifts=kpi_drifts,
            run_id=persisted["run"]["id"],
        ),
    )
    print(f"mission_id={persisted['mission']['id']}")
    print(f"run_id={persisted['run']['id']}")
    print(f"routing_step_id={persisted['routing_step']['id']}")
    print(f"policy_step_id={persisted['policy_step']['id']}")
    print(f"founder_inbox={inbox_path}")
    if persisted["approval"]:
        print(f"approval_id={persisted['approval']['id']}")
    print(f"status={persisted['run']['status']}")
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

    route_next_slice = subparsers.add_parser(
        "route-next-slice",
        help="Derive the next HQ slice from active-work.json and write private resume packets.",
    )
    route_next_slice.add_argument(
        "--session",
        default=f"session-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        help="Session identifier used for the generated spec and handoff packets.",
    )
    route_next_slice.add_argument(
        "--task-name",
        default="Route next slice",
        help="Private packet task name. Defaults to 'Route next slice'.",
    )
    route_next_slice.add_argument(
        "--owner",
        default="AI Operations Lead",
        help="Owner written into the generated packets. Defaults to AI Operations Lead.",
    )
    route_next_slice.add_argument(
        "--project",
        help="Optional project filter; only actionable tasks for this project are considered.",
    )
    route_next_slice.add_argument(
        "--thread-id",
        help="Optional durable execution thread identifier to keep packet pointers synced.",
    )
    route_next_slice.set_defaults(func=route_next_slice_command)

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
        "--runner",
        choices=["builtin", "mastra", "auto"],
        default="builtin",
        help="Execution runner. Defaults to builtin; use mastra for the optional sidecar bridge.",
    )
    founder_weekly_review.add_argument(
        "--mastra-sidecar-root",
        help="Local path to the optional Mastra sidecar checkout. Can also be set via HQ_MASTRA_SIDECAR_ROOT.",
    )
    founder_weekly_review.add_argument(
        "--review-date",
        default=date.today().isoformat(),
        help="Review date in ISO format. Defaults to today.",
    )
    founder_weekly_review.add_argument(
        "--max-routes",
        type=int,
        default=5,
        help="Maximum routes to emit when using the Mastra sidecar. Defaults to 5.",
    )
    founder_weekly_review.add_argument(
        "--dry-run",
        action="store_true",
        help="When using the Mastra sidecar, avoid writing review artifacts.",
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
        default="prove-founder-weekly-review-as-primary-workflow",
        help="Task identifier used for telemetry lineage. Defaults to prove-founder-weekly-review-as-primary-workflow.",
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
