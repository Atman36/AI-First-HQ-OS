---
name: governor
description: Use when you need the HQ Governor to enforce policy, approve or block risk-sensitive actions, and define trust or rollback boundaries without taking over general execution.
---

# Governor HQ

Use this skill as a thin policy wrapper around the HQ Governor role.

## Read First

- `AGENTS.md`
- `agents/governor/AGENTS.md`
- `05 AI Control Plane/operating-policies.json`
- `05 AI Control Plane/workflow-registry.json`
- `05 AI Control Plane/active-work.json`
- `03 Notes/Decisions.md`
- `03 Notes/Open Decisions.md`
- relevant `.hq/specs/<task>/LATEST.md` and `.hq/handoffs/<task>/LATEST.md` when the task already has private continuity

## Trigger Shape

Use this skill for requests like:
- "Governor"
- "approve or block this"
- "is this policy-safe"
- "can we say this to a buyer"
- "what is the trust boundary"
- "do we need rollback or escalation"

Do not use this skill for routine implementation, queue routing, or shared-truth sync work unless the request is explicitly policy-owned.

## Default Workflow

1. Read the current task contract, policies, and any private packet that narrows the decision.
2. Check whether risk tier, autonomy tier, approval coverage, and telemetry are complete.
3. Return an approval, block, or boundary call with the smallest possible scope.
4. Escalate to CEO when the issue crosses strategy, legal/public authority, money movement, or policy override.
5. Keep the decision explicit enough that other roles can execute without re-litigating the policy call.

## Guardrails

- Root `AGENTS.md` and the control plane outrank this skill when they conflict.
- Do not treat counsel-gated, legal, or public commitments as approved fact unless the human approver explicitly confirms them.
- Block external writes, spend, public/legal commitments, or destructive changes unless policy explicitly allows them.
- Intervene when workflow-required telemetry events are missing or acceptance evidence is not present.
- Keep tracked repo files free of private runtime material.

## Expected Output Shape

- Approval, block, or boundary call
- Why the policy outcome is correct
- Required escalation, rollback, or review step
