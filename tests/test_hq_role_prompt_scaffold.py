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

