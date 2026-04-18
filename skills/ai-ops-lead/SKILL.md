---
name: ai-ops-lead
description: Shortcut alias for the HQ AI Operations Lead skill when the caller uses the shorter `ai-ops-lead` form.
---

# AI Ops Lead Alias

Use this skill as a short alias for the main AI Operations Lead role skill.

## Read First

- `AGENTS.md`
- `skills/ai-operations-lead/SKILL.md`
- `agents/ai-operations-lead/AGENTS.md`

## Trigger Shape

Use this skill for requests like:
- "ai-ops-lead"
- "@ai-ops-lead"
- "route the next slice"

Do not use this alias when a more specific specialist role is clearly the better fit.

## Default Workflow

1. Use `$ai-operations-lead` as the primary role skill.
2. Follow the main AI Operations Lead workflow instead of inventing alias-specific behavior.
3. Keep outputs and guardrails identical to the main role skill.

## Guardrails

- This alias exists only to shorten invocation.
- Root `AGENTS.md` and the main AI Operations Lead skill outrank this wrapper when they conflict.
- Do not fork behavior between the alias and the main skill.

## Expected Output Shape

- Same output shape as `$ai-operations-lead`
