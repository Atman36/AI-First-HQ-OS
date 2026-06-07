#!/usr/bin/env python3
"""Reference-pattern analysis and a deterministic identifier scan.

This module supports a bounded analysis activity that distills adoptable
patterns from local reference projects into a narrow, generic spec, plus an
identifier scan that blocks any tracked or committed output from naming a
specific reference project.

Reference-project identifiers are NEVER hardcoded here. They are derived at
runtime from the git-ignored ``reports/reference-projects/`` directory, so the
tracked source of this module contains no project name (Requirement 10).
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

REPO_ROOT = Path(
    os.environ.get("HQ_REFERENCE_SCAN_REPO_ROOT", Path(__file__).resolve().parents[1])
).resolve()
REFERENCE_PROJECTS_DIR = REPO_ROOT / "reports" / "reference-projects"
PRIVATE_ROOT = Path(
    os.environ.get("HQ_RUNTIME_PRIVATE_ROOT", REPO_ROOT / ".hq")
).resolve()

# The five permission-governance primitives every distilled pattern must map to.
PRIMITIVES = (
    "permission_model",
    "decision_function",
    "pre_action_gate",
    "run_receipt",
    "release_gate",
)

# Tracked output that may legitimately contain the literal directory name.
SCAN_ALLOWED_PREFIXES = (
    "scripts/hq_reference_scan.py",
)

_TOKEN_SUFFIXES = ("-main", "-master", "_main", "_master")


def discover_reference_projects(base: Path = REFERENCE_PROJECTS_DIR) -> list[Path]:
    """Return reference-project directories, or an empty list when absent."""

    if not base.exists() or not base.is_dir():
        return []
    return sorted(item for item in base.iterdir() if item.is_dir())


def _identifier_tokens(dir_name: str) -> set[str]:
    """Derive identifying tokens from a reference-project directory name."""

    tokens: set[str] = set()
    name = dir_name.strip()
    if not name:
        return tokens
    tokens.add(name)
    stem = name
    for suffix in _TOKEN_SUFFIXES:
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    if stem and len(stem) >= 4:
        tokens.add(stem)
    return {token for token in tokens if len(token) >= 4}


def reference_identifiers(base: Path = REFERENCE_PROJECTS_DIR) -> set[str]:
    """Return the set of identifier tokens for all reference projects."""

    tokens: set[str] = set()
    for project in discover_reference_projects(base):
        tokens |= _identifier_tokens(project.name)
    return tokens


def analyze_reference_projects(base: Path = REFERENCE_PROJECTS_DIR) -> dict[str, Any]:
    """Record which reference projects are analyzable.

    Missing, empty, or unreadable projects are recorded as ``not_analyzed``
    with a reason; the activity continues across the remaining projects. This
    function intentionally returns project-identifying data for use only in
    private ``.hq/`` notes; it must not be written to a tracked path.
    """

    analyzed: list[str] = []
    not_analyzed: list[dict[str, str]] = []

    if not base.exists():
        return {"analyzed": [], "not_analyzed": [], "base_missing": True}

    for project in discover_reference_projects(base):
        try:
            entries = list(project.iterdir())
        except (PermissionError, OSError) as exc:
            not_analyzed.append({"project": project.name, "reason": f"unreadable: {exc}"})
            continue
        if not entries:
            not_analyzed.append({"project": project.name, "reason": "empty"})
            continue
        analyzed.append(project.name)

    return {"analyzed": analyzed, "not_analyzed": not_analyzed, "base_missing": False}


def _normalize(relative_path: Path | str) -> str:
    return PurePosixPath(relative_path).as_posix()


def _is_scan_allowed(normalized: str) -> bool:
    return normalized.startswith(SCAN_ALLOWED_PREFIXES)


def scan_text_for_identifiers(text: str, identifiers: set[str]) -> list[str]:
    """Return sorted identifier tokens found as whole words in ``text``."""

    found: set[str] = set()
    for token in identifiers:
        pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])", re.IGNORECASE)
        if pattern.search(text):
            found.add(token)
    return sorted(found)


def load_tracked_files(repo_root: Path) -> list[Path]:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    output = completed.stdout.decode("utf-8", errors="strict")
    return [Path(item) for item in output.split("\0") if item]


def scan_tracked_files(
    repo_root: Path = REPO_ROOT,
    identifiers: set[str] | None = None,
) -> list[str]:
    """Scan tracked files for reference-project identifiers.

    Returns a sorted list of violation messages. When no reference projects are
    present (and thus no identifiers), the scan is a no-op.
    """

    tokens = identifiers if identifiers is not None else reference_identifiers()
    if not tokens:
        return []

    violations: list[str] = []
    for relative_path in load_tracked_files(repo_root):
        normalized = _normalize(relative_path)
        if _is_scan_allowed(normalized):
            continue
        absolute = repo_root / relative_path
        try:
            text = absolute.read_text(encoding="utf-8")
        except (FileNotFoundError, IsADirectoryError, UnicodeDecodeError):
            continue
        found = scan_text_for_identifiers(text, tokens)
        if found:
            violations.append(
                f"{normalized}: contains reference-project identifier(s) "
                f"{', '.join(found)}; remove and replace with a generic descriptor"
            )
    return sorted(violations)


def has_git_metadata(repo_root: Path) -> bool:
    return (repo_root / ".git").exists()


def scan_command(args: argparse.Namespace) -> int:
    if not has_git_metadata(REPO_ROOT):
        print("reference_scan=skipped_no_git_metadata", flush=True)
        return 0
    try:
        violations = scan_tracked_files(REPO_ROOT)
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"[fail] reference-scan: {exc}", file=sys.stderr, flush=True)
        return 2
    if violations:
        print("[fail] reference-scan", flush=True)
        for violation in violations:
            print(f"- {violation}", flush=True)
        return 1
    print("reference_scan=ok", flush=True)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reference-pattern identifier scan for tracked output."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan", help="Scan tracked files for reference identifiers.")
    scan.set_defaults(func=scan_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
