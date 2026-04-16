#!/usr/bin/env python3
"""Run Parallel.ai Deep Research tasks and save markdown reports locally."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


API_BASE = "https://api.parallel.ai/v1/tasks/runs"
AUTO_PROCESSORS = {
    "simple": "base",
    "standard": "core",
    "serious": "pro",
    "deep": "ultra",
}
AUTO_FAST_PROCESSORS = {
    "simple": "base-fast",
    "standard": "core-fast",
    "serious": "pro-fast",
    "deep": "ultra-fast",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launch a Parallel.ai Deep Research run and save the markdown report."
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="Research prompt. Use --prompt-file for long prompts.",
    )
    parser.add_argument(
        "--prompt-file",
        type=Path,
        help="Read the research prompt from a text or markdown file.",
    )
    parser.add_argument(
        "--title",
        help="Short title used for the output file name.",
    )
    parser.add_argument(
        "--processor",
        default="auto",
        help="Parallel processor to use. Defaults to 'auto'.",
    )
    parser.add_argument(
        "--effort",
        choices=sorted(AUTO_PROCESSORS),
        default="standard",
        help="Routing hint for --processor=auto. Defaults to 'standard'.",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Prefer the matching -fast processor when --processor=auto.",
    )
    parser.add_argument(
        "--description",
        default=(
            "Return a rigorous markdown report in Russian with a short executive summary, "
            "numbered sections, comparison tables where useful, concrete recommendations for "
            "a founder, and inline citations."
        ),
        help="Steering description for the text output schema.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env.parallel"),
        help="Env file with PARALLEL_API_KEY. Defaults to .env.parallel.",
    )
    parser.add_argument(
        "--previous-interaction-id",
        help="Continue an existing Parallel interaction.",
    )
    parser.add_argument(
        "--schema-file",
        type=Path,
        help="Optional JSON schema file for structured output.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/deep-research"),
        help="Directory for markdown reports and JSON metadata.",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=20,
        help="Seconds between status checks. Defaults to 20.",
    )
    parser.add_argument(
        "--max-wait-minutes",
        type=int,
        default=30,
        help="Hard timeout for the local polling loop. Defaults to 30 minutes.",
    )
    args = parser.parse_args()
    if not args.prompt and not args.prompt_file:
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


def resolve_processor(processor: str, effort: str, fast: bool) -> str:
    if processor != "auto":
        return processor
    if fast:
        return AUTO_FAST_PROCESSORS[effort]
    return AUTO_PROCESSORS[effort]


def build_output_schema(args: argparse.Namespace) -> dict[str, Any]:
    if args.schema_file:
        return {
            "type": "json",
            "json_schema": json.loads(args.schema_file.read_text(encoding="utf-8")),
        }
    return {
        "type": "text",
        "description": args.description,
    }


def slugify(value: str) -> str:
    normalized = value.lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "deep-research"


def request_json(
    method: str,
    url: str,
    api_key: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = None
    headers = {
        "x-api-key": api_key,
        "content-type": "application/json",
        "accept": "application/json",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(
            f"Parallel API request failed: {exc.code} {exc.reason}\n{body}"
        ) from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Network error while calling Parallel API: {exc}") from exc


def create_run(
    api_key: str,
    prompt: str,
    processor: str,
    output_schema: dict[str, Any],
    previous_interaction_id: str | None = None,
) -> dict[str, Any]:
    payload = {
        "input": prompt,
        "processor": processor,
        "task_spec": {
            "output_schema": output_schema
        },
    }
    if previous_interaction_id:
        payload["previous_interaction_id"] = previous_interaction_id
    return request_json("POST", API_BASE, api_key, payload)


def wait_for_completion(
    api_key: str,
    run_id: str,
    poll_interval: int,
    max_wait_minutes: int,
) -> dict[str, Any]:
    started = time.monotonic()
    deadline = started + (max_wait_minutes * 60)
    status_url = f"{API_BASE}/{run_id}"

    while True:
        run = request_json("GET", status_url, api_key)
        status = run.get("status", "unknown")
        modified_at = run.get("modified_at")
        print(f"[status] {status}  run_id={run_id}  modified_at={modified_at}", flush=True)

        if status == "completed":
            return run
        if status in {"failed", "cancelled"}:
            error = run.get("error") or {}
            raise SystemExit(f"Deep Research ended with status={status}: {json.dumps(error, ensure_ascii=False)}")
        if time.monotonic() >= deadline:
            raise SystemExit(
                f"Timed out waiting for run {run_id} after {max_wait_minutes} minutes."
            )
        time.sleep(poll_interval)


def fetch_result(api_key: str, run_id: str) -> dict[str, Any]:
    url = f"{API_BASE}/{run_id}/result?{urllib.parse.urlencode({'timeout': 30})}"
    return request_json("GET", url, api_key)


def extract_markdown(result: dict[str, Any]) -> str:
    output = result.get("output", {})
    if isinstance(output, str):
        return output.strip() + "\n"
    content = output.get("content", output)
    if isinstance(content, str):
        return content.strip() + "\n"
    if isinstance(content, (dict, list)):
        return json.dumps(content, ensure_ascii=False, indent=2) + "\n"
    raise SystemExit(f"Unexpected output payload: {json.dumps(output, ensure_ascii=False)}")


def save_outputs(
    output_dir: Path,
    title: str,
    processor: str,
    result: dict[str, Any],
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d")
    stem = f"{stamp}-{slugify(title)[:80]}.{processor}"
    markdown_path = output_dir / f"{stem}.md"
    json_path = output_dir / f"{stem}.json"

    markdown = extract_markdown(result)
    markdown_path.write_text(markdown, encoding="utf-8")
    json_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return markdown_path, json_path


def main() -> int:
    args = parse_args()
    load_env_file(args.env_file)

    api_key = os.environ.get("PARALLEL_API_KEY")
    if not api_key:
        raise SystemExit(
            f"PARALLEL_API_KEY is missing. Put it into {args.env_file} or your shell env."
        )

    prompt = build_prompt(args)
    title = args.title or prompt[:80]
    processor = resolve_processor(args.processor, args.effort, args.fast)
    output_schema = build_output_schema(args)

    run = create_run(
        api_key=api_key,
        prompt=prompt,
        processor=processor,
        output_schema=output_schema,
        previous_interaction_id=args.previous_interaction_id,
    )
    run_id = run["run_id"]
    print(f"[created] run_id={run_id} processor={processor}", flush=True)

    wait_for_completion(
        api_key=api_key,
        run_id=run_id,
        poll_interval=args.poll_interval,
        max_wait_minutes=args.max_wait_minutes,
    )
    result = fetch_result(api_key, run_id)
    markdown_path, json_path = save_outputs(args.output_dir, title, processor, result)

    print(f"[saved] markdown={markdown_path}", flush=True)
    print(f"[saved] metadata={json_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
