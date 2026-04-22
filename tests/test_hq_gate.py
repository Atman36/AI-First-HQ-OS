from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "hq_gate.py"


def load_module():
    spec = importlib.util.spec_from_file_location("hq_gate_test_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class HqGateTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_dir.name)
        self.module = load_module()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_build_commands_includes_private_prompt_lint_when_prompts_exist(self):
        self.module.REPO_ROOT = self.temp_root
        (self.temp_root / ".hq" / "prompts").mkdir(parents=True, exist_ok=True)

        commands = self.module.build_commands()

        self.assertEqual(
            [name for name, _ in commands],
            [
                "public-safety",
                "instruction-lint",
                "private-prompt-lint",
                "tests",
                "control-plane",
            ],
        )

    def test_main_stops_on_first_failure(self):
        self.module.REPO_ROOT = self.temp_root
        runner = Mock(side_effect=[Mock(returncode=0), Mock(returncode=2)])

        with patch.object(self.module.subprocess, "run", runner):
            exit_code = self.module.main()

        self.assertEqual(exit_code, 2)
        self.assertEqual(runner.call_count, 2)
        self.assertEqual(runner.call_args_list[0].args[0][1], "scripts/hq_public_safety.py")
        self.assertEqual(runner.call_args_list[1].args[0][1], "scripts/hq_instruction_lint.py")


if __name__ == "__main__":
    unittest.main()
