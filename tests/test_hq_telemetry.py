from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "hq_telemetry.py"
SCHEMA_FIXTURES = Path(__file__).resolve().parents[1] / "05 AI Control Plane" / "schemas"


def load_module(temp_root: Path):
    os.environ["HQ_TELEMETRY_REPO_ROOT"] = str(temp_root)
    os.environ["HQ_RUNTIME_PRIVATE_ROOT"] = str(temp_root / ".hq")
    sys.modules.pop("hq_io", None)
    sys.modules.pop("hq_telemetry_store", None)
    sys.modules.pop("hq_telemetry_review", None)
    spec = importlib.util.spec_from_file_location("hq_telemetry_test_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class HqTelemetryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_dir.name)
        (self.temp_root / "05 AI Control Plane" / "schemas").mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            SCHEMA_FIXTURES,
            self.temp_root / "05 AI Control Plane" / "schemas",
            dirs_exist_ok=True,
        )
        self.write_workflow_registry()
        self.module = load_module(self.temp_root)

    def tearDown(self):
        os.environ.pop("HQ_TELEMETRY_REPO_ROOT", None)
        os.environ.pop("HQ_RUNTIME_PRIVATE_ROOT", None)
        os.environ.pop("HQ_TELEMETRY_JSONL_MAX_BYTES", None)
        os.environ.pop("HQ_TELEMETRY_JSONL_MAX_RECORDS", None)
        os.environ.pop("HQ_REVIEW_ARCHIVE_KEEP", None)
        self.temp_dir.cleanup()

    def write_workflow_registry(self, required_events: list[str] | None = None) -> None:
        events = required_events or [
            "intake",
            "route",
            "policy_check",
            "start",
            "acceptance",
            "sync",
        ]
        workflow_registry = {
            "version": 1,
            "updated_at": "2026-04-16",
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
                    "progress",
                    "approval",
                    "acceptance",
                    "sync",
                    "escalation",
                    "rollback",
                    "review",
                    "eval",
                ],
                "statuses": [
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
                ],
                "event_sets": {
                    "intake": ["intake"],
                    "ready": ["policy_check", "approval", "start"],
                    "completion": ["acceptance", "sync"],
                    "acceptance": ["acceptance"],
                    "sync": ["sync"],
                    "eval": ["review", "eval"],
                    "rollback": ["rollback"],
                    "escalation": ["escalation"],
                },
                "status_sets": {
                    "ready": ["ready", "approved", "running"],
                    "completion": ["accepted", "synced", "done"],
                    "accepted": ["accepted"],
                    "synced": ["synced"],
                },
            },
            "workflows": [
                {
                    "id": "intake-to-execution",
                    "purpose": "Default loop.",
                    "states": ["waiting", "executing", "done"],
                    "required_task_fields": [
                        "id",
                        "workflow",
                        "owner",
                        "column",
                    ],
                    "required_telemetry_events": events,
                    "transition_owners": {
                        "waiting->executing": "task_manager",
                        "executing->done": "documentation",
                    },
                }
            ],
        }
        (self.temp_root / "05 AI Control Plane" / "workflow-registry.json").write_text(
            json.dumps(workflow_registry, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_event_command_writes_jsonl(self):
        parser = self.module.build_parser()
        args = parser.parse_args(
            [
                "event",
                "--event-type",
                "route",
                "--actor",
                "ai_operations_lead",
                "--role",
                "AI Operations Lead",
                "--task-id",
                "run-first-governed-loop",
                "--thread-id",
                "thread-run-first-governed-loop-1234",
                "--mission-id",
                "mission-run-first-governed-loop-5678",
                "--run-id",
                "run-run-first-governed-loop-9abc",
                "--handoff-id",
                "handoff-run-first-governed-loop-fedc",
                "--status",
                "ready",
                "--summary",
                "Task routed to Governor for policy review.",
                "--workflow",
                "intake-to-execution",
                "--risk-tier",
                "medium",
                "--autonomy-tier",
                "A2",
                "--touched-file",
                "05 AI Control Plane/active-work.json",
                "--metadata",
                '{"phase":"triage"}',
            ]
        )

        exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        telemetry_files = sorted((self.temp_root / ".hq" / "telemetry").glob("**/*.jsonl"))
        self.assertEqual(len(telemetry_files), 1)
        payload = json.loads(telemetry_files[0].read_text(encoding="utf-8").strip())
        self.assertEqual(payload["event_type"], "route")
        self.assertEqual(payload["agent"], "ai_operations_lead")
        self.assertEqual(payload["task_id"], "run-first-governed-loop")
        self.assertEqual(payload["thread_id"], "thread-run-first-governed-loop-1234")
        self.assertEqual(payload["mission_id"], "mission-run-first-governed-loop-5678")
        self.assertEqual(payload["run_id"], "run-run-first-governed-loop-9abc")
        self.assertEqual(payload["handoff_id"], "handoff-run-first-governed-loop-fedc")
        self.assertEqual(payload["metadata"], {"phase": "triage"})
        self.assertEqual(payload["touched_files"], ["05 AI Control Plane/active-work.json"])

    def test_event_command_rotates_daily_jsonl_when_threshold_is_hit(self):
        os.environ["HQ_TELEMETRY_JSONL_MAX_BYTES"] = "256"
        os.environ["HQ_TELEMETRY_JSONL_MAX_RECORDS"] = "1000"
        telemetry_path = self.module.event_file_for_timestamp(self.module.utc_now())
        telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        telemetry_path.write_text(
            json.dumps(
                {
                    "id": "old-event",
                    "created_at": "2026-04-16T09:00:00Z",
                    "event_type": "route",
                    "agent": "ai_operations_lead",
                    "task_id": "task-0",
                    "status": "ready",
                    "summary": "x" * 400,
                    "metadata": {},
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        parser = self.module.build_parser()
        args = parser.parse_args(
            [
                "event",
                "--event-type",
                "route",
                "--actor",
                "ai_operations_lead",
                "--role",
                "AI Operations Lead",
                "--task-id",
                "task-1",
                "--status",
                "ready",
                "--summary",
                "Task routed after rotation threshold was reached.",
                "--workflow",
                "intake-to-execution",
            ]
        )

        exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        archived_files = sorted((telemetry_path.parent / "archive").glob("*.jsonl"))
        self.assertEqual(len(archived_files), 1)
        self.assertIn("old-event", archived_files[0].read_text(encoding="utf-8"))
        current_lines = telemetry_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(current_lines), 1)
        self.assertEqual(json.loads(current_lines[0])["task_id"], "task-1")

    def test_trace_contract_uses_run_as_trace_and_mission_as_thread(self):
        contract = self.module.build_trace_contract()

        self.assertEqual(contract["canonical_trace_entity"], "run")
        self.assertEqual(contract["grouping_entity"], "thread")
        self.assertEqual(contract["join_key"], "task_id")
        self.assertEqual(contract["entities"]["thread"]["otel_role"], "session")
        self.assertEqual(contract["entities"]["mission"]["parent_entity"], "thread")
        self.assertEqual(contract["entities"]["run"]["otel_role"], "trace")
        self.assertEqual(contract["entities"]["step"]["otel_role"], "span")
        self.assertEqual(contract["entities"]["approval"]["parent_entity"], "step")
        self.assertEqual(contract["entities"]["handoff"]["parent_entity"], "thread")
        self.assertEqual(contract["entities"]["eval"]["parent_entity"], "run")

    def test_weekly_metrics_generates_review_and_flags_breach(self):
        control_plane_dir = self.temp_root / "05 AI Control Plane"
        (control_plane_dir / "agent-registry.json").write_text(
            json.dumps(
                {
                    "roles": [
                        {"id": "ceo", "role_type": "human", "mission": "Approve."},
                        {"id": "ai_operations_lead", "role_type": "ai", "mission": "Operate."},
                        {"id": "delivery", "role_type": "ai", "mission": "Deliver."},
                        {"id": "documentation", "role_type": "ai", "mission": "Sync."},
                        {"id": "governor", "role_type": "ai", "mission": "Control."},
                    ]
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (control_plane_dir / "metrics-registry.json").write_text(
            json.dumps(
                {
                    "primary_metrics": [
                        {
                            "id": "autonomous_completion_rate",
                            "definition": "x",
                            "source": [".hq/telemetry/"],
                            "unit": "ratio",
                            "review_owner": "ai_operations_lead",
                            "threshold": {"comparison": ">=", "value": 0.6},
                            "action_if_breached": "tighten checks",
                        },
                        {
                            "id": "human_escalation_rate",
                            "definition": "x",
                            "source": [".hq/telemetry/"],
                            "unit": "ratio",
                            "review_owner": "ai_operations_lead",
                            "threshold": {"comparison": "<=", "value": 0.3},
                        },
                        {
                            "id": "decision_latency_hours",
                            "definition": "x",
                            "source": [".hq/telemetry/"],
                            "unit": "hours",
                            "review_owner": "ai_operations_lead",
                            "threshold": {"comparison": "<=", "value": 24},
                        },
                        {
                            "id": "documentation_lag_hours",
                            "definition": "x",
                            "source": [".hq/telemetry/"],
                            "unit": "hours",
                            "review_owner": "documentation",
                            "threshold": {"comparison": "<=", "value": 24},
                        },
                        {
                            "id": "rework_or_rollback_rate",
                            "definition": "x",
                            "source": [".hq/telemetry/"],
                            "unit": "ratio",
                            "review_owner": "governor",
                            "threshold": {"comparison": "<=", "value": 0.2},
                        },
                    ],
                    "secondary_metrics": [
                        {
                            "id": "telemetry_coverage_rate",
                            "definition": "x",
                            "source": [".hq/telemetry/"],
                            "unit": "ratio",
                            "review_owner": "ai_operations_lead",
                            "threshold": {"comparison": ">=", "value": 0.9},
                        },
                        {
                            "id": "eval_coverage_rate",
                            "definition": "x",
                            "source": [".hq/telemetry/"],
                            "unit": "ratio",
                            "review_owner": "ai_operations_lead",
                            "threshold": {"comparison": ">=", "value": 0.5},
                        },
                        {
                            "id": "repeated_internal_task_cycle_rate",
                            "definition": "x",
                            "source": [".hq/telemetry/", "05 AI Control Plane/active-work.json"],
                            "unit": "ratio",
                            "review_owner": "ai_operations_lead",
                            "threshold": {"comparison": ">=", "value": 1.0},
                        },
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.write_workflow_registry()
        (control_plane_dir / "active-work.json").write_text(
            json.dumps(
                {
                    "tasks": [
                        {
                            "id": "task-1",
                            "owner": "ai_operations_lead",
                            "support": ["governor", "delivery", "documentation"],
                            "accepts_result": "ceo",
                            "workflow": "intake-to-execution",
                            "risk_tier": "medium",
                            "autonomy_tier": "A2",
                            "column": "done",
                            "completed_at": "2026-04-15",
                        },
                        {"id": "task-2", "owner": "delivery", "risk_tier": "medium", "column": "waiting"},
                        {
                            "id": "task-3",
                            "owner": "ai_operations_lead",
                            "support": ["governor", "delivery", "documentation"],
                            "accepts_result": "ceo",
                            "workflow": "intake-to-execution",
                            "risk_tier": "medium",
                            "autonomy_tier": "A2",
                            "task_cycle_required": True,
                            "column": "done",
                            "completed_at": "2026-04-15",
                        },
                    ]
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        events = [
            {
                "created_at": "2026-04-15T10:00:00Z",
                "event_type": "intake",
                "task_id": "task-1",
                "agent": "assistant",
                "status": "queued",
                "metadata": {},
            },
            {
                "created_at": "2026-04-15T11:00:00Z",
                "event_type": "route",
                "task_id": "task-1",
                "agent": "ai_operations_lead",
                "status": "ready",
                "metadata": {},
            },
            {
                "created_at": "2026-04-15T11:15:00Z",
                "event_type": "policy_check",
                "task_id": "task-1",
                "agent": "governor",
                "status": "approved",
                "metadata": {},
            },
            {
                "created_at": "2026-04-15T11:30:00Z",
                "event_type": "start",
                "task_id": "task-1",
                "agent": "delivery",
                "status": "running",
                "metadata": {},
            },
            {
                "created_at": "2026-04-15T12:00:00Z",
                "event_type": "acceptance",
                "task_id": "task-1",
                "agent": "ceo",
                "status": "accepted",
                "metadata": {"founder_hours_recovered": 2, "acceptance_check": "basic"},
            },
            {
                "created_at": "2026-04-15T13:00:00Z",
                "event_type": "sync",
                "task_id": "task-1",
                "agent": "documentation",
                "status": "synced",
                "metadata": {},
            },
            {
                "created_at": "2026-04-15T09:00:00Z",
                "event_type": "intake",
                "task_id": "task-2",
                "agent": "assistant",
                "status": "queued",
                "metadata": {},
            },
            {
                "created_at": "2026-04-15T10:00:00Z",
                "event_type": "escalation",
                "task_id": "task-2",
                "agent": "ceo",
                "status": "blocked",
                "metadata": {"human_escalation": True},
            },
            {
                "created_at": "2026-04-15T14:00:00Z",
                "event_type": "intake",
                "task_id": "task-3",
                "agent": "assistant",
                "status": "queued",
                "metadata": {},
            },
            {
                "created_at": "2026-04-15T14:05:00Z",
                "event_type": "route",
                "task_id": "task-3",
                "agent": "ai_operations_lead",
                "status": "ready",
                "metadata": {},
            },
            {
                "created_at": "2026-04-15T14:10:00Z",
                "event_type": "policy_check",
                "task_id": "task-3",
                "agent": "governor",
                "status": "approved",
                "metadata": {},
            },
            {
                "created_at": "2026-04-15T14:15:00Z",
                "event_type": "start",
                "task_id": "task-3",
                "agent": "delivery",
                "status": "running",
                "metadata": {},
            },
            {
                "created_at": "2026-04-15T14:20:00Z",
                "event_type": "acceptance",
                "task_id": "task-3",
                "agent": "ceo",
                "status": "accepted",
                "metadata": {},
            },
            {
                "created_at": "2026-04-15T14:25:00Z",
                "event_type": "sync",
                "task_id": "task-3",
                "agent": "documentation",
                "status": "synced",
                "metadata": {},
            },
        ]
        telemetry_path = self.temp_root / ".hq" / "telemetry" / "2026-04" / "2026-04-15.jsonl"
        telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        telemetry_path.write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in events) + "\n",
            encoding="utf-8",
        )

        parser = self.module.build_parser()
        args = parser.parse_args(
            [
                "weekly-metrics",
                "--since",
                "2026-04-15",
                "--until",
                "2026-04-15",
            ]
        )

        exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        latest_json = self.temp_root / ".hq" / "telemetry" / "reviews" / "LATEST.json"
        review = json.loads(latest_json.read_text(encoding="utf-8"))
        self.assertEqual(review["total_events"], 14)
        self.assertEqual(review["active_tasks"], 1)
        self.assertIn("human_escalation_rate", review["breached_metrics"])
        metrics = {item["id"]: item for item in review["metrics"]}
        self.assertEqual(metrics["autonomous_completion_rate"]["threshold_status"], "ok")
        self.assertEqual(metrics["human_escalation_rate"]["threshold_status"], "breached")
        self.assertEqual(metrics["telemetry_coverage_rate"]["threshold_status"], "ok")
        self.assertEqual(metrics["repeated_internal_task_cycle_rate"]["threshold_status"], "ok")
        self.assertEqual(
            review["repeated_internal_work"]["required_task_cycle_task_ids"],
            ["task-3"],
        )
        self.assertEqual(review["repeated_internal_work"]["task_cycle_missing_task_ids"], [])

    def test_weekly_metrics_flags_missing_task_cycle_on_repeated_internal_work(self):
        control_plane_dir = self.temp_root / "05 AI Control Plane"
        (control_plane_dir / "agent-registry.json").write_text(
            json.dumps(
                {
                    "roles": [
                        {"id": "ceo", "role_type": "human", "mission": "Approve."},
                        {"id": "assistant", "role_type": "ai", "mission": "Intake."},
                        {"id": "ai_operations_lead", "role_type": "ai", "mission": "Operate."},
                        {"id": "delivery", "role_type": "ai", "mission": "Deliver."},
                        {"id": "documentation", "role_type": "ai", "mission": "Sync."},
                        {"id": "governor", "role_type": "ai", "mission": "Control."},
                    ]
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (control_plane_dir / "metrics-registry.json").write_text(
            json.dumps(
                {
                    "primary_metrics": [
                        {
                            "id": "autonomous_completion_rate",
                            "definition": "x",
                            "source": [".hq/telemetry/"],
                            "unit": "ratio",
                            "review_owner": "ai_operations_lead",
                            "threshold": {"comparison": ">=", "value": 0.6},
                        },
                        {
                            "id": "human_escalation_rate",
                            "definition": "x",
                            "source": [".hq/telemetry/"],
                            "unit": "ratio",
                            "review_owner": "ai_operations_lead",
                            "threshold": {"comparison": "<=", "value": 0.35},
                        },
                        {
                            "id": "decision_latency_hours",
                            "definition": "x",
                            "source": [".hq/telemetry/"],
                            "unit": "hours",
                            "review_owner": "ai_operations_lead",
                            "threshold": {"comparison": "<=", "value": 24},
                        },
                        {
                            "id": "documentation_lag_hours",
                            "definition": "x",
                            "source": [".hq/telemetry/"],
                            "unit": "hours",
                            "review_owner": "documentation",
                            "threshold": {"comparison": "<=", "value": 24},
                        },
                        {
                            "id": "rework_or_rollback_rate",
                            "definition": "x",
                            "source": [".hq/telemetry/"],
                            "unit": "ratio",
                            "review_owner": "governor",
                            "threshold": {"comparison": "<=", "value": 0.2},
                        },
                    ],
                    "secondary_metrics": [
                        {
                            "id": "telemetry_coverage_rate",
                            "definition": "x",
                            "source": [".hq/telemetry/"],
                            "unit": "ratio",
                            "review_owner": "ai_operations_lead",
                            "threshold": {"comparison": ">=", "value": 0.9},
                        },
                        {
                            "id": "eval_coverage_rate",
                            "definition": "x",
                            "source": [".hq/telemetry/"],
                            "unit": "ratio",
                            "review_owner": "ai_operations_lead",
                            "threshold": {"comparison": ">=", "value": 0.5},
                        },
                        {
                            "id": "repeated_internal_task_cycle_rate",
                            "definition": "x",
                            "source": [".hq/telemetry/", "05 AI Control Plane/active-work.json"],
                            "unit": "ratio",
                            "review_owner": "ai_operations_lead",
                            "threshold": {"comparison": ">=", "value": 1.0},
                        },
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.write_workflow_registry()
        (control_plane_dir / "active-work.json").write_text(
            json.dumps(
                {
                    "tasks": [
                        {
                            "id": "task-1",
                            "title": "First loop",
                            "owner": "ai_operations_lead",
                            "support": ["governor", "delivery", "documentation"],
                            "accepts_result": "ceo",
                            "workflow": "intake-to-execution",
                            "risk_tier": "medium",
                            "autonomy_tier": "A2",
                            "column": "done",
                            "completed_at": "2026-04-15",
                        },
                        {
                            "id": "task-2",
                            "title": "Second loop",
                            "owner": "ai_operations_lead",
                            "support": ["governor", "delivery", "documentation"],
                            "accepts_result": "ceo",
                            "workflow": "intake-to-execution",
                            "risk_tier": "medium",
                            "autonomy_tier": "A2",
                            "task_cycle_required": True,
                            "column": "done",
                            "completed_at": "2026-04-15",
                        },
                    ]
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        events = [
            {
                "created_at": "2026-04-15T09:00:00Z",
                "event_type": "intake",
                "task_id": "task-1",
                "agent": "assistant",
                "status": "queued",
                "metadata": {},
            },
            {
                "created_at": "2026-04-15T09:05:00Z",
                "event_type": "route",
                "task_id": "task-1",
                "agent": "ai_operations_lead",
                "status": "ready",
                "metadata": {},
            },
            {
                "created_at": "2026-04-15T09:10:00Z",
                "event_type": "policy_check",
                "task_id": "task-1",
                "agent": "governor",
                "status": "approved",
                "metadata": {},
            },
            {
                "created_at": "2026-04-15T09:15:00Z",
                "event_type": "start",
                "task_id": "task-1",
                "agent": "delivery",
                "status": "running",
                "metadata": {},
            },
            {
                "created_at": "2026-04-15T09:20:00Z",
                "event_type": "acceptance",
                "task_id": "task-1",
                "agent": "ceo",
                "status": "accepted",
                "metadata": {},
            },
            {
                "created_at": "2026-04-15T09:25:00Z",
                "event_type": "sync",
                "task_id": "task-1",
                "agent": "documentation",
                "status": "synced",
                "metadata": {},
            },
            {
                "created_at": "2026-04-15T10:00:00Z",
                "event_type": "intake",
                "task_id": "task-2",
                "agent": "assistant",
                "status": "queued",
                "metadata": {},
            },
            {
                "created_at": "2026-04-15T10:05:00Z",
                "event_type": "route",
                "task_id": "task-2",
                "agent": "ai_operations_lead",
                "status": "ready",
                "metadata": {},
            },
            {
                "created_at": "2026-04-15T10:15:00Z",
                "event_type": "start",
                "task_id": "task-2",
                "agent": "delivery",
                "status": "running",
                "metadata": {},
            },
            {
                "created_at": "2026-04-15T10:20:00Z",
                "event_type": "acceptance",
                "task_id": "task-2",
                "agent": "ceo",
                "status": "accepted",
                "metadata": {},
            },
            {
                "created_at": "2026-04-15T10:25:00Z",
                "event_type": "sync",
                "task_id": "task-2",
                "agent": "documentation",
                "status": "synced",
                "metadata": {},
            },
        ]
        telemetry_path = self.temp_root / ".hq" / "telemetry" / "2026-04" / "2026-04-15.jsonl"
        telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        telemetry_path.write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in events) + "\n",
            encoding="utf-8",
        )

        review = self.module.build_review_payload(
            self.module.parse_date("2026-04-15"),
            self.module.parse_date("2026-04-15"),
        )
        metrics = {item["id"]: item for item in review["metrics"]}

        self.assertIn("repeated_internal_task_cycle_rate", review["breached_metrics"])
        self.assertEqual(metrics["repeated_internal_task_cycle_rate"]["threshold_status"], "breached")
        self.assertEqual(review["repeated_internal_work"]["required_task_cycle_task_ids"], ["task-2"])
        self.assertEqual(review["repeated_internal_work"]["task_cycle_missing_task_ids"], ["task-2"])

    def test_task_cycle_verifies_full_governed_loop(self):
        control_plane_dir = self.temp_root / "05 AI Control Plane"
        self.write_workflow_registry()
        (control_plane_dir / "active-work.json").write_text(
            json.dumps(
                {
                    "tasks": [
                        {
                            "id": "verify-second-governed-loop",
                            "title": "Verify second governed loop",
                            "column": "done",
                            "completed_at": "2026-04-15",
                            "owner": "ai_operations_lead",
                            "support": ["governor", "delivery", "documentation"],
                            "accepts_result": "ceo",
                            "workflow": "intake-to-execution",
                        }
                    ]
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        telemetry_path = self.temp_root / ".hq" / "telemetry" / "2026-04" / "2026-04-15.jsonl"
        telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        telemetry_path.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "created_at": "2026-04-15T09:00:00Z",
                            "event_type": "intake",
                            "task_id": "verify-second-governed-loop",
                            "agent": "assistant",
                            "status": "queued",
                        }
                    ),
                    json.dumps(
                        {
                            "created_at": "2026-04-15T09:05:00Z",
                            "event_type": "route",
                            "task_id": "verify-second-governed-loop",
                            "agent": "ai_operations_lead",
                            "status": "ready",
                        }
                    ),
                    json.dumps(
                        {
                            "created_at": "2026-04-15T09:10:00Z",
                            "event_type": "policy_check",
                            "task_id": "verify-second-governed-loop",
                            "agent": "governor",
                            "status": "approved",
                        }
                    ),
                    json.dumps(
                        {
                            "created_at": "2026-04-15T09:15:00Z",
                            "event_type": "start",
                            "task_id": "verify-second-governed-loop",
                            "agent": "delivery",
                            "status": "running",
                        }
                    ),
                    json.dumps(
                        {
                            "created_at": "2026-04-15T09:20:00Z",
                            "event_type": "acceptance",
                            "task_id": "verify-second-governed-loop",
                            "agent": "ceo",
                            "status": "accepted",
                        }
                    ),
                    json.dumps(
                        {
                            "created_at": "2026-04-15T09:25:00Z",
                            "event_type": "sync",
                            "task_id": "verify-second-governed-loop",
                            "agent": "documentation",
                            "status": "synced",
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        parser = self.module.build_parser()
        args = parser.parse_args(["task-cycle", "--task-id", "verify-second-governed-loop"])

        exit_code = args.func(args)
        report = self.module.build_task_cycle_report("verify-second-governed-loop")

        self.assertEqual(exit_code, 0)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["missing_required_events"], [])
        self.assertTrue(report["queue_state_ok"])

    def test_task_cycle_fails_when_policy_gate_or_done_state_is_missing(self):
        control_plane_dir = self.temp_root / "05 AI Control Plane"
        self.write_workflow_registry()
        (control_plane_dir / "active-work.json").write_text(
            json.dumps(
                {
                    "tasks": [
                        {
                            "id": "verify-second-governed-loop",
                            "title": "Verify second governed loop",
                            "column": "executing",
                            "owner": "ai_operations_lead",
                            "support": ["governor", "delivery", "documentation"],
                            "accepts_result": "ceo",
                            "workflow": "intake-to-execution",
                        }
                    ]
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        telemetry_path = self.temp_root / ".hq" / "telemetry" / "2026-04" / "2026-04-15.jsonl"
        telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        telemetry_path.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "created_at": "2026-04-15T09:00:00Z",
                            "event_type": "intake",
                            "task_id": "verify-second-governed-loop",
                            "agent": "assistant",
                            "status": "queued",
                        }
                    ),
                    json.dumps(
                        {
                            "created_at": "2026-04-15T09:05:00Z",
                            "event_type": "route",
                            "task_id": "verify-second-governed-loop",
                            "agent": "ai_operations_lead",
                            "status": "ready",
                        }
                    ),
                    json.dumps(
                        {
                            "created_at": "2026-04-15T09:15:00Z",
                            "event_type": "start",
                            "task_id": "verify-second-governed-loop",
                            "agent": "delivery",
                            "status": "running",
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        parser = self.module.build_parser()
        args = parser.parse_args(["task-cycle", "--task-id", "verify-second-governed-loop"])

        exit_code = args.func(args)
        report = self.module.build_task_cycle_report("verify-second-governed-loop")

        self.assertEqual(exit_code, 1)
        self.assertEqual(report["status"], "failed")
        self.assertIn("policy_check", report["missing_required_events"])
        self.assertFalse(report["queue_state_ok"])


if __name__ == "__main__":
    unittest.main()
