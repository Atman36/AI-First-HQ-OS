#!/usr/bin/env python3
"""Run the official HQ validation gate locally or in CI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def build_commands() -> list[tuple[str, list[str]]]:
    commands = [
        ("public-safety", [sys.executable, "scripts/hq_public_safety.py"]),
        ("instruction-lint", [sys.executable, "scripts/hq_instruction_lint.py"]),
        ("generated-check", [sys.executable, "scripts/hq_control_plane.py", "generated-check"]),
        ("ruff", [sys.executable, "-m", "ruff", "check", "--select", "F,E9", "scripts", "tests"]),
    ]
    if (REPO_ROOT / ".hq" / "prompts").exists():
        commands.append(("private-prompt-lint", [sys.executable, "scripts/hq_private_prompt_lint.py"]))
    commands.extend(
        [
            ("tests", [sys.executable, "-m", "unittest", "discover", "tests"]),
            ("control-plane", [sys.executable, "scripts/hq_control_plane.py", "validate"]),
        ]
    )
    return commands


def main() -> int:
    for name, command in build_commands():
        print(f"[run] {name}: {' '.join(command)}", flush=True)
        completed = subprocess.run(command, check=False)
        if completed.returncode != 0:
            print(f"[fail] {name}: exit_code={completed.returncode}", flush=True)
            return completed.returncode
    print("gate=ok", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
