# HQ Audit Review - 2026-04-14

This is a dated review snapshot, not a live status board.

Live state belongs in `now.md`, `projects.md`, `02 Planning/Task Board.md`, `02 Planning/Weekly Plan.md`, `03 Notes/Decisions.md`, and `04 Projects/...`.

## Executive Summary

### Facts

- The real operating model is a lean manual dispatch loop: CEO sets direction, COO routes work, a role owner executes bounded work, and Documentation aligns the shared record.
- Root files already hold direction well: `now.md`, `projects.md`, `routines.md`, and `stack.md` are compact and mostly consistent.
- `02 Planning/Task Board.md` is still the only live task board, but the task-card contract was underspecified because actual cards named several update files.
- The current weekly cycle was being mirrored across `02 Planning/Weekly Plan.md` and `04 Projects/HQ Bootstrap.md`.
- Existing agents covered strategy, routing, research, finance, growth, intake, and documentation, but there was no clear default owner for bounded implementation work.

### Interpretation

The system is already good enough for a one-founder, one-project operating cycle. The main risk is not lack of structure. The main risk is drift caused by too many files summarizing the same cycle and by the missing execution owner between COO and Documentation.

## What Works

### Facts

- `AGENTS.md` clearly separates root truth from the working layer.
- `now.md` stays at focus level instead of turning into a second board.
- `projects.md` is still a lean registry, not a project notebook.
- `02 Planning/Task Board.md` carries owners, done conditions, and acceptance rules.
- `03 Notes/Decisions.md` already records durable why in compact form.
- `01 Operating System/Agent Routing.md` already makes COO the default dispatcher and rejects a premature orchestrator.

### Interpretation

The base architecture is sound. For the current scale, the system does not need more layers. It needs sharper boundaries between the layers it already has.

## Structural Risks

### Facts

- `02 Planning/Weekly Plan.md` contained a live cycle snapshot with completed work, active work, blocker checks, and next priorities.
- `04 Projects/HQ Bootstrap.md` also contained completed work, still active work, blockers, and next 3 priorities for the same cycle.
- The previous version of this file (`01 Operating System/HQ Audit Roadmap.md`) also tracked what was closed, partially closed, still relevant, and next moves.
- `agents/*/AGENTS.md` used machine-specific absolute paths, even though the repo is meant to be shared across Codex and future runners.

### Interpretation

Without intervention, the system would have drifted into three parallel status ledgers: Weekly Plan, project page, and audit roadmap. That would create ambiguity exactly where the system is trying to remove it.

## Source-of-Truth Violations

### Facts

- `agents/coo/AGENTS.md` said every active task should have one target file, while the live cards in `02 Planning/Task Board.md` often named several update files.
- `01 Operating System/How To Operate HQ.md` and the board schema also used singular `update file`, but live cards already needed more than one alignment step.
- `02 Planning/Backlog.md` still suggested a separate weekly review note even though `routines.md` and `02 Planning/Weekly Plan.md` explicitly keep the weekly review embedded and lean.
- Project-local cycle status had started to mirror the weekly summary instead of staying project-local.

### Interpretation

The contract itself was directionally right, but the singular update-file rule and the duplicate weekly snapshot created real openings for drift. The fix is not a bigger process. The fix is a clearer first-write rule and stricter scoping of the project page.

## Role Bottlenecks

### COO

#### Facts

- `stack.md` and `01 Operating System/Agent Routing.md` both make COO the default dispatcher.
- Both active `This Week` cards on `02 Planning/Task Board.md` were COO-owned.
- `01 Operating System/Agent Routing.md` already allows a fast-track path for bounded work.

#### Interpretation

COO is not yet a proven bottleneck because there is one active project, one active cycle, and a fast-track escape hatch. The risk is real only when more than one project or repeated inbound work appears.

### Documentation

#### Facts

- `routines.md`, `01 Operating System/Agent Routing.md`, and `agents/documentation/AGENTS.md` all make Documentation the closer of shared records.
- `02 Planning/Weekly Plan.md` and `04 Projects/HQ Bootstrap.md` both flagged Documentation closeout as the live watchpoint.
- Many task cards still implied multi-file manual sync.

#### Interpretation

Documentation is not yet the bottleneck by volume. The bottleneck mechanism is multi-file closeout. If one result still requires several shared files to be updated manually, Documentation will queue even with a small workload.

### 04 Projects vs `projects.md`

#### Facts

- `projects.md` remains a short registry.
- `04 Projects/HQ Bootstrap.md` held extra project detail, risks, dependencies, and support-role inputs.
- The real duplication happened in cycle snapshot sections, not in project registry fields.

#### Interpretation

`04 Projects/` has not yet broken the registry contract. The actual danger is the project page becoming a second weekly summary, not a second `projects.md`.

### Weekly Plan vs second task board

#### Facts

- `02 Planning/Weekly Plan.md` did not contain owner-level task cards.
- It did contain shipped work, still active work, blockers, and next priorities.

#### Interpretation

`Weekly Plan.md` was not yet a second task board, but it was drifting toward a second status ledger. Keeping it as the weekly summary is enough. It should not also carry a live mid-cycle board mirror.

## Minimal Fixes

1. Keep one primary update file on each active task card. Align other files only after the result is accepted.
2. Keep `02 Planning/Weekly Plan.md` as the weekly commitments and weekly summary only.
3. Keep `04 Projects/...` focused on local context, risks, dependencies, support inputs, and implementation detail.
4. Make all scoped role prompts repo-relative instead of machine-specific.
5. Add one missing role: Delivery, as the default bounded execution owner for implementation work that is more than documentation.
6. Freeze this audit file as a dated review note instead of a live tracker.

## Files To Change First

1. `02 Planning/Task Board.md`
2. `02 Planning/Weekly Plan.md`
3. `04 Projects/HQ Bootstrap.md`
4. `agents/*/AGENTS.md`
5. `AGENTS.md`
6. `90 Templates/Task Template.md`

## What Not To Add

- Do not add a separate standing orchestrator yet.
- Do not add a second task board.
- Do not add a separate weekly review file unless the embedded weekly review actually fails.
- Do not add `people.md`, `channels.md`, or extra control-plane files before repeated real usage requires them.
- Do not add role-specific queues until the shared board becomes too broad.
- Do not push execution work back into Documentation just because the result eventually changes markdown.
