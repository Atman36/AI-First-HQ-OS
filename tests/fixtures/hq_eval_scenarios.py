#!/usr/bin/env python3
"""Runnable eval fixture scenarios for HQ datasets."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_FIXTURES = REPO_ROOT / "05 AI Control Plane" / "schemas"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def scenario_env(temp_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HQ_RUNTIME_PRIVATE_ROOT"] = str(temp_root / ".hq")
    env["HQ_TELEMETRY_REPO_ROOT"] = str(temp_root)
    env["HQ_MISSION_RUNTIME_REPO_ROOT"] = str(temp_root)
    env["HQ_CONTROL_PLANE_REPO_ROOT"] = str(temp_root)
    return env


def copy_schema_fixtures(temp_root: Path) -> None:
    (temp_root / "05 AI Control Plane" / "schemas").mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        SCHEMA_FIXTURES,
        temp_root / "05 AI Control Plane" / "schemas",
        dirs_exist_ok=True,
    )


def run_passthrough(command: list[str], *, env: dict[str, str], cwd: Path) -> int:
    completed = subprocess.run(command, cwd=str(cwd), env=env, capture_output=True, text=True, check=False)
    if completed.stdout:
        sys.stdout.write(completed.stdout)
    if completed.stderr:
        sys.stderr.write(completed.stderr)
    return completed.returncode


def parse_kv(output: str) -> dict[str, str]:
    payload: dict[str, str] = {}
    for line in output.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        payload[key.strip()] = value.strip()
    return payload


def write_task_cycle_fixture(temp_root: Path, *, success: bool) -> str:
    task_id = "verify-second-governed-loop"
    write_json(
        temp_root / "05 AI Control Plane" / "workflow-registry.json",
        {
            "version": 1,
            "updated_at": "2026-04-17",
            "board_columns": [
                {"id": "waiting", "title": "Waiting"},
                {"id": "executing", "title": "Executing"},
                {"id": "done", "title": "Done"},
            ],
            "telemetry": {
                "event_types": [
                    "intake",
                    "route",
                    "policy_check",
                    "start",
                    "acceptance",
                    "sync",
                    "review",
                    "eval",
                ],
                "statuses": [
                    "queued",
                    "ready",
                    "approved",
                    "running",
                    "accepted",
                    "synced",
                    "done",
                    "reviewed",
                    "blocked",
                ],
                "event_sets": {
                    "intake": ["intake"],
                    "ready": ["policy_check", "start"],
                    "completion": ["acceptance", "sync"],
                    "eval": ["review", "eval"],
                },
                "status_sets": {
                    "ready": ["ready", "approved", "running"],
                    "completion": ["accepted", "synced", "done"],
                },
            },
            "workflows": [
                {
                    "id": "intake-to-execution",
                    "purpose": "Default loop.",
                    "states": ["waiting", "executing", "done"],
                    "required_task_fields": ["id", "workflow", "owner", "column"],
                    "required_telemetry_events": [
                        "intake",
                        "route",
                        "policy_check",
                        "start",
                        "acceptance",
                        "sync",
                    ],
                    "transition_owners": {
                        "waiting->executing": "task_manager",
                        "executing->done": "documentation",
                    },
                }
            ],
        },
    )
    write_json(
        temp_root / "05 AI Control Plane" / "active-work.json",
        {
            "tasks": [
                {
                    "id": task_id,
                    "owner": "ai_operations_lead",
                    "support": ["governor", "delivery", "documentation"],
                    "accepts_result": "ceo",
                    "workflow": "intake-to-execution",
                    "risk_tier": "medium",
                    "autonomy_tier": "A2",
                    "column": "done" if success else "executing",
                    "completed_at": "2026-04-15" if success else "",
                }
            ]
        },
    )

    events = [
        {
            "created_at": "2026-04-15T14:00:00Z",
            "event_type": "intake",
            "task_id": task_id,
            "agent": "assistant",
            "status": "queued",
            "metadata": {},
        },
        {
            "created_at": "2026-04-15T14:05:00Z",
            "event_type": "route",
            "task_id": task_id,
            "agent": "ai_operations_lead",
            "status": "ready",
            "metadata": {},
        },
        {
            "created_at": "2026-04-15T14:15:00Z",
            "event_type": "start",
            "task_id": task_id,
            "agent": "delivery",
            "status": "running",
            "metadata": {},
        },
    ]
    if success:
        events[2:2] = [
            {
                "created_at": "2026-04-15T14:10:00Z",
                "event_type": "policy_check",
                "task_id": task_id,
                "agent": "governor",
                "status": "approved",
                "metadata": {},
            }
        ]
        events.extend(
            [
                {
                    "created_at": "2026-04-15T14:20:00Z",
                    "event_type": "acceptance",
                    "task_id": task_id,
                    "agent": "ceo",
                    "status": "accepted",
                    "metadata": {},
                },
                {
                    "created_at": "2026-04-15T14:25:00Z",
                    "event_type": "sync",
                    "task_id": task_id,
                    "agent": "documentation",
                    "status": "synced",
                    "metadata": {},
                },
            ]
        )
    telemetry_path = temp_root / ".hq" / "telemetry" / "2026-04" / "2026-04-15.jsonl"
    telemetry_path.parent.mkdir(parents=True, exist_ok=True)
    telemetry_path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in events) + "\n",
        encoding="utf-8",
    )
    return task_id


def telemetry_task_cycle_scenario(*, success: bool) -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        copy_schema_fixtures(temp_root)
        task_id = write_task_cycle_fixture(temp_root, success=success)
        env = scenario_env(temp_root)
        return run_passthrough(
            [sys.executable, str(REPO_ROOT / "scripts" / "hq_telemetry.py"), "task-cycle", "--task-id", task_id],
            env=env,
            cwd=REPO_ROOT,
        )


def mission_runtime_happy_scenario() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        copy_schema_fixtures(temp_root)
        env = scenario_env(temp_root)

        create_mission = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "hq_mission_runtime.py"),
                "create-mission",
                "--title",
                "Eval Mission Runtime",
                "--workflow",
                "eval-foundation",
                "--owner",
                "ai_operations_lead",
                "--source-task-id",
                "eval-mission-runtime",
            ],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        sys.stdout.write(create_mission.stdout)
        sys.stderr.write(create_mission.stderr)
        if create_mission.returncode != 0:
            return create_mission.returncode
        mission_id = parse_kv(create_mission.stdout)["mission_id"]

        start_run = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "hq_mission_runtime.py"),
                "start-run",
                "--mission-id",
                mission_id,
                "--actor",
                "delivery",
            ],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        sys.stdout.write(start_run.stdout)
        sys.stderr.write(start_run.stderr)
        if start_run.returncode != 0:
            return start_run.returncode
        run_id = parse_kv(start_run.stdout)["run_id"]

        checkpoint_step = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "hq_mission_runtime.py"),
                "checkpoint-step",
                "--run-id",
                run_id,
                "--key",
                "planner",
                "--actor",
                "delivery",
                "--status",
                "completed",
                "--summary",
                "Planned the mission loop.",
            ],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        sys.stdout.write(checkpoint_step.stdout)
        sys.stderr.write(checkpoint_step.stderr)
        if checkpoint_step.returncode != 0:
            return checkpoint_step.returncode

        finish_run = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "hq_mission_runtime.py"),
                "finish-run",
                "--run-id",
                run_id,
                "--status",
                "completed",
            ],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        sys.stdout.write(finish_run.stdout)
        sys.stderr.write(finish_run.stderr)
        if finish_run.returncode != 0:
            return finish_run.returncode

        mission_path = temp_root / ".hq" / "state" / "mission-runtime" / "missions" / f"{mission_id}.json"
        run_path = temp_root / ".hq" / "state" / "mission-runtime" / "runs" / f"{run_id}.json"
        telemetry_files = sorted((temp_root / ".hq" / "telemetry").glob("**/*.jsonl"))
        mission = json.loads(mission_path.read_text(encoding="utf-8"))
        run = json.loads(run_path.read_text(encoding="utf-8"))
        event_count = 0
        for path in telemetry_files:
            event_count += len([line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()])

        print("runtime_status=ok")
        print(f"mission_status={mission['status']}")
        print(f"run_status={run['status']}")
        print(f"telemetry_events={event_count}")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run hermetic HQ eval fixture scenarios.")
    parser.add_argument(
        "scenario",
        choices=[
            "telemetry-task-cycle-happy",
            "telemetry-task-cycle-failure",
            "mission-runtime-happy",
        ],
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.scenario == "telemetry-task-cycle-happy":
        return telemetry_task_cycle_scenario(success=True)
    if args.scenario == "telemetry-task-cycle-failure":
        return telemetry_task_cycle_scenario(success=False)
    return mission_runtime_happy_scenario()


if __name__ == "__main__":
    raise SystemExit(main())
