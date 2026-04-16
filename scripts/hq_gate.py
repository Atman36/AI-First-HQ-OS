#!/usr/bin/env python3
"""Run the official HQ validation gate locally or in CI."""

from __future__ import annotations

import subprocess
import sys


COMMANDS = [
    ("public-safety", [sys.executable, "scripts/hq_public_safety.py"]),
    ("instruction-lint", [sys.executable, "scripts/hq_instruction_lint.py"]),
    ("tests", [sys.executable, "-m", "unittest", "discover", "tests"]),
    ("control-plane", [sys.executable, "scripts/hq_control_plane.py", "validate"]),
]


def main() -> int:
    for name, command in COMMANDS:
        print(f"[run] {name}: {' '.join(command)}", flush=True)
        completed = subprocess.run(command, check=False)
        if completed.returncode != 0:
            print(f"[fail] {name}: exit_code={completed.returncode}", flush=True)
            return completed.returncode
    print("gate=ok", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
