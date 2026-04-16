import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "hq_runtime.py"
SCHEMA_FIXTURES = Path(__file__).resolve().parents[1] / "05 AI Control Plane" / "schemas"


def load_runtime_module(temp_root: Path):
    os.environ["HQ_RUNTIME_REPO_ROOT"] = str(temp_root)
    os.environ.pop("HQ_RUNTIME_PRIVATE_ROOT", None)
    sys.modules.pop("hq_io", None)
    sys.modules.pop("hq_runtime_review", None)
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
        os.environ.pop("HQ_RUNTIME_REPO_ROOT", None)
        os.environ.pop("HQ_RUNTIME_PRIVATE_ROOT", None)
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

    def test_spec_command_writes_private_spec_packet(self):
        parser = self.module.build_parser()
        args = parser.parse_args(
            [
                "spec",
                "--task",
                "Launch scheduler hardening",
                "--owner",
                "AI Operations Lead",
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
        self.assertEqual(manifest["read_first"], ["scripts/hq_runtime.py"])
        self.assertEqual(manifest["primary_file"], "scripts/hq_runtime.py")

    def test_handoff_command_records_spec_file_in_read_first(self):
        parser = self.module.build_parser()
        args = parser.parse_args(
            [
                "handoff",
                "--task",
                "Launch scheduler hardening",
                "--owner",
                "Delivery",
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


if __name__ == "__main__":
    unittest.main()
