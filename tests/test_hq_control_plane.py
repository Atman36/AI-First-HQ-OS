import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "hq_control_plane.py"


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
        (self.temp_root / "02 Planning").mkdir(parents=True, exist_ok=True)
        (self.temp_root / "03 Notes").mkdir(parents=True, exist_ok=True)
        (self.temp_root / "04 Projects").mkdir(parents=True, exist_ok=True)
        (self.temp_root / "scripts").mkdir(parents=True, exist_ok=True)
        (self.temp_root / "tests").mkdir(parents=True, exist_ok=True)
        (self.temp_root / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
        (self.temp_root / "03 Notes" / "Decisions.md").write_text("# Decisions\n", encoding="utf-8")
        (self.temp_root / "03 Notes" / "Open Decisions.md").write_text("# Open Decisions\n", encoding="utf-8")
        (self.temp_root / "04 Projects" / "HQ Bootstrap.md").write_text("# HQ Bootstrap\n", encoding="utf-8")
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
                    "roles": [
                        {"id": "ceo", "role_type": "human", "mission": "Approve high-risk work."},
                        {"id": "coo", "role_type": "ai", "mission": "Route work."},
                        {"id": "delivery", "role_type": "ai", "mission": "Execute work."},
                        {"id": "documentation", "role_type": "ai", "mission": "Sync truth."},
                        {"id": "governor", "role_type": "ai", "mission": "Enforce policy."},
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
                    "autonomy_tiers": [{"id": "A1"}, {"id": "A2"}, {"id": "A3"}, {"id": "A4"}],
                    "risk_tiers": [{"id": "low"}, {"id": "medium"}, {"id": "high"}],
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
                    "workflows": [
                        {
                            "id": "intake-to-execution",
                            "required_task_fields": [
                                "id",
                                "title",
                                "column",
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
                    "primary_metrics": [
                        {"id": "autonomous_completion_rate", "definition": "x"},
                        {"id": "human_escalation_rate", "definition": "x"},
                        {"id": "decision_latency_hours", "definition": "x"},
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
                    "version": 1,
                    "updated_at": "2026-04-15",
                    "operating_mode": "stage-1",
                    "objective": {
                        "id": "obj-1",
                        "title": "Run one governed loop",
                        "success_criteria": ["One task completes through the control plane."],
                    },
                    "tasks": [
                        {
                            "id": "task-1",
                            "title": "Run first loop",
                            "column": "this_week",
                            "owner": "coo",
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


if __name__ == "__main__":
    unittest.main()
