# HQ Shared Instructions

This repository is the shared root for the HQ system.

It now has three operating layers:

1. human-readable company truth in Markdown;
2. a machine-readable AI control plane under `05 AI Control Plane/`;
3. a private runtime under `.hq/`.

## Source Of Truth

### Strategic truth

These files define the current company truth for humans:

1. `now.md`
2. `projects.md`
3. `routines.md`
4. `stack.md`
5. `agents/`
6. `03 Notes/Decisions.md`
7. `03 Notes/Open Decisions.md`

### Machine-readable control plane

These files define delegated authority and active AI-executable work:

1. `05 AI Control Plane/active-work.json`
2. `05 AI Control Plane/agent-registry.json`
3. `05 AI Control Plane/operating-policies.json`
4. `05 AI Control Plane/workflow-registry.json`
5. `05 AI Control Plane/metrics-registry.json`

### Human-readable working layer

These files make the control plane legible for humans:

1. `02 Planning/Task Board.md` - rendered mirror of `active-work.json`
2. `02 Planning/Weekly Plan.md` - weekly commitments, review, and carry-forward
3. `04 Projects/` - project-local detail, risks, dependencies, and support inputs

### Support material

- `reports/` is support input, not source of truth.
- Reports change company state only after the conclusion is summarized into a tracked source-of-truth file.
- Private runtime artifacts stay only under `.hq/`.
- User or customer data is never valid tracked source of truth in this repository.
- If a file contains personal data, customer data, imported workspace data, credentials, payment exports, or raw transcripts, it must stay under `.hq/` or outside this repository.

## File Contract

- `now.md` holds company focus, not a second task list.
- `projects.md` is the registry of active projects and owners.
- `05 AI Control Plane/active-work.json` is the machine-readable queue for delegated work.
- `02 Planning/Task Board.md` is the human-readable mirror of that queue and should be rendered, not hand-maintained.
- `02 Planning/Weekly Plan.md` holds weekly commitments, review, and carry-forward decisions.
- `03 Notes/Decisions.md` records durable why after a decision is made.
- `03 Notes/Open Decisions.md` records explicit unresolved choices that block safe autonomy or scaling.
- `04 Projects/` holds project-local context, execution detail, and risks that would clutter the root.

## AI-First Operating Rules

- AI is the default operator for low- and medium-risk work only when the task has an owner, accepting role, risk tier, autonomy tier, workflow, and primary update file.
- Humans retain strategy, budget, legal, public, destructive, hiring, and override authority.
- Governor can block or pause work that lacks policy coverage, telemetry, or approval.
- AI Operations Lead owns orchestration quality: queue health, telemetry discipline, weekly metric review, eval follow-through, memory hygiene, and runtime-quality escalation.
- Do not let two agents edit the same file at the same time.
- Shared docs describe company state, not private scratchpads.
- Keep tracked Git history limited to system files, instructions, skills, scripts, and accepted shared truth; do not commit private user or customer data.
- Use `.hq/handoffs/` for task-scoped private continuity.
- Make a git commit when you change system files, scripts, or agent prompts; ordinary source-of-truth Markdown updates do not require a commit unless the user explicitly asks for one.
- Never commit private user data, customer data, raw imports, credentials, payment artifacts, or other private runtime material.

## Coordination Rules

- Change `05 AI Control Plane/active-work.json` first when delegated task state changes.
- Re-render `02 Planning/Task Board.md` with `python3 scripts/hq_control_plane.py sync` after material task-state changes.
- Confirm local tool availability before routing a workflow through a specific CLI or runner.
- Route orchestration, weekly metric review, telemetry coverage, eval discipline, memory hygiene, and runtime-quality issues through AI Operations Lead.
- Escalate strategic, financial, legal, public, destructive, or policy-changing work to CEO.
- Route policy, risk, and approval work through Governor.
- Keep outputs short, operational, and easy to hand off.

## Private Improvement Loop

- Use `.hq/reflections/` and `.hq/improvements/` only as private runtime artifacts.
- Use `.hq/telemetry/` for structured execution events.
- Use `.hq/evals/` for eval runs and `.hq/releases/` for rollout notes.
- Do not auto-edit `AGENTS.md`, `agents/*/AGENTS.md`, access rules, safety rules, or production logic from the improvement loop.
- Candidate improvements remain review artifacts until applied manually.

## Default Routing

- CEO: strategy, approvals, high-risk decisions, overrides.
- AI Operations Lead: intake, decomposition, routing, sequencing, queue state, observability, weekly metric review, eval discipline, memory hygiene, runtime quality.
- Governor: risk review, guardrails, approvals, rollback triggers, policy exceptions.
- Delivery: bounded implementation and execution.
- Documentation: shared truth sync after acceptance.
- Assistant, Finance, Growth, and Research: bounded specialist support.

## Current Team

- CEO
- AI Operations Lead
- Governor
- Delivery
- Documentation
- Assistant
- Finance
- Growth
- Research

## Directory Convention

- Root files describe company state and operating rhythm.
- `05 AI Control Plane/` holds machine-readable state, workflows, policies, and metrics.
- `agents/<role>/AGENTS.md` contains the role prompt.
- `.hq/` is the only repo-local private runtime path and must remain git-ignored.
- User files, customer files, raw imports, and private operating data stay only under `.hq/` or outside the repo; they do not belong in future public GitHub history.
- `reports/` remains reference material only until summarized into tracked truth.
