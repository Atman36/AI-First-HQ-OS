from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from hq_io import append_jsonl, archive_old_directories, atomic_write_text, write_json


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
SKILL_ELIGIBLE_CHANGE_SCOPES = {
    "workflow",
    "prompt",
    "routing",
    "documentation",
    "memory",
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
        if not text or text in seen:
            continue
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
        return "derived_from_lesson", f"Before similar tasks, follow this rule: {lesson}"

    summary = summarize_observation(group)
    return (
        "derived_from_observation",
        f"Add a lightweight checklist step to prevent this recurring issue: {summary}",
    )


def determine_manual_targets(status: str, change_scopes: list[str]) -> tuple[list[str], bool]:
    if status != "candidate":
        return [], False

    targets = [
        "agent prompt",
        "task checklist",
        "operating procedure",
    ]
    skill_candidate = bool(change_scopes) and all(
        scope in SKILL_ELIGIBLE_CHANGE_SCOPES for scope in change_scopes
    )
    if skill_candidate:
        targets.append("skill")
    return targets, skill_candidate


def build_group_record(
    group: dict[str, Any],
    min_observations: int,
    min_unique_sessions: int,
) -> dict[str, Any]:
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

    manual_targets, skill_candidate = determine_manual_targets(status, change_scopes)
    return {
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
        "manual_targets": manual_targets,
        "skill_candidate": skill_candidate,
        "promotion_target": "skill" if skill_candidate else "",
    }


def render_review_markdown(review: dict[str, Any]) -> str:
    lines = [
        "# Weekly Reflection Review",
        "",
        f"- Generated At: {review['generated_at']}",
        f"- Window: {review['window']['since']} -> {review['window']['until']}",
        f"- Total reflections: {review['total_reflections']}",
        f"- Candidate improvements: {review['candidate_improvements']}",
        f"- Skill candidates: {review['skill_candidates']}",
        f"- Manual-only groups: {review['manual_only_groups']}",
        "",
    ]

    candidates = [group for group in review["groups"] if group["status"] == "candidate"]
    skill_candidates = [group for group in candidates if group.get("skill_candidate")]
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

    lines.extend(["", "## Skill Candidates"])
    if not skill_candidates:
        lines.append("- None")
    else:
        for group in skill_candidates:
            lines.extend(
                [
                    f"- {group['issue_key']}: {group['candidate_rule']}",
                    "  Promotion target: skill backlog only",
                    f"  Summary: {group['summary']}",
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
            "- This review does not edit AGENTS.md, shared markdown, access rules, safety rules, tools, or production logic.",
            "- Skill candidates are private backlog artifacts only and must be promoted manually.",
            "- Candidate improvements are review artifacts only and must be applied manually or by a separate gated command.",
            "",
        ]
    )
    return "\n".join(lines)


def build_skill_candidates_backlog(review: dict[str, Any]) -> dict[str, Any]:
    candidates = []
    for group in review["groups"]:
        if not group.get("skill_candidate"):
            continue
        candidates.append(
            {
                "issue_key": group["issue_key"],
                "summary": group["summary"],
                "candidate_rule": group["candidate_rule"],
                "change_scopes": group["change_scopes"],
                "observations": group["observations"],
                "unique_sessions": group["unique_sessions"],
                "manual_targets": group["manual_targets"],
                "promotion_target": "skill",
            }
        )

    return {
        "generated_at": review["generated_at"],
        "window": review["window"],
        "total_skill_candidates": len(candidates),
        "guardrails": [
            "Skill promotion remains manual-first.",
            "Weekly review does not edit AGENTS.md, shared truth, access rules, safety rules, or production logic.",
            "Skill backlog artifacts stay under .hq/improvements/ until reviewed.",
        ],
        "candidates": candidates,
    }


def review_archive_keep() -> int:
    return max(1, int(os.environ.get("HQ_REVIEW_ARCHIVE_KEEP", "12")))


def write_review_artifacts(review: dict[str, Any], review_slug: str) -> tuple[Path, Path]:
    review_dir = RUNTIME_DIRS["improvements"] / review_slug
    review_dir.mkdir(parents=True, exist_ok=True)
    json_path = review_dir / "review.json"
    md_path = review_dir / "review.md"
    review_markdown = render_review_markdown(review) + "\n"
    write_json(json_path, review)
    atomic_write_text(md_path, review_markdown)
    write_json(RUNTIME_DIRS["improvements"] / "LATEST.json", review)
    atomic_write_text(RUNTIME_DIRS["improvements"] / "LATEST.md", review_markdown)
    write_json(
        RUNTIME_DIRS["improvements"] / "skill-candidates.json",
        build_skill_candidates_backlog(review),
    )
    archive_old_directories(RUNTIME_DIRS["improvements"], keep=review_archive_keep())
    return json_path, md_path


def build_review(
    since: date,
    until: date,
    *,
    min_observations: int,
    min_unique_sessions: int,
) -> dict[str, Any]:
    reflections = load_reflections(since, until)
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"items": []})
    for reflection in reflections:
        issue_key = reflection.get("issue_key") or derive_issue_key(reflection)
        group = grouped[issue_key]
        group["issue_key"] = issue_key
        group["items"].append(reflection)

    groups = [
        build_group_record(group, min_observations, min_unique_sessions)
        for group in grouped.values()
    ]
    groups.sort(key=lambda item: (-item["observations"], item["issue_key"]))

    return {
        "generated_at": utc_now(),
        "window": {"since": since.isoformat(), "until": until.isoformat()},
        "total_reflections": len(reflections),
        "total_groups": len(groups),
        "candidate_improvements": sum(1 for group in groups if group["status"] == "candidate"),
        "skill_candidates": sum(1 for group in groups if group.get("skill_candidate")),
        "manual_only_groups": sum(1 for group in groups if group["status"] == "manual_only"),
        "thresholds": {
            "min_observations": min_observations,
            "min_unique_sessions": min_unique_sessions,
        },
        "groups": groups,
    }


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

    review = build_review(
        since,
        until,
        min_observations=args.min_observations,
        min_unique_sessions=args.min_unique_sessions,
    )
    review_slug = f"{since.isoformat()}_to_{until.isoformat()}"
    json_path, md_path = write_review_artifacts(review, review_slug)
    print(f"review_json={json_path}")
    print(f"review_md={md_path}")
    print(f"candidate_improvements={review['candidate_improvements']}")
    return 0
