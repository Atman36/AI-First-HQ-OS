---
name: hq-publication-safety
description: Use before committing, pushing, publishing, exporting, sharing, or making public any HQ repo change. Also use when checking that .hq, private docs, prospect data, secrets, credentials, raw imports, telemetry, or technical internal documentation are not leaking into GitHub.
---

# HQ Publication Safety

Use this skill as a thin operator wrapper around deterministic safety checks. Publication safety should be hook-first when possible; this skill tells the agent when to run and interpret the checks.

## Read First

- `AGENTS.md`
- `.gitignore`
- `scripts/hq_public_safety.py`
- `scripts/hq_policy_hooks.py` only when hook behavior is relevant
- `git status --short` from the HQ repo root, never from the home directory

## Trigger Shape

Use this skill for requests like:
- "commit this"
- "push this"
- "is this public-safe"
- "check for leaks"
- "can this go to GitHub"

## Default Workflow

1. Inspect the intended publication action: commit, push, public doc, export, or buyer-facing artifact.
2. Run the existing safety check for the touched surface. Prefer `python3 scripts/hq_public_safety.py --help` first if unsure about arguments.
3. Confirm forbidden paths remain untracked: `.hq/`, `02 Planning/`, `03 Notes/`, `04 Projects/`, private data folders, raw imports, telemetry, local reports, and ignored skill-reference downloads.
4. Check staged or tracked changes for secrets, credentials, prospect/customer data, raw operational artifacts, and internal technical documentation not approved for GitHub.
5. Block the publication if any private or policy-sensitive artifact is present.
6. Report the exact checks and the publication boundary decision.

## Guardrails

- This skill does not replace hooks, tests, or review. It is the manual safety wrapper.
- Never relax `.gitignore` to publish private HQ state unless the founder explicitly approves the exact file and reason.
- Technical documentation for internal operation should stay local unless explicitly approved for publication.
- Do not run `git status` in the user's home directory.

## Expected Output Shape

- Boundary call: safe / blocked
- Checked files:
- Commands run:
- Blockers:
- Next safe action:
