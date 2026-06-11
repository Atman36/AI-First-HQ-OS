import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "hq_runtime.py"
SCHEMA_FIXTURES = Path(__file__).resolve().parents[1] / "05 AI Control Plane" / "schemas"


def load_runtime_module(temp_root: Path):
    os.environ["HQ_RUNTIME_REPO_ROOT"] = str(temp_root)
    os.environ["HQ_MISSION_RUNTIME_REPO_ROOT"] = str(temp_root)
    os.environ["HQ_TELEMETRY_REPO_ROOT"] = str(temp_root)
    os.environ["HQ_POLICY_HOOKS_REPO_ROOT"] = str(temp_root)
    os.environ["HQ_CONTROL_PLANE_REPO_ROOT"] = str(temp_root)
    os.environ.pop("HQ_RUNTIME_PRIVATE_ROOT", None)
    sys.modules.pop("hq_io", None)
    sys.modules.pop("hq_control_plane", None)
    sys.modules.pop("hq_mission_runtime", None)
    sys.modules.pop("hq_policy_hooks", None)
    sys.modules.pop("hq_runtime_review", None)
    sys.modules.pop("hq_telemetry_store", None)
    spec = importlib.util.spec_from_file_location("hq_runtime_test_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class HqRuntimeReflectionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_dir.name)
        (self.temp_root / "05 AI Control Plane" / "schemas").mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            SCHEMA_FIXTURES,
            self.temp_root / "05 AI Control Plane" / "schemas",
            dirs_exist_ok=True,
        )
        self.module = load_runtime_module(self.temp_root)
        self.module.ensure_private_runtime()

    def tearDown(self):
        os.environ.pop("HQ_MISSION_RUNTIME_REPO_ROOT", None)
        os.environ.pop("HQ_RUNTIME_REPO_ROOT", None)
        os.environ.pop("HQ_RUNTIME_PRIVATE_ROOT", None)
        os.environ.pop("HQ_POLICY_HOOKS_REPO_ROOT", None)
        os.environ.pop("HQ_CONTROL_PLANE_REPO_ROOT", None)
        os.environ.pop("HQ_TELEMETRY_REPO_ROOT", None)
        os.environ.pop("HQ_REVIEW_ARCHIVE_KEEP", None)
        self.temp_dir.cleanup()

    def test_reflection_command_writes_jsonl_entry(self):
        parser = self.module.build_parser()
        args = parser.parse_args(
            [
                "reflection",
                "--agent",
                "Delivery",
                "--task",
                "Weekly self-improvement",
                "--summary",
                "Missed a repo-specific instruction before editing.",
                "--observation",
                "Started coding before checking AGENTS.md in full.",
                "--issue",
                "Instruction loading happened too late.",
                "--lesson",
                "Always read repo instructions before touching code.",
                "--proposed-rule",
                "Add an upfront checklist item to read AGENTS.md and role instructions.",
                "--issue-key",
                "instruction-loading",
                "--tag",
                "instructions",
                "--tag",
                "startup",
            ]
        )

        exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        reflection_files = sorted(
            self.module.RUNTIME_DIRS["reflections"].glob("**/*.jsonl")
        )
        self.assertEqual(len(reflection_files), 1)
        lines = reflection_files[0].read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        payload = json.loads(lines[0])
        self.assertEqual(payload["agent"], "Delivery")
        self.assertEqual(payload["issue_key"], "instruction-loading")
        self.assertEqual(payload["change_scope"], "workflow")
        self.assertEqual(payload["tags"], ["instructions", "startup"])

    def test_weekly_review_requires_minimum_observations_for_candidate(self):
        base_reflection = {
            "agent": "Delivery",
            "task": "Task",
            "summary": "Missed instruction context.",
            "observation": "Checked repo rules too late.",
            "issue": "Instruction loading happened too late.",
            "lesson": "Read rules before changing files.",
            "issue_key": "instruction-loading",
            "change_scope": "workflow",
            "proposed_rule": "Add a startup checklist for repo instructions.",
            "tags": ["instructions"],
        }
        self.module.append_jsonl(
            self.module.reflections_file_for_timestamp("2026-04-10T10:00:00Z"),
            self.module.normalize_reflection_payload(
                base_reflection | {"created_at": "2026-04-10T10:00:00Z", "session": "s1"}
            ),
        )
        self.module.append_jsonl(
            self.module.reflections_file_for_timestamp("2026-04-11T11:00:00Z"),
            self.module.normalize_reflection_payload(
                base_reflection
                | {
                    "created_at": "2026-04-11T11:00:00Z",
                    "session": "s2",
                    "summary": "Instruction context was still late.",
                }
            ),
        )

        parser = self.module.build_parser()
        args = parser.parse_args(
            [
                "weekly-review",
                "--since",
                "2026-04-07",
                "--until",
                "2026-04-14",
                "--min-observations",
                "3",
            ]
        )

        exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        latest_json = self.module.RUNTIME_DIRS["improvements"] / "LATEST.json"
        review = json.loads(latest_json.read_text(encoding="utf-8"))
        self.assertEqual(review["total_reflections"], 2)
        self.assertEqual(review["candidate_improvements"], 0)
        self.assertEqual(review["skill_candidates"], 0)
        self.assertEqual(review["groups"][0]["status"], "insufficient_evidence")

    def test_weekly_review_generates_candidate_and_blocks_restricted_scope(self):
        reflections = [
            {
                "created_at": "2026-04-08T09:00:00Z",
                "session": "a1",
                "agent": "Delivery",
                "summary": "Missed startup context.",
                "observation": "Repo rules were not loaded upfront.",
                "issue": "Instruction loading happened too late.",
                "lesson": "Read rules first.",
                "issue_key": "instruction-loading",
                "change_scope": "workflow",
                "proposed_rule": "Add a startup checklist for repo instructions.",
                "tags": ["instructions", "startup"],
            },
            {
                "created_at": "2026-04-09T09:00:00Z",
                "session": "a2",
                "agent": "Delivery",
                "summary": "Same issue repeated.",
                "observation": "Repo-specific rules were still read too late.",
                "issue": "Instruction loading happened too late.",
                "lesson": "Read rules first.",
                "issue_key": "instruction-loading",
                "change_scope": "workflow",
                "proposed_rule": "Add a startup checklist for repo instructions.",
                "tags": ["instructions", "startup"],
            },
            {
                "created_at": "2026-04-10T09:00:00Z",
                "session": "b1",
                "agent": "Delivery",
                "summary": "Tool access changed during debugging.",
                "observation": "Needed different CLI permissions.",
                "issue": "Tool access policy was too open-ended.",
                "lesson": "Review tool access manually.",
                "issue_key": "tool-access",
                "change_scope": "tool_access",
                "proposed_rule": "Grant broader tool permissions automatically.",
                "tags": ["tools", "safety"],
            },
            {
                "created_at": "2026-04-11T09:00:00Z",
                "session": "b2",
                "agent": "Delivery",
                "summary": "Tool access changed again.",
                "observation": "Permission boundaries were unclear.",
                "issue": "Tool access policy was too open-ended.",
                "lesson": "Review tool access manually.",
                "issue_key": "tool-access",
                "change_scope": "tool_access",
                "proposed_rule": "Grant broader tool permissions automatically.",
                "tags": ["tools", "safety"],
            },
        ]
        for item in reflections:
            self.module.append_jsonl(
                self.module.reflections_file_for_timestamp(item["created_at"]),
                self.module.normalize_reflection_payload(item),
            )

        parser = self.module.build_parser()
        args = parser.parse_args(
            [
                "weekly-review",
                "--since",
                "2026-04-07",
                "--until",
                "2026-04-14",
                "--min-observations",
                "2",
            ]
        )

        exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        latest_json = self.module.RUNTIME_DIRS["improvements"] / "LATEST.json"
        latest_md = self.module.RUNTIME_DIRS["improvements"] / "LATEST.md"
        review = json.loads(latest_json.read_text(encoding="utf-8"))
        self.assertTrue(latest_md.exists())
        self.assertEqual(review["candidate_improvements"], 1)
        self.assertEqual(review["skill_candidates"], 1)
        groups = {group["issue_key"]: group for group in review["groups"]}
        self.assertEqual(groups["instruction-loading"]["status"], "candidate")
        self.assertIn("skill", groups["instruction-loading"]["manual_targets"])
        self.assertTrue(groups["instruction-loading"]["skill_candidate"])
        self.assertEqual(groups["tool-access"]["status"], "manual_only")
        self.assertIn("must stay manual", groups["tool-access"]["guardrail_reason"])
        skill_candidates = json.loads(
            (self.module.RUNTIME_DIRS["improvements"] / "skill-candidates.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(skill_candidates["total_skill_candidates"], 1)
        self.assertEqual(skill_candidates["candidates"][0]["issue_key"], "instruction-loading")
        self.assertEqual(
            skill_candidates["candidates"][0]["promotion_target"],
            "skill",
        )

    def test_weekly_review_loads_standalone_json_reflection(self):
        standalone_path = (
            self.module.RUNTIME_DIRS["reflections"] / "2026-04-15-deep-research-timeout.json"
        )
        standalone_path.write_text(
            json.dumps(
                {
                    "created_at": "2026-04-15T00:00:00+05:00",
                    "session_topic": "Parallel.ai deep research on agent self-improvement",
                    "type": "tooling-friction",
                    "observation": "A 5-minute timeout was too short for this class of prompt.",
                    "what_happened": [
                        "The first run used a 5-minute wait.",
                        "The first run timed out without producing a report.",
                        "The second run used a 10-minute wait and completed successfully.",
                    ],
                    "impact": "The first run delayed implementation work.",
                    "proposed_improvement": "Default to at least 10 minutes for broad deep research prompts.",
                    "confidence": "high",
                    "evidence": ["/tmp/report.md"],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        parser = self.module.build_parser()
        args = parser.parse_args(
            [
                "weekly-review",
                "--since",
                "2026-04-14",
                "--until",
                "2026-04-15",
                "--min-observations",
                "1",
                "--min-unique-sessions",
                "1",
            ]
        )

        exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        latest_json = self.module.RUNTIME_DIRS["improvements"] / "LATEST.json"
        review = json.loads(latest_json.read_text(encoding="utf-8"))
        self.assertEqual(review["total_reflections"], 1)
        self.assertEqual(review["candidate_improvements"], 1)
        self.assertEqual(review["skill_candidates"], 1)
        group = review["groups"][0]
        self.assertEqual(group["status"], "candidate")
        self.assertIn("10 minutes", group["candidate_rule"])
        self.assertIn("timed out", group["summary"])

    def test_weekly_review_keeps_skill_promotion_manual_for_restricted_scope(self):
        reflections = [
            {
                "created_at": "2026-04-12T09:00:00Z",
                "session": "s1",
                "agent": "Delivery",
                "summary": "Production writes were too tempting.",
                "observation": "An automation proposal drifted toward production logic.",
                "issue": "Improvement touched production logic directly.",
                "lesson": "Keep production changes gated.",
                "issue_key": "production-logic-drift",
                "change_scope": "production_logic",
                "proposed_rule": "Auto-update the production flow from the review.",
                "tags": ["production", "safety"],
            },
            {
                "created_at": "2026-04-13T09:00:00Z",
                "session": "s2",
                "agent": "Delivery",
                "summary": "The same drift repeated.",
                "observation": "Weekly review suggestions again touched production logic.",
                "issue": "Improvement touched production logic directly.",
                "lesson": "Keep production changes gated.",
                "issue_key": "production-logic-drift",
                "change_scope": "production_logic",
                "proposed_rule": "Auto-update the production flow from the review.",
                "tags": ["production", "safety"],
            },
        ]
        for item in reflections:
            self.module.append_jsonl(
                self.module.reflections_file_for_timestamp(item["created_at"]),
                self.module.normalize_reflection_payload(item),
            )

        parser = self.module.build_parser()
        args = parser.parse_args(
            [
                "weekly-review",
                "--since",
                "2026-04-12",
                "--until",
                "2026-04-13",
                "--min-observations",
                "2",
            ]
        )

        exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        review = json.loads(
            (self.module.RUNTIME_DIRS["improvements"] / "LATEST.json").read_text(
                encoding="utf-8"
            )
        )
        group = review["groups"][0]
        self.assertEqual(group["status"], "manual_only")
        self.assertEqual(review["skill_candidates"], 0)
        self.assertFalse(group["skill_candidate"])
        self.assertNotIn("skill", group["manual_targets"])
        skill_candidates = json.loads(
            (self.module.RUNTIME_DIRS["improvements"] / "skill-candidates.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(skill_candidates["total_skill_candidates"], 0)

    def test_weekly_review_archives_old_review_directories(self):
        os.environ["HQ_REVIEW_ARCHIVE_KEEP"] = "1"
        old_review_dir = self.module.RUNTIME_DIRS["improvements"] / "2026-03-01_to_2026-03-07"
        old_review_dir.mkdir(parents=True, exist_ok=True)
        (old_review_dir / "review.json").write_text("{}\n", encoding="utf-8")

        self.module.append_jsonl(
            self.module.reflections_file_for_timestamp("2026-04-15T10:00:00Z"),
            self.module.normalize_reflection_payload(
                {
                    "created_at": "2026-04-15T10:00:00Z",
                    "session": "archive-test",
                    "agent": "Delivery",
                    "summary": "Review output retention should archive older windows.",
                    "observation": "The current review replaced a prior output window.",
                    "issue": "Review output count kept growing.",
                    "lesson": "Archive stale review windows.",
                    "issue_key": "review-retention",
                    "change_scope": "workflow",
                    "proposed_rule": "Archive older review windows automatically.",
                    "tags": ["retention"],
                }
            ),
        )

        parser = self.module.build_parser()
        args = parser.parse_args(
            [
                "weekly-review",
                "--since",
                "2026-04-15",
                "--until",
                "2026-04-15",
                "--min-observations",
                "1",
                "--min-unique-sessions",
                "1",
            ]
        )

        exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        current_review_dir = self.module.RUNTIME_DIRS["improvements"] / "2026-04-15_to_2026-04-15"
        archived_review_dir = (
            self.module.RUNTIME_DIRS["improvements"] / "archive" / "2026-03-01_to_2026-03-07"
        )
        self.assertTrue(current_review_dir.exists())
        self.assertFalse(old_review_dir.exists())
        self.assertTrue(archived_review_dir.exists())

    def test_bootstrap_creates_local_state_scaffold(self):
        parser = self.module.build_parser()
        args = parser.parse_args(["bootstrap"])

        exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        self.assertTrue((self.temp_root / ".hq").exists())
        self.assertTrue((self.temp_root / "now.md").exists())
        self.assertTrue((self.temp_root / "projects.md").exists())
        self.assertTrue((self.temp_root / "02 Planning" / "Weekly Plan.md").exists())
        self.assertTrue((self.temp_root / "03 Notes" / "Decisions.md").exists())
        self.assertTrue((self.temp_root / "04 Projects" / "HQ Bootstrap.md").exists())
        self.assertTrue((self.temp_root / "05 AI Control Plane" / "active-work.json").exists())
        task_board = self.temp_root / "02 Planning" / "Task Board.md"
        self.assertTrue(task_board.exists())
        self.assertIn("Generated from `05 AI Control Plane/active-work.json`", task_board.read_text(encoding="utf-8"))
        active_work = json.loads(
            (self.temp_root / "05 AI Control Plane" / "active-work.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(active_work["operating_mode"], "stage-2-minimal-demo-scaffold")
        agent_registry = json.loads(
            (self.temp_root / "05 AI Control Plane" / "agent-registry.json").read_text(
                encoding="utf-8"
            )
        )
        role_ids = {role["id"] for role in agent_registry["roles"]}
        self.assertIn("finance", role_ids)
        self.assertIn("growth", role_ids)
        self.assertIn("research", role_ids)
        self.assertNotIn("assistant", role_ids)

    def test_mission_runtime_command_proxies_new_runtime_surface(self):
        parser = self.module.build_parser()
        args = parser.parse_args(["mission-runtime", "init"])

        exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        runtime_root = self.temp_root / ".hq" / "state" / "mission-runtime"
        self.assertTrue((runtime_root / "missions").exists())
        self.assertTrue((runtime_root / "runs").exists())

    def test_route_next_slice_writes_private_packets_from_active_work(self):
        active_work_path = self.temp_root / "05 AI Control Plane" / "active-work.json"
        active_work_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "updated_at": "2026-04-17",
                    "operating_mode": "test",
                    "objective": {
                        "id": "objective",
                        "title": "Objective",
                        "window": {"start": "2026-04-17", "target_end": "2026-04-30"},
                    },
                    "tasks": [
                        {
                            "id": "review-trust",
                            "title": "Review trust wording",
                            "column": "review",
                            "manager": "ai_operations_lead",
                            "owner": "governor",
                            "project": "Founder Revenue Sprint",
                            "next_step": "Lock the live review wording.",
                            "done_when": "Wording is founder-reviewed.",
                            "primary_update_file": "04 Projects/Founder Revenue Sprint.md",
                            "align_files": ["03 Notes/Open Decisions.md"],
                            "accepts_result": "ceo",
                            "risk_tier": "high",
                            "autonomy_tier": "A1",
                            "workflow": "intake-to-execution",
                        },
                        {
                            "id": "work-ready-accounts",
                            "title": "Work ready accounts",
                            "column": "executing",
                            "manager": "ai_operations_lead",
                            "owner": "growth",
                            "project": "Founder Revenue Sprint",
                            "next_step": "Work the ready accounts first.",
                            "done_when": "Accounts are worked.",
                            "primary_update_file": "04 Projects/Founder Revenue Sprint.md",
                            "align_files": ["projects.md"],
                            "accepts_result": "ceo",
                            "risk_tier": "medium",
                            "autonomy_tier": "A2",
                            "workflow": "intake-to-execution",
                        },
                        {
                            "id": "future-task",
                            "title": "Future task",
                            "column": "this_week",
                            "manager": "ai_operations_lead",
                            "owner": "delivery",
                            "project": "AI-First HQ OS",
                            "next_step": "Handle later.",
                            "done_when": "Handled later.",
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

        parser = self.module.build_parser()
        args = parser.parse_args(["route-next-slice", "--session", "autopilot-test"])

        exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        spec_path = self.temp_root / ".hq" / "specs" / "route-next-slice" / "LATEST.md"
        handoff_path = self.temp_root / ".hq" / "handoffs" / "route-next-slice" / "LATEST.md"
        self.assertTrue(spec_path.exists())
        self.assertTrue(handoff_path.exists())
        spec_text = spec_path.read_text(encoding="utf-8")
        handoff_text = handoff_path.read_text(encoding="utf-8")
        self.assertIn("Review trust wording", spec_text)
        self.assertIn("Work ready accounts", spec_text)
        self.assertIn("Founder review", spec_text)
        self.assertIn("Future task", spec_text)
        self.assertIn("up to two adjacent support tracks", spec_text)
        self.assertIn("execution-ready task 'Work ready accounts' in column 'executing'", spec_text)
        self.assertIn(".hq/specs/route-next-slice/LATEST.md", handoff_text)
        self.assertIn("Continue now: [Founder Revenue Sprint] Work ready accounts", handoff_text)
        self.assertIn("Move in parallel: [AI-First HQ OS] Future task", handoff_text)
        self.assertIn("up to two adjacent tasks", handoff_text)

    def test_route_next_slice_uses_founder_review_as_primary_only_when_no_execution_tasks_exist(self):
        active_work_path = self.temp_root / "05 AI Control Plane" / "active-work.json"
        active_work_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "updated_at": "2026-04-17",
                    "operating_mode": "test",
                    "objective": {
                        "id": "objective",
                        "title": "Objective",
                        "window": {"start": "2026-04-17", "target_end": "2026-04-30"},
                    },
                    "tasks": [
                        {
                            "id": "review-trust",
                            "title": "Review trust wording",
                            "column": "review",
                            "manager": "ai_operations_lead",
                            "owner": "governor",
                            "project": "Founder Revenue Sprint",
                            "next_step": "Lock the live review wording.",
                            "done_when": "Wording is founder-reviewed.",
                            "primary_update_file": "04 Projects/Founder Revenue Sprint.md",
                            "align_files": ["03 Notes/Open Decisions.md"],
                            "accepts_result": "ceo",
                            "risk_tier": "high",
                            "autonomy_tier": "A1",
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

        parser = self.module.build_parser()
        args = parser.parse_args(["route-next-slice", "--session", "founder-review-only"])

        exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        handoff_path = self.temp_root / ".hq" / "handoffs" / "route-next-slice" / "LATEST.md"
        handoff_text = handoff_path.read_text(encoding="utf-8")
        self.assertIn("Continue now: [Founder Revenue Sprint] Review trust wording", handoff_text)

    def test_route_next_slice_preserves_queue_order_within_same_column(self):
        active_work_path = self.temp_root / "05 AI Control Plane" / "active-work.json"
        active_work_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "updated_at": "2026-04-17",
                    "operating_mode": "test",
                    "objective": {
                        "id": "objective",
                        "title": "Objective",
                        "window": {"start": "2026-04-17", "target_end": "2026-04-30"},
                    },
                    "tasks": [
                        {
                            "id": "work-ready-accounts",
                            "title": "Work ready accounts",
                            "column": "executing",
                            "manager": "ai_operations_lead",
                            "owner": "growth",
                            "project": "Founder Revenue Sprint",
                            "next_step": "Work the ready accounts first.",
                            "done_when": "Accounts are worked.",
                            "primary_update_file": "04 Projects/Founder Revenue Sprint.md",
                            "accepts_result": "ceo",
                            "risk_tier": "medium",
                            "autonomy_tier": "A2",
                            "workflow": "intake-to-execution",
                        },
                        {
                            "id": "alpha-pilot",
                            "title": "Alpha pilot",
                            "column": "executing",
                            "manager": "ai_operations_lead",
                            "owner": "delivery",
                            "project": "Founder Revenue Sprint",
                            "next_step": "Run the pilot second.",
                            "done_when": "Pilot is run.",
                            "primary_update_file": "04 Projects/Founder Revenue Sprint.md",
                            "accepts_result": "ceo",
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

        parser = self.module.build_parser()
        args = parser.parse_args(["route-next-slice", "--session", "preserve-queue-order"])

        exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        handoff_path = self.temp_root / ".hq" / "handoffs" / "route-next-slice" / "LATEST.md"
        handoff_text = handoff_path.read_text(encoding="utf-8")
        self.assertIn("Continue now: [Founder Revenue Sprint] Work ready accounts", handoff_text)
        self.assertIn("Move in parallel: [Founder Revenue Sprint] Alpha pilot", handoff_text)

    def test_route_next_slice_errors_when_no_actionable_tasks_exist(self):
        active_work_path = self.temp_root / "05 AI Control Plane" / "active-work.json"
        active_work_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "updated_at": "2026-04-17",
                    "operating_mode": "test",
                    "objective": {
                        "id": "objective",
                        "title": "Objective",
                        "window": {"start": "2026-04-17", "target_end": "2026-04-30"},
                    },
                    "tasks": [
                        {
                            "id": "done-task",
                            "title": "Done task",
                            "column": "done",
                            "completed_at": "2026-04-17",
                            "manager": "ai_operations_lead",
                            "owner": "delivery",
                            "project": "AI-First HQ OS",
                            "next_step": "None.",
                            "done_when": "Done.",
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

        parser = self.module.build_parser()
        args = parser.parse_args(["route-next-slice"])

        exit_code = args.func(args)

        self.assertEqual(exit_code, 2)

    def test_founder_weekly_review_completes_without_founder_attention_items(self):
        parser = self.module.build_parser()
        args = parser.parse_args(
            [
                "founder-weekly-review",
                "--review-summary",
                "Reviewed weekly operating state and next priorities.",
                "--route",
                "Route repo hardening mission to delivery.",
                "--route",
                "Route telemetry follow-up to ai_operations_lead.",
            ]
        )

        exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        mission_files = sorted(
            (self.temp_root / ".hq" / "state" / "mission-runtime" / "missions").glob("*.json")
        )
        run_files = sorted(
            (self.temp_root / ".hq" / "state" / "mission-runtime" / "runs").glob("*.json")
        )
        approval_files = sorted(
            (self.temp_root / ".hq" / "state" / "mission-runtime" / "approvals").glob("*.json")
        )
        artifact_files = sorted(
            (self.temp_root / ".hq" / "state" / "mission-runtime" / "artifacts").glob("*.json")
        )
        self.assertEqual(len(mission_files), 1)
        self.assertEqual(len(run_files), 1)
        self.assertEqual(len(approval_files), 0)
        self.assertEqual(len(artifact_files), 1)

        mission = json.loads(mission_files[0].read_text(encoding="utf-8"))
        run = json.loads(run_files[0].read_text(encoding="utf-8"))
        artifact = json.loads(artifact_files[0].read_text(encoding="utf-8"))
        self.assertEqual(mission["workflow"], "founder-weekly-operating-review")
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["verification_state"]["status"], "verified")
        self.assertEqual(artifact["kind"], "founder_inbox")

        inbox_path = self.temp_root / artifact["path"]
        self.assertTrue(inbox_path.exists())
        inbox_text = inbox_path.read_text(encoding="utf-8")
        self.assertIn("Mission Routes", inbox_text)
        self.assertIn("No founder review items.", inbox_text)
        self.assertIn(run["id"], inbox_text)
        self.assertNotIn("pending-runtime-record", inbox_text)

        telemetry_files = sorted(
            path
            for path in (self.temp_root / ".hq" / "telemetry").glob("**/*.jsonl")
            if "feedback-loop" not in path.parts
        )
        self.assertEqual(len(telemetry_files), 1)
        events = [
            json.loads(line)
            for line in telemetry_files[0].read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        review_events = [event for event in events if event.get("event_type") == "review"]
        acceptance_events = [event for event in events if event.get("event_type") == "acceptance"]
        self.assertEqual(len(review_events), 1)
        self.assertEqual(review_events[0]["status"], "reviewed")
        self.assertEqual(review_events[0]["run_id"], run["id"])
        self.assertEqual(len(acceptance_events), 1)
        self.assertEqual(acceptance_events[0]["status"], "accepted")
        self.assertEqual(acceptance_events[0]["run_id"], run["id"])

    def test_founder_weekly_review_pauses_for_founder_approval_when_attention_items_exist(self):
        parser = self.module.build_parser()
        args = parser.parse_args(
            [
                "founder-weekly-review",
                "--review-summary",
                "Weekly review identified founder decisions.",
                "--route",
                "Route runtime hardening mission to delivery.",
                "--approval",
                "Approve telemetry schema extension for runtime lineage.",
                "--blocker",
                "Need founder sign-off on policy escalation wording.",
                "--policy-exception",
                "Governor flagged an exception for a new approval path.",
                "--kpi-drift",
                "Telemetry coverage fell below target.",
            ]
        )

        exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        run_files = sorted(
            (self.temp_root / ".hq" / "state" / "mission-runtime" / "runs").glob("*.json")
        )
        approval_files = sorted(
            (self.temp_root / ".hq" / "state" / "mission-runtime" / "approvals").glob("*.json")
        )
        self.assertEqual(len(run_files), 1)
        self.assertEqual(len(approval_files), 1)

        run = json.loads(run_files[0].read_text(encoding="utf-8"))
        approval = json.loads(approval_files[0].read_text(encoding="utf-8"))
        self.assertEqual(run["status"], "waiting_approval")
        self.assertEqual(approval["status"], "pending")
        self.assertEqual(approval["policy_action"], "pause_for_founder_approval")

        telemetry_files = sorted(
            path
            for path in (self.temp_root / ".hq" / "telemetry").glob("**/*.jsonl")
            if "feedback-loop" not in path.parts
        )
        self.assertEqual(len(telemetry_files), 1)
        events = [
            json.loads(line)
            for line in telemetry_files[0].read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertTrue(any(event.get("run_id") == run["id"] for event in events))
        self.assertTrue(any(event.get("approval_id") == approval["id"] for event in events))
        review_events = [event for event in events if event.get("event_type") == "review"]
        acceptance_events = [event for event in events if event.get("event_type") == "acceptance"]
        self.assertEqual(len(review_events), 1)
        self.assertEqual(review_events[0]["status"], "reviewed")
        self.assertEqual(review_events[0]["run_id"], run["id"])
        self.assertEqual(acceptance_events, [])

    def test_founder_weekly_review_mastra_runner_bridges_to_optional_sidecar(self):
        sidecar_root = self.temp_root / "vendor" / "at-masta"
        sidecar_root.mkdir(parents=True, exist_ok=True)
        (sidecar_root / "package.json").write_text(
            json.dumps({"name": "at-masta", "scripts": {"run:weekly-review": "node weekly.js"}})
            + "\n",
            encoding="utf-8",
        )
        for path, content in self.module.local_text_files().items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        for path, payload in self.module.local_json_files().items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        parser = self.module.build_parser()
        args = parser.parse_args(
            [
                "founder-weekly-review",
                "--runner",
                "mastra",
                "--mastra-sidecar-root",
                str(sidecar_root),
                "--session",
                "bridge-test",
                "--review-date",
                "2026-04-20",
                "--force-founder-review",
                "--founder-decision",
                "approved",
                "--founder-rationale",
                "bounded approval",
            ]
        )

        completed = mock.Mock()
        completed.returncode = 0
        completed.stdout = json.dumps(
            {
                "status": "success",
                "founderAttentionRequired": True,
                "approvalStatus": "approved",
                "summary": "Bridge completed",
                "artifactPaths": {
                    "json": ".hq/mastra-sidecar/founder-weekly-review/bridge-test.json",
                    "markdown": ".hq/mastra-sidecar/founder-weekly-review/bridge-test.md",
                },
            }
        )
        completed.stderr = ""
        artifact_dir = self.temp_root / ".hq" / "mastra-sidecar" / "founder-weekly-review"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "bridge-test.json").write_text(
            json.dumps(
                {
                    "summary": "Bridge completed",
                    "routes": ["Route runtime hardening mission to delivery."],
                    "approvals": ["Approve founder-facing route."],
                    "blockers": [],
                    "policyExceptions": [],
                    "kpiDrifts": [],
                    "founderAttentionRequired": True,
                    "founderRationale": "bounded approval",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (artifact_dir / "bridge-test.md").write_text("# Bridge Test\n", encoding="utf-8")
        buffer = io.StringIO()
        with mock.patch.object(self.module.shutil, "which", return_value="/usr/bin/npm"), mock.patch.object(
            self.module.subprocess, "run", return_value=completed
        ) as mocked_run, redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        command = mocked_run.call_args.args[0]
        self.assertEqual(command[:4], ["/usr/bin/npm", "run", "run:weekly-review", "--"])
        self.assertIn("--hq-root", command)
        self.assertIn(str(self.module.REPO_ROOT), command)
        self.assertIn("--force-founder-review", command)
        self.assertIn("--approve", command)
        self.assertIn("approved", command)
        self.assertIn("--rationale", command)
        self.assertIn("bounded approval", command)
        self.assertIn("--hq-status-file", command)
        status_path = Path(command[command.index("--hq-status-file") + 1])
        self.assertEqual(
            status_path.resolve(),
            (self.temp_root / ".hq" / "state" / "session-bootstrap.json").resolve(),
        )
        self.assertTrue(status_path.exists())
        status_payload = json.loads(status_path.read_text(encoding="utf-8"))
        self.assertIn("workflow_inputs", status_payload)
        self.assertIn("founder_weekly_review", status_payload["workflow_inputs"])
        self.assertIn("runner=mastra", buffer.getvalue())
        self.assertIn('"approvalStatus": "approved"', buffer.getvalue())
        mission_files = sorted(
            (self.temp_root / ".hq" / "state" / "mission-runtime" / "missions").glob("*.json")
        )
        run_files = sorted(
            (self.temp_root / ".hq" / "state" / "mission-runtime" / "runs").glob("*.json")
        )
        artifact_files = sorted(
            (self.temp_root / ".hq" / "state" / "mission-runtime" / "artifacts").glob("*.json")
        )
        self.assertEqual(len(mission_files), 1)
        self.assertEqual(len(run_files), 1)
        self.assertEqual(len(artifact_files), 2)
        mission = json.loads(mission_files[0].read_text(encoding="utf-8"))
        run = json.loads(run_files[0].read_text(encoding="utf-8"))
        self.assertEqual(mission["source_task_id"], "prove-founder-weekly-review-as-primary-workflow")
        self.assertEqual(mission["metadata"]["runner"], "mastra")
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["verification_state"]["status"], "verified")
        self.assertEqual(run["verification_state"]["metadata"]["acceptance_check"], True)
        telemetry_files = sorted(
            path
            for path in (self.temp_root / ".hq" / "telemetry").glob("**/*.jsonl")
            if "feedback-loop" not in path.parts
        )
        self.assertEqual(len(telemetry_files), 1)
        events = [
            json.loads(line)
            for line in telemetry_files[0].read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        review_events = [event for event in events if event.get("event_type") == "review"]
        acceptance_events = [event for event in events if event.get("event_type") == "acceptance"]
        self.assertEqual(len(review_events), 1)
        self.assertEqual(review_events[0]["status"], "reviewed")
        self.assertEqual(review_events[0]["run_id"], run["id"])
        self.assertEqual(len(acceptance_events), 1)
        self.assertEqual(acceptance_events[0]["status"], "accepted")
        self.assertEqual(acceptance_events[0]["run_id"], run["id"])

    def test_founder_weekly_review_mastra_runner_requires_sidecar_configuration(self):
        parser = self.module.build_parser()
        args = parser.parse_args(
            [
                "founder-weekly-review",
                "--runner",
                "mastra",
            ]
        )

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 2)
        self.assertIn("mastra sidecar is not configured", buffer.getvalue().lower())

    def test_founder_weekly_review_mastra_runner_rejects_checkout_without_weekly_script(self):
        sidecar_root = self.temp_root / "vendor" / "wrong-sidecar"
        sidecar_root.mkdir(parents=True, exist_ok=True)
        (sidecar_root / "package.json").write_text(
            json.dumps({"name": "wrong-sidecar", "scripts": {"test": "node --test"}}) + "\n",
            encoding="utf-8",
        )

        parser = self.module.build_parser()
        args = parser.parse_args(
            [
                "founder-weekly-review",
                "--runner",
                "mastra",
                "--mastra-sidecar-root",
                str(sidecar_root),
            ]
        )

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 2)
        self.assertIn("mastra sidecar is not configured", buffer.getvalue().lower())

    def test_spec_command_writes_private_spec_packet(self):
        thread = self.module.hq_mission_runtime.create_thread_record(
            title="Launch scheduler hardening",
            owner="AI Operations Lead",
        )
        parser = self.module.build_parser()
        args = parser.parse_args(
            [
                "spec",
                "--task",
                "Launch scheduler hardening",
                "--owner",
                "AI Operations Lead",
                "--thread-id",
                thread["id"],
                "--goal",
                "Define a narrow implementation packet for scheduler work.",
                "--primary-file",
                "scripts/hq_runtime.py",
                "--why",
                "The next chat should not re-read the whole repo.",
                "--in-scope",
                "Define the private spec structure.",
                "--out-of-scope",
                "Do not add background daemons yet.",
                "--read-file",
                "scripts/hq_runtime.py",
                "--constraint",
                "Keep runtime artifacts private under .hq/.",
                "--acceptance",
                "A future chat can resume from this spec alone.",
                "--question",
                "Should scheduler setup become a separate skill later?",
                "--note",
                "Reference launchd ideas without copying them.",
            ]
        )

        exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        spec_dir = self.module.RUNTIME_DIRS["specs"] / "launch-scheduler-hardening"
        latest_path = spec_dir / "LATEST.md"
        manifest_path = spec_dir / "manifest.json"
        self.assertTrue(latest_path.exists())
        self.assertTrue(manifest_path.exists())
        content = latest_path.read_text(encoding="utf-8")
        self.assertIn("# Spec", content)
        self.assertIn("Define a narrow implementation packet for scheduler work.", content)
        self.assertIn("scripts/hq_runtime.py", content)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["task"], "Launch scheduler hardening")
        self.assertEqual(manifest["thread_id"], thread["id"])
        self.assertEqual(manifest["read_first"], ["scripts/hq_runtime.py"])
        self.assertEqual(manifest["primary_file"], "scripts/hq_runtime.py")
        self.assertTrue(manifest["mission_id"])
        self.assertTrue(manifest["run_id"])
        self.assertTrue(manifest["step_id"])
        thread_state = json.loads(
            self.module.hq_mission_runtime.thread_path(thread["id"]).read_text(encoding="utf-8")
        )
        self.assertEqual(thread_state["latest_spec_path"], ".hq/specs/launch-scheduler-hardening/LATEST.md")
        self.assertEqual(thread_state["resume_packet_path"], ".hq/specs/launch-scheduler-hardening/LATEST.md")
        self.assertEqual(thread_state["active_mission_id"], manifest["mission_id"])
        self.assertEqual(thread_state["active_run_id"], manifest["run_id"])
        run_state = json.loads(
            self.module.hq_mission_runtime.run_path(manifest["run_id"]).read_text(encoding="utf-8")
        )
        self.assertIn(manifest["step_id"], run_state["step_ids"])
        step_state = json.loads(
            self.module.hq_mission_runtime.step_path(manifest["step_id"]).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(step_state["key"], "spec_packet")
        self.assertEqual(step_state["status"], "completed")
        self.assertEqual(
            step_state["metadata"]["spec_path"],
            ".hq/specs/launch-scheduler-hardening/LATEST.md",
        )

    def test_handoff_command_records_spec_file_in_read_first(self):
        thread = self.module.hq_mission_runtime.create_thread_record(
            title="Launch scheduler hardening",
            owner="Delivery",
        )
        parser = self.module.build_parser()
        args = parser.parse_args(
            [
                "handoff",
                "--task",
                "Launch scheduler hardening",
                "--owner",
                "Delivery",
                "--thread-id",
                thread["id"],
                "--spec-file",
                ".hq/specs/launch-scheduler-hardening/LATEST.md",
                "--continue-from",
                "scripts/hq_runtime.py",
                "--primary-file",
                "scripts/hq_runtime.py",
                "--read-first",
                ".hq/handoffs/launch-scheduler-hardening/LATEST.md",
                "--done",
                "Spec created.",
                "--next",
                "Implement the runtime changes.",
            ]
        )

        exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        handoff_dir = self.module.RUNTIME_DIRS["handoffs"] / "launch-scheduler-hardening"
        latest_path = handoff_dir / "LATEST.md"
        manifest_path = handoff_dir / "manifest.json"
        self.assertTrue(latest_path.exists())
        content = latest_path.read_text(encoding="utf-8")
        self.assertIn("Spec File: .hq/specs/launch-scheduler-hardening/LATEST.md", content)
        self.assertIn("## Read First", content)
        self.assertIn(".hq/handoffs/launch-scheduler-hardening/LATEST.md", content)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["read_first"],
            [
                ".hq/specs/launch-scheduler-hardening/LATEST.md",
                ".hq/handoffs/launch-scheduler-hardening/LATEST.md",
            ],
        )
        self.assertEqual(manifest["thread_id"], thread["id"])
        self.assertTrue(manifest["handoff_id"])
        self.assertTrue(manifest["mission_id"])
        self.assertTrue(manifest["run_id"])
        self.assertTrue(manifest["step_id"])
        thread_state = json.loads(
            self.module.hq_mission_runtime.thread_path(thread["id"]).read_text(encoding="utf-8")
        )
        self.assertEqual(
            thread_state["latest_handoff_path"],
            ".hq/handoffs/launch-scheduler-hardening/LATEST.md",
        )
        self.assertEqual(thread_state["latest_handoff_id"], manifest["handoff_id"])
        self.assertEqual(
            thread_state["resume_packet_path"],
            ".hq/handoffs/launch-scheduler-hardening/LATEST.md",
        )
        handoff_state = json.loads(
            self.module.hq_mission_runtime.handoff_path(manifest["handoff_id"]).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(handoff_state["handoff_path"], ".hq/handoffs/launch-scheduler-hardening/LATEST.md")
        self.assertEqual(handoff_state["thread_id"], thread["id"])
        self.assertEqual(handoff_state["mission_id"], manifest["mission_id"])
        self.assertEqual(handoff_state["run_id"], manifest["run_id"])
        run_state = json.loads(
            self.module.hq_mission_runtime.run_path(manifest["run_id"]).read_text(encoding="utf-8")
        )
        self.assertIn(manifest["step_id"], run_state["step_ids"])
        step_state = json.loads(
            self.module.hq_mission_runtime.step_path(manifest["step_id"]).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(step_state["key"], "handoff_packet")
        self.assertEqual(step_state["status"], "completed")
        self.assertEqual(step_state["metadata"]["handoff_id"], manifest["handoff_id"])


if __name__ == "__main__":
    unittest.main()
