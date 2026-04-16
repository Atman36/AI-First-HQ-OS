#!/usr/bin/env python3
"""Run fast local analysis prompts through Cerebras models."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


API_BASE = "https://api.cerebras.ai"
DEFAULT_SYSTEM = (
    "You are a concise operations analyst. Return compact, decision-useful answers, "
    "state assumptions, and avoid filler."
)
PROFILE_MODELS = {
    "ultrafast": "llama3.1-8b",
    "balanced": "qwen-3-235b-a22b-instruct-2507",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a quick analysis prompt through Cerebras."
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="Prompt to analyze. Use --prompt-file for longer text.",
    )
    parser.add_argument(
        "--prompt-file",
        type=Path,
        help="Read the prompt from a text or markdown file.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env.cerebras"),
        help="Env file with CEREBRAS_API_KEY. Defaults to .env.cerebras.",
    )
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILE_MODELS),
        default="ultrafast",
        help="Model routing preset. Defaults to 'ultrafast'.",
    )
    parser.add_argument(
        "--model",
        help="Override the preset model.",
    )
    parser.add_argument(
        "--system",
        default=DEFAULT_SYSTEM,
        help="System prompt used for the analysis.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="Sampling temperature. Defaults to 0.2.",
    )
    parser.add_argument(
        "--max-completion-tokens",
        type=int,
        default=800,
        help="Maximum completion tokens. Defaults to 800.",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=["low", "medium", "high"],
        help="Optional reasoning effort hint for supported models.",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="Print public Cerebras model metadata and exit.",
    )
    args = parser.parse_args()
    if not args.list_models and not args.prompt and not args.prompt_file:
        parser.error("Provide a prompt argument or --prompt-file.")
    return args


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def build_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file:
        return args.prompt_file.read_text(encoding="utf-8").strip()
    assert args.prompt is not None
    return args.prompt.strip()


def request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    data = None
    headers = {
        "accept": "application/json",
        "user-agent": "hq-codex/1.0",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["content-type"] = "application/json"
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"

    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(
            f"Cerebras API request failed: {exc.code} {exc.reason}\n{body}"
        ) from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Network error while calling Cerebras API: {exc}") from exc


def build_completion_payload(args: argparse.Namespace, prompt: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": args.model or PROFILE_MODELS[args.profile],
        "messages": [
            {"role": "system", "content": args.system},
            {"role": "user", "content": prompt},
        ],
        "temperature": args.temperature,
        "max_completion_tokens": args.max_completion_tokens,
    }
    if args.reasoning_effort:
        payload["reasoning_effort"] = args.reasoning_effort
    return payload


def list_models() -> list[dict[str, Any]]:
    url = f"{API_BASE}/public/v1/models?{urllib.parse.urlencode({'format': 'huggingface'})}"
    payload = request_json("GET", url)
    return payload.get("data", [])


def format_models(models: list[dict[str, Any]]) -> str:
    lines = []
    for model in models:
        pricing = model.get("pricing", {})
        context_length = model.get("context_length", "?")
        lines.append(
            f"{model.get('id')}  context={context_length}  "
            f"input=${pricing.get('input', '?')}/1M  output=${pricing.get('output', '?')}/1M"
        )
    return "\n".join(lines) + ("\n" if lines else "")


def extract_text(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        raise SystemExit(f"Unexpected Cerebras response: {json.dumps(response, ensure_ascii=False)}")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content.strip() + "\n"
    raise SystemExit(f"Unexpected Cerebras response: {json.dumps(response, ensure_ascii=False)}")


def main() -> int:
    args = parse_args()
    if args.list_models:
        sys.stdout.write(format_models(list_models()))
        return 0

    load_env_file(args.env_file)
    api_key = os.environ.get("CEREBRAS_API_KEY")
    if not api_key:
        raise SystemExit(
            f"CEREBRAS_API_KEY is missing. Put it into {args.env_file} or your shell env."
        )

    prompt = build_prompt(args)
    response = request_json(
        "POST",
        f"{API_BASE}/v1/chat/completions",
        payload=build_completion_payload(args, prompt),
        api_key=api_key,
    )
    sys.stdout.write(extract_text(response))
    return 0


if __name__ == "__main__":
    sys.exit(main())
