#!/usr/bin/env python3
"""Minimal private runtime helpers for HQ sessions, probes, and handoffs."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from hq_io import append_jsonl as append_jsonl_record
from hq_io import atomic_write_text, write_json
from hq_runtime_review import ALLOWED_CHANGE_SCOPES
from hq_runtime_review import derive_issue_key
from hq_runtime_review import load_reflections
from hq_runtime_review import normalize_reflection_payload
from hq_runtime_review import normalize_string_list
from hq_runtime_review import reflection_command
from hq_runtime_review import reflection_payload_from_args
from hq_runtime_review import reflections_file_for_timestamp
from hq_runtime_review import render_review_markdown
from hq_runtime_review import weekly_review_command


REPO_ROOT = Path(
    os.environ.get("HQ_RUNTIME_REPO_ROOT", Path(__file__).resolve().parents[1])
).resolve()
PRIVATE_ROOT = Path(os.environ.get("HQ_RUNTIME_PRIVATE_ROOT", REPO_ROOT / ".hq")).resolve()
RUNTIME_DIRS = {
    "handoffs": PRIVATE_ROOT / "handoffs",
    "logs": PRIVATE_ROOT / "logs",
    "state": PRIVATE_ROOT / "state",
    "memory": PRIVATE_ROOT / "memory",
    "journals": PRIVATE_ROOT / "journals",
    "reflections": PRIVATE_ROOT / "reflections",
    "improvements": PRIVATE_ROOT / "improvements",
    "telemetry": PRIVATE_ROOT / "telemetry",
    "evals": PRIVATE_ROOT / "evals",
    "releases": PRIVATE_ROOT / "releases",
}
CAPABILITIES_FILE = RUNTIME_DIRS["state"] / "capabilities.json"


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def slugify(value: str) -> str:
    cleaned = []
    previous_dash = False
    for char in (value or "").strip().lower():
        if char.isalnum():
            cleaned.append(char)
            previous_dash = False
            continue
        if not previous_dash:
            cleaned.append("-")
            previous_dash = True
    normalized = "".join(cleaned).strip("-")
    return normalized or "session"


def ensure_private_runtime() -> dict[str, Path]:
    PRIVATE_ROOT.mkdir(parents=True, exist_ok=True)
    for path in RUNTIME_DIRS.values():
        path.mkdir(parents=True, exist_ok=True)
    return RUNTIME_DIRS


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    append_jsonl_record(path, payload)


def bootstrap_command(_: argparse.Namespace) -> int:
    paths = ensure_private_runtime()
    print(f"private_root={PRIVATE_ROOT}")
    for name, path in paths.items():
        print(f"{name}={path}")
    return 0


def probe_tool(tool: str, timeout: int) -> dict[str, Any]:
    binary = shutil.which(tool)
    result: dict[str, Any] = {
        "tool": tool,
        "checked_at": utc_now(),
        "binary": binary,
        "available": False,
        "probe": "--help",
    }
    if binary is None:
        result["status"] = "missing"
        result["reason"] = "binary not found in PATH"
        return result

    try:
        completed = subprocess.run(
            [binary, "--help"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        result["status"] = "timeout"
        result["reason"] = f"timed out after {timeout}s while probing --help"
        return result
    except OSError as exc:
        result["status"] = "error"
        result["reason"] = str(exc)
        return result

    preview = (completed.stdout or completed.stderr or "").strip().splitlines()
    result["available"] = True
    result["status"] = "ready"
    result["returncode"] = completed.returncode
    if preview:
        result["preview"] = preview[0][:160]
    return result


def probe_command(args: argparse.Namespace) -> int:
    ensure_private_runtime()
    results = [probe_tool(tool, args.timeout) for tool in args.tools]
    payload = {
        "updated_at": utc_now(),
        "tools": {item["tool"]: item for item in results},
    }
    write_json(CAPABILITIES_FILE, payload)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"capabilities_file={CAPABILITIES_FILE}")
    for item in results:
        status = "ready" if item["available"] else item["status"]
        binary = item.get("binary") or "-"
        print(f"{item['tool']}: {status} ({binary})")
        preview = item.get("preview")
        if preview:
            print(f"  {preview}")
        reason = item.get("reason")
        if reason:
            print(f"  {reason}")
    return 0


def render_section(title: str, items: list[str]) -> str:
    lines = [f"## {title}"]
    if items:
        lines.extend(f"- {item}" for item in items)
    else:
        lines.append("- None")
    return "\n".join(lines)


def handoff_markdown(args: argparse.Namespace, updated_at: str) -> str:
    header = [
        "# Handoff",
        "",
        f"- Task: {args.task}",
        f"- Session: {args.session}",
        f"- Updated At: {updated_at}",
        f"- Owner: {args.owner or 'Unassigned'}",
        f"- Status: {args.status}",
        f"- Continue From: {args.continue_from or 'Not set'}",
        f"- Primary Update File: {args.primary_file or 'Not set'}",
        f"- Accepting Role: {args.accepting_role or 'Not set'}",
        "",
    ]
    sections = [
        render_section("Done", args.done),
        "",
        render_section("Next", args.next),
        "",
        render_section("Important Files", args.important_file),
        "",
        render_section("Risks", args.risk),
        "",
        render_section("Blockers", args.blocker),
        "",
        render_section("Notes", args.note),
        "",
    ]
    return "\n".join(header + sections)


def handoff_command(args: argparse.Namespace) -> int:
    ensure_private_runtime()
    updated_at = utc_now()
    task_slug = slugify(args.task)
    session_slug = slugify(args.session)
    task_dir = RUNTIME_DIRS["handoffs"] / task_slug
    task_dir.mkdir(parents=True, exist_ok=True)

    markdown = handoff_markdown(args, updated_at)
    handoff_path = task_dir / f"{session_slug}.md"
    latest_path = task_dir / "LATEST.md"
    manifest_path = task_dir / "manifest.json"

    atomic_write_text(handoff_path, markdown)
    atomic_write_text(latest_path, markdown)
    write_json(
        manifest_path,
        {
            "task": args.task,
            "task_slug": task_slug,
            "session": args.session,
            "owner": args.owner or "",
            "status": args.status,
            "updated_at": updated_at,
            "latest_file": latest_path.relative_to(REPO_ROOT).as_posix(),
            "session_file": handoff_path.relative_to(REPO_ROOT).as_posix(),
            "continue_from": args.continue_from or "",
            "primary_file": args.primary_file or "",
            "important_files": args.important_file,
            "risks": args.risk,
            "blockers": args.blocker,
        },
    )

    print(f"handoff_file={handoff_path}")
    print(f"latest_file={latest_path}")
    print(f"manifest_file={manifest_path}")
    return 0


def parse_json_object(value: str) -> dict[str, Any]:
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise argparse.ArgumentTypeError("JSON payload must be an object")
    return payload


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO date: {value}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Minimal private runtime helpers for HQ.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap = subparsers.add_parser(
        "bootstrap",
        help="Create the private runtime directories if missing.",
    )
    bootstrap.set_defaults(func=bootstrap_command)

    probe = subparsers.add_parser(
        "probe",
        help="Check whether required CLI surfaces are really available.",
    )
    probe.add_argument("tools", nargs="+", help="CLI names to probe, e.g. codex claude")
    probe.add_argument(
        "--timeout",
        type=int,
        default=5,
        help="Seconds allowed for each --help probe. Defaults to 5.",
    )
    probe.add_argument(
        "--json",
        action="store_true",
        help="Print JSON instead of plain text.",
    )
    probe.set_defaults(func=probe_command)

    handoff = subparsers.add_parser(
        "handoff",
        help="Write a task-scoped handoff file into the private runtime.",
    )
    handoff.add_argument("--task", required=True, help="Task or workstream identifier.")
    handoff.add_argument(
        "--session",
        default=f"session-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        help="Session identifier. Defaults to a UTC timestamp.",
    )
    handoff.add_argument("--owner", help="Current owner of the task slice.")
    handoff.add_argument(
        "--status",
        default="ready_for_handoff",
        help="Current task status. Defaults to ready_for_handoff.",
    )
    handoff.add_argument(
        "--continue-from",
        help="File or place where the next agent should continue first.",
    )
    handoff.add_argument(
        "--primary-file",
        help="Primary update file for the next slice.",
    )
    handoff.add_argument(
        "--accepting-role",
        help="Role that should accept or continue the result.",
    )
    handoff.add_argument("--done", action="append", default=[], help="Repeat for each completed item.")
    handoff.add_argument("--next", action="append", default=[], help="Repeat for each next step.")
    handoff.add_argument(
        "--important-file",
        action="append",
        default=[],
        help="Repeat for each file the next agent should read.",
    )
    handoff.add_argument("--risk", action="append", default=[], help="Repeat for each risk.")
    handoff.add_argument("--blocker", action="append", default=[], help="Repeat for each blocker.")
    handoff.add_argument(
        "--note",
        action="append",
        default=[],
        help="Repeat for any extra note that should stay private.",
    )
    handoff.set_defaults(func=handoff_command)

    reflection = subparsers.add_parser(
        "reflection",
        help="Write one structured JSONL reflection into the private runtime.",
    )
    reflection.add_argument("--json", type=parse_json_object, help="Inline JSON object payload.")
    reflection.add_argument("--agent", help="Agent or role name.")
    reflection.add_argument("--role", help="Optional role name.")
    reflection.add_argument("--task", help="Task or workstream identifier.")
    reflection.add_argument("--session", help="Session identifier.")
    reflection.add_argument(
        "--outcome",
        default="partial",
        choices=["success", "partial", "failed"],
        help="Outcome of the finished work. Defaults to partial.",
    )
    reflection.add_argument(
        "--category",
        default="execution",
        help="Short category label, e.g. execution, routing, context, tooling.",
    )
    reflection.add_argument(
        "--change-scope",
        default="workflow",
        choices=sorted(ALLOWED_CHANGE_SCOPES),
        help="Area where an improvement might later apply.",
    )
    reflection.add_argument("--summary", help="Short outcome summary.")
    reflection.add_argument("--observation", help="Concrete observation from the task.")
    reflection.add_argument("--issue", help="Underlying recurring issue.")
    reflection.add_argument("--lesson", help="What the agent should remember next time.")
    reflection.add_argument(
        "--proposed-rule",
        help="Optional candidate rule. This is stored separately from the observation.",
    )
    reflection.add_argument(
        "--issue-key",
        help="Stable clustering key for recurring issues. Recommended when logging similar reflections.",
    )
    reflection.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Repeat for each short tag used for grouping.",
    )
    reflection.add_argument(
        "--related-file",
        action="append",
        default=[],
        help="Repeat for any file relevant to the reflection.",
    )
    reflection.add_argument(
        "--evidence",
        action="append",
        default=[],
        help="Repeat for lightweight evidence items such as commands, errors, or artifacts.",
    )
    reflection.add_argument(
        "--metadata",
        type=parse_json_object,
        help="Optional inline JSON object with extra metadata.",
    )
    reflection.set_defaults(func=reflection_command)

    weekly_review = subparsers.add_parser(
        "weekly-review",
        aliases=["improve", "synthesize"],
        help="Aggregate reflections and emit safe candidate improvements into .hq/improvements/.",
    )
    weekly_review.add_argument(
        "--since",
        type=parse_date,
        help="Inclusive start date in ISO format, e.g. 2026-04-07.",
    )
    weekly_review.add_argument(
        "--until",
        type=parse_date,
        help="Inclusive end date in ISO format. Defaults to today.",
    )
    weekly_review.add_argument(
        "--days",
        type=int,
        default=7,
        help="If --since is omitted, review this many trailing days. Defaults to 7.",
    )
    weekly_review.add_argument(
        "--min-observations",
        type=int,
        default=2,
        help="Minimum repeated observations required before a candidate improvement is emitted.",
    )
    weekly_review.add_argument(
        "--min-unique-sessions",
        type=int,
        default=2,
        help="Minimum distinct sessions required before a candidate improvement is emitted.",
    )
    weekly_review.set_defaults(func=weekly_review_command)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
