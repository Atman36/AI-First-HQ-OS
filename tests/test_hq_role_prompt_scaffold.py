import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "hq_role_prompt_scaffold.py"


def load_module():
    spec = importlib.util.spec_from_file_location("hq_role_prompt_scaffold_test_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class HqRolePromptScaffoldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()
        cls.repo_root = SCRIPT_PATH.parents[1]

    def test_generated_prompts_match_repository_files(self):
        for path, expected in self.module.render_all().items():
            with self.subTest(path=path.relative_to(self.repo_root).as_posix()):
                actual = path.read_text(encoding="utf-8")
                self.assertEqual(actual, expected)

    def test_generated_prompts_include_shared_note(self):
        for role_id in self.module.ROLE_PROMPTS:
            with self.subTest(role_id=role_id):
                rendered = self.module.render_prompt(role_id)
                self.assertIn("Generated from the shared HQ role prompt skeleton", rendered)

    def test_generated_prompts_include_quick_start_and_split_read_paths(self):
        for role_id in self.module.ROLE_PROMPTS:
            with self.subTest(role_id=role_id):
                rendered = self.module.render_prompt(role_id)
                self.assertIn("First command: run `python3 scripts/hq_control_plane.py status`.", rendered)
                self.assertIn("## Quick Start", rendered)
                self.assertIn("## Read First", rendered)
                self.assertIn("### Always Read", rendered)
                self.assertIn("### Read When Needed", rendered)

    def test_generated_prompts_drop_root_level_execution_duplicates(self):
        duplicated_rules = (
            "Default to best-effort execution.",
            "If a blocker question is required, ask one bundled question at most.",
            "Work long by default on the current slice.",
            "Do not return control to the founder only because a delegated slice is still running.",
        )

        for role_id in self.module.ROLE_PROMPTS:
            with self.subTest(role_id=role_id):
                rendered = self.module.render_prompt(role_id)
                for duplicated_rule in duplicated_rules:
                    self.assertNotIn(duplicated_rule, rendered)
