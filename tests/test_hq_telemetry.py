import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "hq_telemetry.py"


def load_module(temp_root: Path):
    os.environ["HQ_TELEMETRY_REPO_ROOT"] = str(temp_root)
    os.environ["HQ_RUNTIME_PRIVATE_ROOT"] = str(temp_root / ".hq")
    spec = importlib.util.spec_from_file_location("hq_telemetry_test_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class HqTelemetryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_dir.name)
        (self.temp_root / "05 AI Control Plane").mkdir(parents=True, exist_ok=True)
        self.module = load_module(self.temp_root)

    def tearDown(self):
        os.environ.pop("HQ_TELEMETRY_REPO_ROOT", None)
        os.environ.pop("HQ_RUNTIME_PRIVATE_ROOT", None)
        self.temp_dir.cleanup()

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
        self.assertEqual(payload["metadata"], {"phase": "triage"})
        self.assertEqual(payload["touched_files"], ["05 AI Control Plane/active-work.json"])

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
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (control_plane_dir / "active-work.json").write_text(
            json.dumps(
                {
                    "tasks": [
                        {"id": "task-1", "owner": "delivery", "risk_tier": "medium", "column": "this_week"},
                        {"id": "task-2", "owner": "delivery", "risk_tier": "medium", "column": "waiting"},
                        {"id": "task-3", "owner": "delivery", "risk_tier": "medium", "column": "done"},
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
                "status": "queued",
                "metadata": {},
            },
            {
                "created_at": "2026-04-15T11:00:00Z",
                "event_type": "start",
                "task_id": "task-1",
                "status": "running",
                "metadata": {},
            },
            {
                "created_at": "2026-04-15T12:00:00Z",
                "event_type": "acceptance",
                "task_id": "task-1",
                "status": "accepted",
                "metadata": {"founder_hours_recovered": 2, "acceptance_check": "basic"},
            },
            {
                "created_at": "2026-04-15T13:00:00Z",
                "event_type": "sync",
                "task_id": "task-1",
                "status": "synced",
                "metadata": {},
            },
            {
                "created_at": "2026-04-15T09:00:00Z",
                "event_type": "intake",
                "task_id": "task-2",
                "status": "queued",
                "metadata": {},
            },
            {
                "created_at": "2026-04-15T10:00:00Z",
                "event_type": "escalation",
                "task_id": "task-2",
                "status": "blocked",
                "metadata": {"human_escalation": True},
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
        self.assertEqual(review["total_events"], 6)
        self.assertEqual(review["active_tasks"], 2)
        self.assertIn("human_escalation_rate", review["breached_metrics"])
        metrics = {item["id"]: item for item in review["metrics"]}
        self.assertEqual(metrics["autonomous_completion_rate"]["threshold_status"], "ok")
        self.assertEqual(metrics["human_escalation_rate"]["threshold_status"], "breached")
        self.assertEqual(metrics["telemetry_coverage_rate"]["threshold_status"], "ok")

    def test_task_cycle_verifies_full_governed_loop(self):
        control_plane_dir = self.temp_root / "05 AI Control Plane"
        (control_plane_dir / "workflow-registry.json").write_text(
            json.dumps(
                {
                    "workflows": [
                        {
                            "id": "intake-to-execution",
                            "required_telemetry_events": [
                                "intake",
                                "route",
                                "policy_check",
                                "start",
                                "acceptance",
                                "sync",
                            ],
                        }
                    ]
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
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
        (control_plane_dir / "workflow-registry.json").write_text(
            json.dumps(
                {
                    "workflows": [
                        {
                            "id": "intake-to-execution",
                            "required_telemetry_events": [
                                "intake",
                                "route",
                                "policy_check",
                                "start",
                                "acceptance",
                                "sync",
                            ],
                        }
                    ]
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
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
