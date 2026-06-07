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


    def test_after_iteration_id_collapses_superseded_running_record(self):
        before = self.module.build_iteration_payload(
            task_id="task-1",
            hypothesis="Packet will pass review.",
            action="Draft the packet.",
            metric="review_ready",
            status="running",
            evidence=[],
            touched_files=[],
            next_focus="Run the review.",
            rollback_reason="",
            actor="delivery",
            created_at="2026-04-20T09:00:00Z",
        )
        after = self.module.build_iteration_payload(
            task_id="task-1",
            hypothesis="Packet will pass review.",
            action="Reviewed the packet.",
            metric="review_ready",
            status="done",
            evidence=["Review passed."],
            touched_files=[],
            next_focus="Ship the packet.",
            rollback_reason="",
            actor="delivery",
            parent_id=before["id"],
            created_at="2026-04-20T09:30:00Z",
        )
        self.module.write_iteration(before)
        self.module.write_iteration(after)

        recent = self.module.load_recent_iterations(self.temp_root / ".hq", limit=10)

        self.assertEqual([item["status"] for item in recent], ["done"])
        self.assertEqual(recent[0]["parent_id"], before["id"])

    def test_open_running_attempt_stays_visible(self):
        before = self.module.build_iteration_payload(
            task_id="task-1",
            hypothesis="In-flight work.",
            action="Started the attempt.",
            metric="progress",
            status="running",
            evidence=[],
            touched_files=[],
            next_focus="Finish the attempt.",
            rollback_reason="",
            actor="delivery",
            created_at="2026-04-20T09:00:00Z",
        )
        self.module.write_iteration(before)

        summary = self.module.build_feedback_summary(self.temp_root / ".hq")

        self.assertEqual(summary["overall"]["open_attempts"], 1)

    def test_summary_reports_baseline_best_and_delta(self):
        common = dict(
            task_id="task-1",
            hypothesis="Higher revenue is better.",
            action="Ran the experiment.",
            metric="revenue",
            metric_direction="higher",
            evidence=[],
            touched_files=[],
            next_focus="Try the next lever.",
            rollback_reason="",
            actor="growth",
        )
        self.module.write_iteration(
            self.module.build_iteration_payload(
                status="done", metric_value=100, created_at="2026-04-20T09:00:00Z", **common
            )
        )
        self.module.write_iteration(
            self.module.build_iteration_payload(
                status="hypothesis_failed", metric_value=80, created_at="2026-04-20T10:00:00Z", **common
            )
        )
        self.module.write_iteration(
            self.module.build_iteration_payload(
                status="done", metric_value=150, created_at="2026-04-20T11:00:00Z", **common
            )
        )

        summary = self.module.build_feedback_summary(self.temp_root / ".hq")
        task = summary["tasks"]["task-1"]

        self.assertEqual(task["metric_direction"], "higher")
        self.assertEqual(task["baseline"]["metric_value"], 100.0)
        self.assertEqual(task["best"]["metric_value"], 150.0)
        self.assertEqual(task["latest"]["metric_value"], 150.0)
        self.assertEqual(task["latest_delta_pct"], 50.0)
        self.assertEqual(task["status_counts"], {"done": 2, "hypothesis_failed": 1})

    def test_open_next_steps_uses_latest_per_task(self):
        self.module.write_iteration(
            self.module.build_iteration_payload(
                task_id="task-1",
                hypothesis="First.",
                action="Did first.",
                metric="m",
                status="done",
                evidence=[],
                touched_files=[],
                next_focus="Old focus.",
                rollback_reason="",
                actor="delivery",
                created_at="2026-04-20T09:00:00Z",
            )
        )
        self.module.write_iteration(
            self.module.build_iteration_payload(
                task_id="task-1",
                hypothesis="Second.",
                action="Did second.",
                metric="m",
                status="checks_failed",
                evidence=[],
                touched_files=[],
                next_focus="New focus.",
                rollback_reason="",
                actor="delivery",
                created_at="2026-04-20T10:00:00Z",
            )
        )

        summary = self.module.build_feedback_summary(self.temp_root / ".hq")

        self.assertEqual(len(summary["open_next_steps"]), 1)
        self.assertEqual(summary["open_next_steps"][0]["next_focus"], "New focus.")

    def _write(self, *, status, created_at, task_id="task-1", parent_id=""):
        self.module.write_iteration(
            self.module.build_iteration_payload(
                task_id=task_id,
                hypothesis="h",
                action="a",
                metric="m",
                status=status,
                evidence=[],
                touched_files=[],
                next_focus="n",
                rollback_reason="Rolled back." if status == "rolled_back" else "",
                actor="delivery",
                parent_id=parent_id,
                created_at=created_at,
            )
        )

    def test_review_signal_immediate_on_adverse_outcome(self):
        self._write(status="done", created_at="2026-04-20T09:00:00Z")
        self._write(status="checks_failed", created_at="2026-04-20T10:00:00Z")

        signal = self.module.build_review_signal(self.temp_root / ".hq")

        self.assertTrue(signal["review_due"])
        self.assertIn("adverse_outcomes:checks_failed", signal["reason"])
        self.assertEqual(signal["adverse_since_review"], 1)

    def test_review_signal_cadence_after_batch_of_successes(self):
        for hour in range(5):
            self._write(status="done", created_at=f"2026-04-20T0{hour}:00:00Z")

        os.environ["HQ_FEEDBACK_REVIEW_CADENCE"] = "5"
        try:
            signal = self.module.build_review_signal(self.temp_root / ".hq")
        finally:
            os.environ.pop("HQ_FEEDBACK_REVIEW_CADENCE", None)

        self.assertTrue(signal["review_due"])
        self.assertTrue(signal["reason"].startswith("cadence:"))
        self.assertEqual(signal["successful_since_review"], 5)

    def test_review_signal_not_due_below_cadence(self):
        for hour in range(3):
            self._write(status="done", created_at=f"2026-04-20T0{hour}:00:00Z")

        signal = self.module.build_review_signal(self.temp_root / ".hq")

        self.assertFalse(signal["review_due"])
        self.assertEqual(signal["reason"], "")

    def test_mark_reviewed_resets_cadence(self):
        self._write(status="checks_failed", created_at="2026-04-20T09:00:00Z")
        self.assertTrue(self.module.build_review_signal(self.temp_root / ".hq")["review_due"])

        self.module.mark_reviewed(self.temp_root / ".hq")

        after = self.module.build_review_signal(self.temp_root / ".hq")
        self.assertFalse(after["review_due"])
        self.assertEqual(after["adverse_since_review"], 0)

        self._write(status="technical_error", created_at="2026-04-20T11:00:00Z")
        self.assertTrue(self.module.build_review_signal(self.temp_root / ".hq")["review_due"])

    def test_invalid_metric_direction_rejected(self):
        with self.assertRaises(ValueError):
            self.module.build_iteration_payload(
                task_id="task-1",
                hypothesis="x",
                action="y",
                metric="m",
                status="done",
                evidence=[],
                touched_files=[],
                next_focus="z",
                rollback_reason="",
                actor="delivery",
                metric_direction="sideways",
            )


if __name__ == "__main__":
    unittest.main()
