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

    def test_key_role_skills_expose_openai_interface_metadata(self):
        repo_root = Path(__file__).resolve().parents[1]
        expectations = {
            "ai-operations-lead": "AI Operations Lead",
            "governor": "Governor",
            "delivery": "Delivery",
        }

        for role_id, display_name in expectations.items():
            with self.subTest(role_id=role_id):
                metadata_path = repo_root / "skills" / role_id / "agents" / "openai.yaml"
                self.assertTrue(metadata_path.exists(), metadata_path)
                content = metadata_path.read_text(encoding="utf-8")
                self.assertIn(f'display_name: "{display_name}"', content)
                self.assertIn('default_prompt:', content)

    def test_ai_ops_short_alias_skill_exists(self):
        repo_root = Path(__file__).resolve().parents[1]
        skill_path = repo_root / "skills" / "ai-ops-lead" / "SKILL.md"
        metadata_path = repo_root / "skills" / "ai-ops-lead" / "agents" / "openai.yaml"

        self.assertTrue(skill_path.exists(), skill_path)
        self.assertTrue(metadata_path.exists(), metadata_path)
        self.assertIn("Use `$ai-operations-lead`", skill_path.read_text(encoding="utf-8"))
        self.assertIn('display_name: "AI Ops Lead"', metadata_path.read_text(encoding="utf-8"))

    def test_core_hq_operating_skills_exist_with_interface_metadata(self):
        repo_root = Path(__file__).resolve().parents[1]
        expectations = {
            "hq-task-lifecycle": "HQ Task Lifecycle",
            "hq-context-aware-triage": "HQ Triage",
            "hq-spec-handoff-writer": "HQ Spec/Handoff",
            "hq-weekly-operating-review": "HQ Weekly Review",
            "hq-publication-safety": "HQ Publication Safety",
            "hq-revenue-sprint-ops": "HQ Revenue Sprint",
        }

        for skill_id, display_name in expectations.items():
            with self.subTest(skill_id=skill_id):
                skill_path = repo_root / "skills" / skill_id / "SKILL.md"
                metadata_path = repo_root / "skills" / skill_id / "agents" / "openai.yaml"

                self.assertTrue(skill_path.exists(), skill_path)
                self.assertTrue(metadata_path.exists(), metadata_path)
                skill_content = skill_path.read_text(encoding="utf-8")
                metadata_content = metadata_path.read_text(encoding="utf-8")
                self.assertIn(f"name: {skill_id}", skill_content)
                self.assertIn("description:", skill_content)
                self.assertIn(f'display_name: "{display_name}"', metadata_content)
                self.assertIn("default_prompt:", metadata_content)

    def test_core_hq_operating_skills_reference_public_safe_control_plane_boundaries(self):
        repo_root = Path(__file__).resolve().parents[1]
        skill_markers = {
            "hq-task-lifecycle": [
                "05 AI Control Plane/active-work.json",
                "python3 scripts/hq_control_plane.py validate",
            ],
            "hq-context-aware-triage": [
                "risk tier",
                "autonomy tier",
                "primary update file",
            ],
            "hq-spec-handoff-writer": [
                ".hq/specs/<task>/LATEST.md",
                ".hq/handoffs/<task>/LATEST.md",
            ],
            "hq-weekly-operating-review": [
                "python3 scripts/hq_control_plane.py status",
                "Do not hand-edit generated artifacts",
            ],
            "hq-publication-safety": [
                "git status --short",
                "Technical documentation for internal operation should stay local",
            ],
            "hq-revenue-sprint-ops": [
                "Founder Revenue Sprint.md",
                "Require founder approval before any outbound",
            ],
        }

        for skill_id, markers in skill_markers.items():
            with self.subTest(skill_id=skill_id):
                content = (repo_root / "skills" / skill_id / "SKILL.md").read_text(encoding="utf-8")
                for marker in markers:
                    self.assertIn(marker, content)

    def test_new_wave_skills_exist_with_interface_metadata(self):
        repo_root = Path(__file__).resolve().parents[1]
        expectations = {
            "hq-research-router": "HQ Research Router",
            "hq-telemetry-event-logger": "HQ Telemetry Logger",
        }

        for skill_id, display_name in expectations.items():
            with self.subTest(skill_id=skill_id):
                skill_path = repo_root / "skills" / skill_id / "SKILL.md"
                metadata_path = repo_root / "skills" / skill_id / "agents" / "openai.yaml"

                self.assertTrue(skill_path.exists(), skill_path)
                self.assertTrue(metadata_path.exists(), metadata_path)
                skill_content = skill_path.read_text(encoding="utf-8")
                metadata_content = metadata_path.read_text(encoding="utf-8")
                self.assertIn(f"name: {skill_id}", skill_content)
                self.assertIn("description:", skill_content)
                self.assertIn(f'display_name: "{display_name}"', metadata_content)
                self.assertIn("default_prompt:", metadata_content)

    def test_new_wave_skills_reference_key_boundaries(self):
        repo_root = Path(__file__).resolve().parents[1]
        skill_markers = {
            "hq-research-router": [
                "reports/DEEP_RESEARCH_INDEX.md",
                "05 AI Control Plane/active-work.json",
                "python3 scripts/hq_control_plane.py validate",
                ".hq/specs/",
            ],
            "hq-telemetry-event-logger": [
                ".hq/telemetry/",
                "05 AI Control Plane/metrics-registry.json",
                "never add it to git",
            ],
        }

        for skill_id, markers in skill_markers.items():
            with self.subTest(skill_id=skill_id):
                content = (repo_root / "skills" / skill_id / "SKILL.md").read_text(encoding="utf-8")
                for marker in markers:
                    self.assertIn(marker, content)

    def test_publication_safety_skill_references_hook_layer(self):
        repo_root = Path(__file__).resolve().parents[1]
        content = (repo_root / "skills" / "hq-publication-safety" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("scripts/hooks/pre-commit", content)
        self.assertIn("scripts/install_hq_hooks.sh", content)
        self.assertIn("hook-first", content)

    def test_hook_scripts_exist_and_are_executable(self):
        import stat
        repo_root = Path(__file__).resolve().parents[1]
        hook_template = repo_root / "scripts" / "hooks" / "pre-commit"
        installer = repo_root / "scripts" / "install_hq_hooks.sh"

        self.assertTrue(hook_template.exists(), hook_template)
        self.assertTrue(installer.exists(), installer)
        self.assertTrue(hook_template.stat().st_mode & stat.S_IXUSR, "pre-commit hook not executable")
        self.assertTrue(installer.stat().st_mode & stat.S_IXUSR, "install_hq_hooks.sh not executable")

    def test_hook_template_calls_public_safety_script(self):
        repo_root = Path(__file__).resolve().parents[1]
        content = (repo_root / "scripts" / "hooks" / "pre-commit").read_text(encoding="utf-8")
        self.assertIn("hq_public_safety.py", content)
        self.assertIn("exit 1", content)
