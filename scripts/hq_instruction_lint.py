#!/usr/bin/env python3
"""Lint HQ prompts and skills for portability and required instruction structure."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


REPO_ROOT = Path(
    os.environ.get("HQ_INSTRUCTION_LINT_REPO_ROOT", Path(__file__).resolve().parents[1])
).resolve()
ABSOLUTE_PATH_RE = re.compile(r"(^|[\s`'\"])(/Users/[^`\s\"']+)")
CODE_SPAN_RE = re.compile(r"`([^`]+)`")
ROOT_REQUIRED_SECTIONS = (
    "## Instruction Precedence And Conflict Rule",
    "## Execution Mode",
)
ROLE_REQUIRED_SECTIONS = (
    "## Read First",
    "## Outputs",
    "## Rules",
)
SKILL_REQUIRED_SECTIONS = (
    "## Read First",
    "## Trigger Shape",
    "## Default Workflow",
    "## Guardrails",
    "## Expected Output Shape",
)


def iter_role_prompts(repo_root: Path) -> list[Path]:
    return sorted((repo_root / "agents").glob("*/AGENTS.md"))


def iter_skills(repo_root: Path) -> list[Path]:
    return sorted((repo_root / "skills").glob("*/SKILL.md"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def relative_to_repo(path: Path, repo_root: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def missing_sections(text: str, required_sections: tuple[str, ...]) -> list[str]:
    return [section for section in required_sections if section not in text]


def section_body(text: str, heading: str) -> str:
    lines = text.splitlines()
    target = heading.removeprefix("## ").strip()
    capture = False
    collected: list[str] = []
    for line in lines:
        if line.startswith("## "):
            current = line.removeprefix("## ").strip()
            if current == target:
                capture = True
                continue
            if capture:
                break
        if capture:
            collected.append(line)
    return "\n".join(collected).strip()


def has_absolute_path(text: str) -> bool:
    return ABSOLUTE_PATH_RE.search(text) is not None


def is_path_reference(token: str) -> bool:
    if token == "AGENTS.md":
        return True
    if token.startswith(".hq/"):
        return True
    if "/" in token:
        return True
    return token.endswith((".md", ".json", ".py", ".yaml", ".yml"))


def should_skip_reference(token: str) -> bool:
    if "<" in token or ">" in token:
        return True
    return token.startswith("python3 ")


def validate_references(repo_root: Path, source_path: Path, section_name: str) -> list[str]:
    body = section_body(read_text(source_path), section_name)
    errors: list[str] = []
    for token in CODE_SPAN_RE.findall(body):
        if not is_path_reference(token) or should_skip_reference(token):
            continue
        candidate = repo_root / token.rstrip("/")
        if not candidate.exists():
            errors.append(
                f"{relative_to_repo(source_path, repo_root)}: missing referenced path `{token}` in {section_name}"
            )
    return errors


def lint_root_prompt(repo_root: Path) -> list[str]:
    path = repo_root / "AGENTS.md"
    text = read_text(path)
    errors: list[str] = []

    for section in missing_sections(text, ROOT_REQUIRED_SECTIONS):
        errors.append(f"AGENTS.md: missing required section `{section}`")

    if has_absolute_path(text):
        errors.append("AGENTS.md: contains machine-specific absolute path")

    execution_body = section_body(text, "## Execution Mode")
    if execution_body:
        if "bundled blocker question" not in execution_body:
            errors.append("AGENTS.md: Execution Mode must cap clarification to one bundled blocker question")
        if "`wait`" not in execution_body or "`timeout_wait`" not in execution_body:
            errors.append("AGENTS.md: Execution Mode must define `wait` and `timeout_wait` behavior")

    return errors


def lint_role_prompt(repo_root: Path, path: Path) -> list[str]:
    text = read_text(path)
    rel_path = relative_to_repo(path, repo_root)
    errors: list[str] = []

    if has_absolute_path(text):
        errors.append(f"{rel_path}: contains machine-specific absolute path")

    for section in missing_sections(text, ROLE_REQUIRED_SECTIONS):
        errors.append(f"{rel_path}: missing required section `{section}`")

    read_first_body = section_body(text, "## Read First")
    if read_first_body and "`AGENTS.md`" not in read_first_body:
        errors.append(f"{rel_path}: Read First must include `AGENTS.md`")

    errors.extend(validate_references(repo_root, path, "## Read First"))
    return errors


def lint_skill(repo_root: Path, path: Path) -> list[str]:
    text = read_text(path)
    rel_path = relative_to_repo(path, repo_root)
    errors: list[str] = []

    if has_absolute_path(text):
        errors.append(f"{rel_path}: contains machine-specific absolute path")

    for section in missing_sections(text, SKILL_REQUIRED_SECTIONS):
        errors.append(f"{rel_path}: missing required section `{section}`")

    errors.extend(validate_references(repo_root, path, "## Read First"))
    return errors


def lint_repo(repo_root: Path = REPO_ROOT) -> list[str]:
    errors = lint_root_prompt(repo_root)
    for path in iter_role_prompts(repo_root):
        errors.extend(lint_role_prompt(repo_root, path))
    for path in iter_skills(repo_root):
        errors.extend(lint_skill(repo_root, path))
    return sorted(errors)


def main() -> int:
    errors = lint_repo(REPO_ROOT)
    if errors:
        print("[fail] instruction-lint", flush=True)
        for error in errors:
            print(f"- {error}", flush=True)
        return 1

    print("instruction_lint=ok", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
