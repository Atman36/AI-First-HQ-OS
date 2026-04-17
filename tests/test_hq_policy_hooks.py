import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "hq_policy_hooks.py"
SCHEMA_FIXTURES = Path(__file__).resolve().parents[1] / "05 AI Control Plane" / "schemas"


def load_module(temp_root: Path):
    os.environ["HQ_POLICY_HOOKS_REPO_ROOT"] = str(temp_root)
    spec = importlib.util.spec_from_file_location("hq_policy_hooks_test_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class HqPolicyHooksTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_dir.name)
        (self.temp_root / "05 AI Control Plane" / "schemas").mkdir(parents=True, exist_ok=True)
        for schema_path in SCHEMA_FIXTURES.glob("*.json"):
            target = self.temp_root / "05 AI Control Plane" / "schemas" / schema_path.name
            target.write_text(schema_path.read_text(encoding="utf-8"), encoding="utf-8")
        self.module = load_module(self.temp_root)

    def tearDown(self):
        os.environ.pop("HQ_POLICY_HOOKS_REPO_ROOT", None)
        self.temp_dir.cleanup()

    def write_json(self, relative_path: str, payload: dict) -> Path:
        path = self.temp_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def write_text(self, relative_path: str, content: str) -> Path:
        path = self.temp_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_policy_check_returns_strictest_matching_decision(self):
        policy_path = self.write_json(
            "runtime/policy.json",
            {
                "version": 1,
                "default_decision": "allow",
                "rules": [
                    {
                        "id": "tracked-write-review",
                        "action_prefix": ["hq", "tracked", "write"],
                        "decision": "allow_with_review",
                        "match": [["hq", "tracked", "write"]],
                    },
                    {
                        "id": "control-plane-block",
                        "action_prefix": ["hq", "tracked", "write"],
                        "path_prefixes": ["05 AI Control Plane/"],
                        "decision": "block",
                        "match": ["hq tracked write"],
                    },
                ],
            },
        )

        policy = self.module.load_policy(policy_path)
        result = self.module.evaluate_policy(
            policy,
            {
                "action": ["hq", "tracked", "write"],
                "path": "05 AI Control Plane/operating-policies.json",
                "risk_tier": "medium",
                "autonomy_tier": "A2",
            },
        )

        self.assertEqual(result["decision"], "block")
        self.assertEqual(len(result["matchedRules"]), 2)
        self.assertEqual(result["matchedRules"][0]["id"], "tracked-write-review")
        self.assertEqual(result["matchedRules"][1]["id"], "control-plane-block")

    def test_policy_validation_rejects_bad_example(self):
        policy_path = self.write_json(
            "runtime/policy-invalid.json",
            {
                "version": 1,
                "default_decision": "allow",
                "rules": [
                    {
                        "id": "bad-example",
                        "action_prefix": ["hq", "runtime", "write"],
                        "decision": "allow",
                        "match": ["hq tracked write"],
                    }
                ],
            },
        )

        with self.assertRaises(ValueError):
            self.module.load_policy(policy_path)

    def test_emit_runs_matching_hooks(self):
        output_path = self.temp_root / "hook-output.json"
        script_path = self.write_text(
            "scripts/capture_hook.py",
            """import json\nimport sys\nfrom pathlib import Path\npayload = json.loads(sys.stdin.read())\nPath(sys.argv[1]).write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')\n""",
        )
        hooks_path = self.write_json(
            "runtime/hooks.json",
            {
                "version": 1,
                "hooks": [
                    {
                        "id": "capture-pre-action",
                        "event": "pre_action",
                        "action_prefixes": [["hq", "tracked", "write"]],
                        "decisions": ["allow_with_review"],
                        "command": [sys.executable, str(script_path), str(output_path)],
                    }
                ],
            },
        )

        parser = self.module.build_parser()
        args = parser.parse_args(
            [
                "emit",
                "--hooks-file",
                str(hooks_path),
                "--event",
                "pre_action",
                "--payload",
                json.dumps(
                    {
                        "action": ["hq", "tracked", "write"],
                        "decision": "allow_with_review",
                        "status": "running",
                    }
                ),
            ]
        )

        exit_code = args.func(args)

        self.assertEqual(exit_code, 0)
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["event"], "pre_action")
        self.assertEqual(payload["action"], ["hq", "tracked", "write"])
        self.assertEqual(payload["decision"], "allow_with_review")


if __name__ == "__main__":
    unittest.main()
