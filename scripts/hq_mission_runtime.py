#!/usr/bin/env python3
"""Additive mission runtime nucleus for durable local Mission/Run/Step state."""

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

from hq_io import append_jsonl, write_json


REPO_ROOT = Path(
    os.environ.get("HQ_MISSION_RUNTIME_REPO_ROOT", Path(__file__).resolve().parents[1])
).resolve()
PRIVATE_ROOT = Path(os.environ.get("HQ_RUNTIME_PRIVATE_ROOT", REPO_ROOT / ".hq")).resolve()
RUNTIME_ROOT = PRIVATE_ROOT / "state" / "mission-runtime"
RUNTIME_DIRS = {
    "missions": RUNTIME_ROOT / "missions",
    "runs": RUNTIME_ROOT / "runs",
    "steps": RUNTIME_ROOT / "steps",
    "approvals": RUNTIME_ROOT / "approvals",
    "artifacts": RUNTIME_ROOT / "artifacts",
    "events": RUNTIME_ROOT / "events",
}
ALLOWED_STEP_STATUSES = {
    "planned",
    "running",
    "completed",
    "blocked",
    "waiting_approval",
    "failed",
    "skipped",
}
ALLOWED_APPROVAL_DECISIONS = {"approved", "rejected", "blocked"}
ALLOWED_POLICY_ACTIONS = {"allow", "allow_with_review", "pause_for_founder_approval", "block"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify(value: str) -> str:
    chunks: list[str] = []
    current: list[str] = []
    for char in value.lower().strip():
        if char.isalnum():
            current.append(char)
            continue
        if current:
            chunks.append("".join(current))
            current = []
    if current:
        chunks.append("".join(current))
    return "-".join(chunks) or "item"


def make_id(prefix: str, label: str) -> str:
    return f"{prefix}-{slugify(label)}-{uuid.uuid4().hex[:8]}"


def parse_json_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise argparse.ArgumentTypeError("JSON payload must be an object")
    return payload


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_runtime() -> None:
    for path in RUNTIME_DIRS.values():
        path.mkdir(parents=True, exist_ok=True)


def mission_path(mission_id: str) -> Path:
    return RUNTIME_DIRS["missions"] / f"{mission_id}.json"


def run_path(run_id: str) -> Path:
    return RUNTIME_DIRS["runs"] / f"{run_id}.json"


def step_path(step_id: str) -> Path:
    return RUNTIME_DIRS["steps"] / f"{step_id}.json"


def approval_path(approval_id: str) -> Path:
    return RUNTIME_DIRS["approvals"] / f"{approval_id}.json"


def artifact_path(artifact_id: str) -> Path:
    return RUNTIME_DIRS["artifacts"] / f"{artifact_id}.json"


def event_file_for_timestamp(timestamp: str) -> Path:
    day = timestamp[:10]
    month = day[:7]
    return RUNTIME_DIRS["events"] / month / f"{day}.jsonl"


def record_event(
    *,
    event_type: str,
    entity_id: str,
    summary: str,
    payload: dict[str, Any] | None = None,
) -> None:
    created_at = utc_now()
    event = {
        "id": str(uuid.uuid4()),
        "created_at": created_at,
        "event_type": event_type,
        "entity_id": entity_id,
        "summary": summary,
        "payload": payload or {},
    }
    append_jsonl(event_file_for_timestamp(created_at), event)


def require_file(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"{label} not found: {path.stem}")
    return load_json(path)


def create_mission(args: argparse.Namespace) -> dict[str, Any]:
    mission_id = make_id("mission", args.title)
    created_at = utc_now()
    payload = {
        "schema_version": 1,
        "entity_type": "mission",
        "id": mission_id,
        "title": args.title.strip(),
        "goal": str(args.goal or "").strip(),
        "workflow": str(args.workflow or "").strip(),
        "project": str(args.project or "").strip(),
        "owner": str(args.owner or "").strip(),
        "manager": str(args.manager or "").strip(),
        "accepts_result": str(args.accepts_result or "").strip(),
        "source_task_id": str(args.source_task_id or "").strip(),
        "status": "planned",
        "latest_run_id": "",
        "run_ids": [],
        "created_at": created_at,
        "updated_at": created_at,
        "metadata": args.metadata or {},
    }
    write_json(mission_path(mission_id), payload)
    record_event(
        event_type="mission_created",
        entity_id=mission_id,
        summary=f"Created mission '{payload['title']}'.",
        payload={"workflow": payload["workflow"], "source_task_id": payload["source_task_id"]},
    )
    return payload


def create_mission_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    payload = create_mission(args)
    print(f"mission_id={payload['id']}")
    print(f"mission_file={mission_path(payload['id'])}")
    return 0


def start_run(args: argparse.Namespace) -> dict[str, Any]:
    mission = require_file(mission_path(args.mission_id), "mission")
    run_id = make_id("run", f"{mission['title']}-{args.actor or 'runtime'}")
    created_at = utc_now()
    payload = {
        "schema_version": 1,
        "entity_type": "run",
        "id": run_id,
        "mission_id": mission["id"],
        "status": "running",
        "actor": str(args.actor or "").strip(),
        "loop": str(args.loop or "").strip(),
        "current_step_id": "",
        "resume_from_step_id": "",
        "last_successful_step_id": "",
        "step_ids": [],
        "approval_ids": [],
        "artifact_ids": [],
        "checkpoint_count": 0,
        "started_at": created_at,
        "finished_at": "",
        "created_at": created_at,
        "updated_at": created_at,
        "metadata": args.metadata or {},
    }
    write_json(run_path(run_id), payload)
    mission["latest_run_id"] = run_id
    mission["run_ids"] = list(dict.fromkeys([*mission.get("run_ids", []), run_id]))
    mission["status"] = "active"
    mission["updated_at"] = created_at
    write_json(mission_path(mission["id"]), mission)
    record_event(
        event_type="run_started",
        entity_id=run_id,
        summary=f"Started run for mission '{mission['title']}'.",
        payload={"mission_id": mission["id"], "actor": payload["actor"]},
    )
    return payload


def start_run_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    try:
        payload = start_run(args)
    except ValueError as exc:
        print(f"error={exc}")
        return 2
    print(f"run_id={payload['id']}")
    print(f"run_file={run_path(payload['id'])}")
    return 0


def checkpoint_step(args: argparse.Namespace) -> dict[str, Any]:
    if args.status not in ALLOWED_STEP_STATUSES:
        raise ValueError("status must be one of: " + ", ".join(sorted(ALLOWED_STEP_STATUSES)))
    run = require_file(run_path(args.run_id), "run")
    step_id = make_id("step", f"{args.key}-{args.actor or 'actor'}")
    created_at = utc_now()
    payload = {
        "schema_version": 1,
        "entity_type": "step",
        "id": step_id,
        "run_id": run["id"],
        "mission_id": run["mission_id"],
        "key": args.key.strip(),
        "actor": str(args.actor or "").strip(),
        "status": args.status,
        "summary": str(args.summary or "").strip(),
        "evidence": [item for item in args.evidence if item.strip()],
        "metadata": args.metadata or {},
        "created_at": created_at,
        "updated_at": created_at,
        "completed_at": created_at if args.status == "completed" else "",
    }
    write_json(step_path(step_id), payload)
    run["step_ids"] = list(dict.fromkeys([*run.get("step_ids", []), step_id]))
    run["current_step_id"] = step_id
    if args.status == "completed":
        run["checkpoint_count"] = int(run.get("checkpoint_count", 0)) + 1
        run["resume_from_step_id"] = step_id
        run["last_successful_step_id"] = step_id
        run["status"] = "running"
    elif args.status == "waiting_approval":
        run["status"] = "waiting_approval"
    elif args.status in {"blocked", "failed"}:
        run["status"] = args.status
    else:
        run["status"] = "running"
    run["updated_at"] = created_at
    write_json(run_path(run["id"]), run)
    record_event(
        event_type="step_checkpointed",
        entity_id=step_id,
        summary=f"Recorded step '{payload['key']}' with status '{payload['status']}'.",
        payload={"run_id": run["id"], "actor": payload["actor"]},
    )
    return payload


def checkpoint_step_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    try:
        payload = checkpoint_step(args)
    except ValueError as exc:
        print(f"error={exc}")
        return 2
    print(f"step_id={payload['id']}")
    print(f"step_file={step_path(payload['id'])}")
    return 0


def request_approval(args: argparse.Namespace) -> dict[str, Any]:
    if args.policy_action not in ALLOWED_POLICY_ACTIONS:
        raise ValueError(
            "policy_action must be one of: " + ", ".join(sorted(ALLOWED_POLICY_ACTIONS))
        )
    run = require_file(run_path(args.run_id), "run")
    step = require_file(step_path(args.step_id), "step")
    approval_id = make_id("approval", f"{step['key']}-{args.requested_by or 'requester'}")
    created_at = utc_now()
    payload = {
        "schema_version": 1,
        "entity_type": "approval",
        "id": approval_id,
        "mission_id": run["mission_id"],
        "run_id": run["id"],
        "step_id": step["id"],
        "requested_by": str(args.requested_by or "").strip(),
        "requested_for": str(args.requested_for or "founder").strip(),
        "policy_action": args.policy_action,
        "status": "pending",
        "decision": "",
        "summary": str(args.summary or "").strip(),
        "rationale": "",
        "requested_at": created_at,
        "decided_at": "",
        "decided_by": "",
        "metadata": args.metadata or {},
    }
    write_json(approval_path(approval_id), payload)
    run["approval_ids"] = list(dict.fromkeys([*run.get("approval_ids", []), approval_id]))
    run["status"] = "waiting_approval"
    run["updated_at"] = created_at
    write_json(run_path(run["id"]), run)
    if step["status"] != "waiting_approval":
        step["status"] = "waiting_approval"
        step["updated_at"] = created_at
        write_json(step_path(step["id"]), step)
    record_event(
        event_type="approval_requested",
        entity_id=approval_id,
        summary=f"Requested approval for step '{step['key']}'.",
        payload={"run_id": run["id"], "step_id": step["id"], "policy_action": args.policy_action},
    )
    return payload


def request_approval_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    try:
        payload = request_approval(args)
    except ValueError as exc:
        print(f"error={exc}")
        return 2
    print(f"approval_id={payload['id']}")
    print(f"approval_file={approval_path(payload['id'])}")
    return 0


def decide_approval(args: argparse.Namespace) -> dict[str, Any]:
    if args.decision not in ALLOWED_APPROVAL_DECISIONS:
        raise ValueError("decision must be one of: " + ", ".join(sorted(ALLOWED_APPROVAL_DECISIONS)))
    approval = require_file(approval_path(args.approval_id), "approval")
    run = require_file(run_path(approval["run_id"]), "run")
    step = require_file(step_path(approval["step_id"]), "step")
    decided_at = utc_now()
    approval["decision"] = args.decision
    approval["status"] = "decided"
    approval["rationale"] = str(args.rationale or "").strip()
    approval["decided_by"] = str(args.decided_by or "").strip()
    approval["decided_at"] = decided_at
    approval["updated_at"] = decided_at
    write_json(approval_path(approval["id"]), approval)
    if args.decision == "approved":
        run["status"] = "running"
    elif args.decision == "rejected":
        run["status"] = "blocked"
    else:
        run["status"] = "blocked"
    run["updated_at"] = decided_at
    write_json(run_path(run["id"]), run)
    step["metadata"] = step.get("metadata", {})
    step["metadata"]["approval_decision"] = args.decision
    step["updated_at"] = decided_at
    write_json(step_path(step["id"]), step)
    record_event(
        event_type="approval_decided",
        entity_id=approval["id"],
        summary=f"Approval decision '{args.decision}' recorded.",
        payload={"run_id": run["id"], "step_id": step["id"], "decided_by": approval["decided_by"]},
    )
    return approval


def decide_approval_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    try:
        payload = decide_approval(args)
    except ValueError as exc:
        print(f"error={exc}")
        return 2
    print(f"approval_id={payload['id']}")
    print(f"decision={payload['decision']}")
    return 0


def attach_artifact(args: argparse.Namespace) -> dict[str, Any]:
    run = require_file(run_path(args.run_id), "run")
    step = require_file(step_path(args.step_id), "step")
    artifact_id = make_id("artifact", f"{args.kind}-{Path(args.path).name}")
    created_at = utc_now()
    payload = {
        "schema_version": 1,
        "entity_type": "artifact",
        "id": artifact_id,
        "mission_id": run["mission_id"],
        "run_id": run["id"],
        "step_id": step["id"],
        "kind": str(args.kind or "").strip(),
        "path": str(args.path or "").strip(),
        "summary": str(args.summary or "").strip(),
        "created_at": created_at,
        "updated_at": created_at,
        "metadata": args.metadata or {},
    }
    write_json(artifact_path(artifact_id), payload)
    run["artifact_ids"] = list(dict.fromkeys([*run.get("artifact_ids", []), artifact_id]))
    run["updated_at"] = created_at
    write_json(run_path(run["id"]), run)
    record_event(
        event_type="artifact_attached",
        entity_id=artifact_id,
        summary=f"Attached artifact '{payload['kind']}'.",
        payload={"run_id": run["id"], "step_id": step["id"], "path": payload["path"]},
    )
    return payload


def attach_artifact_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    try:
        payload = attach_artifact(args)
    except ValueError as exc:
        print(f"error={exc}")
        return 2
    print(f"artifact_id={payload['id']}")
    print(f"artifact_file={artifact_path(payload['id'])}")
    return 0


def finish_run(args: argparse.Namespace) -> dict[str, Any]:
    run = require_file(run_path(args.run_id), "run")
    mission = require_file(mission_path(run["mission_id"]), "mission")
    finished_at = utc_now()
    run["status"] = args.status
    run["finished_at"] = finished_at
    run["updated_at"] = finished_at
    write_json(run_path(run["id"]), run)
    mission["status"] = "completed" if args.status == "completed" else args.status
    mission["updated_at"] = finished_at
    write_json(mission_path(mission["id"]), mission)
    record_event(
        event_type="run_finished",
        entity_id=run["id"],
        summary=f"Finished run with status '{args.status}'.",
        payload={"mission_id": mission["id"]},
    )
    return run


def finish_run_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    try:
        payload = finish_run(args)
    except ValueError as exc:
        print(f"error={exc}")
        return 2
    print(f"run_id={payload['id']}")
    print(f"status={payload['status']}")
    return 0


def show_run_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    try:
        payload = require_file(run_path(args.run_id), "run")
    except ValueError as exc:
        print(f"error={exc}")
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Additive durable mission runtime nucleus for HQ Mission/Run/Step state."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Create the mission runtime state directories.")
    init.set_defaults(func=lambda args: (ensure_runtime() or print(f"runtime_root={RUNTIME_ROOT}") or 0))

    create_mission_parser = subparsers.add_parser(
        "create-mission",
        help="Create a mission record in the local mission runtime.",
    )
    create_mission_parser.add_argument("--title", required=True, help="Mission title.")
    create_mission_parser.add_argument("--goal", help="Mission goal.")
    create_mission_parser.add_argument("--workflow", help="Workflow identifier.")
    create_mission_parser.add_argument("--project", help="Project label.")
    create_mission_parser.add_argument("--owner", help="Owner role.")
    create_mission_parser.add_argument("--manager", help="Manager role.")
    create_mission_parser.add_argument("--accepts-result", help="Accepting role.")
    create_mission_parser.add_argument("--source-task-id", help="Optional source task id.")
    create_mission_parser.add_argument(
        "--metadata",
        type=parse_json_object,
        help="Optional inline JSON metadata object.",
    )
    create_mission_parser.set_defaults(func=create_mission_command)

    start_run_parser = subparsers.add_parser(
        "start-run",
        help="Start a new run for an existing mission.",
    )
    start_run_parser.add_argument("--mission-id", required=True, help="Mission identifier.")
    start_run_parser.add_argument("--actor", help="Actor starting the run.")
    start_run_parser.add_argument("--loop", help="Loop description.")
    start_run_parser.add_argument(
        "--metadata",
        type=parse_json_object,
        help="Optional inline JSON metadata object.",
    )
    start_run_parser.set_defaults(func=start_run_command)

    checkpoint_step_parser = subparsers.add_parser(
        "checkpoint-step",
        help="Record a step checkpoint for a run.",
    )
    checkpoint_step_parser.add_argument("--run-id", required=True, help="Run identifier.")
    checkpoint_step_parser.add_argument("--key", required=True, help="Step key, e.g. planner.")
    checkpoint_step_parser.add_argument("--actor", help="Actor role for the step.")
    checkpoint_step_parser.add_argument(
        "--status",
        required=True,
        choices=sorted(ALLOWED_STEP_STATUSES),
        help="Step status.",
    )
    checkpoint_step_parser.add_argument("--summary", help="Short step summary.")
    checkpoint_step_parser.add_argument(
        "--evidence",
        action="append",
        default=[],
        help="Repeat for each evidence link or artifact reference.",
    )
    checkpoint_step_parser.add_argument(
        "--metadata",
        type=parse_json_object,
        help="Optional inline JSON metadata object.",
    )
    checkpoint_step_parser.set_defaults(func=checkpoint_step_command)

    request_approval_parser = subparsers.add_parser(
        "request-approval",
        help="Create a first-class approval object linked to a run step.",
    )
    request_approval_parser.add_argument("--run-id", required=True, help="Run identifier.")
    request_approval_parser.add_argument("--step-id", required=True, help="Step identifier.")
    request_approval_parser.add_argument("--requested-by", required=True, help="Requesting actor.")
    request_approval_parser.add_argument(
        "--requested-for",
        help="Approver or inbox owner. Defaults to founder.",
    )
    request_approval_parser.add_argument(
        "--policy-action",
        required=True,
        choices=sorted(ALLOWED_POLICY_ACTIONS),
        help="Policy action that triggered the approval.",
    )
    request_approval_parser.add_argument("--summary", help="Approval summary.")
    request_approval_parser.add_argument(
        "--metadata",
        type=parse_json_object,
        help="Optional inline JSON metadata object.",
    )
    request_approval_parser.set_defaults(func=request_approval_command)

    decide_approval_parser = subparsers.add_parser(
        "decide-approval",
        help="Record an approval decision and unblock or block the run.",
    )
    decide_approval_parser.add_argument("--approval-id", required=True, help="Approval identifier.")
    decide_approval_parser.add_argument(
        "--decision",
        required=True,
        choices=sorted(ALLOWED_APPROVAL_DECISIONS),
        help="Final approval decision.",
    )
    decide_approval_parser.add_argument("--decided-by", required=True, help="Decision maker.")
    decide_approval_parser.add_argument("--rationale", help="Decision rationale.")
    decide_approval_parser.set_defaults(func=decide_approval_command)

    attach_artifact_parser = subparsers.add_parser(
        "attach-artifact",
        help="Attach a first-class artifact to a run step.",
    )
    attach_artifact_parser.add_argument("--run-id", required=True, help="Run identifier.")
    attach_artifact_parser.add_argument("--step-id", required=True, help="Step identifier.")
    attach_artifact_parser.add_argument("--kind", required=True, help="Artifact kind.")
    attach_artifact_parser.add_argument("--path", required=True, help="Artifact path or URI.")
    attach_artifact_parser.add_argument("--summary", help="Artifact summary.")
    attach_artifact_parser.add_argument(
        "--metadata",
        type=parse_json_object,
        help="Optional inline JSON metadata object.",
    )
    attach_artifact_parser.set_defaults(func=attach_artifact_command)

    finish_run_parser = subparsers.add_parser(
        "finish-run",
        help="Mark a run as completed or otherwise terminal.",
    )
    finish_run_parser.add_argument("--run-id", required=True, help="Run identifier.")
    finish_run_parser.add_argument(
        "--status",
        required=True,
        choices=["completed", "failed", "blocked", "cancelled"],
        help="Terminal run status.",
    )
    finish_run_parser.set_defaults(func=finish_run_command)

    show_run_parser = subparsers.add_parser(
        "show-run",
        help="Render one run record as JSON.",
    )
    show_run_parser.add_argument("--run-id", required=True, help="Run identifier.")
    show_run_parser.set_defaults(func=show_run_command)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = args.func(args)
    return int(result)


if __name__ == "__main__":
    raise SystemExit(main())
