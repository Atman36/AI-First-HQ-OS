#!/usr/bin/env python3
"""Block private runtime artifacts and obvious secrets from public git history."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath


REPO_ROOT = Path(
    os.environ.get("HQ_PUBLIC_SAFETY_REPO_ROOT", Path(__file__).resolve().parents[1])
).resolve()

BLOCKED_PATH_PREFIXES = (
    ".hq/",
    "private/",
    "private-data/",
    "user-data/",
    "customer-data/",
    "imports/raw/",
    "uploads/",
    "exports/",
    "datasets/",
    "billing/",
    "banking/",
    "contracts/",
    "prospects/",
    "customers/",
    "reports/deep-research/",
    "99 Archive/",
    "journals/",
    "03 Notes/Journals/",
    "03 Notes/Daily/",
    "03 Notes/Session Logs/",
)

BLOCKED_EXACT_PATHS = {
    "00 Home.md",
    "now.md",
    "projects.md",
    "routines.md",
    "stack.md",
}

BLOCKED_LIVE_STATE_DIRS = {
    "02 Planning": {"README.md"},
    "03 Notes": {"README.md"},
    "04 Projects": {"README.md"},
}

ALLOWED_EXACT_PATHS = {
    ".gitignore",
    "README.md",
    "AGENTS.md",
    "requirements-dev.txt",
}

ALLOWED_PATH_PREFIXES = (
    ".github/workflows/",
    "docs/",
    "scripts/",
    "skills/",
    "tests/",
    "05 AI Control Plane/schemas/",
)


def is_allowed_public_path(normalized: str) -> bool:
    if normalized in ALLOWED_EXACT_PATHS:
        return True

    if normalized.startswith(ALLOWED_PATH_PREFIXES):
        return True

    path_obj = PurePosixPath(normalized)
    if len(path_obj.parts) >= 3 and path_obj.parts[0] == "agents" and path_obj.name == "AGENTS.md":
        return True

    return False

BLOCKED_SUFFIXES = {
    ".sqlite",
    ".sqlite3",
    ".db",
    ".csv",
    ".tsv",
    ".xlsx",
    ".xls",
    ".numbers",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".har",
}

SECRET_PATTERNS = (
    ("openai", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("github", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("aws", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("google", re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")),
    ("slack", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("private-key", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
)


def normalize_relative_path(relative_path: Path | str) -> str:
    return PurePosixPath(relative_path).as_posix()


def load_tracked_files(repo_root: Path) -> list[Path]:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z"],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise RuntimeError("git ls-files failed; run this inside the repository")
    output = completed.stdout.decode("utf-8", errors="strict")
    return [Path(item) for item in output.split("\0") if item]


def path_violations(relative_path: Path | str) -> list[str]:
    normalized = normalize_relative_path(relative_path)
    violations: list[str] = []

    if normalized in BLOCKED_EXACT_PATHS:
        violations.append(f"{normalized}: blocked live operating state for public git history")

    path_obj = PurePosixPath(normalized)
    parent = str(path_obj.parent)
    if (
        parent in BLOCKED_LIVE_STATE_DIRS
        and path_obj.suffix.lower() == ".md"
        and path_obj.name not in BLOCKED_LIVE_STATE_DIRS[parent]
    ):
        violations.append(f"{normalized}: blocked live operating state for public git history")

    if any(
        normalized == prefix.rstrip("/") or normalized.startswith(prefix)
        for prefix in BLOCKED_PATH_PREFIXES
    ):
        violations.append(f"{normalized}: blocked private path for public git history")

    if not violations and not is_allowed_public_path(normalized):
        violations.append(f"{normalized}: path is outside the public GitHub allowlist")

    suffix = PurePosixPath(normalized).suffix.lower()
    if suffix in BLOCKED_SUFFIXES:
        violations.append(f"{normalized}: blocked sensitive local artifact type `{suffix}`")

    return violations


def content_violations(repo_root: Path, relative_path: Path | str) -> list[str]:
    absolute_path = repo_root / relative_path
    try:
        text = absolute_path.read_text(encoding="utf-8")
    except (FileNotFoundError, IsADirectoryError, UnicodeDecodeError):
        return []

    normalized = normalize_relative_path(relative_path)
    violations: list[str] = []
    for label, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            violations.append(f"{normalized}: detected potential {label} secret")
    return violations


def find_violations(repo_root: Path, tracked_files: list[Path]) -> list[str]:
    violations: list[str] = []
    for relative_path in tracked_files:
        violations.extend(path_violations(relative_path))
        violations.extend(content_violations(repo_root, relative_path))
    return sorted(set(violations))


def main() -> int:
    try:
        tracked_files = load_tracked_files(REPO_ROOT)
    except RuntimeError as error:
        print(f"[fail] public-safety: {error}", file=sys.stderr)
        return 2

    violations = find_violations(REPO_ROOT, tracked_files)
    if violations:
        print("[fail] public-safety", flush=True)
        for violation in violations:
            print(f"- {violation}", flush=True)
        return 1

    print("public_safety=ok", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
