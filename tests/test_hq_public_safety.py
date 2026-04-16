import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "hq_public_safety.py"


def load_module():
    spec = importlib.util.spec_from_file_location("hq_public_safety_test_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class HqPublicSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_dir.name)
        self.module = load_module()

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_file(self, relative_path: str, content: str) -> Path:
        path = self.temp_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return Path(relative_path)

    def test_public_safe_files_pass(self):
        tracked_files = [
            self.write_file("README.md", "# AI-First HQ OS\n"),
            self.write_file("scripts/tool.py", "print('ok')\n"),
        ]

        violations = self.module.find_violations(self.temp_root, tracked_files)

        self.assertEqual(violations, [])

    def test_blocked_private_runtime_path_fails(self):
        tracked_files = [
            self.write_file(".hq/telemetry/2026-04-16.jsonl", "{\"event\":\"test\"}\n"),
        ]

        violations = self.module.find_violations(self.temp_root, tracked_files)

        self.assertEqual(len(violations), 1)
        self.assertIn(".hq/telemetry/2026-04-16.jsonl", violations[0])

    def test_blocked_sensitive_extension_fails(self):
        tracked_files = [
            self.write_file("exports/customers.csv", "name,email\n"),
        ]

        violations = self.module.find_violations(self.temp_root, tracked_files)

        self.assertEqual(len(violations), 2)
        self.assertTrue(any("blocked private path" in item for item in violations))
        self.assertTrue(any("blocked sensitive local artifact type" in item for item in violations))

    def test_obvious_secret_fails(self):
        tracked_files = [
            self.write_file("docs/example.md", "token=sk-1234567890abcdefghijklmnop\n"),
        ]

        violations = self.module.find_violations(self.temp_root, tracked_files)

        self.assertEqual(len(violations), 1)
        self.assertIn("potential openai secret", violations[0])
