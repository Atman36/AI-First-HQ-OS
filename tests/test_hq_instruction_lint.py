import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "hq_instruction_lint.py"


def load_module(temp_root: Path):
    os.environ["HQ_INSTRUCTION_LINT_REPO_ROOT"] = str(temp_root)
    spec = importlib.util.spec_from_file_location("hq_instruction_lint_test_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class HqInstructionLintTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_dir.name)
        self.write_file(
            "AGENTS.md",
            """# HQ

## Instruction Precedence And Conflict Rule

- `AGENTS.md` wins over lower layers.

## Execution Mode

- Ask one bundled blocker question at most.
- Use `wait` or `timeout_wait`.
""",
        )
        self.write_file("now.md", "# Now\n")
        self.write_file("projects.md", "# Projects\n")
        self.write_file("stack.md", "# Stack\n")
        self.write_file("03 Notes/Inbox.md", "# Inbox\n")
        self.write_file("03 Notes/Decisions.md", "# Decisions\n")
        self.write_file("03 Notes/Open Decisions.md", "# Open Decisions\n")
        self.write_file("04 Projects/README.md", "# Projects\n")
        self.write_file("05 AI Control Plane/active-work.json", "{}\n")
        self.write_file("05 AI Control Plane/operating-policies.json", "{}\n")
        self.write_file("agents/ceo/AGENTS.md", self.valid_role_prompt())
        self.write_file("skills/ceo/SKILL.md", self.valid_skill())
        self.module = load_module(self.temp_root)

    def tearDown(self):
        os.environ.pop("HQ_INSTRUCTION_LINT_REPO_ROOT", None)
        self.temp_dir.cleanup()

    def write_file(self, relative_path: str, content: str) -> None:
        path = self.temp_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def valid_role_prompt(self) -> str:
        return """You are the CEO.

## Read First

- `AGENTS.md`
- `now.md`
- `projects.md`
- `05 AI Control Plane/active-work.json`

## Outputs

- A recommendation

## Rules

- Follow the control plane.
"""

    def valid_skill(self) -> str:
        return """---
name: ceo
description: CEO skill.
---

# CEO

## Read First

- `AGENTS.md`
- `agents/ceo/AGENTS.md`
- `05 AI Control Plane/active-work.json`
- relevant `.hq/specs/<task>/LATEST.md`

## Trigger Shape

- "what next"

## Default Workflow

1. Restate the objective.

## Guardrails

- Use one bundled blocker question at most.

## Expected Output Shape

- Current call
"""

    def test_valid_repo_passes(self):
        self.assertEqual(self.module.lint_repo(self.temp_root), [])

    def test_root_missing_execution_mode_fails(self):
        self.write_file(
            "AGENTS.md",
            """# HQ

## Instruction Precedence And Conflict Rule

- Present.
""",
        )

        errors = self.module.lint_repo(self.temp_root)

        self.assertTrue(any("missing required section `## Execution Mode`" in error for error in errors))

    def test_role_prompt_requires_root_agents_and_no_absolute_paths(self):
        self.write_file(
            "agents/ceo/AGENTS.md",
            """You are the CEO.

## Read First

- `/Users/Apple/Documents/HQ/now.md`

## Outputs

- A recommendation

## Rules

- Follow the control plane.
""",
        )

        errors = self.module.lint_repo(self.temp_root)

        self.assertTrue(any("contains machine-specific absolute path" in error for error in errors))
        self.assertTrue(any("Read First must include `AGENTS.md`" in error for error in errors))

    def test_role_prompt_missing_required_section_fails(self):
        self.write_file(
            "agents/ceo/AGENTS.md",
            """You are the CEO.

## Read First

- `AGENTS.md`

## Rules

- Follow the control plane.
""",
        )

        errors = self.module.lint_repo(self.temp_root)

        self.assertTrue(any("missing required section `## Outputs`" in error for error in errors))

    def test_missing_referenced_path_fails(self):
        self.write_file(
            "skills/ceo/SKILL.md",
            """---
name: ceo
description: CEO skill.
---

# CEO

## Read First

- `AGENTS.md`
- `agents/ceo/AGENTS.md`
- `missing.md`

## Trigger Shape

- "what next"

## Default Workflow

1. Restate the objective.

## Guardrails

- Use one bundled blocker question at most.

## Expected Output Shape

- Current call
""",
        )

        errors = self.module.lint_repo(self.temp_root)

        self.assertTrue(any("missing referenced path `missing.md`" in error for error in errors))

    def test_skill_rejects_extra_root_docs_and_unknown_entries(self):
        self.write_file("skills/ceo/README.md", "# Extra doc\n")
        self.write_file("skills/ceo/helpers/tool.py", "print('nope')\n")

        errors = self.module.lint_repo(self.temp_root)

        self.assertTrue(any("skills/ceo/README.md" in error for error in errors))
        self.assertTrue(any("skills/ceo/helpers" in error for error in errors))

    def test_skill_requires_compact_skill_markdown(self):
        oversized_body = "\n".join(f"- Line {index}" for index in range(300))
        self.write_file(
            "skills/ceo/SKILL.md",
            f"""---
name: ceo
description: CEO skill.
---

# CEO

## Read First

- `AGENTS.md`

## Trigger Shape

- "what next"

## Default Workflow

1. Restate the objective.

## Guardrails

- Use one bundled blocker question at most.

## Expected Output Shape

{oversized_body}
""",
        )

        errors = self.module.lint_repo(self.temp_root)

        self.assertTrue(any("SKILL.md must stay compact" in error for error in errors))
