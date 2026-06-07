from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "hq_feedback_loop.py"


def load_module(temp_root: Path):
    os.environ["HQ_FEEDBACK_LOOP_REPO_ROOT"] = str(temp_root)
    os.environ["HQ_RUNTIME_PRIVATE_ROOT"] = str(temp_root / ".hq")
    sys.modules.pop("hq_feedback_loop_test_module", None)
    spec = importlib.util.spec_from_file_location("hq_feedback_loop_test_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class HqFeedbackLoopTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_dir.name)
        self.module = load_module(self.temp_root)

    def tearDown(self):
        os.environ.pop("HQ_FEEDBACK_LOOP_REPO_ROOT", None)
        os.environ.pop("HQ_RUNTIME_PRIVATE_ROOT", None)
        self.temp_dir.cleanup()

    def test_write_iteration_appends_private_jsonl(self):
        payload = self.module.build_iteration_payload(
            task_id="task-1",
            hypothesis="A short packet will pass review.",
            action="Draft the packet.",
            metric="review_ready=true",
            status="done",
            evidence=["Packet drafted and checked."],
            touched_files=[".hq/specs/task-1/LATEST.md"],
            next_focus="Ask for review.",
            rollback_reason="",
            actor="ai_operations_lead",
        )

        path, iteration_id = self.module.write_iteration(payload)

        self.assertTrue(path.match("*/.hq/telemetry/feedback-loop/*.jsonl"))
        self.assertEqual(iteration_id, payload["id"])
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        written = json.loads(lines[0])
        self.assertEqual(written["task_id"], "task-1")
        self.assertEqual(written["status"], "done")
        self.assertEqual(written["evidence"], ["Packet drafted and checked."])

    def test_recent_iterations_returns_newest_first_and_supports_checks_failed(self):
        first = self.module.build_iteration_payload(
            task_id="task-1",
            hypothesis="Initial check will pass.",
            action="Run the check.",
            metric="exit_code=0",
            status="checks_failed",
            evidence=["exit_code=1"],
            touched_files=["scripts/example.py"],
            next_focus="Fix the failing assertion.",
            rollback_reason="",
            actor="delivery",
            created_at="2026-04-20T09:00:00Z",
        )
        second = self.module.build_iteration_payload(
            task_id="task-2",
            hypothesis="Approval is needed.",
            action="Prepare approval note.",
            metric="approval_ready=true",
            status="needs_approval",
            evidence=["Draft is ready."],
            touched_files=[],
            next_focus="Wait for founder review.",
            rollback_reason="",
            actor="growth",
            created_at="2026-04-20T10:00:00Z",
        )
        self.module.write_iteration(first)
        self.module.write_iteration(second)

        recent = self.module.load_recent_iterations(self.temp_root / ".hq", limit=2)

        self.assertEqual([item["task_id"] for item in recent], ["task-2", "task-1"])
        self.assertEqual(recent[1]["status"], "checks_failed")
        self.assertEqual(recent[1]["next_focus"], "Fix the failing assertion.")


if __name__ == "__main__":
    unittest.main()
