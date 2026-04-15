#!/usr/bin/env python3
"""Minimal private runtime helpers for HQ sessions, probes, and handoffs."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


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
RESTRICTED_CHANGE_SCOPES = {"tool_access", "safety_policy", "production_logic", "access"}
ALLOWED_CHANGE_SCOPES = {
    "workflow",
    "prompt",
    "routing",
    "documentation",
    "memory",
    "tool_access",
    "safety_policy",
    "production_logic",
    "access",
}
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "before",
    "by",
    "for",
    "from",
    "had",
    "have",
    "if",
    "in",
    "into",
    "is",
    "it",
    "late",
    "not",
    "of",
    "on",
    "or",
    "our",
    "so",
    "still",
    "that",
    "the",
    "their",
    "then",
    "this",
    "to",
    "too",
    "was",
    "were",
    "with",
}


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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


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

    handoff_path.write_text(markdown, encoding="utf-8")
    latest_path.write_text(markdown, encoding="utf-8")
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
        raise argparse.ArgumentTypeError("reflection JSON must be an object")
    return payload


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO date: {value}") from exc


def normalize_string_list(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, list):
        raw_items = values
    else:
        raw_items = [values]

    items: list[str] = []
    seen: set[str] = set()
    for raw in raw_items:
        if raw is None:
            continue
        text = str(raw).strip()
        if not text:
            continue
        if text not in seen:
            seen.add(text)
            items.append(text)
    return items


def derive_issue_key(payload: dict[str, Any]) -> str:
    explicit = str(payload.get("issue_key") or "").strip()
    if explicit:
        return slugify(explicit)

    tags = normalize_string_list(payload.get("tags"))
    if tags:
        prefix = payload.get("category") or payload.get("change_scope") or "issue"
        return slugify("-".join([str(prefix), *sorted(tags)[:3]]))

    source = " ".join(
        str(payload.get(field) or "")
        for field in ("issue", "observation", "summary", "lesson")
    )
    tokens = [
        token
        for token in re.findall(r"[a-z0-9]+", source.lower())
        if token not in STOPWORDS and len(token) > 2
    ]
    if not tokens:
        return "general-improvement"
    return slugify("-".join(sorted(set(tokens[:8]))))


def normalize_reflection_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    created_at = str(normalized.get("created_at") or utc_now())
    summary = str(normalized.get("summary") or "").strip()
    observation = str(normalized.get("observation") or "").strip()
    if not summary:
        raise ValueError("reflection requires summary")
    if not observation:
        raise ValueError("reflection requires observation")

    change_scope = str(normalized.get("change_scope") or "workflow").strip() or "workflow"
    if change_scope not in ALLOWED_CHANGE_SCOPES:
        raise ValueError(
            "change_scope must be one of: " + ", ".join(sorted(ALLOWED_CHANGE_SCOPES))
        )

    tags = sorted(normalize_string_list(normalized.get("tags")))
    normalized_tags = [slugify(item) for item in tags]

    session = str(normalized.get("session") or f"session-{created_at[:19].replace(':', '')}")
    reflection = {
        "id": str(normalized.get("id") or f"{created_at}-{slugify(summary)[:48]}"),
        "created_at": created_at,
        "agent": str(normalized.get("agent") or "unknown").strip() or "unknown",
        "role": str(normalized.get("role") or "").strip(),
        "task": str(normalized.get("task") or "").strip(),
        "session": session,
        "outcome": str(normalized.get("outcome") or "partial").strip() or "partial",
        "category": str(normalized.get("category") or "execution").strip() or "execution",
        "change_scope": change_scope,
        "summary": summary,
        "observation": observation,
        "issue": str(normalized.get("issue") or "").strip(),
        "lesson": str(normalized.get("lesson") or "").strip(),
        "proposed_rule": str(normalized.get("proposed_rule") or "").strip(),
        "issue_key": str(normalized.get("issue_key") or "").strip(),
        "evidence": normalize_string_list(normalized.get("evidence")),
        "related_files": normalize_string_list(normalized.get("related_files")),
        "tags": normalized_tags,
        "metadata": normalized.get("metadata") if isinstance(normalized.get("metadata"), dict) else {},
    }
    reflection["issue_key"] = derive_issue_key(reflection)
    return reflection


def reflection_payload_from_args(args: argparse.Namespace) -> dict[str, Any]:
    if args.json:
        payload = dict(args.json)
    else:
        payload = {
            "agent": args.agent,
            "role": args.role,
            "task": args.task,
            "session": args.session,
            "outcome": args.outcome,
            "category": args.category,
            "change_scope": args.change_scope,
            "summary": args.summary,
            "observation": args.observation,
            "issue": args.issue,
            "lesson": args.lesson,
            "proposed_rule": args.proposed_rule,
            "issue_key": args.issue_key,
            "tags": args.tag,
            "related_files": args.related_file,
            "evidence": args.evidence,
            "metadata": args.metadata or {},
        }
    return normalize_reflection_payload(payload)


def reflections_file_for_timestamp(timestamp: str) -> Path:
    day = timestamp[:10]
    month = day[:7]
    return RUNTIME_DIRS["reflections"] / month / f"{day}.jsonl"


def reflection_command(args: argparse.Namespace) -> int:
    ensure_private_runtime()
    try:
        reflection = reflection_payload_from_args(args)
    except ValueError as exc:
        print(f"error={exc}")
        return 2
    reflection_path = reflections_file_for_timestamp(reflection["created_at"])
    append_jsonl(reflection_path, reflection)
    print(f"reflection_file={reflection_path}")
    print(f"reflection_id={reflection['id']}")
    print(f"issue_key={reflection['issue_key']}")
    return 0


def normalize_legacy_reflection_payload(payload: dict[str, Any], source_path: Path) -> dict[str, Any]:
    created_at = str(payload.get("created_at") or utc_now())
    topic = str(payload.get("session_topic") or source_path.stem).strip()
    observation = str(payload.get("observation") or "").strip()
    what_happened = normalize_string_list(payload.get("what_happened"))
    summary = str(payload.get("impact") or topic or observation).strip()
    proposed_rule = str(payload.get("proposed_improvement") or "").strip()
    evidence = normalize_string_list(payload.get("evidence"))
    legacy_type = str(payload.get("type") or "legacy-reflection").strip()
    confidence = str(payload.get("confidence") or "").strip()
    key_fact = next(
        (
            item
            for item in what_happened
            if any(marker in item.lower() for marker in ("timed out", "failed", "error", "blocked"))
        ),
        "",
    )

    normalized = {
        "created_at": created_at,
        "agent": str(payload.get("agent") or "unknown").strip() or "unknown",
        "task": topic,
        "session": str(payload.get("session") or slugify(topic) or source_path.stem),
        "summary": summary,
        "observation": observation or summary,
        "issue": key_fact or observation or (what_happened[0] if what_happened else summary),
        "lesson": str(payload.get("lesson") or "").strip(),
        "issue_key": str(payload.get("issue_key") or slugify(legacy_type) or source_path.stem),
        "change_scope": str(payload.get("change_scope") or "workflow").strip() or "workflow",
        "proposed_rule": proposed_rule,
        "evidence": evidence,
        "tags": normalize_string_list(payload.get("tags")) or [legacy_type],
        "metadata": {
            "source_format": "legacy_json_reflection",
            "source_file": source_path.name,
            "what_happened": what_happened,
            "impact": str(payload.get("impact") or "").strip(),
            "confidence": confidence,
        },
    }
    return normalize_reflection_payload(normalized)


def parse_reflection_file(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".jsonl":
        reflections: list[dict[str, Any]] = []
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            reflections.append(json.loads(line))
        return reflections

    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [
                normalize_legacy_reflection_payload(item, path)
                if isinstance(item, dict)
                else {}
                for item in payload
                if isinstance(item, dict)
            ]
        if isinstance(payload, dict):
            return [normalize_legacy_reflection_payload(payload, path)]
    return []


def load_reflections(since: date, until: date) -> list[dict[str, Any]]:
    reflections: list[dict[str, Any]] = []
    for path in sorted(RUNTIME_DIRS["reflections"].glob("**/*")):
        if path.suffix not in {".jsonl", ".json"} or not path.is_file():
            continue
        for payload in parse_reflection_file(path):
            created_at = str(payload.get("created_at") or "")
            if not created_at:
                continue
            created_day = date.fromisoformat(created_at[:10])
            if since <= created_day <= until:
                reflections.append(payload)
    reflections.sort(key=lambda item: item.get("created_at", ""))
    return reflections


def summarize_observation(group: dict[str, Any]) -> str:
    issues = [item["issue"] for item in group["items"] if item.get("issue")]
    observations = [item["observation"] for item in group["items"] if item.get("observation")]
    source = issues or observations
    if not source:
        return "Recurring issue observed, but source text was sparse."
    summary, _ = Counter(source).most_common(1)[0]
    return summary


def choose_candidate_rule(group: dict[str, Any]) -> tuple[str, str]:
    proposed_rules = [
        item["proposed_rule"] for item in group["items"] if item.get("proposed_rule")
    ]
    if proposed_rules:
        rule, _ = Counter(proposed_rules).most_common(1)[0]
        return "explicit", rule

    lessons = [item["lesson"] for item in group["items"] if item.get("lesson")]
    if lessons:
        lesson, _ = Counter(lessons).most_common(1)[0]
        rule = f"Before similar tasks, follow this rule: {lesson}"
        return "derived_from_lesson", rule

    summary = summarize_observation(group)
    return (
        "derived_from_observation",
        f"Add a lightweight checklist step to prevent this recurring issue: {summary}",
    )


def build_group_record(group: dict[str, Any], min_observations: int, min_unique_sessions: int) -> dict[str, Any]:
    change_scopes = sorted({item.get("change_scope") or "workflow" for item in group["items"]})
    unique_sessions = sorted({item.get("session") or "" for item in group["items"] if item.get("session")})
    unique_agents = sorted({item.get("agent") or "unknown" for item in group["items"]})
    tags = sorted({tag for item in group["items"] for tag in item.get("tags", [])})
    source_type, candidate_rule = choose_candidate_rule(group)
    restricted = any(scope in RESTRICTED_CHANGE_SCOPES for scope in change_scopes)
    observations = len(group["items"])
    enough_observations = observations >= min_observations
    enough_sessions = len(unique_sessions) >= min_unique_sessions

    status = "candidate"
    guardrail_reason = ""
    if restricted:
        status = "manual_only"
        guardrail_reason = (
            "This topic touches access, tools, safety, or production logic and must stay manual."
        )
    elif not enough_observations or not enough_sessions:
        status = "insufficient_evidence"
        guardrail_reason = (
            "Not enough repeated observations yet to promote a candidate improvement."
        )

    record = {
        "issue_key": group["issue_key"],
        "change_scopes": change_scopes,
        "observations": observations,
        "unique_sessions": len(unique_sessions),
        "unique_agents": unique_agents,
        "tags": tags,
        "summary": summarize_observation(group),
        "supporting_examples": [
            {
                "created_at": item.get("created_at"),
                "agent": item.get("agent"),
                "session": item.get("session"),
                "summary": item.get("summary"),
                "observation": item.get("observation"),
                "lesson": item.get("lesson"),
            }
            for item in group["items"][:5]
        ],
        "status": status,
        "guardrail_reason": guardrail_reason,
        "candidate_rule": candidate_rule if status == "candidate" else "",
        "candidate_rule_source": source_type,
        "manual_targets": [
            "agent prompt",
            "task checklist",
            "operating procedure",
        ]
        if status == "candidate"
        else [],
    }
    return record


def render_review_markdown(review: dict[str, Any]) -> str:
    lines = [
        "# Weekly Reflection Review",
        "",
        f"- Generated At: {review['generated_at']}",
        f"- Window: {review['window']['since']} -> {review['window']['until']}",
        f"- Total reflections: {review['total_reflections']}",
        f"- Candidate improvements: {review['candidate_improvements']}",
        f"- Manual-only groups: {review['manual_only_groups']}",
        "",
    ]

    candidates = [group for group in review["groups"] if group["status"] == "candidate"]
    parked = [group for group in review["groups"] if group["status"] != "candidate"]

    lines.append("## Candidate Improvements")
    if not candidates:
        lines.append("- None")
    else:
        for group in candidates:
            lines.extend(
                [
                    f"- {group['issue_key']}: {group['candidate_rule']}",
                    f"  Observations: {group['observations']} across {group['unique_sessions']} sessions",
                    f"  Summary: {group['summary']}",
                    f"  Apply manually to: {', '.join(group['manual_targets'])}",
                ]
            )

    lines.extend(["", "## Parked Or Manual Review"])
    if not parked:
        lines.append("- None")
    else:
        for group in parked:
            lines.extend(
                [
                    f"- {group['issue_key']}: {group['status']}",
                    f"  Reason: {group['guardrail_reason'] or 'Held for review.'}",
                    f"  Summary: {group['summary']}",
                ]
            )

    lines.extend(
        [
            "",
            "## Safety Notes",
            "- This review does not edit AGENTS.md, shared markdown, access rules, tools, or production logic.",
            "- Candidate improvements are review artifacts only and must be applied manually or by a separate gated command.",
            "",
        ]
    )
    return "\n".join(lines)


def write_review_artifacts(review: dict[str, Any], review_slug: str) -> tuple[Path, Path]:
    review_dir = RUNTIME_DIRS["improvements"] / review_slug
    review_dir.mkdir(parents=True, exist_ok=True)
    json_path = review_dir / "review.json"
    md_path = review_dir / "review.md"
    write_json(json_path, review)
    md_path.write_text(render_review_markdown(review) + "\n", encoding="utf-8")
    write_json(RUNTIME_DIRS["improvements"] / "LATEST.json", review)
    (RUNTIME_DIRS["improvements"] / "LATEST.md").write_text(
        render_review_markdown(review) + "\n",
        encoding="utf-8",
    )
    return json_path, md_path


def weekly_review_command(args: argparse.Namespace) -> int:
    ensure_private_runtime()
    if args.days < 1:
        print("error=days must be at least 1")
        return 2
    if args.min_observations < 1:
        print("error=min-observations must be at least 1")
        return 2
    if args.min_unique_sessions < 1:
        print("error=min-unique-sessions must be at least 1")
        return 2

    until = args.until or date.today()
    since = args.since or (until - timedelta(days=args.days - 1))
    if since > until:
        print("error=since must be earlier than or equal to until")
        return 2

    reflections = load_reflections(since, until)

    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"items": []})
    for reflection in reflections:
        issue_key = reflection.get("issue_key") or derive_issue_key(reflection)
        group = grouped[issue_key]
        group["issue_key"] = issue_key
        group["items"].append(reflection)

    groups = [
        build_group_record(group, args.min_observations, args.min_unique_sessions)
        for group in grouped.values()
    ]
    groups.sort(key=lambda item: (-item["observations"], item["issue_key"]))

    review = {
        "generated_at": utc_now(),
        "window": {"since": since.isoformat(), "until": until.isoformat()},
        "total_reflections": len(reflections),
        "total_groups": len(groups),
        "candidate_improvements": sum(1 for group in groups if group["status"] == "candidate"),
        "manual_only_groups": sum(1 for group in groups if group["status"] == "manual_only"),
        "thresholds": {
            "min_observations": args.min_observations,
            "min_unique_sessions": args.min_unique_sessions,
        },
        "groups": groups,
    }
    review_slug = f"{since.isoformat()}_to_{until.isoformat()}"
    json_path, md_path = write_review_artifacts(review, review_slug)
    print(f"review_json={json_path}")
    print(f"review_md={md_path}")
    print(f"candidate_improvements={review['candidate_improvements']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Minimal private runtime helpers for HQ."
    )
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
    handoff.add_argument(
        "--done",
        action="append",
        default=[],
        help="Repeat for each completed item.",
    )
    handoff.add_argument(
        "--next",
        action="append",
        default=[],
        help="Repeat for each next step.",
    )
    handoff.add_argument(
        "--important-file",
        action="append",
        default=[],
        help="Repeat for each file the next agent should read.",
    )
    handoff.add_argument(
        "--risk",
        action="append",
        default=[],
        help="Repeat for each risk.",
    )
    handoff.add_argument(
        "--blocker",
        action="append",
        default=[],
        help="Repeat for each blocker.",
    )
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
        help="Minimum repeated observations required before proposing a candidate improvement.",
    )
    weekly_review.add_argument(
        "--min-unique-sessions",
        type=int,
        default=2,
        help="Minimum distinct sessions required before proposing a candidate improvement.",
    )
    weekly_review.set_defaults(func=weekly_review_command)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
