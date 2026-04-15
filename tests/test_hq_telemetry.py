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
                "coo",
                "--role",
                "COO",
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
        self.assertEqual(payload["agent"], "coo")
        self.assertEqual(payload["task_id"], "run-first-governed-loop")
        self.assertEqual(payload["metadata"], {"phase": "triage"})
        self.assertEqual(payload["touched_files"], ["05 AI Control Plane/active-work.json"])


if __name__ == "__main__":
    unittest.main()
