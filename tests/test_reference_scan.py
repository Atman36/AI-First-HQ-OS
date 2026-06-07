from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "hq_reference_scan.py"


def load_module():
    spec = importlib.util.spec_from_file_location("hq_reference_scan_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ref = load_module()


class IdentifierTokenTests(unittest.TestCase):
    def test_strips_main_suffix(self):
        tokens = ref._identifier_tokens("exampleproj-main")
        self.assertIn("exampleproj-main", tokens)
        self.assertIn("exampleproj", tokens)

    def test_short_tokens_excluded(self):
        # Stem shorter than 4 chars is not added on its own.
        tokens = ref._identifier_tokens("abc-main")
        self.assertNotIn("abc", tokens)

    def test_discover_and_identifiers_from_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "alpha-main").mkdir()
            (base / "beta-tool-main").mkdir()
            (base / "afile.txt").write_text("x", encoding="utf-8")
            projects = ref.discover_reference_projects(base)
            self.assertEqual([p.name for p in projects], ["alpha-main", "beta-tool-main"])
            tokens = ref.reference_identifiers(base)
            self.assertIn("alpha-main", tokens)
            self.assertIn("alpha", tokens)
            self.assertIn("beta-tool", tokens)


class ScanTextTests(unittest.TestCase):
    def test_whole_word_match_only(self):
        tokens = {"alpha"}
        self.assertEqual(ref.scan_text_for_identifiers("uses alpha here", tokens), ["alpha"])
        self.assertEqual(ref.scan_text_for_identifiers("alphabetical", tokens), [])

    def test_generic_descriptor_passes(self):
        tokens = {"alpha", "beta-tool"}
        text = "a relationship-and-tuple authorization style with generic descriptors"
        self.assertEqual(ref.scan_text_for_identifiers(text, tokens), [])


class AnalyzeTests(unittest.TestCase):
    def test_missing_and_empty_projects_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            populated = base / "alpha-main"
            populated.mkdir()
            (populated / "readme.md").write_text("x", encoding="utf-8")
            (base / "empty-main").mkdir()
            result = ref.analyze_reference_projects(base)
            self.assertIn("alpha-main", result["analyzed"])
            reasons = {item["project"]: item["reason"] for item in result["not_analyzed"]}
            self.assertEqual(reasons.get("empty-main"), "empty")

    def test_missing_base_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "does-not-exist"
            result = ref.analyze_reference_projects(base)
            self.assertTrue(result["base_missing"])


class ScanTrackedFilesTests(unittest.TestCase):
    def _init_repo(self, tmp: Path) -> None:
        import subprocess

        subprocess.run(["git", "-C", str(tmp), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(tmp), "config", "user.email", "t@example.com"], check=True)
        subprocess.run(["git", "-C", str(tmp), "config", "user.name", "t"], check=True)

    def test_identifier_bearing_tracked_output_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_repo(root)
            (root / "doc.md").write_text("we copied ideas from alpha-main here", encoding="utf-8")
            import subprocess

            subprocess.run(["git", "-C", str(root), "add", "doc.md"], check=True)
            violations = ref.scan_tracked_files(root, identifiers={"alpha-main", "alpha"})
            self.assertTrue(violations)
            self.assertIn("doc.md", violations[0])

    def test_generic_descriptor_output_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_repo(root)
            (root / "doc.md").write_text("a generic relationship-and-tuple style", encoding="utf-8")
            import subprocess

            subprocess.run(["git", "-C", str(root), "add", "doc.md"], check=True)
            violations = ref.scan_tracked_files(root, identifiers={"alpha-main", "alpha"})
            self.assertEqual(violations, [])

    def test_no_identifiers_is_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_repo(root)
            (root / "doc.md").write_text("alpha-main", encoding="utf-8")
            import subprocess

            subprocess.run(["git", "-C", str(root), "add", "doc.md"], check=True)
            self.assertEqual(ref.scan_tracked_files(root, identifiers=set()), [])


if __name__ == "__main__":
    unittest.main()
