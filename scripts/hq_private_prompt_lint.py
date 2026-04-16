#!/usr/bin/env python3
"""Lint private `.hq/prompts/` files for path safety and audit quality."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


REPO_ROOT = Path(
    os.environ.get("HQ_PRIVATE_PROMPT_LINT_REPO_ROOT", Path(__file__).resolve().parents[1])
).resolve()
PROMPTS_DIR = REPO_ROOT / ".hq" / "prompts"
CODE_SPAN_RE = re.compile(r"`([^`]+)`")
SECTION_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
KNOWN_PATH_PREFIXES = (
    ".hq/",
    "AGENTS.md",
    "README.md",
    "now.md",
    "projects.md",
    "routines.md",
    "stack.md",
    "agents/",
    "scripts/",
    "tests/",
    "01 Operating System/",
    "02 Planning/",
    "03 Notes/",
    "04 Projects/",
    "05 AI Control Plane/",
)
COMMAND_PREFIXES = (
    "python3 ",
    "git ",
    "find ",
    "sed ",
    "rg ",
    "ls ",
)
PROMPT_REQUIRED_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "audit",
        (
            "## Role",
            "## Input Boundary",
            "## Core Objective",
            "## Evidence Discipline",
            "## How To Work",
            "## Required Output",
        ),
    ),
    (
        "import",
        (
            "## Objective",
            "## Files To Potentially Update",
            "## Rules",
            "## What To Deliver In Chat",
        ),
    ),
    (
        "remediation",
        (
            "## Task",
            "## Goal",
            "## Rules",
            "## Validation",
            "## Final Report",
        ),
    ),
)
AUDIT_FEEDBACK_GROUPS = (
    ("prompt feedback loop", "feedback loop"),
    ("founder", "founder experience"),
    ("question", "question drag"),
    ("long", "long-session", "long session"),
    ("wait", "`wait`", "`timeout_wait`", "subagent waiting"),
)


def iter_prompt_files(repo_root: Path = REPO_ROOT) -> list[Path]:
    prompts_dir = repo_root / ".hq" / "prompts"
    if not prompts_dir.exists():
        return []
    return sorted(prompts_dir.glob("*.md"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def relative_to_repo(path: Path, repo_root: Path = REPO_ROOT) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def profile_for(path: Path) -> str | None:
    name = path.name.lower()
    if "audit" in name:
        return "audit"
    if "import" in name:
        return "import"
    if "remediation" in name:
        return "remediation"
    return None


def missing_sections(text: str, required_sections: tuple[str, ...]) -> list[str]:
    return [section for section in required_sections if section not in text]


def should_skip_token(token: str) -> bool:
    stripped = token.strip()
    if not stripped:
        return True
    if "\n" in stripped:
        return True
    if stripped.startswith(("http://", "https://")):
        return True
    if any(stripped.startswith(prefix) for prefix in COMMAND_PREFIXES):
        return True
    if any(marker in stripped for marker in ("<", ">", "{", "}", "*")):
        return True
    return False


def is_path_reference(token: str) -> bool:
    stripped = token.strip()
    if stripped.startswith("/"):
        return True
    if stripped.startswith(KNOWN_PATH_PREFIXES):
        return True
    return stripped.endswith((".md", ".json", ".py", ".yaml", ".yml"))


def resolve_reference(token: str, repo_root: Path) -> Path | None:
    stripped = token.strip()
    if stripped.startswith(str(repo_root)):
        return Path(stripped)
    if stripped.startswith("/"):
        return None
    return repo_root / stripped


def validate_paths(path: Path, repo_root: Path = REPO_ROOT) -> list[str]:
    errors: list[str] = []
    for token in CODE_SPAN_RE.findall(read_text(path)):
        if should_skip_token(token) or not is_path_reference(token):
            continue
        target = resolve_reference(token, repo_root)
        if target is None:
            errors.append(
                f"{relative_to_repo(path, repo_root)}: invalid absolute path `{token}` outside repo root"
            )
            continue
        if not target.exists():
            reference_type = "absolute" if token.strip().startswith("/") else "repo-relative"
            errors.append(
                f"{relative_to_repo(path, repo_root)}: missing {reference_type} path `{token}`"
            )
    return errors


def validate_sections(path: Path) -> list[str]:
    text = read_text(path)
    profile = profile_for(path)
    if profile is None:
        return []

    required_sections = dict(PROMPT_REQUIRED_SECTIONS)[profile]
    return [
        f"{relative_to_repo(path)}: missing required section `{section}`"
        for section in missing_sections(text, required_sections)
    ]


def validate_audit_feedback_loop(path: Path) -> list[str]:
    if profile_for(path) != "audit":
        return []

    text = read_text(path).lower()
    if ".hq/prompts" not in text:
        return [f"{relative_to_repo(path)}: audit prompt must mention `.hq/prompts` availability"]

    missing_groups = [
        label
        for label, *variants in AUDIT_FEEDBACK_GROUPS
        if not any(variant.lower() in text for variant in variants)
    ]
    if missing_groups:
        return [
            f"{relative_to_repo(path)}: audit prompt feedback loop is missing {', '.join(missing_groups)}"
        ]
    return []


def lint_private_prompts(repo_root: Path = REPO_ROOT) -> list[str]:
    if not (repo_root / ".hq" / "prompts").exists():
        return []

    errors: list[str] = []
    for path in iter_prompt_files(repo_root):
        errors.extend(validate_paths(path, repo_root))
        errors.extend(validate_sections(path))
        errors.extend(validate_audit_feedback_loop(path))
    return sorted(errors)


def main() -> int:
    if not PROMPTS_DIR.exists():
        print("private_prompt_lint=skipped", flush=True)
        return 0

    errors = lint_private_prompts(REPO_ROOT)
    if errors:
        print("[fail] private-prompt-lint", flush=True)
        for error in errors:
            print(f"- {error}", flush=True)
        return 1

    print("private_prompt_lint=ok", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
