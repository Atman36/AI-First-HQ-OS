from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

from hq_io import append_jsonl, archive_old_directories, atomic_write_text, write_json


REPO_ROOT = Path(
    os.environ.get("HQ_TELEMETRY_REPO_ROOT", Path(__file__).resolve().parents[1])
).resolve()
PRIVATE_ROOT = Path(os.environ.get("HQ_RUNTIME_PRIVATE_ROOT", REPO_ROOT / ".hq")).resolve()
TELEMETRY_ROOT = PRIVATE_ROOT / "telemetry"


def ensure_runtime() -> None:
    TELEMETRY_ROOT.mkdir(parents=True, exist_ok=True)


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def event_file_for_timestamp(timestamp: str) -> Path:
    day = timestamp[:10]
    month = day[:7]
    return TELEMETRY_ROOT / month / f"{day}.jsonl"


def telemetry_jsonl_max_bytes() -> int:
    return max(1, int(os.environ.get("HQ_TELEMETRY_JSONL_MAX_BYTES", str(5 * 1024 * 1024))))


def telemetry_jsonl_max_records() -> int:
    return max(1, int(os.environ.get("HQ_TELEMETRY_JSONL_MAX_RECORDS", "5000")))


def review_archive_keep() -> int:
    return max(1, int(os.environ.get("HQ_REVIEW_ARCHIVE_KEEP", "12")))


def append_event(path: Path, payload: dict[str, Any]) -> Path | None:
    return append_jsonl(
        path,
        payload,
        max_bytes=telemetry_jsonl_max_bytes(),
        max_records=telemetry_jsonl_max_records(),
    )


def iter_event_files() -> list[Path]:
    if not TELEMETRY_ROOT.exists():
        return []
    return sorted(
        path
        for path in TELEMETRY_ROOT.glob("**/*.jsonl")
        if "reviews" not in path.parts
    )


def load_events(since: date, until: date) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for path in iter_event_files():
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            created_at = str(payload.get("created_at") or "").strip()
            if not created_at:
                continue
            created_date = parse_timestamp(created_at).date()
            if since <= created_date <= until:
                events.append(payload)
    events.sort(key=lambda item: str(item.get("created_at") or ""))
    return events


def load_task_events(
    task_id: str,
    since: date | None = None,
    until: date | None = None,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for path in iter_event_files():
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if str(payload.get("task_id") or "").strip() != task_id:
                continue
            created_at = str(payload.get("created_at") or "").strip()
            if not created_at:
                continue
            created_date = parse_timestamp(created_at).date()
            if since and created_date < since:
                continue
            if until and created_date > until:
                continue
            events.append(payload)
    events.sort(key=lambda item: str(item.get("created_at") or ""))
    return events


def write_review_artifacts(review: dict[str, Any], review_markdown: str) -> tuple[Path, Path]:
    review_slug = f"{review['window']['since']}_to_{review['window']['until']}"
    review_dir = TELEMETRY_ROOT / "reviews" / review_slug
    review_dir.mkdir(parents=True, exist_ok=True)
    json_path = review_dir / "metrics-review.json"
    md_path = review_dir / "metrics-review.md"
    write_json(json_path, review)
    atomic_write_text(md_path, review_markdown)

    latest_dir = TELEMETRY_ROOT / "reviews"
    write_json(latest_dir / "LATEST.json", review)
    atomic_write_text(latest_dir / "LATEST.md", review_markdown)
    archive_old_directories(latest_dir, keep=review_archive_keep())
    return json_path, md_path
