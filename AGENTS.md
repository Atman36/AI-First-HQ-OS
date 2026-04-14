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
- In this repository, documentation changes are primary project work. If you change shared Markdown files here, make a git commit unless the user explicitly asks not to.
- When a task touches several files, name one primary update file and align the rest only after the result is accepted.
- Escalate strategic, financial, or destructive decisions to the CEO.
- When a task belongs to a specific role, prefer that role's prompt under `agents/`.
- Keep outputs short, operational, and easy to hand off.

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
- `reports/` is reference material only until summarized back into a source-of-truth file.
- Future Paperclip-only files like `HEARTBEAT.md`, `SOUL.md`, and `TOOLS.md` should not live in this repo.
