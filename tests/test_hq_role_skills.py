from pathlib import Path
import unittest


class HqRoleSkillTests(unittest.TestCase):
    def test_key_role_skill_wrappers_exist_and_point_at_role_prompts(self):
        repo_root = Path(__file__).resolve().parents[1]
        expectations = {
            "ai-operations-lead": "agents/ai-operations-lead/AGENTS.md",
            "governor": "agents/governor/AGENTS.md",
            "delivery": "agents/delivery/AGENTS.md",
        }

        for role_id, agent_prompt in expectations.items():
            with self.subTest(role_id=role_id):
                skill_path = repo_root / "skills" / role_id / "SKILL.md"
                self.assertTrue(skill_path.exists(), skill_path)
                content = skill_path.read_text(encoding="utf-8")
                self.assertIn(f"name: {role_id}", content)
                self.assertIn(agent_prompt, content)
                self.assertIn("Use this skill as a thin", content)
