import importlib.util
import io
import contextlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "hq_mission_runtime.py"
SCHEMA_FIXTURES = Path(__file__).resolve().parents[1] / "05 AI Control Plane" / "schemas"


def load_module(temp_root: Path):
    os.environ["HQ_MISSION_RUNTIME_REPO_ROOT"] = str(temp_root)
    os.environ["HQ_RUNTIME_PRIVATE_ROOT"] = str(temp_root / ".hq")
    os.environ["HQ_TELEMETRY_REPO_ROOT"] = str(temp_root)
    os.environ["HQ_POLICY_HOOKS_REPO_ROOT"] = str(temp_root)
    sys.modules.pop("hq_io", None)
    sys.modules.pop("hq_policy_hooks", None)
    sys.modules.pop("hq_telemetry_store", None)
    spec = importlib.util.spec_from_file_location("hq_mission_runtime_test_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class HqMissionRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_dir.name)
        (self.temp_root / "05 AI Control Plane" / "schemas").mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            SCHEMA_FIXTURES,
            self.temp_root / "05 AI Control Plane" / "schemas",
            dirs_exist_ok=True,
        )
        self.module = load_module(self.temp_root)
        self.module.ensure_runtime()

    def tearDown(self):
        os.environ.pop("HQ_MISSION_RUNTIME_REPO_ROOT", None)
        os.environ.pop("HQ_RUNTIME_PRIVATE_ROOT", None)
        os.environ.pop("HQ_TELEMETRY_REPO_ROOT", None)
        os.environ.pop("HQ_POLICY_HOOKS_REPO_ROOT", None)
        os.environ.pop("HQ_RUNTIME_HOOKS_FILE", None)
        os.environ.pop("HQ_RUNTIME_POLICY_FILE", None)
        self.temp_dir.cleanup()

    def read_json(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def runtime_path(self, path_value: str) -> Path:
        candidate = Path(path_value)
        if candidate.is_absolute():
            return candidate
        return self.temp_root / candidate

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
        thread_files = sorted(self.module.RUNTIME_DIRS["threads"].glob("*.json"))
        self.assertEqual(len(mission_files), 1)
        self.assertEqual(len(thread_files), 1)
        mission = json.loads(mission_files[0].read_text(encoding="utf-8"))
        thread = json.loads(thread_files[0].read_text(encoding="utf-8"))
        self.assertEqual(mission["entity_type"], "mission")
        self.assertEqual(mission["status"], "planned")
        self.assertEqual(mission["thread_id"], thread["id"])
        self.assertEqual(thread["mission_ids"], [mission["id"]])

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
        self.assertEqual(run["thread_id"], mission["thread_id"])
        self.assertEqual(run["trace_state"]["trace_id"], run["id"])
        self.assertEqual(run["execution_context"]["scope"], "isolated")
        self.assertEqual(run["execution_context"]["runtime_home_mode"], "scoped")
        self.assertTrue(run["execution_context"]["session_id"])
        self.assertTrue((self.temp_root / run["execution_context"]["work_dir"]).is_dir())
        self.assertTrue((self.temp_root / run["execution_context"]["runtime_home"]).is_dir())

        mission = json.loads(mission_files[0].read_text(encoding="utf-8"))
        self.assertEqual(mission["latest_run_id"], run["id"])
        self.assertEqual(mission["run_ids"], [run["id"]])
        thread = json.loads(thread_files[0].read_text(encoding="utf-8"))
        self.assertEqual(thread["active_run_id"], run["id"])
        self.assertEqual(thread["trace_state"]["trace_id"], run["id"])
        self.assertTrue(thread["trace_state"]["resume_fingerprint"])
        self.assertEqual(thread["execution_context"]["session_id"], run["execution_context"]["session_id"])
        self.assertEqual(thread["execution_context"]["work_dir"], run["execution_context"]["work_dir"])

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
        self.assertEqual(current_run["trace_state"]["current_step_id"], gate_step["id"])
        self.assertEqual(current_run["trace_state"]["resume_from_step_id"], planner_step["id"])
        self.assertEqual(planner_step["thread_id"], mission["thread_id"])
        self.assertEqual(gate_step["thread_id"], mission["thread_id"])

    def test_completed_step_creates_checkpoint_packet(self):
        mission = self.module.create_mission(
            self.module.build_parser().parse_args(["create-mission", "--title", "Checkpoint Mission"])
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
                    "planner",
                    "--actor",
                    "delivery",
                    "--status",
                    "completed",
                    "--summary",
                    "Planner checkpoint completed.",
                ]
            )
        )

        run_state = self.read_json(self.module.run_path(run["id"]))
        checkpoint_path = self.runtime_path(run_state["latest_checkpoint_path"])
        self.assertTrue(checkpoint_path.exists())
        checkpoint = self.read_json(checkpoint_path)
        self.assertEqual(checkpoint["entity_type"], "checkpoint")
        self.assertEqual(checkpoint["checkpoint_kind"], "step_completed")
        self.assertEqual(checkpoint["run_id"], run["id"])
        self.assertEqual(checkpoint["thread_id"], mission["thread_id"])
        self.assertEqual(checkpoint["source_step_id"], step["id"])
        self.assertEqual(checkpoint["current_step_id"], step["id"])
        self.assertEqual(checkpoint["resume_from_step_id"], step["id"])
        self.assertEqual(checkpoint["last_successful_step_id"], step["id"])
        self.assertEqual(checkpoint["execution_context"]["session_id"], run_state["execution_context"]["session_id"])
        self.assertEqual(checkpoint["trace_state"]["checkpoint_id"], checkpoint["id"])
        self.assertEqual(checkpoint["trace_state"]["checkpoint_path"], run_state["latest_checkpoint_path"])

    def test_interrupt_run_writes_checkpoint_and_resume_status(self):
        mission = self.module.create_mission(
            self.module.build_parser().parse_args(["create-mission", "--title", "Interrupt Mission"])
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
                    "planner",
                    "--actor",
                    "delivery",
                    "--status",
                    "completed",
                    "--summary",
                    "Checkpoint before interruption.",
                ]
            )
        )

        interrupted = self.module.interrupt_run(
            self.module.build_parser().parse_args(
                [
                    "interrupt-run",
                    "--run-id",
                    run["id"],
                    "--requested-by",
                    "delivery",
                    "--reason",
                    "Need to pause.",
                ]
            )
        )

        checkpoint_path = self.runtime_path(interrupted["latest_checkpoint_path"])
        self.assertTrue(checkpoint_path.exists())
        checkpoint = self.read_json(checkpoint_path)
        self.assertEqual(checkpoint["checkpoint_kind"], "interrupt")
        self.assertEqual(checkpoint["resume_from_step_id"], step["id"])
        self.assertEqual(checkpoint["source_event"], "interrupt-run")

        status_path = self.runtime_path(interrupted["resume_status_path"])
        self.assertTrue(status_path.exists())
        resume_status = self.read_json(status_path)
        self.assertEqual(resume_status["latest_checkpoint_id"], checkpoint["id"])
        self.assertEqual(resume_status["latest_checkpoint_path"], interrupted["latest_checkpoint_path"])
        self.assertTrue(resume_status["resumable"])
        self.assertTrue(resume_status["safe_to_resume"])
        self.assertFalse(resume_status["needs_handoff_refresh"])
        self.assertEqual(resume_status["resume_plan"]["resume_from_step_id"], step["id"])

    def test_finish_run_writes_final_checkpoint(self):
        mission = self.module.create_mission(
            self.module.build_parser().parse_args(["create-mission", "--title", "Finish Checkpoint Mission"])
        )
        run = self.module.start_run(
            self.module.build_parser().parse_args(
                ["start-run", "--mission-id", mission["id"], "--actor", "delivery"]
            )
        )
        self.module.checkpoint_step(
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
                ]
            )
        )
        self.module.verify_run(
            self.module.build_parser().parse_args(
                [
                    "verify-run",
                    "--run-id",
                    run["id"],
                    "--actor",
                    "documentation",
                    "--summary",
                    "Ready for finish.",
                ]
            )
        )

        finished = self.module.finish_run(
            self.module.build_parser().parse_args(
                ["finish-run", "--run-id", run["id"], "--status", "completed"]
            )
        )["finished_run"]

        checkpoint_path = self.runtime_path(finished["latest_checkpoint_path"])
        self.assertTrue(checkpoint_path.exists())
        checkpoint = self.read_json(checkpoint_path)
        self.assertEqual(checkpoint["checkpoint_kind"], "pre_finish")
        self.assertEqual(checkpoint["source_event"], "finish-run")
        resume_status = self.read_json(self.runtime_path(finished["resume_status_path"]))
        self.assertFalse(resume_status["resumable"])
        self.assertFalse(resume_status["safe_to_resume"])
        self.assertIn("terminal", resume_status["resume_reason"])

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
        self.assertEqual(approval["approval_key"]["namespace"], "hq.runtime")
        self.assertEqual(approval["approval_key"]["name"], "policy_gate")

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
        self.assertEqual(approval_state["thread_id"], mission["thread_id"])

    def test_create_handoff_record_links_thread_run_and_resume_state(self):
        mission = self.module.create_mission(
            self.module.build_parser().parse_args(["create-mission", "--title", "Handoff Mission"])
        )
        run = self.module.start_run(
            self.module.build_parser().parse_args(
                ["start-run", "--mission-id", mission["id"], "--actor", "delivery"]
            )
        )

        handoff = self.module.create_handoff_record(
            thread_id=mission["thread_id"],
            task="Handoff Mission",
            session="session-1",
            handoff_file=".hq/handoffs/handoff-mission/LATEST.md",
            owner="delivery",
            status="ready_for_handoff",
            next_steps=["Resume from the last checkpoint."],
        )

        self.assertEqual(handoff["thread_id"], mission["thread_id"])
        self.assertEqual(handoff["run_id"], run["id"])
        run_state = json.loads(self.module.run_path(run["id"]).read_text(encoding="utf-8"))
        self.assertEqual(run_state["handoff_ids"], [handoff["id"]])
        self.assertEqual(run_state["trace_state"]["handoff_id"], handoff["id"])
        thread_state = json.loads(
            self.module.thread_path(mission["thread_id"]).read_text(encoding="utf-8")
        )
        self.assertEqual(thread_state["latest_handoff_id"], handoff["id"])
        self.assertEqual(
            thread_state["trace_state"]["resume_packet_path"],
            ".hq/handoffs/handoff-mission/LATEST.md",
        )
        self.assertEqual(
            handoff["metadata"]["execution_context"]["session_id"],
            run_state["execution_context"]["session_id"],
        )
        self.assertEqual(
            handoff["metadata"]["execution_context"]["work_dir"],
            run_state["execution_context"]["work_dir"],
        )

    def test_runtime_entities_emit_policy_hook_events(self):
        output_path = self.temp_root / "hook-events.jsonl"
        script_path = self.temp_root / "capture_hook.py"
        script_path.write_text(
            (
                "import json\n"
                "import sys\n"
                "from pathlib import Path\n"
                "payload = json.loads(sys.stdin.read())\n"
                "path = Path(sys.argv[1])\n"
                "existing = path.read_text(encoding='utf-8') if path.exists() else ''\n"
                "path.write_text(existing + json.dumps(payload, ensure_ascii=False) + '\\n', encoding='utf-8')\n"
            ),
            encoding="utf-8",
        )
        hooks_path = self.temp_root / ".hq" / "runtime" / "hooks.json"
        hooks_path.parent.mkdir(parents=True, exist_ok=True)
        hooks_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "hooks": [
                        {
                            "id": "capture-run-started",
                            "event": "run_started",
                            "action_prefixes": [["hq", "run", "start"]],
                            "tool_names": ["run"],
                            "command": [sys.executable, str(script_path), str(output_path)],
                        },
                        {
                            "id": "capture-run-checkpointed",
                            "event": "run_checkpointed",
                            "action_prefixes": [["hq", "run", "checkpoint"]],
                            "tool_names": ["verification"],
                            "command": [sys.executable, str(script_path), str(output_path)],
                        },
                        {
                            "id": "capture-agent-finished",
                            "event": "agent_finished",
                            "action_prefixes": [["hq", "agent", "finish"]],
                            "tool_names": ["verification"],
                            "statuses": ["completed"],
                            "command": [sys.executable, str(script_path), str(output_path)],
                        },
                        {
                            "id": "capture-handoff-written",
                            "event": "handoff_written",
                            "action_prefixes": [["hq", "handoff", "write"]],
                            "command": [sys.executable, str(script_path), str(output_path)],
                        },
                        {
                            "id": "capture-run-finished",
                            "event": "run_finished",
                            "action_prefixes": [["hq", "run", "finish"]],
                            "tool_names": ["run"],
                            "statuses": ["completed"],
                            "command": [sys.executable, str(script_path), str(output_path)],
                        },
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        os.environ["HQ_RUNTIME_HOOKS_FILE"] = str(hooks_path)

        mission = self.module.create_mission(
            self.module.build_parser().parse_args(["create-mission", "--title", "Hook Mission"])
        )
        run = self.module.start_run(
            self.module.build_parser().parse_args(
                ["start-run", "--mission-id", mission["id"], "--actor", "delivery"]
            )
        )
        self.module.verify_run(
            self.module.build_parser().parse_args(
                [
                    "verify-run",
                    "--run-id",
                    run["id"],
                    "--actor",
                    "documentation",
                    "--summary",
                    "Verification checklist passed.",
                ]
            )
        )
        self.module.create_handoff_record(
            thread_id=mission["thread_id"],
            task="Hook Mission",
            session="session-1",
            handoff_file=".hq/handoffs/hook-mission/LATEST.md",
            owner="delivery",
            status="ready_for_handoff",
            next_steps=["Resume from the verified state."],
        )
        self.module.finish_run(
            self.module.build_parser().parse_args(
                ["finish-run", "--run-id", run["id"], "--status", "completed"]
            )
        )

        events = [
            json.loads(line)
            for line in output_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        event_types = [event["event"] for event in events]
        self.assertIn("run_started", event_types)
        self.assertIn("run_checkpointed", event_types)
        self.assertIn("agent_finished", event_types)
        self.assertIn("handoff_written", event_types)
        self.assertIn("run_finished", event_types)
        verification_event = next(event for event in events if event["event"] == "run_checkpointed")
        self.assertEqual(verification_event["tool_name"], "verification")
        self.assertEqual(verification_event["run_id"], run["id"])

    def test_finish_run_requires_verification_before_completed(self):
        mission = self.module.create_mission(
            self.module.build_parser().parse_args(["create-mission", "--title", "Verification Mission"])
        )
        run = self.module.start_run(
            self.module.build_parser().parse_args(
                ["start-run", "--mission-id", mission["id"], "--actor", "delivery"]
            )
        )

        with self.assertRaises(ValueError):
            self.module.finish_run(
                self.module.build_parser().parse_args(
                    ["finish-run", "--run-id", run["id"], "--status", "completed"]
                )
            )

        verified = self.module.verify_run(
            self.module.build_parser().parse_args(
                [
                    "verify-run",
                    "--run-id",
                    run["id"],
                    "--actor",
                    "documentation",
                    "--summary",
                    "Verification checklist passed.",
                    "--evidence",
                    "python3 -m unittest tests.test_hq_mission_runtime",
                ]
            )
        )
        self.assertEqual(verified["verification_state"]["status"], "verified")

        finished = self.module.finish_run(
            self.module.build_parser().parse_args(
                ["finish-run", "--run-id", run["id"], "--status", "completed"]
            )
        )
        self.assertEqual(finished["finished_run"]["status"], "completed")
        self.assertEqual(finished["finished_run"]["verification_state"]["status"], "verified")

    def test_staged_verification_routes_review_then_approval_before_completion(self):
        mission = self.module.create_mission(
            self.module.build_parser().parse_args(["create-mission", "--title", "Staged Verification Mission"])
        )
        run = self.module.start_run(
            self.module.build_parser().parse_args(
                [
                    "start-run",
                    "--mission-id",
                    mission["id"],
                    "--actor",
                    "delivery",
                    "--verification-stage",
                    "review:documentation",
                    "--verification-stage",
                    "approval:ceo",
                ]
            )
        )
        self.assertEqual(run["verification_state"]["current_stage_id"], "review-1")
        self.assertEqual(run["verification_state"]["current_participant"], "documentation")
        self.assertEqual(run["verification_state"]["return_target"], "delivery")

        reviewed = self.module.verify_run(
            self.module.build_parser().parse_args(
                [
                    "verify-run",
                    "--run-id",
                    run["id"],
                    "--actor",
                    "documentation",
                    "--summary",
                    "Review passed with expected evidence.",
                ]
            )
        )
        self.assertEqual(reviewed["verification_state"]["status"], "pending")
        self.assertEqual(reviewed["verification_state"]["current_stage_id"], "approval-2")
        self.assertEqual(reviewed["verification_state"]["current_stage_type"], "approval")
        self.assertEqual(reviewed["verification_state"]["current_participant"], "ceo")
        self.assertEqual(reviewed["verification_state"]["completed_stage_ids"], ["review-1"])
        self.assertEqual(reviewed["verification_state"]["last_decision"], "approved")
        self.assertEqual(
            reviewed["verification_state"]["last_decision_note"],
            "Review passed with expected evidence.",
        )

        approved = self.module.verify_run(
            self.module.build_parser().parse_args(
                [
                    "verify-run",
                    "--run-id",
                    run["id"],
                    "--actor",
                    "ceo",
                    "--summary",
                    "Approval granted for completion.",
                ]
            )
        )
        self.assertEqual(approved["verification_state"]["status"], "verified")
        self.assertEqual(approved["verification_state"]["current_stage_id"], "")
        self.assertEqual(approved["verification_state"]["completed_stage_ids"], ["review-1", "approval-2"])

        finished = self.module.finish_run(
            self.module.build_parser().parse_args(
                ["finish-run", "--run-id", run["id"], "--status", "completed"]
            )
        )
        self.assertEqual(finished["finished_run"]["status"], "completed")

    def test_staged_verification_changes_requested_returns_to_executor_then_rereviews(self):
        mission = self.module.create_mission(
            self.module.build_parser().parse_args(["create-mission", "--title", "Re-review Mission"])
        )
        run = self.module.start_run(
            self.module.build_parser().parse_args(
                [
                    "start-run",
                    "--mission-id",
                    mission["id"],
                    "--actor",
                    "delivery",
                    "--verification-stage",
                    "review:documentation",
                ]
            )
        )

        changes_requested = self.module.verify_run(
            self.module.build_parser().parse_args(
                [
                    "verify-run",
                    "--run-id",
                    run["id"],
                    "--actor",
                    "documentation",
                    "--status",
                    "changes_requested",
                    "--summary",
                    "Please fix the missing regression coverage.",
                ]
            )
        )
        self.assertEqual(changes_requested["verification_state"]["status"], "changes_requested")
        self.assertEqual(changes_requested["verification_state"]["current_stage_id"], "review-1")
        self.assertEqual(changes_requested["verification_state"]["current_participant"], "delivery")
        self.assertEqual(changes_requested["verification_state"]["return_target"], "delivery")
        self.assertEqual(changes_requested["verification_state"]["last_decision"], "changes_requested")

        resubmitted = self.module.verify_run(
            self.module.build_parser().parse_args(
                [
                    "verify-run",
                    "--run-id",
                    run["id"],
                    "--actor",
                    "delivery",
                    "--summary",
                    "Regression coverage added and re-submitted.",
                ]
            )
        )
        self.assertEqual(resubmitted["verification_state"]["status"], "pending")
        self.assertEqual(resubmitted["verification_state"]["current_stage_id"], "review-1")
        self.assertEqual(resubmitted["verification_state"]["current_participant"], "documentation")
        self.assertEqual(resubmitted["verification_state"]["last_decision"], "changes_requested")

        rereviewed = self.module.verify_run(
            self.module.build_parser().parse_args(
                [
                    "verify-run",
                    "--run-id",
                    run["id"],
                    "--actor",
                    "documentation",
                    "--summary",
                    "Re-review passed after requested changes.",
                ]
            )
        )
        self.assertEqual(rereviewed["verification_state"]["status"], "verified")
        self.assertEqual(rereviewed["verification_state"]["completed_stage_ids"], ["review-1"])

        finished = self.module.finish_run(
            self.module.build_parser().parse_args(
                ["finish-run", "--run-id", run["id"], "--status", "completed"]
            )
        )
        self.assertEqual(finished["finished_run"]["status"], "completed")

    def test_finish_run_rejects_completion_while_verification_stages_remain_open(self):
        mission = self.module.create_mission(
            self.module.build_parser().parse_args(["create-mission", "--title", "Open Verification Mission"])
        )
        run = self.module.start_run(
            self.module.build_parser().parse_args(
                [
                    "start-run",
                    "--mission-id",
                    mission["id"],
                    "--actor",
                    "delivery",
                    "--verification-stage",
                    "review:documentation",
                    "--verification-stage",
                    "approval:ceo",
                ]
            )
        )
        self.module.verify_run(
            self.module.build_parser().parse_args(
                [
                    "verify-run",
                    "--run-id",
                    run["id"],
                    "--actor",
                    "documentation",
                    "--summary",
                    "Review passed and moved to approval.",
                ]
            )
        )

        with self.assertRaises(ValueError):
            self.module.finish_run(
                self.module.build_parser().parse_args(
                    ["finish-run", "--run-id", run["id"], "--status", "completed"]
                )
            )

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

        self.module.verify_run(
            self.module.build_parser().parse_args(
                [
                    "verify-run",
                    "--run-id",
                    run["id"],
                    "--actor",
                    "documentation",
                    "--summary",
                    "Artifact mission verification passed.",
                ]
            )
        )

        finished = self.module.finish_run(
            self.module.build_parser().parse_args(
                ["finish-run", "--run-id", run["id"], "--status", "completed"]
            )
        )
        self.assertEqual(finished["finished_run"]["status"], "completed")
        mission_state = json.loads(self.module.mission_path(mission["id"]).read_text(encoding="utf-8"))
        self.assertEqual(mission_state["status"], "completed")
        thread_state = json.loads(
            self.module.thread_path(mission["thread_id"]).read_text(encoding="utf-8")
        )
        self.assertEqual(thread_state["status"], "idle")
        self.assertEqual(thread_state["active_run_id"], "")
        self.assertEqual(thread_state["trace_state"]["trace_id"], run["id"])

        event_files = sorted(self.module.RUNTIME_DIRS["events"].glob("**/*.jsonl"))
        self.assertTrue(event_files)

    def test_runtime_events_are_mirrored_into_telemetry_with_run_lineage(self):
        mission = self.module.create_mission(
            self.module.build_parser().parse_args(
                [
                    "create-mission",
                    "--title",
                    "Founder Weekly Review",
                    "--source-task-id",
                    "weekly-review-task",
                    "--workflow",
                    "founder-weekly-operating-review",
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
                    "ai_operations_lead",
                ]
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
                    "--summary",
                    "Founder review required.",
                ]
            )
        )

        telemetry_files = sorted((self.temp_root / ".hq" / "telemetry").glob("**/*.jsonl"))
        self.assertEqual(len(telemetry_files), 1)
        events = [
            json.loads(line)
            for line in telemetry_files[0].read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        step_events = [event for event in events if event["event_type"] == "step_checkpointed"]
        self.assertTrue(any(event["event_type"] == "mission_created" for event in events))
        self.assertTrue(any(event["event_type"] == "run_started" for event in events))
        self.assertTrue(step_events)
        self.assertEqual(step_events[-1]["run_id"], run["id"])
        self.assertEqual(step_events[-1]["step_id"], step["id"])
        self.assertEqual(step_events[-1]["mission_id"], mission["id"])
        self.assertEqual(step_events[-1]["thread_id"], mission["thread_id"])

    def test_link_thread_command_updates_spec_and_handoff_pointers(self):
        thread = self.module.create_thread_record(title="Reference Donor Analysis", owner="delivery")
        parser = self.module.build_parser()
        args = parser.parse_args(
            [
                "link-thread",
                "--thread-id",
                thread["id"],
                "--spec-path",
                ".hq/specs/reference-donor-analysis/LATEST.md",
                "--handoff-path",
                ".hq/handoffs/reference-donor-analysis/LATEST.md",
                "--resume-packet-path",
                ".hq/handoffs/reference-donor-analysis/LATEST.md",
                "--status",
                "paused",
            ]
        )
        exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        thread_state = json.loads(self.module.thread_path(thread["id"]).read_text(encoding="utf-8"))
        self.assertEqual(thread_state["latest_spec_path"], ".hq/specs/reference-donor-analysis/LATEST.md")
        self.assertEqual(
            thread_state["latest_handoff_path"],
            ".hq/handoffs/reference-donor-analysis/LATEST.md",
        )
        self.assertEqual(thread_state["resume_packet_path"], ".hq/handoffs/reference-donor-analysis/LATEST.md")
        self.assertEqual(thread_state["status"], "paused")

    def test_resume_context_command_returns_narrow_resume_linkage(self):
        mission = self.module.create_mission(
            self.module.build_parser().parse_args(["create-mission", "--title", "Resume Mission"])
        )
        run = self.module.start_run(
            self.module.build_parser().parse_args(
                [
                    "start-run",
                    "--mission-id",
                    mission["id"],
                    "--actor",
                    "delivery",
                    "--session-id",
                    "codex-session-42",
                ]
            )
        )
        self.module.checkpoint_step(
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
                    "Resume packet ready.",
                ]
            )
        )
        handoff = self.module.create_handoff_record(
            thread_id=mission["thread_id"],
            task="Resume Mission",
            session="session-1",
            handoff_file=".hq/handoffs/resume-mission/LATEST.md",
            owner="delivery",
            status="ready_for_handoff",
            next_steps=["Resume from the isolated workdir."],
        )

        parser = self.module.build_parser()
        args = parser.parse_args(["resume-context", "--thread-id", mission["thread_id"]])
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["thread_id"], mission["thread_id"])
        self.assertEqual(payload["run_id"], run["id"])
        self.assertEqual(payload["session_id"], "codex-session-42")
        self.assertEqual(payload["work_dir"], run["execution_context"]["work_dir"])
        self.assertEqual(payload["runtime_home"], run["execution_context"]["runtime_home"])
        self.assertEqual(payload["handoff_id"], handoff["id"])
        self.assertEqual(payload["resume_packet_path"], ".hq/handoffs/resume-mission/LATEST.md")

    def test_show_resume_status_keeps_resumable_when_handoff_is_missing(self):
        mission = self.module.create_mission(
            self.module.build_parser().parse_args(["create-mission", "--title", "Missing Handoff Mission"])
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
                    "planner",
                    "--actor",
                    "delivery",
                    "--status",
                    "completed",
                ]
            )
        )
        self.module.create_handoff_record(
            thread_id=mission["thread_id"],
            task="Missing Handoff Mission",
            session="session-1",
            handoff_file=".hq/handoffs/missing-handoff/LATEST.md",
            owner="delivery",
            status="ready_for_handoff",
            next_steps=["Resume from checkpoint."],
        )
        self.module.interrupt_run(
            self.module.build_parser().parse_args(
                [
                    "interrupt-run",
                    "--run-id",
                    run["id"],
                    "--requested-by",
                    "delivery",
                    "--reason",
                    "Pause before handoff refresh.",
                ]
            )
        )
        missing_handoff_path = self.temp_root / ".hq" / "handoffs" / "missing-handoff" / "LATEST.md"
        if missing_handoff_path.exists():
            missing_handoff_path.unlink()

        parser = self.module.build_parser()
        args = parser.parse_args(["show-resume-status", "--run-id", run["id"]])
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["resumable"])
        self.assertTrue(payload["safe_to_resume"])
        self.assertTrue(payload["needs_handoff_refresh"])
        self.assertIn(step["id"], payload["resume_plan"]["resume_from_step_id"])
        self.assertTrue(any("latest_handoff_path" in item for item in payload["stale_inputs"]))

    def test_show_resume_status_handles_corrupted_checkpoint_without_crashing(self):
        mission = self.module.create_mission(
            self.module.build_parser().parse_args(["create-mission", "--title", "Corrupt Checkpoint Mission"])
        )
        run = self.module.start_run(
            self.module.build_parser().parse_args(
                ["start-run", "--mission-id", mission["id"], "--actor", "delivery"]
            )
        )
        self.module.checkpoint_step(
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
                ]
            )
        )
        interrupted = self.module.interrupt_run(
            self.module.build_parser().parse_args(
                [
                    "interrupt-run",
                    "--run-id",
                    run["id"],
                    "--requested-by",
                    "delivery",
                    "--reason",
                    "Pause before corruption test.",
                ]
            )
        )
        checkpoint_path = self.runtime_path(interrupted["latest_checkpoint_path"])
        checkpoint_path.write_text("{not json}\n", encoding="utf-8")

        parser = self.module.build_parser()
        args = parser.parse_args(["show-resume-status", "--run-id", run["id"]])
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertFalse(payload["resumable"])
        self.assertFalse(payload["safe_to_resume"])
        self.assertIn("checkpoint", payload["resume_reason"])

    def test_resume_run_with_same_token_is_idempotent(self):
        mission = self.module.create_mission(
            self.module.build_parser().parse_args(["create-mission", "--title", "Idempotent Resume Mission"])
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
                    "planner",
                    "--actor",
                    "delivery",
                    "--status",
                    "completed",
                ]
            )
        )
        self.module.interrupt_run(
            self.module.build_parser().parse_args(
                [
                    "interrupt-run",
                    "--run-id",
                    run["id"],
                    "--requested-by",
                    "delivery",
                    "--reason",
                    "Pause before resume.",
                ]
            )
        )

        resumed = self.module.resume_run(
            self.module.build_parser().parse_args(
                [
                    "resume-run",
                    "--run-id",
                    run["id"],
                    "--resumed-by",
                    "delivery",
                    "--resume-token",
                    "resume-token-1",
                ]
            )
        )
        resumed_state = self.read_json(self.module.run_path(run["id"]))
        resumed_status = self.read_json(self.runtime_path(resumed_state["resume_status_path"]))

        resumed_again = self.module.resume_run(
            self.module.build_parser().parse_args(
                [
                    "resume-run",
                    "--run-id",
                    run["id"],
                    "--resumed-by",
                    "delivery",
                    "--resume-token",
                    "resume-token-1",
                ]
            )
        )
        resumed_state_again = self.read_json(self.module.run_path(run["id"]))
        resumed_status_again = self.read_json(self.runtime_path(resumed_state_again["resume_status_path"]))

        self.assertEqual(resumed["id"], resumed_again["id"])
        self.assertEqual(resumed_again["status"], "running")
        self.assertEqual(resumed_state["updated_at"], resumed_state_again["updated_at"])
        self.assertEqual(resumed_state["current_step_id"], step["id"])
        self.assertEqual(resumed_status["resume_epoch"], 1)
        self.assertEqual(resumed_status_again["resume_epoch"], 1)
        self.assertEqual(resumed_status_again["idempotency_key"], "resume-token-1")

    def test_new_resume_token_increments_epoch_and_updates_status(self):
        mission = self.module.create_mission(
            self.module.build_parser().parse_args(["create-mission", "--title", "Resume Epoch Mission"])
        )
        run = self.module.start_run(
            self.module.build_parser().parse_args(
                ["start-run", "--mission-id", mission["id"], "--actor", "delivery"]
            )
        )
        self.module.checkpoint_step(
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
                ]
            )
        )
        self.module.interrupt_run(
            self.module.build_parser().parse_args(
                [
                    "interrupt-run",
                    "--run-id",
                    run["id"],
                    "--requested-by",
                    "delivery",
                ]
            )
        )
        self.module.resume_run(
            self.module.build_parser().parse_args(
                [
                    "resume-run",
                    "--run-id",
                    run["id"],
                    "--resumed-by",
                    "delivery",
                    "--resume-token",
                    "resume-token-1",
                ]
            )
        )
        self.module.interrupt_run(
            self.module.build_parser().parse_args(
                [
                    "interrupt-run",
                    "--run-id",
                    run["id"],
                    "--requested-by",
                    "delivery",
                    "--reason",
                    "Pause again.",
                ]
            )
        )

        resumed = self.module.resume_run(
            self.module.build_parser().parse_args(
                [
                    "resume-run",
                    "--run-id",
                    run["id"],
                    "--resumed-by",
                    "delivery",
                    "--resume-token",
                    "resume-token-2",
                ]
            )
        )
        resume_status = self.read_json(self.runtime_path(resumed["resume_status_path"]))
        self.assertEqual(resume_status["resume_epoch"], 2)
        self.assertEqual(resume_status["idempotency_key"], "resume-token-2")
        self.assertFalse(resume_status["resumable"])
        self.assertIn("already running", resume_status["resume_reason"])

    def test_resume_run_still_works_for_legacy_interrupted_run_without_checkpoint(self):
        mission = self.module.create_mission(
            self.module.build_parser().parse_args(["create-mission", "--title", "Legacy Resume Mission"])
        )
        run = self.module.start_run(
            self.module.build_parser().parse_args(
                ["start-run", "--mission-id", mission["id"], "--actor", "delivery"]
            )
        )
        self.module.checkpoint_step(
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
                ]
            )
        )
        interrupted = self.module.interrupt_run(
            self.module.build_parser().parse_args(
                [
                    "interrupt-run",
                    "--run-id",
                    run["id"],
                    "--requested-by",
                    "delivery",
                ]
            )
        )

        legacy_run = self.read_json(self.module.run_path(run["id"]))
        self.runtime_path(legacy_run["latest_checkpoint_path"]).unlink()
        legacy_run["latest_checkpoint_id"] = ""
        legacy_run["latest_checkpoint_path"] = ""
        self.module.run_path(run["id"]).write_text(
            json.dumps(legacy_run, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        legacy_thread = self.read_json(self.module.thread_path(mission["thread_id"]))
        legacy_thread["latest_checkpoint_id"] = ""
        legacy_thread["latest_checkpoint_path"] = ""
        self.module.thread_path(mission["thread_id"]).write_text(
            json.dumps(legacy_thread, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        resumed = self.module.resume_run(
            self.module.build_parser().parse_args(
                [
                    "resume-run",
                    "--run-id",
                    interrupted["id"],
                    "--resumed-by",
                    "delivery",
                    "--resume-token",
                    "legacy-token",
                ]
            )
        )

        self.assertEqual(resumed["status"], "running")
        self.assertTrue(resumed["latest_checkpoint_path"])

    def test_start_run_can_prepare_child_isolated_context_with_default_blocked_tool_classes(self):
        mission = self.module.create_mission(
            self.module.build_parser().parse_args(["create-mission", "--title", "Delegation Mission"])
        )
        run = self.module.start_run(
            self.module.build_parser().parse_args(
                [
                    "start-run",
                    "--mission-id",
                    mission["id"],
                    "--actor",
                    "delivery",
                    "--parent-session-id",
                    "parent-session-1",
                ]
            )
        )

        self.assertEqual(run["execution_context"]["scope"], "child_isolated")
        self.assertEqual(run["execution_context"]["parent_session_id"], "parent-session-1")
        self.assertEqual(
            run["execution_context"]["blocked_tool_classes"],
            ["delegation", "user_interaction", "shared_memory_write", "external_side_effect"],
        )

    def test_checkpoint_step_rejects_corrupt_run_payload_against_schema(self):
        mission = self.module.create_mission(
            self.module.build_parser().parse_args(["create-mission", "--title", "Corrupt Run Mission"])
        )
        run = self.module.start_run(
            self.module.build_parser().parse_args(
                ["start-run", "--mission-id", mission["id"], "--actor", "delivery"]
            )
        )
        corrupt_run = json.loads(self.module.run_path(run["id"]).read_text(encoding="utf-8"))
        corrupt_run.pop("mission_id")
        self.module.run_path(run["id"]).write_text(
            json.dumps(corrupt_run, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        with self.assertRaises(ValueError):
            self.module.checkpoint_step(
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
                    ]
                )
            )


    def _create_run_for_error_tests(self):
        """Helper: create a mission + run for error taxonomy tests."""
        mission = self.module.create_mission(
            self.module.build_parser().parse_args(
                ["create-mission", "--title", "Error Taxonomy Mission"]
            )
        )
        run = self.module.start_run(
            self.module.build_parser().parse_args(
                ["start-run", "--mission-id", mission["id"], "--actor", "delivery"]
            )
        )
        return mission, run

    def test_checkpoint_step_stores_error_type_and_retry_count(self):
        _mission, run = self._create_run_for_error_tests()
        step = self.module.checkpoint_step(
            self.module.build_parser().parse_args(
                [
                    "checkpoint-step",
                    "--run-id", run["id"],
                    "--key", "fetch-data",
                    "--actor", "delivery",
                    "--status", "failed",
                    "--error-type", "transient",
                    "--summary", "Network timeout.",
                ]
            )
        )
        self.assertEqual(step["error_type"], "transient")
        self.assertEqual(step["retry_count"], 1)

    def test_completed_step_has_empty_error_type_and_zero_retry_count(self):
        _mission, run = self._create_run_for_error_tests()
        step = self.module.checkpoint_step(
            self.module.build_parser().parse_args(
                [
                    "checkpoint-step",
                    "--run-id", run["id"],
                    "--key", "planner",
                    "--actor", "delivery",
                    "--status", "completed",
                    "--summary", "Plan done.",
                ]
            )
        )
        self.assertEqual(step["error_type"], "")
        self.assertEqual(step["retry_count"], 0)

    def test_transient_error_keeps_run_running_within_retry_cap(self):
        _mission, run = self._create_run_for_error_tests()
        self.module.checkpoint_step(
            self.module.build_parser().parse_args(
                [
                    "checkpoint-step",
                    "--run-id", run["id"],
                    "--key", "api-call",
                    "--actor", "delivery",
                    "--status", "failed",
                    "--error-type", "transient",
                    "--summary", "Timeout #1.",
                ]
            )
        )
        run_state = json.loads(self.module.run_path(run["id"]).read_text(encoding="utf-8"))
        self.assertEqual(run_state["status"], "running")

    def test_transient_error_escalates_to_unexpected_after_retry_cap(self):
        _mission, run = self._create_run_for_error_tests()
        # Exhaust the retry cap (MAX_TRANSIENT_RETRIES = 2)
        for i in range(3):
            step = self.module.checkpoint_step(
                self.module.build_parser().parse_args(
                    [
                        "checkpoint-step",
                        "--run-id", run["id"],
                        "--key", "api-call",
                        "--actor", "delivery",
                        "--status", "failed",
                        "--error-type", "transient",
                        "--summary", f"Timeout #{i + 1}.",
                    ]
                )
            )
        # The 3rd attempt should be escalated to unexpected
        self.assertEqual(step["error_type"], "unexpected")
        run_state = json.loads(self.module.run_path(run["id"]).read_text(encoding="utf-8"))
        self.assertEqual(run_state["status"], "failed")

    def test_recoverable_error_keeps_run_running(self):
        _mission, run = self._create_run_for_error_tests()
        step = self.module.checkpoint_step(
            self.module.build_parser().parse_args(
                [
                    "checkpoint-step",
                    "--run-id", run["id"],
                    "--key", "parse-output",
                    "--actor", "delivery",
                    "--status", "failed",
                    "--error-type", "recoverable",
                    "--summary", "JSON parse error returned as context.",
                ]
            )
        )
        self.assertEqual(step["error_type"], "recoverable")
        run_state = json.loads(self.module.run_path(run["id"]).read_text(encoding="utf-8"))
        self.assertEqual(run_state["status"], "running")

    def test_user_fixable_error_pauses_run_for_approval(self):
        _mission, run = self._create_run_for_error_tests()
        step = self.module.checkpoint_step(
            self.module.build_parser().parse_args(
                [
                    "checkpoint-step",
                    "--run-id", run["id"],
                    "--key", "credential-check",
                    "--actor", "delivery",
                    "--status", "failed",
                    "--error-type", "user_fixable",
                    "--summary", "Missing API key.",
                ]
            )
        )
        self.assertEqual(step["error_type"], "user_fixable")
        run_state = json.loads(self.module.run_path(run["id"]).read_text(encoding="utf-8"))
        self.assertEqual(run_state["status"], "waiting_approval")

    def test_checkpoint_step_records_allowed_tool_classes_with_allow_decision(self):
        mission = self.module.create_mission(
            self.module.build_parser().parse_args(["create-mission", "--title", "Tool Allow Mission"])
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
                    "planner",
                    "--actor",
                    "delivery",
                    "--status",
                    "completed",
                    "--allowed-tool-class",
                    "workspace_read",
                    "--allowed-tool-class",
                    "repo_query",
                ]
            )
        )

        self.assertEqual(step["allowed_tool_classes"], ["workspace_read", "repo_query"])
        self.assertEqual(step["policy_action"], "allow")
        self.assertFalse(step["policy_context"]["tripwire_triggered"])
        run_state = json.loads(self.module.run_path(run["id"]).read_text(encoding="utf-8"))
        self.assertEqual(run_state["status"], "running")

    def test_checkpoint_step_marks_review_required_when_policy_returns_allow_with_review(self):
        policy_path = self.temp_root / ".hq" / "runtime" / "policy.json"
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        policy_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "default_decision": "allow",
                    "rules": [
                        {
                            "id": "tracked-write-review",
                            "action_prefix": ["hq", "step", "tool", "tracked_write"],
                            "decision": "allow_with_review",
                            "match": [["hq", "step", "tool", "tracked_write"]],
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        os.environ["HQ_RUNTIME_POLICY_FILE"] = str(policy_path)
        mission = self.module.create_mission(
            self.module.build_parser().parse_args(["create-mission", "--title", "Tool Review Mission"])
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
                    "writer",
                    "--actor",
                    "delivery",
                    "--status",
                    "completed",
                    "--allowed-tool-class",
                    "tracked_write",
                ]
            )
        )

        self.assertEqual(step["policy_action"], "allow_with_review")
        self.assertTrue(step["policy_context"]["review_required"])
        self.assertEqual(step["status"], "completed")
        self.assertEqual(step["policy_context"]["matched_rules"][0]["id"], "tracked-write-review")
        run_state = json.loads(self.module.run_path(run["id"]).read_text(encoding="utf-8"))
        self.assertEqual(run_state["status"], "running")
        self.assertEqual(run_state["approval_ids"], [])

    def test_checkpoint_step_pauses_for_founder_approval_when_tool_policy_requires_it(self):
        policy_path = self.temp_root / ".hq" / "runtime" / "policy.json"
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        policy_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "default_decision": "allow",
                    "rules": [
                        {
                            "id": "external-send-pause",
                            "action_prefix": ["hq", "step", "tool", "external_side_effect"],
                            "decision": "pause_for_founder_approval",
                            "match": [["hq", "step", "tool", "external_side_effect"]],
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        os.environ["HQ_RUNTIME_POLICY_FILE"] = str(policy_path)
        mission = self.module.create_mission(
            self.module.build_parser().parse_args(["create-mission", "--title", "Tool Pause Mission"])
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
                    "outreach",
                    "--actor",
                    "delivery",
                    "--status",
                    "completed",
                    "--allowed-tool-class",
                    "external_side_effect",
                ]
            )
        )

        self.assertEqual(step["policy_action"], "pause_for_founder_approval")
        self.assertEqual(step["status"], "waiting_approval")
        self.assertTrue(step["policy_context"]["tripwire_triggered"])
        run_state = json.loads(self.module.run_path(run["id"]).read_text(encoding="utf-8"))
        self.assertEqual(run_state["status"], "waiting_approval")
        self.assertEqual(len(run_state["approval_ids"]), 1)
        approval = json.loads(
            self.module.approval_path(run_state["approval_ids"][0]).read_text(encoding="utf-8")
        )
        self.assertEqual(approval["policy_action"], "pause_for_founder_approval")
        self.assertEqual(approval["tool_scope"], ["external_side_effect"])
        self.assertEqual(step["policy_context"]["approval_id"], approval["id"])

    def test_checkpoint_step_blocks_when_tool_class_is_blocked_by_execution_context(self):
        mission = self.module.create_mission(
            self.module.build_parser().parse_args(["create-mission", "--title", "Tool Block Mission"])
        )
        run = self.module.start_run(
            self.module.build_parser().parse_args(
                [
                    "start-run",
                    "--mission-id",
                    mission["id"],
                    "--actor",
                    "delivery",
                    "--blocked-tool-class",
                    "external_side_effect",
                ]
            )
        )

        step = self.module.checkpoint_step(
            self.module.build_parser().parse_args(
                [
                    "checkpoint-step",
                    "--run-id",
                    run["id"],
                    "--key",
                    "outreach",
                    "--actor",
                    "delivery",
                    "--status",
                    "completed",
                    "--allowed-tool-class",
                    "external_side_effect",
                ]
            )
        )

        self.assertEqual(step["policy_action"], "block")
        self.assertEqual(step["status"], "blocked")
        self.assertEqual(step["policy_context"]["blocked_tool_classes"], ["external_side_effect"])
        self.assertTrue(step["policy_context"]["tripwire_triggered"])
        run_state = json.loads(self.module.run_path(run["id"]).read_text(encoding="utf-8"))
        self.assertEqual(run_state["status"], "blocked")
        self.assertEqual(run_state["approval_ids"], [])

    def test_unexpected_error_fails_run(self):
        _mission, run = self._create_run_for_error_tests()
        step = self.module.checkpoint_step(
            self.module.build_parser().parse_args(
                [
                    "checkpoint-step",
                    "--run-id", run["id"],
                    "--key", "critical-step",
                    "--actor", "delivery",
                    "--status", "failed",
                    "--error-type", "unexpected",
                    "--summary", "Unhandled exception.",
                ]
            )
        )
        self.assertEqual(step["error_type"], "unexpected")
        run_state = json.loads(self.module.run_path(run["id"]).read_text(encoding="utf-8"))
        self.assertEqual(run_state["status"], "failed")

    def test_error_type_rejected_when_status_is_not_failed(self):
        _mission, run = self._create_run_for_error_tests()
        with self.assertRaises(ValueError):
            self.module.checkpoint_step(
                self.module.build_parser().parse_args(
                    [
                        "checkpoint-step",
                        "--run-id", run["id"],
                        "--key", "bad-combo",
                        "--actor", "delivery",
                        "--status", "completed",
                        "--error-type", "transient",
                        "--summary", "Should fail validation.",
                    ]
                )
            )

    def test_transient_retry_count_resets_after_different_key(self):
        _mission, run = self._create_run_for_error_tests()
        # First transient failure
        self.module.checkpoint_step(
            self.module.build_parser().parse_args(
                [
                    "checkpoint-step",
                    "--run-id", run["id"],
                    "--key", "api-call",
                    "--actor", "delivery",
                    "--status", "failed",
                    "--error-type", "transient",
                    "--summary", "Timeout #1.",
                ]
            )
        )
        # Different key step
        self.module.checkpoint_step(
            self.module.build_parser().parse_args(
                [
                    "checkpoint-step",
                    "--run-id", run["id"],
                    "--key", "parser",
                    "--actor", "delivery",
                    "--status", "completed",
                    "--summary", "Parsed output.",
                ]
            )
        )
        # Same key again — retry count should restart because
        # the consecutive chain was broken by 'parser'
        step = self.module.checkpoint_step(
            self.module.build_parser().parse_args(
                [
                    "checkpoint-step",
                    "--run-id", run["id"],
                    "--key", "api-call",
                    "--actor", "delivery",
                    "--status", "failed",
                    "--error-type", "transient",
                    "--summary", "Timeout after reset.",
                ]
            )
        )
        self.assertEqual(step["retry_count"], 1)
        run_state = json.loads(self.module.run_path(run["id"]).read_text(encoding="utf-8"))
        self.assertEqual(run_state["status"], "running")


if __name__ == "__main__":
    unittest.main()
