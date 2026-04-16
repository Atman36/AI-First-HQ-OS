from __future__ import annotations

import fcntl
import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


def atomic_write_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding=encoding,
        dir=path.parent,
        delete=False,
    ) as handle:
        temp_path = Path(handle.name)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_path, path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )


@contextmanager
def file_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.parent / f".{path.name}.lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def count_jsonl_records(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def next_archived_path(path: Path) -> Path:
    archive_dir = path.parent / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    index = 1
    while True:
        candidate = archive_dir / f"{path.stem}.part{index:03d}{path.suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def maybe_rotate_jsonl(
    path: Path,
    *,
    incoming_line: str,
    max_bytes: int | None,
    max_records: int | None,
) -> Path | None:
    if not path.exists():
        return None

    should_rotate = False
    if max_bytes is not None and max_bytes > 0:
        should_rotate = path.stat().st_size + len(incoming_line.encode("utf-8")) > max_bytes
    if not should_rotate and max_records is not None and max_records > 0:
        should_rotate = count_jsonl_records(path) >= max_records
    if not should_rotate:
        return None

    archive_path = next_archived_path(path)
    os.replace(path, archive_path)
    return archive_path


def append_jsonl(
    path: Path,
    payload: dict[str, Any],
    *,
    max_bytes: int | None = None,
    max_records: int | None = None,
) -> Path | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False) + "\n"
    with file_lock(path):
        archived_path = maybe_rotate_jsonl(
            path,
            incoming_line=line,
            max_bytes=max_bytes,
            max_records=max_records,
        )
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
    return archived_path


def archive_old_directories(base_dir: Path, *, keep: int) -> list[Path]:
    if keep < 1:
        raise ValueError("keep must be at least 1")
    if not base_dir.exists():
        return []

    archive_dir = base_dir / "archive"
    review_dirs = sorted(
        path for path in base_dir.iterdir() if path.is_dir() and path.name != archive_dir.name
    )
    stale = review_dirs[:-keep]
    archived: list[Path] = []
    for path in stale:
        archive_dir.mkdir(parents=True, exist_ok=True)
        target = archive_dir / path.name
        index = 1
        while target.exists():
            target = archive_dir / f"{path.name}-{index:02d}"
            index += 1
        shutil.move(str(path), str(target))
        archived.append(target)
    return archived
