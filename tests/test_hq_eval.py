import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "hq_eval.py"
SCHEMA_FIXTURES = Path(__file__).resolve().parents[1] / "05 AI Control Plane" / "schemas"


def load_module(temp_root: Path):
    os.environ["HQ_EVAL_REPO_ROOT"] = str(temp_root)
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
        self.module = load_module(self.temp_root)

    def tearDown(self):
        os.environ.pop("HQ_EVAL_REPO_ROOT", None)
        self.temp_dir.cleanup()

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


if __name__ == "__main__":
    unittest.main()
