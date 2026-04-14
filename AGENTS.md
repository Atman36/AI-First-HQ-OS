# HQ Shared Instructions

This repository is the shared project root for the HQ system.

It is designed to work in two modes:

1. Codex runs directly from this folder and reads `AGENTS.md` files by directory scope.
2. Paperclip agents can later point their `instructionsFilePath` to the same files under `agents/*/AGENTS.md`.

## Source Of Truth

Shared company artifacts are split into a current-state layer, a working layer, and support material.

### Current-State Layer

These files define the current company truth:

1. `now.md`
2. `projects.md`
3. `routines.md`
4. `stack.md`
5. `agents/`

### Working Layer

These files turn direction into execution and history:

1. `02 Planning/Task Board.md` - single live execution board
2. `02 Planning/Weekly Plan.md` - weekly commitments and weekly summary
3. `03 Notes/Decisions.md` - durable decision log
4. `04 Projects/` - project-specific detail and support notes

### Support Material

- `reports/` and ignored research drafts are support inputs, not shared truth.
- They only change company state after the outcome is summarized into `04 Projects/...` or `03 Notes/Decisions.md`.
- Personal memory, heartbeats, and private notes for future Paperclip agents must stay outside this repo in each agent home directory.
- Repo-local private runtime artifacts that must stay inspectable but non-public belong only under the git-ignored `.hq/` path.

## File Contract

- `now.md` holds company focus, not a second task list.
- `projects.md` is the registry of active projects and owners.
- `02 Planning/Task Board.md` is the single live board for active tasks.
- Every active card should have one owner and one primary update file.
- `02 Planning/Weekly Plan.md` holds weekly commitments and the weekly summary, not duplicate task cards.
- `03 Notes/Decisions.md` records durable why after a decision is made.
- `04 Projects/` holds local context, execution detail, risks, dependencies, and support inputs that would clutter the root. It should not mirror the full weekly summary.

## Coordination Rules

- Do not let two agents edit the same file at the same time.
- Shared docs in this repo describe company state, not private scratchpads.
- Use `.hq/handoffs/` for task-scoped private handoff files; do not turn shared Markdown files into continuation logs.
- In this repository, documentation changes are primary project work. If you change shared Markdown files here, make a git commit unless the user explicitly asks not to.
- When a task touches several files, name one primary update file and align the rest only after the result is accepted.
- When a workflow depends on a specific CLI, runner, or agent surface, confirm local availability before routing through it.
- Escalate strategic, financial, or destructive decisions to the CEO.
- When a task belongs to a specific role, prefer that role's prompt under `agents/`.
- Keep outputs short, operational, and easy to hand off.

## Private Improvement Loop

- Use `.hq/reflections/` and `.hq/improvements/` only as private runtime artifacts, never as shared truth.
- Write a `reflection` only when there is a concrete bug, avoidable mistake, repeated friction, missed instruction, tool misuse, or a clear improvement idea worth remembering.
- Do not write a `reflection` for a clean task with no actionable lesson.
- Keep each `reflection` grounded in concrete observations. Separate the observation, the factual record of what happened, and the proposed improvement.
- If the session had several bugs, mistakes, or recurring frictions, list all of them explicitly instead of collapsing them into one vague summary.
- When several issues happened in one session, either capture them as separate reflection entries or include a clear itemized list of all issues and facts in the same reflection.
- Do not use this loop to auto-edit `AGENTS.md`, `agents/*/AGENTS.md`, access rules, safety rules, or production logic.
- After a successful `weekly-review`, processed raw reflections may be removed from the active backlog only if the synthesized review artifact for that window was written to `.hq/improvements/`.
- If cleanup happens, keep the synthesized review artifacts; do not delete the weekly output that explains what changed and why.
- Prefer clearing only the reflections already covered by the completed review window, not the newest unreviewed entries.
- Run `weekly-review` or `improve` only in these cases:
  1. during the weekly review cadence;
  2. when the user explicitly asks for synthesis or improvement review;
  3. when several new reflections have accumulated and there is evidence of a recurring issue.
- Do not run `weekly-review` after every task or after a single minor reflection unless the user asks for it.

## Default Routing

- If the user does not name a role, first determine the best-fit owner before doing the work.
- Use CEO when priority, tradeoff, scope, or approval is unclear.
- Use COO when the decision already exists but the task still needs routing, ownership, sequencing, or a task card.
- Use Delivery when the task is already scoped and needs implementation, execution planning, or shipped artifacts.
- Use Documentation after the result is accepted and shared files need to be aligned.
- Use Assistant, Finance, Growth, and Research only for bounded support work in their domain.
- Do not add a separate standing orchestrator unless routing pain is proven by real workload.

## Current Team

- CEO
- COO
- Delivery
- Documentation
- Assistant
- Finance
- Growth
- Research

## Directory Convention

- Root files describe the company and the operating rhythm.
- `agents/<role>/AGENTS.md` contains the role prompt.
- `.hq/` is the only repo-local private runtime path and must remain git-ignored.
- `reports/` is reference material only until summarized back into a source-of-truth file.
- Future Paperclip-only files like `HEARTBEAT.md`, `SOUL.md`, and `TOOLS.md` should not live in this repo.
