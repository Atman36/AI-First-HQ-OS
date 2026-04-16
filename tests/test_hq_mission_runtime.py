import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "hq_mission_runtime.py"


def load_module(temp_root: Path):
    os.environ["HQ_MISSION_RUNTIME_REPO_ROOT"] = str(temp_root)
    os.environ["HQ_RUNTIME_PRIVATE_ROOT"] = str(temp_root / ".hq")
    sys.modules.pop("hq_io", None)
    spec = importlib.util.spec_from_file_location("hq_mission_runtime_test_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class HqMissionRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_dir.name)
        self.module = load_module(self.temp_root)
        self.module.ensure_runtime()

    def tearDown(self):
        os.environ.pop("HQ_MISSION_RUNTIME_REPO_ROOT", None)
        os.environ.pop("HQ_RUNTIME_PRIVATE_ROOT", None)
        self.temp_dir.cleanup()

    def test_create_mission_and_start_run_persist_first_class_records(self):
        parser = self.module.build_parser()

        mission_args = parser.parse_args(
            [
                "create-mission",
                "--title",
                "Founder Weekly Review",
                "--goal",
                "Route the next mission set.",
                "--workflow",
                "founder-weekly-review",
                "--owner",
                "ai_operations_lead",
                "--manager",
                "ceo",
                "--accepts-result",
                "ceo",
                "--source-task-id",
                "weekly-review",
            ]
        )
        exit_code = mission_args.func(mission_args)
        self.assertEqual(exit_code, 0)

        mission_files = sorted(self.module.RUNTIME_DIRS["missions"].glob("*.json"))
        self.assertEqual(len(mission_files), 1)
        mission = json.loads(mission_files[0].read_text(encoding="utf-8"))
        self.assertEqual(mission["entity_type"], "mission")
        self.assertEqual(mission["status"], "planned")

        run_args = parser.parse_args(
            [
                "start-run",
                "--mission-id",
                mission["id"],
                "--actor",
                "ai_operations_lead",
                "--loop",
                "planner->executor->reviewer->policy_gate",
            ]
        )
        exit_code = run_args.func(run_args)
        self.assertEqual(exit_code, 0)

        run_files = sorted(self.module.RUNTIME_DIRS["runs"].glob("*.json"))
        self.assertEqual(len(run_files), 1)
        run = json.loads(run_files[0].read_text(encoding="utf-8"))
        self.assertEqual(run["entity_type"], "run")
        self.assertEqual(run["mission_id"], mission["id"])
        self.assertEqual(run["status"], "running")

        mission = json.loads(mission_files[0].read_text(encoding="utf-8"))
        self.assertEqual(mission["latest_run_id"], run["id"])
        self.assertEqual(mission["run_ids"], [run["id"]])

    def test_checkpoint_step_tracks_resume_pointer_and_waiting_step(self):
        mission = self.module.create_mission(
            self.module.build_parser().parse_args(
                [
                    "create-mission",
                    "--title",
                    "Product Planning Mission",
                ]
            )
        )
        run = self.module.start_run(
            self.module.build_parser().parse_args(
                [
                    "start-run",
                    "--mission-id",
                    mission["id"],
                    "--actor",
                    "delivery",
                ]
            )
        )
        planner_step = self.module.checkpoint_step(
            self.module.build_parser().parse_args(
                [
                    "checkpoint-step",
                    "--run-id",
                    run["id"],
                    "--key",
                    "planner",
                    "--actor",
                    "delivery",
                    "--status",
                    "completed",
                    "--summary",
                    "Planned the mission loop.",
                ]
            )
        )
        gate_step = self.module.checkpoint_step(
            self.module.build_parser().parse_args(
                [
                    "checkpoint-step",
                    "--run-id",
                    run["id"],
                    "--key",
                    "policy_gate",
                    "--actor",
                    "governor",
                    "--status",
                    "waiting_approval",
                    "--summary",
                    "Approval required before continuing.",
                ]
            )
        )
        current_run = json.loads(self.module.run_path(run["id"]).read_text(encoding="utf-8"))
        self.assertEqual(current_run["checkpoint_count"], 1)
        self.assertEqual(current_run["resume_from_step_id"], planner_step["id"])
        self.assertEqual(current_run["current_step_id"], gate_step["id"])
        self.assertEqual(current_run["status"], "waiting_approval")

    def test_request_and_decide_approval_updates_run_status(self):
        mission = self.module.create_mission(
            self.module.build_parser().parse_args(["create-mission", "--title", "Review Mission"])
        )
        run = self.module.start_run(
            self.module.build_parser().parse_args(
                ["start-run", "--mission-id", mission["id"], "--actor", "delivery"]
            )
        )
        step = self.module.checkpoint_step(
            self.module.build_parser().parse_args(
                [
                    "checkpoint-step",
                    "--run-id",
                    run["id"],
                    "--key",
                    "policy_gate",
                    "--actor",
                    "governor",
                    "--status",
                    "waiting_approval",
                ]
            )
        )
        approval = self.module.request_approval(
            self.module.build_parser().parse_args(
                [
                    "request-approval",
                    "--run-id",
                    run["id"],
                    "--step-id",
                    step["id"],
                    "--requested-by",
                    "governor",
                    "--policy-action",
                    "pause_for_founder_approval",
                ]
            )
        )
        run_state = json.loads(self.module.run_path(run["id"]).read_text(encoding="utf-8"))
        self.assertEqual(run_state["status"], "waiting_approval")
        self.assertEqual(run_state["approval_ids"], [approval["id"]])

        decided = self.module.decide_approval(
            self.module.build_parser().parse_args(
                [
                    "decide-approval",
                    "--approval-id",
                    approval["id"],
                    "--decision",
                    "approved",
                    "--decided-by",
                    "ceo",
                    "--rationale",
                    "Safe to proceed.",
                ]
            )
        )
        self.assertEqual(decided["decision"], "approved")
        run_state = json.loads(self.module.run_path(run["id"]).read_text(encoding="utf-8"))
        self.assertEqual(run_state["status"], "running")
        approval_state = json.loads(
            self.module.approval_path(approval["id"]).read_text(encoding="utf-8")
        )
        self.assertEqual(approval_state["status"], "decided")

    def test_attach_artifact_and_finish_run_persist_lineage(self):
        mission = self.module.create_mission(
            self.module.build_parser().parse_args(["create-mission", "--title", "Artifact Mission"])
        )
        run = self.module.start_run(
            self.module.build_parser().parse_args(
                ["start-run", "--mission-id", mission["id"], "--actor", "delivery"]
            )
        )
        step = self.module.checkpoint_step(
            self.module.build_parser().parse_args(
                [
                    "checkpoint-step",
                    "--run-id",
                    run["id"],
                    "--key",
                    "reviewer",
                    "--actor",
                    "documentation",
                    "--status",
                    "completed",
                ]
            )
        )
        artifact = self.module.attach_artifact(
            self.module.build_parser().parse_args(
                [
                    "attach-artifact",
                    "--run-id",
                    run["id"],
                    "--step-id",
                    step["id"],
                    "--kind",
                    "report",
                    "--path",
                    ".hq/handoffs/example/LATEST.md",
                    "--summary",
                    "Founder review handoff.",
                ]
            )
        )
        self.assertEqual(artifact["run_id"], run["id"])

        finished = self.module.finish_run(
            self.module.build_parser().parse_args(
                ["finish-run", "--run-id", run["id"], "--status", "completed"]
            )
        )
        self.assertEqual(finished["status"], "completed")
        mission_state = json.loads(self.module.mission_path(mission["id"]).read_text(encoding="utf-8"))
        self.assertEqual(mission_state["status"], "completed")

        event_files = sorted(self.module.RUNTIME_DIRS["events"].glob("**/*.jsonl"))
        self.assertTrue(event_files)


if __name__ == "__main__":
    unittest.main()
