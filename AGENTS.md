# HQ Shared Instructions

This repository is the shared root for the HQ system.

It now has three operating layers:

1. human-readable company truth in local Markdown;
2. a machine-readable AI control plane under `05 AI Control Plane/`;
3. a private runtime under `.hq/`.

## Source Of Truth

### Strategic truth

These files define the current company truth for humans, but they are local-only and must not be pushed to public GitHub:

1. `now.md`
2. `projects.md`
3. `routines.md`
4. `stack.md`
5. `agents/`
6. `03 Notes/Decisions.md`
7. `03 Notes/Open Decisions.md`

### Machine-readable control plane

These files define delegated authority and active AI-executable work locally. In public GitHub, only schemas belong in tracked history:

1. `05 AI Control Plane/active-work.json`
2. `05 AI Control Plane/agent-registry.json`
3. `05 AI Control Plane/operating-policies.json`
4. `05 AI Control Plane/workflow-registry.json`
5. `05 AI Control Plane/metrics-registry.json`

### Human-readable working layer

These files make the control plane legible for humans, but they are local-only and must not be pushed to public GitHub:

1. `02 Planning/Task Board.md` - rendered mirror of `active-work.json`
2. `02 Planning/Weekly Plan.md` - weekly commitments, review, and carry-forward
3. `04 Projects/` - project-local detail, risks, dependencies, and support inputs

### Support material

- `reports/` is support input, not source of truth.
- Reports change company state only after the conclusion is summarized into the local source-of-truth files.
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
- AI should make low- and medium-risk operating decisions by default when they fit current strategy and policy; the founder is the override path, not the routine decision bottleneck.
- Humans retain strategy, budget, legal, public, destructive, hiring, and override authority.
- Governor can block or pause work that lacks policy coverage, telemetry, or approval.
- AI Operations Lead owns orchestration quality: queue health, telemetry discipline, weekly metric review, eval follow-through, memory hygiene, and runtime-quality escalation.
- AI Operations Lead also owns cross-session continuity: for large work, leave a private spec in `.hq/specs/` and keep the execution handoff in `.hq/handoffs/` so the next session reads the narrow packet first instead of reconstructing context from scratch.
- Do not let two agents edit the same file at the same time.
- Shared docs describe company state, not private scratchpads.
- Keep tracked Git history limited to prompts, scripts, tests, CI files, schemas, and minimal repo metadata. Everything else is local-only unless explicitly approved for publication.
- Use `.hq/specs/` for large-task private context packets and `.hq/handoffs/` for task-scoped private continuity.
- When deeper external analysis is required, the system may request founder-run Deep Research or GPT 5.4 Pro packets; only accepted conclusions belong in HQ state.
- Make a git commit when you change scripts, agent prompts, agent skills, plugins, or other tracked system files. If a task changes only local operating docs or other untracked private material, do not make a repo commit unless the user explicitly asks for one.
- Never commit private user data, customer data, raw imports, credentials, payment artifacts, or other private runtime material.

## Instruction Precedence And Conflict Rule

- When instructions conflict, use this order:
  1. platform / system / developer constraints outside the repo;
  2. `AGENTS.md`;
  3. current machine-readable control-plane contracts in `05 AI Control Plane/`;
  4. task-scoped private packet in `.hq/specs/<task>/LATEST.md` and `.hq/handoffs/<task>/LATEST.md`;
  5. the active role prompt in `agents/<role>/AGENTS.md`;
  6. current project and notes files;
  7. skills as convenience wrappers only;
  8. historical reviews and archived notes last.
- When a task, policy, workflow, autonomy tier, risk tier, or acceptance field exists in the control plane, the control plane wins over prose summaries.
- Skills may narrow entry behavior, but they may not override higher-level rules.
- Historical or archived notes may inform context, but they do not override current control-plane or current project truth.

## Execution Mode

- Default to best-effort execution with the current accepted strategy and policy. Do not ask a clarifying question unless the work is blocked by missing access, irreversible risk, or a truly unresolved fork that the current HQ state does not answer.
- If a question is required, ask one bundled blocker question at most; do not drip-feed clarification requests.
- Work long by default: keep moving until the current slice is complete, blocked by policy or access, or reduced to a clear founder-only decision.
- When using subagents or long-running tools, choose one of two modes:
  - `wait`: wait for the result and continue the orchestration yourself;
  - `timeout_wait`: wait for a bounded interval, then write the partial result or blocker into `.hq/handoffs/<task>/LATEST.md` and continue everything else that is unblocked.
- Do not return control to the founder only because a subagent or long-running tool is still working.
- For large or ambiguous work, create or refresh `.hq/specs/<task>/LATEST.md` before splitting execution across agents or sessions.

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
- Finance, Growth, and Research: bounded specialist support.
- Assistant: optional non-standing helper for inbox cleanup and task shaping when AI Operations Lead explicitly needs it.

## Current Team

- CEO
- AI Operations Lead
- Governor
- Delivery
- Documentation
- Finance
- Growth
- Research

Assistant remains available as a non-standing helper for inbox hygiene bursts and messy inbound cleanup.

## Directory Convention

- Root files describe company state and operating rhythm locally; public Git history should not include the live root state files.
- `05 AI Control Plane/` holds machine-readable state, workflows, policies, and metrics.
- `agents/<role>/AGENTS.md` contains the role prompt.
- `.hq/` is the only repo-local private runtime path and must remain git-ignored.
- User files, customer files, raw imports, and private operating data stay only under `.hq/` or outside the repo; they do not belong in future public GitHub history.
- `reports/` remains reference material only until summarized into local truth.
