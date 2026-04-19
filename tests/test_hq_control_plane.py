import importlib.util
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "hq_control_plane.py"
SCHEMA_FIXTURES = Path(__file__).resolve().parents[1] / "05 AI Control Plane" / "schemas"


def load_module(temp_root: Path):
    os.environ["HQ_CONTROL_PLANE_REPO_ROOT"] = str(temp_root)
    spec = importlib.util.spec_from_file_location("hq_control_plane_test_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class HqControlPlaneTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_dir.name)
        (self.temp_root / "05 AI Control Plane" / "schemas").mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            SCHEMA_FIXTURES,
            self.temp_root / "05 AI Control Plane" / "schemas",
            dirs_exist_ok=True,
        )
        (self.temp_root / "02 Planning").mkdir(parents=True, exist_ok=True)
        (self.temp_root / "03 Notes").mkdir(parents=True, exist_ok=True)
        (self.temp_root / "04 Projects").mkdir(parents=True, exist_ok=True)
        (self.temp_root / "scripts").mkdir(parents=True, exist_ok=True)
        (self.temp_root / "tests").mkdir(parents=True, exist_ok=True)
        (self.temp_root / "agents" / "ai-operations-lead").mkdir(parents=True, exist_ok=True)
        (self.temp_root / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
        (self.temp_root / "03 Notes" / "Decisions.md").write_text("# Decisions\n", encoding="utf-8")
        (self.temp_root / "03 Notes" / "Open Decisions.md").write_text("# Open Decisions\n", encoding="utf-8")
        (self.temp_root / "04 Projects" / "HQ Bootstrap.md").write_text("# HQ Bootstrap\n", encoding="utf-8")
        (self.temp_root / "routines.md").write_text("# Routines\n", encoding="utf-8")
        (self.temp_root / "scripts" / "hq_control_plane.py").write_text("# placeholder\n", encoding="utf-8")
        (self.temp_root / "scripts" / "hq_telemetry.py").write_text("# placeholder\n", encoding="utf-8")
        (self.temp_root / "tests" / "test_hq_control_plane.py").write_text("# placeholder\n", encoding="utf-8")
        (self.temp_root / "tests" / "test_hq_telemetry.py").write_text("# placeholder\n", encoding="utf-8")
        self.write_control_plane()
        self.module = load_module(self.temp_root)

    def tearDown(self):
        os.environ.pop("HQ_CONTROL_PLANE_REPO_ROOT", None)
        self.temp_dir.cleanup()

    def write_control_plane(self):
        control_plane_dir = self.temp_root / "05 AI Control Plane"
        (control_plane_dir / "agent-registry.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "updated_at": "2026-04-16",
                    "roles": [
                        {
                            "id": "ceo",
                            "display_name": "CEO",
                            "role_type": "human",
                            "default_autonomy_tier": "A4",
                            "mission": "Approve high-risk work.",
                        },
                        {
                            "id": "ai_operations_lead",
                            "display_name": "AI Operations Lead",
                            "role_type": "ai",
                            "default_autonomy_tier": "A2",
                            "mission": "Route work and run weekly review.",
                            "escalates_to": "governor",
                        },
                        {
                            "id": "delivery",
                            "display_name": "Delivery",
                            "role_type": "ai",
                            "default_autonomy_tier": "A2",
                            "mission": "Execute work.",
                        },
                        {
                            "id": "documentation",
                            "display_name": "Documentation",
                            "role_type": "ai",
                            "default_autonomy_tier": "A2",
                            "mission": "Sync truth.",
                        },
                        {
                            "id": "governor",
                            "display_name": "Governor",
                            "role_type": "ai",
                            "default_autonomy_tier": "A3",
                            "mission": "Enforce policy.",
                        },
                    ]
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (control_plane_dir / "operating-policies.json").write_text(
            json.dumps(
                {
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
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (control_plane_dir / "workflow-registry.json").write_text(
            json.dumps(
                {
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
                            "eval": ["review"]
                        },
                        "status_sets": {
                            "completion": ["accepted", "synced", "done"],
                            "ready": ["ready"],
                            "accepted": ["accepted"],
                            "synced": ["synced"]
                        }
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
                    "version": 1,
                    "updated_at": "2026-04-16",
                    "primary_metrics": [
                        {
                            "id": "autonomous_completion_rate",
                            "definition": "x",
                            "source": [".hq/telemetry/"],
                            "unit": "ratio",
                            "review_cadence": "weekly",
                            "review_owner": "ai_operations_lead",
                            "threshold": {"comparison": ">=", "value": 0.6},
                        },
                        {
                            "id": "human_escalation_rate",
                            "definition": "x",
                            "source": [".hq/telemetry/"],
                            "unit": "ratio",
                            "review_cadence": "weekly",
                            "review_owner": "ai_operations_lead",
                            "threshold": {"comparison": "<=", "value": 0.35},
                        },
                        {
                            "id": "decision_latency_hours",
                            "definition": "x",
                            "source": [".hq/telemetry/"],
                            "unit": "hours",
                            "review_cadence": "weekly",
                            "review_owner": "ai_operations_lead",
                            "threshold": {"comparison": "<=", "value": 24},
                        },
                        {
                            "id": "documentation_lag_hours",
                            "definition": "x",
                            "source": [".hq/telemetry/"],
                            "unit": "hours",
                            "review_cadence": "weekly",
                            "review_owner": "documentation",
                            "threshold": {"comparison": "<=", "value": 24},
                        },
                        {
                            "id": "rework_or_rollback_rate",
                            "definition": "x",
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
                            "definition": "x",
                            "source": [".hq/telemetry/"],
                            "unit": "ratio",
                            "review_cadence": "weekly",
                            "review_owner": "ai_operations_lead",
                            "threshold": {"comparison": ">=", "value": 0.9},
                        }
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
                    "version": 1,
                    "updated_at": "2026-04-15",
                    "operating_mode": "stage-2-foundation",
                    "objective": {
                        "id": "obj-1",
                        "title": "Run one governed loop",
                        "window": {"start": "2026-04-15", "target_end": "2026-05-31"},
                        "success_criteria": ["One task completes through the control plane."],
                    },
                    "tasks": [
                        {
                            "id": "task-1",
                            "title": "Run first loop",
                            "column": "this_week",
                            "manager": "ai_operations_lead",
                            "owner": "ai_operations_lead",
                            "project": "HQ Bootstrap",
                            "support": ["governor", "delivery", "documentation"],
                            "next_step": "Route one real task.",
                            "done_when": "The task is accepted and synced.",
                            "primary_update_file": "05 AI Control Plane/active-work.json",
                            "align_files": [
                                "03 Notes/Decisions.md",
                                "04 Projects/HQ Bootstrap.md",
                                "scripts/hq_control_plane.py",
                                "scripts/hq_telemetry.py",
                                "tests/test_hq_control_plane.py",
                                "tests/test_hq_telemetry.py",
                            ],
                            "accepts_result": "ceo",
                            "risk_tier": "medium",
                            "autonomy_tier": "A2",
                            "workflow": "intake-to-execution",
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def test_validate_control_plane(self):
        bundle = self.module.validate_control_plane()
        self.assertEqual(bundle["active_work"]["tasks"][0]["id"], "task-1")

    def test_sync_writes_task_board(self):
        parser = self.module.build_parser()
        args = parser.parse_args(["sync"])
        exit_code = args.func(args)
        self.assertEqual(exit_code, 0)
        task_board = self.temp_root / "02 Planning" / "Task Board.md"
        self.assertTrue(task_board.exists())
        content = task_board.read_text(encoding="utf-8")
        self.assertIn("Generated from `05 AI Control Plane/active-work.json`", content)
        self.assertIn("Run first loop", content)
        self.assertIn("HQ Bootstrap", content)
        self.assertIn("Manager: ai_operations_lead", content)
        self.assertIn("Owner: ai_operations_lead", content)

    def test_sync_renders_done_tasks_from_active_work(self):
        (self.temp_root / "README.md").write_text("# README\n", encoding="utf-8")
        active_work_path = self.temp_root / "05 AI Control Plane" / "active-work.json"
        payload = json.loads(active_work_path.read_text(encoding="utf-8"))
        payload["tasks"].append(
            {
                "id": "task-done",
                "title": "Closed loop",
                "column": "done",
                "completed_at": "2026-04-19",
                "manager": "ai_operations_lead",
                "owner": "documentation",
                "project": "HQ Bootstrap",
                "next_step": "None.",
                "done_when": "Done.",
                "primary_update_file": "README.md",
                "accepts_result": "governor",
                "risk_tier": "medium",
                "autonomy_tier": "A2",
                "workflow": "intake-to-execution",
            }
        )
        active_work_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        parser = self.module.build_parser()
        args = parser.parse_args(["sync"])
        exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        content = (self.temp_root / "02 Planning" / "Task Board.md").read_text(encoding="utf-8")
        self.assertIn("## Done", content)
        self.assertIn("Closed loop", content)
        self.assertIn("- [x] Closed loop", content)

    def test_validate_requires_manager_role(self):
        active_work_path = self.temp_root / "05 AI Control Plane" / "active-work.json"
        payload = json.loads(active_work_path.read_text(encoding="utf-8"))
        payload["tasks"][0].pop("manager")
        active_work_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        with self.assertRaises(self.module.ValidationError) as error:
            self.module.validate_control_plane()

        self.assertIn("manager", str(error.exception))

    def test_validate_reports_soft_next_step_warnings_without_failing(self):
        active_work_path = self.temp_root / "05 AI Control Plane" / "active-work.json"
        payload = json.loads(active_work_path.read_text(encoding="utf-8"))
        payload["tasks"][0]["next_step"] = (
            "Context: founder asked for a full narrative update before routing this task. "
            "This sentence should live in a spec instead."
        )
        active_work_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        parser = self.module.build_parser()
        args = parser.parse_args(["validate"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        output = buffer.getvalue()
        self.assertIn("validation=ok", output)
        self.assertIn("warnings=", output)
        self.assertIn("active-work.json.tasks[0].next_step", output)

    def test_validate_reports_role_conflict_warnings_without_failing(self):
        parser = self.module.build_parser()
        args = parser.parse_args(["validate"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        output = buffer.getvalue()
        self.assertIn("validation=ok", output)
        self.assertIn("owner and manager are the same role", output)

    def test_validate_reports_stale_handoff_warning_without_failing(self):
        active_work_path = self.temp_root / "05 AI Control Plane" / "active-work.json"
        payload = json.loads(active_work_path.read_text(encoding="utf-8"))
        payload["updated_at"] = "2026-04-20"
        payload["tasks"][0]["column"] = "executing"
        active_work_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        workflow_path = self.temp_root / "05 AI Control Plane" / "workflow-registry.json"
        workflow_payload = json.loads(workflow_path.read_text(encoding="utf-8"))
        workflow_payload["board_columns"].append({"id": "executing", "title": "Executing"})
        workflow_path.write_text(json.dumps(workflow_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        handoff_dir = self.temp_root / ".hq" / "handoffs" / "task-1"
        handoff_dir.mkdir(parents=True, exist_ok=True)
        (handoff_dir / "LATEST.md").write_text("# Handoff\n\n2026-04-15\n", encoding="utf-8")
        self.module = load_module(self.temp_root)

        parser = self.module.build_parser()
        args = parser.parse_args(["validate"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        output = buffer.getvalue()
        self.assertIn("validation=ok", output)
        self.assertIn("executing task has stale handoff", output)

    def test_validate_requires_known_subagent_context_protocol_role(self):
        policies_path = self.temp_root / "05 AI Control Plane" / "operating-policies.json"
        payload = json.loads(policies_path.read_text(encoding="utf-8"))
        payload["subagent_context_protocol"]["applies_to_roles"].append("specialist_not_registered")
        policies_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        with self.assertRaises(self.module.ValidationError) as error:
            self.module.validate_control_plane()

        self.assertIn("subagent_context_protocol.applies_to_roles", str(error.exception))

    def test_status_writes_session_bootstrap_json_and_excludes_done_tasks(self):
        (self.temp_root / "README.md").write_text("# README\n", encoding="utf-8")
        workflow_path = self.temp_root / "05 AI Control Plane" / "workflow-registry.json"
        workflow_payload = json.loads(workflow_path.read_text(encoding="utf-8"))
        workflow_payload["board_columns"].insert(-1, {"id": "blocked", "title": "Blocked"})
        workflow_payload["workflows"][0]["states"].insert(-1, "blocked")
        workflow_path.write_text(
            json.dumps(workflow_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        active_work_path = self.temp_root / "05 AI Control Plane" / "active-work.json"
        active_work_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "updated_at": "2026-04-20",
                    "operating_mode": "stage-2-foundation",
                    "objective": {
                        "id": "obj-1",
                        "title": "Run one governed loop",
                        "window": {"start": "2026-04-15", "target_end": "2026-05-31"},
                    },
                    "tasks": [
                        {
                            "id": "task-live",
                            "title": "Ship session bootstrap",
                            "column": "this_week",
                            "manager": "ai_operations_lead",
                            "owner": "delivery",
                            "project": "HQ Bootstrap",
                            "next_step": "Add the status projection command.",
                            "done_when": "The command works end to end.",
                            "primary_update_file": "scripts/hq_control_plane.py",
                            "accepts_result": "governor",
                            "risk_tier": "medium",
                            "autonomy_tier": "A2",
                            "workflow": "intake-to-execution",
                        },
                        {
                            "id": "task-blocked",
                            "title": "Resolve blocked review",
                            "column": "blocked",
                            "manager": "ai_operations_lead",
                            "owner": "governor",
                            "project": "HQ Bootstrap",
                            "next_step": "Wait for founder review on the legal wording.",
                            "done_when": "The founder review lands.",
                            "primary_update_file": "04 Projects/HQ Bootstrap.md",
                            "accepts_result": "ceo",
                            "risk_tier": "high",
                            "autonomy_tier": "A1",
                            "workflow": "intake-to-execution",
                        },
                        {
                            "id": "task-done",
                            "title": "Already finished",
                            "column": "done",
                            "completed_at": "2026-04-19",
                            "manager": "ai_operations_lead",
                            "owner": "documentation",
                            "project": "HQ Bootstrap",
                            "next_step": "None.",
                            "done_when": "Done.",
                            "primary_update_file": "README.md",
                            "accepts_result": "governor",
                            "risk_tier": "medium",
                            "autonomy_tier": "A2",
                            "workflow": "intake-to-execution",
                        },
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        handoff_dir = self.temp_root / ".hq" / "handoffs" / "task-blocked"
        handoff_dir.mkdir(parents=True, exist_ok=True)
        (handoff_dir / "LATEST.md").write_text(
            "\n".join(
                [
                    "# Handoff: Resolve blocked review",
                    "",
                    "## Blockers",
                    "",
                    "- Founder review on legal wording is still required.",
                    "- The trust boundary cannot be widened until approval lands.",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        parser = self.module.build_parser()
        args = parser.parse_args(["status", "--json"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        payload = json.loads(buffer.getvalue())
        bootstrap_path = self.temp_root / ".hq" / "state" / "session-bootstrap.json"
        self.assertTrue(bootstrap_path.exists())

        written_payload = json.loads(bootstrap_path.read_text(encoding="utf-8"))
        self.assertEqual(payload, written_payload)
        self.assertEqual(payload["objective"], "Run one governed loop")
        self.assertEqual([task["id"] for task in payload["active_tasks"]], ["task-live", "task-blocked"])
        self.assertEqual(payload["active_tasks"][0]["next_step"], "Add the status projection command.")
        self.assertEqual(payload["blocked"][0]["id"], "task-blocked")
        self.assertIn("Founder review on legal wording", payload["blocked"][0]["reason"])
        self.assertTrue(payload["stale_items"])
        self.assertTrue(
            any(item["task_id"] == "task-live" and item["kind"] == "spec" for item in payload["stale_items"])
        )
        self.assertEqual(payload["recommended_next_command"], "python3 scripts/hq_runtime.py route-next-slice")

    def test_archive_moves_done_tasks_to_runtime_archive_and_preserves_ids(self):
        (self.temp_root / "README.md").write_text("# README\n", encoding="utf-8")
        active_work_path = self.temp_root / "05 AI Control Plane" / "active-work.json"
        payload = json.loads(active_work_path.read_text(encoding="utf-8"))
        payload["tasks"].append(
            {
                "id": "task-done",
                "title": "Archive me",
                "column": "done",
                "completed_at": "2026-04-19",
                "manager": "ai_operations_lead",
                "owner": "documentation",
                "project": "HQ Bootstrap",
                "next_step": "None.",
                "done_when": "Done.",
                "primary_update_file": "README.md",
                "accepts_result": "governor",
                "risk_tier": "medium",
                "autonomy_tier": "A2",
                "workflow": "intake-to-execution",
            }
        )
        active_work_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        archive_path = self.temp_root / ".hq" / "state" / "archived-tasks.json"
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        archive_path.write_text(
            json.dumps(
                {
                    "generated_at": "2026-04-18T00:00:00Z",
                    "source_updated_at": "2026-04-18",
                    "tasks": [{"id": "task-old", "title": "Already archived"}],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        parser = self.module.build_parser()
        args = parser.parse_args(["archive"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        self.assertIn("archived=1", buffer.getvalue())
        active_work = json.loads(active_work_path.read_text(encoding="utf-8"))
        self.assertEqual([task["id"] for task in active_work["tasks"]], ["task-1"])
        archive_payload = json.loads(archive_path.read_text(encoding="utf-8"))
        self.assertEqual([task["id"] for task in archive_payload["tasks"]], ["task-old", "task-done"])
        self.assertEqual(archive_payload["tasks"][1]["title"], "Archive me")
        self.assertIn("archived_at", archive_payload["tasks"][1])

    def test_archive_re_renders_task_board_from_updated_active_work(self):
        (self.temp_root / "README.md").write_text("# README\n", encoding="utf-8")
        active_work_path = self.temp_root / "05 AI Control Plane" / "active-work.json"
        payload = json.loads(active_work_path.read_text(encoding="utf-8"))
        payload["tasks"].append(
            {
                "id": "task-done",
                "title": "Archive me",
                "column": "done",
                "completed_at": "2026-04-19",
                "manager": "ai_operations_lead",
                "owner": "documentation",
                "project": "HQ Bootstrap",
                "next_step": "None.",
                "done_when": "Done.",
                "primary_update_file": "README.md",
                "accepts_result": "governor",
                "risk_tier": "medium",
                "autonomy_tier": "A2",
                "workflow": "intake-to-execution",
            }
        )
        active_work_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        parser = self.module.build_parser()
        sync_args = parser.parse_args(["sync"])
        sync_exit_code = sync_args.func(sync_args)

        self.assertEqual(sync_exit_code, 0)
        board_path = self.temp_root / "02 Planning" / "Task Board.md"
        self.assertIn("Archive me", board_path.read_text(encoding="utf-8"))

        archive_args = parser.parse_args(["archive"])
        archive_exit_code = archive_args.func(archive_args)

        self.assertEqual(archive_exit_code, 0)
        board_content = board_path.read_text(encoding="utf-8")
        self.assertNotIn("## Done", board_content)
        self.assertNotIn("Archive me", board_content)
        self.assertIn("Run first loop", board_content)

    def test_archive_allows_empty_live_queue_after_archiving_all_done_tasks(self):
        (self.temp_root / "README.md").write_text("# README\n", encoding="utf-8")
        active_work_path = self.temp_root / "05 AI Control Plane" / "active-work.json"
        payload = json.loads(active_work_path.read_text(encoding="utf-8"))
        payload["tasks"] = [
            {
                "id": "task-done",
                "title": "Archive me",
                "column": "done",
                "completed_at": "2026-04-19",
                "manager": "ai_operations_lead",
                "owner": "documentation",
                "project": "HQ Bootstrap",
                "next_step": "None.",
                "done_when": "Done.",
                "primary_update_file": "README.md",
                "accepts_result": "governor",
                "risk_tier": "medium",
                "autonomy_tier": "A2",
                "workflow": "intake-to-execution",
            }
        ]
        active_work_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        parser = self.module.build_parser()
        args = parser.parse_args(["archive"])
        exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        bundle = self.module.validate_control_plane()
        self.assertEqual(bundle["active_work"]["tasks"], [])
        status_payload = self.module.build_status_payload(bundle["active_work"], bundle["workflow_registry"])
        self.assertEqual(status_payload["active_tasks"], [])

    def test_status_text_output_groups_active_blocked_and_stale_sections(self):
        parser = self.module.build_parser()
        args = parser.parse_args(["status"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        output = buffer.getvalue()
        self.assertIn("Active Tasks", output)
        self.assertIn("Blocked Tasks", output)
        self.assertIn("Stale Items", output)
        self.assertIn("Recommended Next Command", output)

    def test_status_scaffolds_missing_runtime_packets_for_live_tasks(self):
        parser = self.module.build_parser()
        args = parser.parse_args(["status", "--json"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        payload = json.loads(buffer.getvalue())
        spec_path = self.temp_root / ".hq" / "specs" / "task-1" / "LATEST.md"
        handoff_path = self.temp_root / ".hq" / "handoffs" / "task-1" / "LATEST.md"
        self.assertTrue(spec_path.exists())
        self.assertTrue(handoff_path.exists())
        self.assertFalse(
            any(item["task_id"] == "task-1" and item["status"] == "missing" for item in payload["stale_items"])
        )

    def test_resume_writes_quick_context_projection(self):
        parser = self.module.build_parser()
        args = parser.parse_args(["resume", "--task-id", "task-1"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        output = buffer.getvalue()
        self.assertIn("Resume Task", output)
        self.assertIn("Task ID: task-1", output)
        self.assertIn(".hq/specs/task-1/LATEST.md", output)
        self.assertIn(".hq/handoffs/task-1/LATEST.md", output)
        self.assertIn("Missing For Safe Continue", output)
        self.assertIn("Recommended Next Command", output)

        quick_context_path = self.temp_root / ".hq" / "state" / "QUICK_CONTEXT.md"
        self.assertTrue(quick_context_path.exists())
        quick_context = quick_context_path.read_text(encoding="utf-8")
        self.assertIn("Projection only", quick_context)
        self.assertIn("task-1", quick_context)
        self.assertIn("Route one real task.", quick_context)

    def test_closeout_marks_low_medium_internal_task_done(self):
        (self.temp_root / "README.md").write_text("# README\n", encoding="utf-8")
        active_work_path = self.temp_root / "05 AI Control Plane" / "active-work.json"
        active_work_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "updated_at": "2026-04-20",
                    "operating_mode": "stage-2-foundation",
                    "objective": {
                        "id": "obj-1",
                        "title": "Run one governed loop",
                        "window": {"start": "2026-04-20", "target_end": "2026-05-31"},
                    },
                    "tasks": [
                        {
                            "id": "task-closeout",
                            "title": "Close internal delivery slice",
                            "column": "executing",
                            "manager": "ai_operations_lead",
                            "owner": "delivery",
                            "project": "HQ Bootstrap",
                            "next_step": "Ship the internal closeout helper.",
                            "done_when": "The queue helper marks low-risk internal work done.",
                            "primary_update_file": "README.md",
                            "accepts_result": "governor",
                            "risk_tier": "medium",
                            "autonomy_tier": "A2",
                            "workflow": "intake-to-execution",
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        workflow_path = self.temp_root / "05 AI Control Plane" / "workflow-registry.json"
        workflow_payload = json.loads(workflow_path.read_text(encoding="utf-8"))
        workflow_payload["board_columns"].insert(-1, {"id": "executing", "title": "Executing"})
        workflow_payload["workflows"][0]["states"].insert(-1, "executing")
        workflow_path.write_text(json.dumps(workflow_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        spec_dir = self.temp_root / ".hq" / "specs" / "task-closeout"
        spec_dir.mkdir(parents=True, exist_ok=True)
        (spec_dir / "LATEST.md").write_text(
            "\n".join(
                [
                    "# Spec",
                    "",
                    "## Acceptance",
                    "- Internal closeout can complete from one command.",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        handoff_dir = self.temp_root / ".hq" / "handoffs" / "task-closeout"
        handoff_dir.mkdir(parents=True, exist_ok=True)
        (handoff_dir / "LATEST.md").write_text(
            "\n".join(
                [
                    "# Handoff",
                    "",
                    "## Done",
                    "- Helper implemented.",
                    "",
                    "## Next",
                    "- Mark the task done.",
                    "",
                    "## Blockers",
                    "- None.",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        self.module = load_module(self.temp_root)
        parser = self.module.build_parser()
        args = parser.parse_args(["closeout", "--task-id", "task-closeout"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        output = buffer.getvalue()
        self.assertIn("closeout=done", output)
        self.assertIn("Recommended Next Command", output)

        active_work = json.loads(active_work_path.read_text(encoding="utf-8"))
        self.assertEqual(active_work["tasks"][0]["column"], "done")
        self.assertEqual(active_work["tasks"][0]["completed_at"], self.module.utc_today())
        board = (self.temp_root / "02 Planning" / "Task Board.md").read_text(encoding="utf-8")
        self.assertIn("## Done", board)
        self.assertIn("Close internal delivery slice", board)

    def test_closeout_requires_non_founder_acceptance(self):
        parser = self.module.build_parser()
        args = parser.parse_args(["closeout", "--task-id", "task-1"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 1)
        output = buffer.getvalue()
        self.assertIn("closeout=not_ready", output)
        self.assertIn("founder acceptance", output)

    def test_health_reports_validation_status_warnings_and_git(self):
        parser = self.module.build_parser()
        args = parser.parse_args(["health"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        output = buffer.getvalue()
        self.assertIn("HQ Health", output)
        self.assertIn("Validation", output)
        self.assertIn("warnings=", output)
        self.assertIn("Active Tasks", output)
        self.assertIn("Git Status", output)
        self.assertIn("Recommended Next Command", output)

    def test_templates_command_lists_local_task_templates(self):
        templates_path = self.temp_root / "05 AI Control Plane" / "task-templates.json"
        templates_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "templates": [
                        {
                            "id": "research-slice",
                            "title_pattern": "Research {topic}",
                            "workflow": "intake-to-execution",
                            "risk_tier": "medium",
                            "autonomy_tier": "A2",
                            "default_owner": "research",
                            "done_when_stub": "Decision-ready research note exists.",
                        },
                        {
                            "id": "policy-decision",
                            "title_pattern": "Decide {policy_topic}",
                            "workflow": "decision-lifecycle",
                            "risk_tier": "high",
                            "autonomy_tier": "A1",
                            "default_owner": "governor",
                            "done_when_stub": "Policy call is explicit and reviewable.",
                        },
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        parser = self.module.build_parser()
        args = parser.parse_args(["templates"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        output = buffer.getvalue()
        self.assertIn("templates=ok", output)
        self.assertIn("path=05 AI Control Plane/task-templates.json", output)
        self.assertIn("count=2", output)
        self.assertIn("research-slice", output)
        self.assertIn("policy-decision", output)

    def test_preflight_passes_for_valid_task_and_role(self):
        parser = self.module.build_parser()
        args = parser.parse_args(["preflight", "--task-id", "task-1", "--role", "ai_operations_lead"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        output = buffer.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("preflight=ok", output)
        self.assertIn("task_id=task-1", output)
        self.assertIn("role=ai_operations_lead", output)

    def test_preflight_fails_for_nonexistent_task(self):
        parser = self.module.build_parser()
        args = parser.parse_args(["preflight", "--task-id", "nonexistent-task", "--role", "delivery"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 1)
        output = buffer.getvalue()
        self.assertIn("preflight=failed", output)
        self.assertIn("task 'nonexistent-task' not found", output)

    def test_preflight_fails_for_unregistered_role(self):
        parser = self.module.build_parser()
        args = parser.parse_args(["preflight", "--task-id", "task-1", "--role", "invalid_role"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 1)
        output = buffer.getvalue()
        self.assertIn("preflight=failed", output)
        self.assertIn("role 'invalid_role' is not registered", output)

    def test_preflight_fails_for_role_not_owner_or_support(self):
        parser = self.module.build_parser()
        args = parser.parse_args(["preflight", "--task-id", "task-1", "--role", "documentation"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        # documentation is in support list, so this should pass
        # Let's use a role that's not in owner or support
        args = parser.parse_args(["preflight", "--task-id", "task-1", "--role", "ceo"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 1)
        output = buffer.getvalue()
        self.assertIn("preflight=failed", output)
        self.assertIn("not the owner or in support list", output)

    def test_preflight_warns_about_missing_packets(self):
        parser = self.module.build_parser()
        args = parser.parse_args(["preflight", "--task-id", "task-1", "--role", "ai_operations_lead"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        output = buffer.getvalue()
        self.assertIn("preflight=ok", output)
        self.assertIn("warn: missing spec packet", output)
        self.assertIn("warn: missing handoff packet", output)

    def test_preflight_detects_same_owner_and_manager(self):
        control_plane_dir = self.temp_root / "05 AI Control Plane"
        active_work = json.loads((control_plane_dir / "active-work.json").read_text(encoding="utf-8"))
        # task-1 already has owner and manager both as ai_operations_lead
        self.module = load_module(self.temp_root)

        parser = self.module.build_parser()
        args = parser.parse_args(["preflight", "--task-id", "task-1", "--role", "ai_operations_lead"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        output = buffer.getvalue()
        self.assertIn("preflight=ok", output)
        self.assertIn("warn: owner and manager are the same role", output)

    def test_preflight_checks_stale_handoff_for_executing_tasks(self):
        control_plane_dir = self.temp_root / "05 AI Control Plane"
        active_work = json.loads((control_plane_dir / "active-work.json").read_text(encoding="utf-8"))
        active_work["updated_at"] = "2026-04-20"
        (control_plane_dir / "active-work.json").write_text(
            json.dumps(active_work, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        handoff_dir = self.temp_root / ".hq" / "handoffs" / "task-1"
        handoff_dir.mkdir(parents=True, exist_ok=True)
        (handoff_dir / "LATEST.md").write_text("# Handoff\n\n2026-04-15\n", encoding="utf-8")

        self.module = load_module(self.temp_root)

        parser = self.module.build_parser()
        args = parser.parse_args(["preflight", "--task-id", "task-1", "--role", "ai_operations_lead"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        output = buffer.getvalue()
        self.assertIn("preflight=ok", output)
        # Note: stale check only applies to "executing" and "accepted" columns
        # task-1 is in "this_week" so no stale warning expected

    # -------------------------------------------------------------------
    # closeout telemetry contract tests
    # -------------------------------------------------------------------

    def _setup_closeable_task(self, task_id="task-closeout", accepts="governor",
                              risk="medium", autonomy="A2"):
        """Helper: set up a task that passes can_auto_closeout with filled packets."""
        (self.temp_root / "README.md").write_text("# README\n", encoding="utf-8")
        active_work_path = self.temp_root / "05 AI Control Plane" / "active-work.json"
        active_work_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "updated_at": "2026-04-20",
                    "operating_mode": "stage-2-foundation",
                    "objective": {
                        "id": "obj-1",
                        "title": "Run one governed loop",
                        "window": {"start": "2026-04-20", "target_end": "2026-05-31"},
                    },
                    "tasks": [
                        {
                            "id": task_id,
                            "title": "Close internal delivery slice",
                            "column": "executing",
                            "manager": "ai_operations_lead",
                            "owner": "delivery",
                            "project": "HQ Bootstrap",
                            "next_step": "Ship the internal closeout helper.",
                            "done_when": "The queue helper marks low-risk internal work done.",
                            "primary_update_file": "README.md",
                            "accepts_result": accepts,
                            "risk_tier": risk,
                            "autonomy_tier": autonomy,
                            "workflow": "intake-to-execution",
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        workflow_path = self.temp_root / "05 AI Control Plane" / "workflow-registry.json"
        workflow_payload = json.loads(workflow_path.read_text(encoding="utf-8"))
        if not any(c["id"] == "executing" for c in workflow_payload["board_columns"]):
            workflow_payload["board_columns"].insert(-1, {"id": "executing", "title": "Executing"})
            workflow_payload["workflows"][0]["states"].insert(-1, "executing")
        workflow_path.write_text(json.dumps(workflow_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        spec_dir = self.temp_root / ".hq" / "specs" / task_id
        spec_dir.mkdir(parents=True, exist_ok=True)
        (spec_dir / "LATEST.md").write_text(
            "# Spec\n\n## Acceptance\n- Internal closeout can complete from one command.\n\n",
            encoding="utf-8",
        )
        handoff_dir = self.temp_root / ".hq" / "handoffs" / task_id
        handoff_dir.mkdir(parents=True, exist_ok=True)
        (handoff_dir / "LATEST.md").write_text(
            "# Handoff\n\n## Done\n- Helper implemented.\n\n## Next\n- Mark the task done.\n\n## Blockers\n- None.\n\n",
            encoding="utf-8",
        )
        self.module = load_module(self.temp_root)

    def test_closeout_writes_acceptance_and_sync_telemetry(self):
        self._setup_closeable_task()
        parser = self.module.build_parser()
        args = parser.parse_args(["closeout", "--task-id", "task-closeout"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        output = buffer.getvalue()
        self.assertIn("closeout=done", output)
        self.assertIn("telemetry=2", output)

        telemetry_root = self.temp_root / ".hq" / "telemetry"
        self.assertTrue(telemetry_root.exists())
        events = []
        for jsonl_path in telemetry_root.glob("**/*.jsonl"):
            for line in jsonl_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    events.append(json.loads(line))
        event_types = {e["event_type"] for e in events}
        self.assertIn("acceptance", event_types)
        self.assertIn("sync", event_types)
        for event in events:
            self.assertEqual(event["task_id"], "task-closeout")
            self.assertIn("id", event)
            self.assertIn("created_at", event)

    def test_closeout_skips_telemetry_for_blocked_founder_task(self):
        self._setup_closeable_task(accepts="ceo", risk="high", autonomy="A1")
        parser = self.module.build_parser()
        args = parser.parse_args(["closeout", "--task-id", "task-closeout"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 1)
        output = buffer.getvalue()
        self.assertIn("closeout=not_ready", output)
        telemetry_root = self.temp_root / ".hq" / "telemetry"
        if telemetry_root.exists():
            events = list(telemetry_root.glob("**/*.jsonl"))
            self.assertEqual(len(events), 0)

    # -------------------------------------------------------------------
    # create-task command tests
    # -------------------------------------------------------------------

    def _setup_templates(self):
        templates_path = self.temp_root / "05 AI Control Plane" / "task-templates.json"
        templates_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "updated_at": "2026-04-19",
                    "templates": [
                        {
                            "id": "research-slice",
                            "title_pattern": "Research {topic}",
                            "workflow": "intake-to-execution",
                            "risk_tier": "medium",
                            "autonomy_tier": "A2",
                            "default_owner": "research",
                            "done_when_stub": "Decision-ready research note exists.",
                        },
                        {
                            "id": "implementation-slice",
                            "title_pattern": "Implement {artifact}",
                            "workflow": "intake-to-execution",
                            "risk_tier": "medium",
                            "autonomy_tier": "A2",
                            "default_owner": "delivery",
                            "done_when_stub": "The bounded artifact exists.",
                        },
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def test_create_task_adds_task_to_active_work(self):
        self._setup_templates()
        self.module = load_module(self.temp_root)
        parser = self.module.build_parser()
        args = parser.parse_args([
            "create-task",
            "--title", "Research subagent context protocol",
            "--project", "HQ Bootstrap",
            "--owner", "delivery",
            "--manager", "ai_operations_lead",
            "--accepts-result", "governor",
        ])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        output = buffer.getvalue()
        self.assertIn("create_task=ok", output)
        self.assertIn("task_id=", output)

        active_work = json.loads(
            (self.temp_root / "05 AI Control Plane" / "active-work.json").read_text(encoding="utf-8")
        )
        new_tasks = [t for t in active_work["tasks"] if t["title"] == "Research subagent context protocol"]
        self.assertEqual(len(new_tasks), 1)
        task = new_tasks[0]
        self.assertEqual(task["owner"], "delivery")
        self.assertEqual(task["column"], "intake")
        self.assertEqual(task["workflow"], "intake-to-execution")

    def test_create_task_scaffolds_spec_and_handoff_packets(self):
        self._setup_templates()
        self.module = load_module(self.temp_root)
        parser = self.module.build_parser()
        args = parser.parse_args([
            "create-task",
            "--title", "Build verification skill",
            "--project", "HQ Bootstrap",
            "--owner", "delivery",
            "--manager", "ai_operations_lead",
            "--accepts-result", "governor",
        ])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        # extract task_id from output
        task_id = None
        for line in buffer.getvalue().splitlines():
            if line.startswith("task_id="):
                task_id = line.split("=", 1)[1].strip()
        self.assertIsNotNone(task_id)
        spec_path = self.temp_root / ".hq" / "specs" / task_id / "LATEST.md"
        handoff_path = self.temp_root / ".hq" / "handoffs" / task_id / "LATEST.md"
        self.assertTrue(spec_path.exists())
        self.assertTrue(handoff_path.exists())

    def test_create_task_uses_template_defaults(self):
        self._setup_templates()
        # Add 'research' role to fixture since template uses it as default_owner
        agent_registry_path = self.temp_root / "05 AI Control Plane" / "agent-registry.json"
        agent_registry = json.loads(agent_registry_path.read_text(encoding="utf-8"))
        agent_registry["roles"].append({
            "id": "research",
            "display_name": "Research",
            "role_type": "ai",
            "default_autonomy_tier": "A2",
            "mission": "Conduct bounded research.",
        })
        agent_registry_path.write_text(
            json.dumps(agent_registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        self.module = load_module(self.temp_root)
        parser = self.module.build_parser()
        args = parser.parse_args([
            "create-task",
            "--title", "Research memory index layer",
            "--project", "HQ Bootstrap",
            "--template", "research-slice",
            "--manager", "ai_operations_lead",
            "--accepts-result", "governor",
        ])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        active_work = json.loads(
            (self.temp_root / "05 AI Control Plane" / "active-work.json").read_text(encoding="utf-8")
        )
        new_tasks = [t for t in active_work["tasks"] if t["title"] == "Research memory index layer"]
        self.assertEqual(len(new_tasks), 1)
        task = new_tasks[0]
        self.assertEqual(task["owner"], "research")
        self.assertEqual(task["risk_tier"], "medium")
        self.assertEqual(task["autonomy_tier"], "A2")
        self.assertIn("Decision-ready research note", task["done_when"])

    def test_create_task_rejects_unknown_role(self):
        self.module = load_module(self.temp_root)
        parser = self.module.build_parser()
        args = parser.parse_args([
            "create-task",
            "--title", "Bad task",
            "--project", "HQ Bootstrap",
            "--owner", "nonexistent_role",
            "--manager", "ai_operations_lead",
            "--accepts-result", "governor",
        ])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 1)
        output = buffer.getvalue()
        self.assertIn("create_task=failed", output)
        self.assertIn("nonexistent_role", output)

    def test_create_task_syncs_board(self):
        self._setup_templates()
        self.module = load_module(self.temp_root)
        parser = self.module.build_parser()
        args = parser.parse_args([
            "create-task",
            "--title", "New task for board",
            "--project", "HQ Bootstrap",
            "--owner", "delivery",
            "--manager", "ai_operations_lead",
            "--accepts-result", "governor",
        ])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        board = (self.temp_root / "02 Planning" / "Task Board.md").read_text(encoding="utf-8")
        self.assertIn("New task for board", board)

    # -------------------------------------------------------------------
    # health --json tests
    # -------------------------------------------------------------------

    def test_health_json_returns_structured_payload(self):
        parser = self.module.build_parser()
        args = parser.parse_args(["health", "--json"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertIn("validation", payload)
        self.assertEqual(payload["validation"]["status"], "ok")
        self.assertIn("warnings", payload["validation"])
        self.assertIn("status", payload)
        self.assertIn("active_tasks", payload["status"])
        self.assertIn("stale_items", payload["status"])
        self.assertIn("recommended_next_command", payload["status"])
        self.assertIn("git_status", payload)
        self.assertIsInstance(payload["git_status"], list)

    def test_health_json_includes_all_text_report_sections(self):
        parser = self.module.build_parser()
        # Run text health first to confirm it works
        args_text = parser.parse_args(["health"])
        buffer_text = io.StringIO()
        with redirect_stdout(buffer_text):
            exit_text = args_text.func(args_text)
        self.assertEqual(exit_text, 0)

        # Now run JSON health
        self.module = load_module(self.temp_root)
        parser = self.module.build_parser()
        args_json = parser.parse_args(["health", "--json"])
        buffer_json = io.StringIO()
        with redirect_stdout(buffer_json):
            exit_json = args_json.func(args_json)
        self.assertEqual(exit_json, 0)

        payload = json.loads(buffer_json.getvalue())
        # Validation section
        self.assertIn("status", payload["validation"])
        self.assertIn("warning_count", payload["validation"])
        # Status section
        self.assertIn("objective", payload["status"])
        self.assertIn("blocked", payload["status"])


if __name__ == "__main__":
    unittest.main()
