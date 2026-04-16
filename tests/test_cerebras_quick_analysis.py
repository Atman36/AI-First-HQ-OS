import importlib.util
import json
import unittest
from io import BytesIO
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError, URLError


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "cerebras_quick_analysis.py"


def load_module():
    spec = importlib.util.spec_from_file_location("cerebras_quick_analysis_test_module", SCRIPT_PATH)
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


class CerebrasQuickAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def test_build_completion_payload_uses_profile_model(self):
        args = self.module.argparse.Namespace(
            model=None,
            profile="balanced",
            system="System",
            temperature=0.1,
            max_completion_tokens=300,
            reasoning_effort="medium",
        )

        payload = self.module.build_completion_payload(args, "Analyze this")

        self.assertEqual(payload["model"], "qwen-3-235b-a22b-instruct-2507")
        self.assertEqual(payload["messages"][1]["content"], "Analyze this")
        self.assertEqual(payload["reasoning_effort"], "medium")

    def test_request_json_posts_auth_header(self):
        with mock.patch.object(
            self.module.urllib.request,
            "urlopen",
            return_value=FakeResponse({"choices": []}),
        ) as mocked_urlopen:
            self.module.request_json(
                "POST",
                "https://api.cerebras.ai/v1/chat/completions",
                payload={"model": "llama3.1-8b"},
                api_key="secret-key",
            )

        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.headers["Authorization"], "Bearer secret-key")
        self.assertEqual(json.loads(request.data.decode("utf-8")), {"model": "llama3.1-8b"})

    def test_request_json_exits_on_http_error(self):
        error = HTTPError(
            url="https://api.cerebras.ai/v1/chat/completions",
            code=500,
            msg="Server Error",
            hdrs=None,
            fp=BytesIO(b'{"error":"boom"}'),
        )
        with mock.patch.object(self.module.urllib.request, "urlopen", side_effect=error):
            with self.assertRaises(SystemExit) as context:
                self.module.request_json("GET", "https://api.cerebras.ai/public/v1/models")

        self.assertIn("500", str(context.exception))
        self.assertIn("boom", str(context.exception))

    def test_request_json_exits_on_network_error(self):
        with mock.patch.object(
            self.module.urllib.request,
            "urlopen",
            side_effect=URLError("offline"),
        ):
            with self.assertRaises(SystemExit) as context:
                self.module.request_json("GET", "https://api.cerebras.ai/public/v1/models")

        self.assertIn("Network error", str(context.exception))

    def test_format_models_renders_context_and_pricing(self):
        rendered = self.module.format_models(
            [
                {
                    "id": "llama3.1-8b",
                    "context_length": 8192,
                    "pricing": {"input": 10, "output": 20},
                }
            ]
        )
        self.assertIn("llama3.1-8b", rendered)
        self.assertIn("context=8192", rendered)
        self.assertIn("input=$10/1M", rendered)

    def test_extract_text_reads_first_choice(self):
        text = self.module.extract_text(
            {"choices": [{"message": {"content": "Quick answer"}}]}
        )
        self.assertEqual(text, "Quick answer\n")


if __name__ == "__main__":
    unittest.main()
