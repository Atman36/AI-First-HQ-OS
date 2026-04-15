# HQ

Shared HQ workspace for the company. It now operates as a hybrid of:

- human-readable company truth in Markdown
- a machine-readable AI control plane for delegated work
- a private runtime for telemetry, handoffs, reflections, evals, and releases

## Goal

Turn HQ into an AI-first company operating system where AI is the default operator for low- and medium-risk work, and humans stay in strategic, financial, legal, public, and escalation roles.

## Quick Routing

Start with the file that matches the question:

- Current company focus: `now.md`
- Active projects and owners: `projects.md`
- Operating cadence: `routines.md`
- Tooling and execution boundaries: `stack.md`
- Machine-readable queue and agent authority: `05 AI Control Plane/`
- Human-readable live board: `02 Planning/Task Board.md`
- Weekly commitments and review: `02 Planning/Weekly Plan.md`
- Durable decisions: `03 Notes/Decisions.md`
- Explicit unresolved choices: `03 Notes/Open Decisions.md`
- Project-local detail: `04 Projects/`

## AI-First Operating Model In One Screen

Each role now works through five operating objects:

- Task state: `05 AI Control Plane/active-work.json`
- Rules: `AGENTS.md` plus `agents/*/AGENTS.md`
- Policies: `05 AI Control Plane/operating-policies.json`
- Workflow: `05 AI Control Plane/workflow-registry.json`
- Telemetry: `.hq/telemetry/`

`02 Planning/Task Board.md` is the human-readable mirror of the machine-readable queue.

## How To Use

- Run Codex from this directory when you want repo-scoped instructions.
- Open this folder in Obsidian if you want a readable company vault.
- Use the root `AGENTS.md` as the common policy layer.
- Use `agents/*/AGENTS.md` as role prompts for specialized runs.
- Use `python3 scripts/hq_control_plane.py sync` after changing `05 AI Control Plane/active-work.json`.
- Use `python3 scripts/hq_control_plane.py validate` before accepting structural changes to the control plane.
- Use `python3 scripts/hq_telemetry.py event ...` to log task, approval, escalation, or sync events into `.hq/telemetry/`.
- Use `python3 scripts/hq_runtime.py bootstrap` to create the local runtime scaffold and `python3 scripts/hq_runtime.py probe ...` before routing work through a local CLI.
- Keep private runtime state under `.hq/`; keep durable company truth in tracked files.

## Founder Path

- CEO sets direction and approves high-risk changes.
- COO converts work into machine-readable tasks.
- Governor checks risk, approvals, and guardrails.
- Delivery or a specialist role executes.
- Documentation syncs accepted outcomes back into shared truth.

## Source Of Truth

### Strategic truth

- `now.md`
- `projects.md`
- `routines.md`
- `stack.md`
- `agents/`
- `03 Notes/Decisions.md`
- `03 Notes/Open Decisions.md`

### AI control plane

- `05 AI Control Plane/active-work.json`
- `05 AI Control Plane/agent-registry.json`
- `05 AI Control Plane/operating-policies.json`
- `05 AI Control Plane/workflow-registry.json`
- `05 AI Control Plane/metrics-registry.json`

### Working layer

- `02 Planning/Task Board.md`
- `02 Planning/Weekly Plan.md`
- `04 Projects/`

## Private Runtime

Use `.hq/` for private, inspectable, non-git-tracked runtime artifacts:

- `.hq/handoffs/` for task-scoped continuity
- `.hq/state/` for capability probe results and lightweight runtime state
- `.hq/telemetry/` for structured event logs
- `.hq/reflections/` for per-task lessons
- `.hq/improvements/` for weekly synthesis
- `.hq/evals/` for eval runs and artifacts
- `.hq/releases/` for rollout and rollback notes

## Runtime Commands

Bootstrap and probe commands:

```bash
python3 scripts/hq_runtime.py bootstrap
python3 scripts/hq_runtime.py probe codex claude
```

Write a handoff:

```bash
python3 scripts/hq_runtime.py handoff \
  --task HQ-bootstrap-runtime \
  --owner Delivery \
  --status ready_for_handoff \
  --continue-from "04 Projects/HQ Bootstrap.md" \
  --primary-file "04 Projects/HQ Bootstrap.md" \
  --important-file "stack.md" \
  --important-file "01 Operating System/Agent Routing.md" \
  --done "Added the private runtime scaffold" \
  --next "Validate the next acceptance slice" \
  --risk "Do not move private notes back into shared docs"
```

Write a reflection and run a weekly review:

```bash
python3 scripts/hq_runtime.py reflection \
  --agent Delivery \
  --task "weekly-agent-self-improvement" \
  --session "2026-04-14-delivery-1" \
  --summary "Missed a repo-specific instruction" \
  --observation "Started coding before reading AGENTS.md in full" \
  --issue "Instruction loading happened too late" \
  --lesson "Read repo instructions before editing code" \
  --proposed-rule "Add a startup checklist for repo instructions" \
  --issue-key instruction-loading \
  --tag instructions

python3 scripts/hq_runtime.py weekly-review \
  --since 2026-04-07 \
  --until 2026-04-14
```

The review output is a safe artifact only:

- `.hq/improvements/LATEST.json` for machine-readable grouped observations
- `.hq/improvements/LATEST.md` for a human review note with candidate improvements
- No shared Markdown files or `AGENTS.md` files are edited automatically by this flow
