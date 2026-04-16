# Stack

## Codex

- Purpose: direct work in the repository, implementation, analysis, structured editing
- Strengths: reads repo instructions, edits tracked files, can operate the control plane and scripts directly
- Limits: should not be treated as durable memory by itself

## Paperclip

- Purpose: optional future external coordinator for scheduled execution and persistent queues
- Strengths: orchestration across tools, reminders, scheduled runs
- Limits: do not depend on it for Stage 1; keep the current system viable without it

## HQ Control Plane

- Machine-readable queue: `05 AI Control Plane/active-work.json`
- Agent registry: `05 AI Control Plane/agent-registry.json`
- Policies: `05 AI Control Plane/operating-policies.json`
- Workflows: `05 AI Control Plane/workflow-registry.json`
- Metrics: `05 AI Control Plane/metrics-registry.json`

## Runtime Scripts

- `python3 scripts/hq_control_plane.py validate`
- `python3 scripts/hq_control_plane.py sync`
- `python3 scripts/hq_runtime.py bootstrap`
- `python3 scripts/hq_runtime.py probe ...`
- `python3 scripts/hq_telemetry.py event ...`
- `python3 scripts/hq_telemetry.py weekly-metrics ...`

## Rule Of Use

- Update `active-work.json` first for delegated task-state changes.
- Render `Task Board.md` from the control plane instead of editing it manually.
- Use AI as the default operator only within autonomy tiers and risk policy.
- Use AI Operations Lead for orchestration, observability, weekly metric review, eval follow-through, memory hygiene, and runtime-quality escalation.
- Use Governor for policy checks, approval gates, and rollback triggers.
- Escalate strategy, budget, legal/public, destructive, hiring, or policy overrides to CEO.
- Confirm local tool availability before routing through a specific CLI or runner.
- Record private runtime state only under `.hq/`.

## Capability Probe

- Use `python3 scripts/hq_runtime.py probe ...` as the cheap check before routing a workflow through `codex`, `claude`, or another local runner.
- A tool is usable only after it is both visible in `PATH` and responsive to a cheap probe such as `--help`.

## Private Runtime Contract

- `.hq/handoffs/` stores private task continuity.
- `.hq/telemetry/` stores structured execution events.
- `.hq/reflections/` stores per-task lessons.
- `.hq/improvements/` stores weekly synthesis artifacts.
- `.hq/evals/` stores eval datasets and run outputs.
- `.hq/releases/` stores rollout and rollback notes.

## Public GitHub Boundary

- Tracked history is for system files, agent instructions, skills, scripts, and accepted company truth.
- User data, customer data, raw imports, credentials, transcripts, and payment exports must stay under `.hq/` or outside this repository.
- If deeper founder memory is added later, keep raw imports private and promote only derived summaries into tracked truth.

## Founder Working Defaults

- Default language: Russian
- Default response style: direct, concrete, concise
- Default decision support: prefer 2-3 concrete options with a clear recommendation
- Default execution bias: ship one well-governed slice before adding more automation
