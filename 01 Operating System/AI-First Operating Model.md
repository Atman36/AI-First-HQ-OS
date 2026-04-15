# AI-First Operating Model

## Purpose

Turn HQ from a Markdown coordination vault into a company operating system where AI is the default operator for low- and medium-risk work, while humans keep strategy, budget, legal/public commitments, and override authority.

## Layers

### 1. Strategic truth

- `now.md`
- `projects.md`
- `routines.md`
- `stack.md`
- `03 Notes/Decisions.md`
- `03 Notes/Open Decisions.md`

### 2. Machine-readable control plane

- `05 AI Control Plane/active-work.json`
- `05 AI Control Plane/agent-registry.json`
- `05 AI Control Plane/operating-policies.json`
- `05 AI Control Plane/workflow-registry.json`
- `05 AI Control Plane/metrics-registry.json`

### 3. Human-readable execution surfaces

- `02 Planning/Task Board.md`
- `02 Planning/Weekly Plan.md`
- `04 Projects/`

### 4. Private runtime

- `.hq/handoffs/`
- `.hq/telemetry/`
- `.hq/reflections/`
- `.hq/improvements/`
- `.hq/evals/`
- `.hq/releases/`

## Human vs AI Roles

### Human roles

- CEO: strategy, priorities, budget, legal/public commitments, policy overrides
- Founder or domain reviewer: escalation and ground truth on risk-sensitive edge cases

### AI roles

- AI Operations Lead: intake, routing, decomposition, queue management, observability, weekly metric review, eval discipline, memory hygiene, runtime quality
- Governor: policy enforcement, approvals, kill switches, rollback triggers
- Delivery: implementation and execution
- Documentation: source-of-truth sync
- Assistant, Research, Finance, Growth: bounded specialist support

## Stage 2 Foundation

- Replace the stage-1 AI COO role with one operating role: `AI Operations Lead`.
- Keep three stable workflows with explicit routing, acceptance, and telemetry contracts.
- Run weekly metric review from `.hq/telemetry/` and the control plane, not from chat reconstruction.
- Add lightweight eval and acceptance discipline for repeated work without introducing heavy automation.
- Keep memory hygiene strict: `.hq/` is runtime, shared Markdown is accepted truth.

## Autonomy Tiers

- `A0` advisory_only
- `A1` draft_and_prepare
- `A2` internal_execution
- `A3` external_action_with_review
- `A4` human_only

## Default Operating Loop

1. Intake lands in Inbox or a founder request.
2. AI Operations Lead converts it into or updates a task in `active-work.json`.
   The task contract must name a `manager`, `owner`, and `accepts_result` role explicitly.
3. Governor checks risk tier, autonomy tier, and missing approvals.
4. Specialist agent executes.
5. Accepting role reviews outcome.
6. Documentation syncs shared truth and re-renders `Task Board.md`.
7. Runtime writes telemetry and reflections into `.hq/`.
8. AI Operations Lead runs the weekly metric review; Governor checks breaches, exceptions, and unsafe drift.

## Hard Rules

- No delegated task without manager, owner, accepting role, risk tier, autonomy tier, workflow, and primary update file.
- `active-work.json` is the machine-readable queue for delegated work.
- `Task Board.md` is a rendered mirror for humans.
- Repeated work needs explicit acceptance checks and telemetry signals before autonomy expands.
- CEO approval is required for `A4` work and any budget, legal, public, or destructive commitment.
- Governor can block execution even if the task is otherwise well-formed.

## Manager vs Owner

- `manager` owns routing, sequencing, and coordination for the task.
- `owner` owns execution of the current work slice.
- `accepts_result` is the role that confirms the result is good enough to count.
- In Stage 2, `AI Operations Lead` remains the default task manager unless the operating model explicitly says otherwise.

## Private Improvement Loop

- Weekly review may emit manual-first candidates for `agent prompt`, `task checklist`, `operating procedure`, and `skill`.
- Skill-oriented candidates are written only as private runtime backlog under `.hq/improvements/skill-candidates.json`.
- The weekly review does not auto-edit `AGENTS.md`, shared truth, access rules, safety rules, or production logic.
