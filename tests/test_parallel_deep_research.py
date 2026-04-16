import datetime as real_datetime
import importlib.util
import json
import unittest
from io import BytesIO
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError, URLError


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "parallel_deep_research.py"


def load_module():
    spec = importlib.util.spec_from_file_location("parallel_deep_research_test_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class ParallelDeepResearchTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def test_request_json_posts_payload_via_urllib(self):
        with mock.patch.object(
            self.module.urllib.request,
            "urlopen",
            return_value=FakeResponse({"run_id": "run-123"}),
        ) as mocked_urlopen:
            result = self.module.request_json(
                "POST",
                "https://example.com/tasks",
                "secret-key",
                {"input": "research"},
            )

        self.assertEqual(result, {"run_id": "run-123"})
        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://example.com/tasks")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(json.loads(request.data.decode("utf-8")), {"input": "research"})

    def test_request_json_exits_on_http_error(self):
        error = HTTPError(
            url="https://example.com/tasks",
            code=500,
            msg="Server Error",
            hdrs=None,
            fp=BytesIO(b'{"error":"boom"}'),
        )
        with mock.patch.object(self.module.urllib.request, "urlopen", side_effect=error):
            with self.assertRaises(SystemExit) as context:
                self.module.request_json("GET", "https://example.com/tasks", "secret-key")

        self.assertIn("500", str(context.exception))
        self.assertIn("boom", str(context.exception))

    def test_request_json_exits_on_network_error(self):
        with mock.patch.object(
            self.module.urllib.request,
            "urlopen",
            side_effect=URLError("offline"),
        ):
            with self.assertRaises(SystemExit) as context:
                self.module.request_json("GET", "https://example.com/tasks", "secret-key")

        self.assertIn("Network error", str(context.exception))

    def test_wait_for_completion_polls_until_completed(self):
        with mock.patch.object(
            self.module,
            "request_json",
            side_effect=[
                {"status": "running", "modified_at": "2026-04-16T00:00:00Z"},
                {"status": "completed", "modified_at": "2026-04-16T00:01:00Z"},
            ],
        ) as mocked_request, mock.patch.object(self.module.time, "sleep") as mocked_sleep:
            result = self.module.wait_for_completion(
                api_key="secret-key",
                run_id="run-123",
                poll_interval=5,
                max_wait_minutes=1,
            )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(mocked_request.call_count, 2)
        mocked_sleep.assert_called_once_with(5)

    def test_save_outputs_writes_markdown_and_metadata(self):
        output_dir = Path("/tmp/parallel-deep-research")
        result = {"output": {"content": "# Report\n"}}
        fake_now = real_datetime.datetime(2026, 4, 16, 9, 0, 0)

        with mock.patch.object(Path, "mkdir") as mocked_mkdir, mock.patch.object(
            Path,
            "write_text",
        ) as mocked_write_text, mock.patch.object(self.module.dt, "datetime") as mocked_datetime:
            mocked_datetime.now.return_value = fake_now

            markdown_path, json_path = self.module.save_outputs(output_dir, "Market audit", "pro", result)

        mocked_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        self.assertEqual(markdown_path.name, "2026-04-16-market-audit.pro.md")
        self.assertEqual(json_path.name, "2026-04-16-market-audit.pro.json")
        self.assertEqual(mocked_write_text.call_count, 2)
        first_write = mocked_write_text.call_args_list[0].args[0]
        second_write = mocked_write_text.call_args_list[1].args[0]
        self.assertEqual(first_write, "# Report\n")
        self.assertIn('"content": "# Report\\n"', second_write)


if __name__ == "__main__":
    unittest.main()
