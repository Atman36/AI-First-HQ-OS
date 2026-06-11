import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import subprocess


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
            self.write_file("CLAUDE.md", "Use `AGENTS.md` as the source of truth.\n"),
            self.write_file("scripts/tool.py", "print('ok')\n"),
            self.write_file("agents/delivery/AGENTS.md", "# Delivery\n"),
            self.write_file("skills/ceo/SKILL.md", "---\nname: ceo\ndescription: CEO skill.\n---\n"),
            self.write_file("skills/ceo/agents/openai.yaml", "interface:\n  display_name: \"CEO\"\n"),
            self.write_file("05 AI Control Plane/schemas/active-work.schema.json", "{}\n"),
        ]

        violations = self.module.find_violations(self.temp_root, tracked_files)

        self.assertEqual(violations, [])

    def test_live_operating_state_path_fails(self):
        tracked_files = [
            self.write_file("03 Notes/Decisions.md", "# Decisions\n"),
            self.write_file("04 Projects/Founder Revenue Sprint.md", "# Project\n"),
            self.write_file("now.md", "# Now\n"),
        ]

        violations = self.module.find_violations(self.temp_root, tracked_files)

        self.assertEqual(len(violations), 3)
        self.assertTrue(all("blocked live operating state" in item for item in violations))

    def test_non_allowlisted_public_path_fails(self):
        tracked_files = [
            self.write_file("01 Operating System/How To Operate HQ.md", "# Doc\n"),
            self.write_file("05 AI Control Plane/active-work.json", "{}\n"),
            self.write_file("90 Templates/Task Template.md", "# Template\n"),
        ]

        violations = self.module.find_violations(self.temp_root, tracked_files)

        self.assertEqual(len(violations), 3)
        self.assertTrue(all("public GitHub allowlist" in item for item in violations))

    def test_blocked_private_runtime_path_fails(self):
        tracked_files = [
            self.write_file(".hq/telemetry/2026-04-16.jsonl", "{\"event\":\"test\"}\n"),
        ]

        violations = self.module.find_violations(self.temp_root, tracked_files)

        self.assertEqual(len(violations), 1)
        self.assertIn(".hq/telemetry/2026-04-16.jsonl", violations[0])

    def test_project_brief_under_docs_projects_fails(self):
        tracked_files = [
            self.write_file("docs/projects/example-brief.md", "# Example Brief\n"),
        ]

        violations = self.module.find_violations(self.temp_root, tracked_files)

        self.assertEqual(len(violations), 1)
        self.assertIn("blocked private path", violations[0])

    def test_blocked_sensitive_extension_fails(self):
        tracked_files = [
            self.write_file("exports/customers.csv", "name,email\n"),
        ]

        violations = self.module.find_violations(self.temp_root, tracked_files)

        self.assertEqual(len(violations), 2)
        self.assertTrue(any("blocked private path" in item for item in violations))
        self.assertTrue(any("blocked sensitive local artifact type" in item for item in violations))

    def test_obvious_secret_fails(self):
        simulated_secret = "sk-" + "1234567890abcdefghijklmnop"
        tracked_files = [
            self.write_file("scripts/example.py", f"token = '{simulated_secret}'\n"),
        ]

        violations = self.module.find_violations(self.temp_root, tracked_files)

        self.assertEqual(len(violations), 1)
        self.assertIn("potential openai secret", violations[0])


    def test_main_skips_without_git_metadata(self):
        import contextlib
        import io

        self.module.REPO_ROOT = self.temp_root

        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            exit_code = self.module.main()

        self.assertEqual(exit_code, 0)
        self.assertIn("public_safety=skipped_no_git_metadata", stdout.getvalue())

    def test_load_tracked_files_uses_check_true_and_parses_output(self):
        with patch.object(self.module.subprocess, "run") as mock_run:
            mock_run.return_value = Mock(stdout=b"README.md\0scripts/tool.py\0", returncode=0)

            tracked_files = self.module.load_tracked_files(self.temp_root)

        self.assertEqual(tracked_files, [Path("README.md"), Path("scripts/tool.py")])
        mock_run.assert_called_once_with(
            ["git", "-C", str(self.temp_root), "ls-files", "-z"],
            check=True,
            capture_output=True,
        )

    def test_load_tracked_files_wraps_git_failure(self):
        with patch.object(self.module.subprocess, "run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=128,
                cmd=["git", "-C", str(self.temp_root), "ls-files", "-z"],
                stderr=b"fatal: not a git repository",
            )

            with self.assertRaisesRegex(RuntimeError, r"git ls-files failed: fatal: not a git repository"):
                self.module.load_tracked_files(self.temp_root)

        mock_run.assert_called_once_with(
            ["git", "-C", str(self.temp_root), "ls-files", "-z"],
            check=True,
            capture_output=True,
        )

    def test_load_tracked_files_handles_non_utf8_stderr(self):
        with patch.object(self.module.subprocess, "run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=128,
                cmd=["git", "-C", str(self.temp_root), "ls-files", "-z"],
                stderr=b"fatal: bad byte \xff",
            )

            with self.assertRaisesRegex(RuntimeError, r"git ls-files failed: fatal: bad byte"):
                self.module.load_tracked_files(self.temp_root)
