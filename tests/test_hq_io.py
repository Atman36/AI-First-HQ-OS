from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "hq_io.py"


def load_module():
    spec = importlib.util.spec_from_file_location("hq_io_test_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class HqIoTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_dir.name)
        self.module = load_module()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_atomic_write_text_replaces_existing_file(self):
        target = self.temp_root / "nested" / "data.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("old", encoding="utf-8")

        self.module.atomic_write_text(target, "new content")

        self.assertEqual(target.read_text(encoding="utf-8"), "new content")

    def test_write_json_serializes_pretty_output(self):
        target = self.temp_root / "payload.json"

        self.module.write_json(target, {"name": "HQ", "count": 2})

        self.assertEqual(
            target.read_text(encoding="utf-8"),
            '{\n  "name": "HQ",\n  "count": 2\n}\n',
        )

    def test_append_jsonl_rotates_existing_file_before_appending(self):
        target = self.temp_root / "events.jsonl"
        target.write_text(
            '{"id":"old-1"}\n{"id":"old-2"}\n',
            encoding="utf-8",
        )

        archived = self.module.append_jsonl(
            target,
            {"id": "new-1"},
            max_records=2,
        )

        self.assertIsNotNone(archived)
        assert archived is not None
        self.assertEqual(archived.name, "events.part001.jsonl")
        self.assertEqual(
            archived.read_text(encoding="utf-8"),
            '{"id":"old-1"}\n{"id":"old-2"}\n',
        )
        self.assertEqual(target.read_text(encoding="utf-8"), '{"id": "new-1"}\n')

    def test_archive_old_directories_keeps_latest_directories(self):
        base_dir = self.temp_root / "reviews"
        for name in ["2026-04-01", "2026-04-02", "2026-04-03"]:
            (base_dir / name).mkdir(parents=True, exist_ok=True)

        archived = self.module.archive_old_directories(base_dir, keep=2)

        self.assertEqual([path.name for path in archived], ["2026-04-01"])
        self.assertFalse((base_dir / "2026-04-01").exists())
        self.assertTrue((base_dir / "2026-04-02").exists())
        self.assertTrue((base_dir / "2026-04-03").exists())
        self.assertTrue((base_dir / "archive" / "2026-04-01").exists())


if __name__ == "__main__":
    unittest.main()
