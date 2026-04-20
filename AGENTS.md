# HQ Shared Instructions

`AGENTS.md` is the HQ gateway: it defines routing, boundaries, and precedence.
It should stay compact. Detailed execution defaults belong in machine-readable control-plane files; operational summaries should be generated, not hand-maintained.

## Gateway Mindset

- Treat this file as a routing and boundary layer, not the full operating manual.
- Prefer one machine-readable config contract plus one generated summary over duplicated prose.
- Load only the policy and context surface that the current task actually needs.
- Keep HQ tool-agnostic: workflows may use local scripts and CLIs, but the operating model does not depend on one vendor tool.

## Operating Layers

HQ runs through four layers:

1. Human-readable company truth in local Markdown.
2. Machine-readable AI control plane under `05 AI Control Plane/`.
3. Generated summaries and session artifacts that mirror the control plane.
4. Private runtime state under `.hq/`.

## Source Of Truth

### Local strategic truth

These files define current company truth for humans and must stay local-only:

- `now.md`
- `projects.md`
- `routines.md`
- `stack.md`
- `agents/`
- `03 Notes/Decisions.md`
- `03 Notes/Open Decisions.md`
- `04 Projects/`

### Machine-readable control plane

These files define executable operating contracts:

- `05 AI Control Plane/active-work.json` - delegated-work queue
- `05 AI Control Plane/agent-registry.json` - role registry and authority map
- `05 AI Control Plane/operating-policies.json` - autonomy, risk, approvals, kill switches
- `05 AI Control Plane/workflow-registry.json` - workflow states and required task fields
- `05 AI Control Plane/metrics-registry.json` - operating review metrics
- `05 AI Control Plane/execution-config.json` - execution defaults, approval defaults, runner assumptions
- `05 AI Control Plane/schemas/` - JSON contracts for all of the above

### Generated summaries

These artifacts are mirrors, not hand-authored source of truth:

- `02 Planning/Task Board.md` - rendered mirror of `active-work.json`
- `.hq/state/WORKFLOW.generated.md` - generated operating summary from the control plane
- `.hq/state/session-bootstrap.json` - generated startup packet

### Private runtime

- `.hq/` is the only repo-local private runtime path and must remain git-ignored.
- Reports, raw imports, transcripts, telemetry, evals, reflections, and handoffs belong under `.hq/` or outside the repo unless explicitly approved otherwise.

## Minimal Artifact Rule

- Keep manual truth only where humans must author or approve it.
- Keep execution defaults in `05 AI Control Plane/execution-config.json`.
- Keep operating summaries generated from the control plane.
- Do not hand-maintain duplicate workflow summaries when a generated artifact can render them.

## Instruction Precedence

When instructions conflict, use this order:

1. Platform, system, and developer constraints outside the repo.
2. `AGENTS.md`.
3. Current machine-readable contracts in `05 AI Control Plane/`.
4. Task-scoped private packets in `.hq/specs/<task>/LATEST.md` and `.hq/handoffs/<task>/LATEST.md`.
5. Active role prompt in `agents/<role>/AGENTS.md`.
6. Current project and notes files.
7. Historical reviews and archived notes.

Additional rules:

- If enforcement, schema validation, tests, or hooks disagree with prose, enforcement wins.
- If a task field, workflow, approval rule, autonomy tier, or risk tier exists in the control plane, the control plane wins over prose summaries.
- Generated summaries help orientation but do not override machine-readable contracts.

## Command Contract

Start narrow and widen only when needed:

1. Start new sessions with `python3 scripts/hq_control_plane.py status` or `.hq/state/session-bootstrap.json`.
2. Use `.hq/state/WORKFLOW.generated.md` as the generated startup summary when available.
3. For delegated task-state changes, update `05 AI Control Plane/active-work.json` first.
4. Re-render `02 Planning/Task Board.md` with `python3 scripts/hq_control_plane.py sync` after material task-state changes.
5. Validate control-plane integrity with `python3 scripts/hq_control_plane.py validate` when contracts or queue state changed materially.
6. For large or ambiguous work, create or refresh `.hq/specs/<task>/LATEST.md` before splitting execution across agents or sessions.
7. Use `.hq/handoffs/<task>/LATEST.md` for bounded continuity when work will resume later or time out.

## Load Rules

Default rule: load only the minimum surface required for the current task.

Always read:

- `AGENTS.md`
- the current startup summary from `python3 scripts/hq_control_plane.py status` or `.hq/state/session-bootstrap.json`

Then load only what matches the task:

- Execution defaults, approval defaults, runner assumptions: `05 AI Control Plane/execution-config.json`
- Task queue, ownership, acceptance, next step: `05 AI Control Plane/active-work.json`
- Workflow states and required fields: `05 AI Control Plane/workflow-registry.json`
- Risk, autonomy, approval, and human-only boundaries: `05 AI Control Plane/operating-policies.json`
- Role-specific behavior: `agents/<role>/AGENTS.md`
- Task-local continuity: `.hq/specs/<task>/LATEST.md`, `.hq/handoffs/<task>/LATEST.md`
- Project-local context that affects the current slice: relevant files in `04 Projects/` and root notes

Load constraints:

- Do not reopen the whole repository by default.
- Do not widen policy/context surface unless the current task actually crosses that boundary.
- Prefer one config contract plus one generated summary over parallel prose documents.
- Narrow policy packs are the right next step for HQ, but until they exist, emulate that behavior by reading only the relevant control-plane files above.

## Policy Contract

HQ is AI-first, but not approval-free.

- Default mode is best-effort execution inside current strategy and policy.
- Do not ask a clarifying question unless blocked by missing access, irreversible risk, or a truly unresolved fork that current HQ state does not answer.
- If a question is required, ask one bundled blocker question at most.
- Work long by default: continue until the current slice is complete, truly blocked, or reduced to a founder-only decision.
- AI may make low- and medium-risk operating decisions only when the task has an owner, accepting role, risk tier, autonomy tier, workflow, and primary update file.
- Humans retain strategy, budget, legal, public, destructive, hiring, and override authority.
- Governor can block or pause work that lacks policy coverage, telemetry coverage, or required approval.
- Do not let two agents edit the same file at the same time.
- Shared docs describe company state; they are not private scratchpads.

### Routing

- AI Operations Lead owns intake, decomposition, queue health, telemetry discipline, eval follow-through, memory hygiene, runtime quality, and cross-session continuity.
- CEO owns strategy, approvals, high-risk decisions, public/legal/financial escalation, and overrides.
- Governor owns policy, risk, trust boundaries, approvals, and rollback triggers.
- Delivery, Documentation, Finance, Growth, and Research own bounded execution within accepted task contracts.
- Managers should route specialist execution instead of absorbing it directly when narrower expertise is required.
- Approved local specialist bench for manager-launched execution: `CTO`, `Senior Product Engineer`, `Data Analyst`, `Evals Engineer`, `Security Engineer`, `QA`, `CloudOps Engineer`, `UX Designer`, `Skill Consultant`.

## Verification Contract

A slice is complete only when all are true:

1. Approved scope is satisfied without unresolved drift.
2. Required control-plane fields, workflow state, and acceptance ownership are consistent.
3. Required approvals and policy boundaries were respected.
4. Required checks or validations for the touched surface were run.
5. The result is synced back to the correct human-readable truth or generated summary.
6. No unintended tracked changes remain.

Additional verification rules:

- `02 Planning/Task Board.md` should be rendered from the queue, not hand-maintained.
- `.hq/state/WORKFLOW.generated.md` and `.hq/state/session-bootstrap.json` are generated artifacts; regenerate instead of editing them by hand.
- Reports change company state only after the accepted conclusion is summarized into the appropriate source-of-truth files.

## Publication And Privacy Boundary

- Keep public Git history limited to prompts, scripts, tests, CI files, schemas, and minimal repo metadata unless publication is explicitly approved.
- Do not commit private user data, customer data, credentials, payment artifacts, raw imports, transcripts, or runtime telemetry.
- If a file contains personal data, customer data, imported workspace data, or raw operational artifacts, it must stay under `.hq/` or outside this repository.
- Technical documentation for internal operation should not be pushed to public GitHub unless explicitly approved for publication.

## Change Control

- Do not auto-edit `AGENTS.md`, `agents/*/AGENTS.md`, access rules, safety rules, or production logic from the private improvement loop.
- Candidate improvements should live in `.hq/reflections/` or `.hq/improvements/` until applied deliberately.
- When an approved improvement is ready, update the smallest governing surface that fixes the issue.
- Make a repo commit when changing tracked system files such as scripts, prompts, skills, plugins, schemas, or this gateway file.
- If a task changes only local operating docs or other untracked private material, do not make a repo commit unless explicitly requested.
