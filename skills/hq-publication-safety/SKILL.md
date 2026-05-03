---
name: hq-publication-safety
description: Use before committing, pushing, publishing, exporting, sharing, or making public any HQ repo change. Also use when checking that .hq, private docs, prospect data, secrets, credentials, raw imports, telemetry, or technical internal documentation are not leaking into GitHub.
---

# HQ Publication Safety

Use this skill as a thin operator wrapper around deterministic safety checks. Publication safety is **hook-first**: the `pre-commit` git hook runs `scripts/hq_public_safety.py` automatically on every commit and blocks before git can write the object. This skill is the manual fallback and the interpreter for hook output.

## Hook-First Layer

The canonical enforcement path is the git hook, not this skill:

```
scripts/hooks/pre-commit   ← tracked source of truth for the hook
scripts/install_hq_hooks.sh ← run once to install into .git/hooks/
```

Install once per checkout:
```bash
bash scripts/install_hq_hooks.sh
```

After installation every `git commit` automatically runs `python3 scripts/hq_public_safety.py` and blocks if violations exist. The hook is non-interactive: it prints the blocking violations and exits non-zero.

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
2. Confirm the hook is installed: `ls .git/hooks/pre-commit`. If absent, run `bash scripts/install_hq_hooks.sh` first.
3. Run the manual check if needed: `python3 scripts/hq_public_safety.py`.
4. Confirm forbidden paths remain untracked: `.hq/`, `02 Planning/`, `03 Notes/`, `04 Projects/`, private data folders, raw imports, telemetry, local reports, and ignored skill-reference downloads.
5. Check staged or tracked changes for secrets, credentials, prospect/customer data, raw operational artifacts, and internal technical documentation not approved for GitHub.
6. Block the publication if any private or policy-sensitive artifact is present.
7. Report the exact checks and the publication boundary decision.

## Guardrails

- The hook is the first line of defense; this skill is the manual fallback and does not replace it.
- Never relax `.gitignore` to publish private HQ state unless the founder explicitly approves the exact file and reason.
- Technical documentation for internal operation should stay local unless explicitly approved for publication.
- Do not run `git status` in the user's home directory.

## Expected Output Shape

- Hook status: installed / absent
- Boundary call: safe / blocked
- Checked files:
- Commands run:
- Blockers:
- Next safe action:
