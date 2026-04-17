import importlib.util
import json
import os
import subprocess
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "hq_eval.py"
REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_FIXTURES = Path(__file__).resolve().parents[1] / "05 AI Control Plane" / "schemas"


def load_module(temp_root: Path):
    os.environ["HQ_EVAL_REPO_ROOT"] = str(temp_root)
    os.environ["HQ_RUNTIME_PRIVATE_ROOT"] = str(temp_root / ".hq")
    os.environ["HQ_TELEMETRY_REPO_ROOT"] = str(temp_root)
    sys.modules.pop("hq_io", None)
    sys.modules.pop("hq_telemetry", None)
    sys.modules.pop("hq_telemetry_store", None)
    sys.modules.pop("hq_telemetry_review", None)
    spec = importlib.util.spec_from_file_location("hq_eval_test_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class HqEvalTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_dir.name)
        (self.temp_root / "05 AI Control Plane" / "schemas").mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            SCHEMA_FIXTURES,
            self.temp_root / "05 AI Control Plane" / "schemas",
            dirs_exist_ok=True,
        )
        self.write_workflow_registry()
        self.module = load_module(self.temp_root)

    def tearDown(self):
        os.environ.pop("HQ_EVAL_REPO_ROOT", None)
        os.environ.pop("HQ_RUNTIME_PRIVATE_ROOT", None)
        os.environ.pop("HQ_TELEMETRY_REPO_ROOT", None)
        self.temp_dir.cleanup()

    def write_workflow_registry(self) -> None:
        workflow_registry = {
            "version": 1,
            "updated_at": "2026-04-17",
            "board_columns": [{"id": "done", "title": "Done"}],
            "telemetry": {
                "event_types": ["review", "eval"],
                "statuses": ["reviewed"],
                "event_sets": {"eval": ["review", "eval"]},
                "status_sets": {},
            },
            "workflows": [],
        }
        (self.temp_root / "05 AI Control Plane" / "workflow-registry.json").write_text(
            json.dumps(workflow_registry, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def write_dataset(self, payload: dict) -> Path:
        path = self.temp_root / "eval-dataset.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def test_validate_accepts_valid_dataset(self):
        dataset_path = self.write_dataset(
            {
                "version": 1,
                "name": "smoke",
                "cases": [
                    {
                        "id": "hello",
                        "kind": "command",
                        "command": [
                            sys.executable,
                            "-c",
                            "print('hello')",
                        ],
                        "expectations": {
                            "exit_code": 0,
                            "stdout_contains": ["hello"],
                        },
                    }
                ],
            }
        )
        parser = self.module.build_parser()
        args = parser.parse_args(["validate", "--dataset", str(dataset_path)])
        exit_code = args.func(args)
        self.assertEqual(exit_code, 0)

    def test_run_returns_nonzero_when_case_fails(self):
        dataset_path = self.write_dataset(
            {
                "version": 1,
                "name": "failing-smoke",
                "cases": [
                    {
                        "id": "bad-exit",
                        "kind": "command",
                        "command": [
                            sys.executable,
                            "-c",
                            "import sys; sys.exit(1)",
                        ],
                        "expectations": {
                            "exit_code": 0,
                        },
                    }
                ],
            }
        )
        parser = self.module.build_parser()
        args = parser.parse_args(["run", "--dataset", str(dataset_path)])
        exit_code = args.func(args)
        self.assertEqual(exit_code, 1)

    def test_run_writes_valid_report(self):
        dataset_path = self.write_dataset(
            {
                "version": 1,
                "name": "passing-smoke",
                "telemetry": {
                    "task_id": "eval-passing-smoke",
                    "actor": "ai_operations_lead",
                    "role": "AI Operations Lead",
                    "workflow": "eval-foundation",
                },
                "cases": [
                    {
                        "id": "stdout-and-stderr",
                        "kind": "command",
                        "command": [
                            sys.executable,
                            "-c",
                            "import sys; print('ready'); sys.stderr.write('warn\\n')",
                        ],
                        "expectations": {
                            "exit_code": 0,
                            "stdout_contains": ["ready"],
                            "stderr_contains": ["warn"],
                            "stdout_not_contains": ["error"],
                        },
                    }
                ],
            }
        )
        output_path = self.temp_root / ".hq" / "evals" / "report.json"
        parser = self.module.build_parser()
        args = parser.parse_args(
            [
                "run",
                "--dataset",
                str(dataset_path),
                "--write-report",
                str(output_path),
            ]
        )
        exit_code = args.func(args)
        self.assertEqual(exit_code, 0)
        report = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(report["summary"]["passed"], 1)
        self.assertEqual(report["cases"][0]["status"], "passed")

    def test_run_resolves_relative_case_cwd_from_dataset_directory(self):
        nested_dir = self.temp_root / "fixtures" / "eval-datasets"
        nested_dir.mkdir(parents=True, exist_ok=True)
        marker_dir = self.temp_root / "workspace"
        marker_dir.mkdir(parents=True, exist_ok=True)
        (marker_dir / "marker.txt").write_text("ok\n", encoding="utf-8")
        dataset_path = nested_dir / "relative-cwd.json"
        dataset_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "name": "relative-cwd",
                    "cases": [
                        {
                            "id": "read-marker",
                            "kind": "command",
                            "cwd": "../../workspace",
                            "command": [
                                sys.executable,
                                "-c",
                                "from pathlib import Path; print(Path('marker.txt').read_text().strip())",
                            ],
                            "expectations": {
                                "exit_code": 0,
                                "stdout_contains": ["ok"],
                            },
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
        args = parser.parse_args(["run", "--dataset", str(dataset_path)])

        exit_code = args.func(args)

        self.assertEqual(exit_code, 0)

    def test_run_writes_default_report_layout_and_eval_telemetry(self):
        dataset_path = self.write_dataset(
            {
                "version": 1,
                "name": "default-report-smoke",
                "telemetry": {
                    "task_id": "eval-default-report-smoke",
                    "actor": "ai_operations_lead",
                    "role": "AI Operations Lead",
                    "workflow": "eval-foundation",
                    "metadata": {"suite": "foundation"},
                },
                "cases": [
                    {
                        "id": "hello",
                        "kind": "command",
                        "command": [
                            sys.executable,
                            "-c",
                            "print('hello')",
                        ],
                        "expectations": {
                            "exit_code": 0,
                            "stdout_contains": ["hello"],
                        },
                    }
                ],
            }
        )
        parser = self.module.build_parser()
        args = parser.parse_args(["run", "--dataset", str(dataset_path)])

        exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        latest_report_path = self.temp_root / ".hq" / "evals" / "default-report-smoke" / "LATEST.json"
        self.assertTrue(latest_report_path.exists())
        latest_report = json.loads(latest_report_path.read_text(encoding="utf-8"))
        self.assertEqual(latest_report["dataset_name"], "default-report-smoke")
        self.assertEqual(latest_report["status"], "passed")
        self.assertTrue(latest_report["report_path"].endswith(".json"))
        stored_report_path = Path(latest_report["report_path"])
        self.assertTrue(stored_report_path.exists())
        self.assertEqual(stored_report_path.parent.name, "runs")

        telemetry_files = sorted((self.temp_root / ".hq" / "telemetry").glob("**/*.jsonl"))
        self.assertEqual(len(telemetry_files), 1)
        payloads = [
            json.loads(line)
            for line in telemetry_files[0].read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(len(payloads), 1)
        payload = payloads[0]
        self.assertEqual(payload["event_type"], "eval")
        self.assertEqual(payload["status"], "reviewed")
        self.assertEqual(payload["task_id"], "eval-default-report-smoke")
        self.assertEqual(payload["run_id"], latest_report["run_id"])
        self.assertEqual(payload["metadata"]["outcome"], "passed")
        self.assertEqual(payload["metadata"]["dataset_name"], "default-report-smoke")
        self.assertEqual(payload["metadata"]["suite"], "foundation")

    def test_repo_eval_datasets_validate_against_live_schema(self):
        dataset_paths = sorted((REPO_ROOT / "tests" / "fixtures" / "eval-datasets").glob("*.json"))
        self.assertEqual(len(dataset_paths), 3)
        for dataset_path in dataset_paths:
            completed = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "validate", "--dataset", str(dataset_path)],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
