import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "hq_private_prompt_lint.py"


def load_module(temp_root: Path):
    os.environ["HQ_PRIVATE_PROMPT_LINT_REPO_ROOT"] = str(temp_root)
    spec = importlib.util.spec_from_file_location("hq_private_prompt_lint_test_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class HqPrivatePromptLintTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_dir.name)
        self.write_file("AGENTS.md", "# HQ\n")
        self.write_file("README.md", "# README\n")
        self.write_file("scripts/hq_gate.py", "print('ok')\n")
        self.write_file(".hq/prompts/repo-audit-prompt.md", self.valid_audit_prompt())
        self.module = load_module(self.temp_root)

    def tearDown(self):
        os.environ.pop("HQ_PRIVATE_PROMPT_LINT_REPO_ROOT", None)
        self.temp_dir.cleanup()

    def write_file(self, relative_path: str, content: str) -> None:
        path = self.temp_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def valid_audit_prompt(self) -> str:
        return f"""# Audit Prompt

## Role

Audit the repository.

## Input Boundary

- Use `{self.temp_root / 'AGENTS.md'}`

## Core Objective

- Produce a repository audit.

## Evidence Discipline

- If `.hq/prompts/` is available, include a prompt feedback loop that covers founder experience, question drag, long-session persistence, and `wait` / `timeout_wait` behavior.

## How To Work

- Read `AGENTS.md`
- Read `README.md`
- Inspect `scripts/hq_gate.py`

## Required Output

- Summary
"""

    def test_valid_private_audit_prompt_passes(self):
        self.assertEqual(self.module.lint_private_prompts(self.temp_root), [])

    def test_missing_audit_feedback_loop_fails(self):
        self.write_file(
            ".hq/prompts/repo-audit-prompt.md",
            """# Audit Prompt

## Role

Audit the repository.

## Input Boundary

- Use `AGENTS.md`

## Core Objective

- Produce a repository audit.

## Evidence Discipline

- Keep conclusions concrete.

## How To Work

- Read `AGENTS.md`

## Required Output

- Summary
""",
        )

        errors = self.module.lint_private_prompts(self.temp_root)

        self.assertTrue(
            any(
                "must mention `.hq/prompts` availability" in error
                or "feedback loop is missing" in error
                for error in errors
            )
        )

    def test_invalid_root_relative_path_fails(self):
        self.write_file(
            ".hq/prompts/session-remediation.md",
            """# Prompt

## Task

- Continue work from `/.hq/audits/latest/`

## Goal

- Finish the slice.

## Rules

- Follow `AGENTS.md`

## Validation

- Run `scripts/hq_gate.py`

## Final Report

- Summary
""",
        )

        errors = self.module.lint_private_prompts(self.temp_root)

        self.assertTrue(any("invalid absolute path `/.hq/audits/latest/`" in error for error in errors))
