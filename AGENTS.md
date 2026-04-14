# HQ Shared Instructions

This repository is the shared project root for the HQ system.

It is designed to work in two modes:

1. Codex runs directly from this folder and reads `AGENTS.md` files by directory scope.
2. Paperclip agents can later point their `instructionsFilePath` to the same files under `agents/*/AGENTS.md`.

## Source Of Truth

Shared company artifacts are split into a current-state layer and a working layer.

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
2. `02 Planning/Weekly Plan.md` - weekly commitments and checkpoints
3. `03 Notes/Decisions.md` - durable decision log
4. `04 Projects/` - project-specific detail and support notes

Personal memory, heartbeats, and private notes for future Paperclip agents must stay outside this repo in each agent home directory.

## File Contract

- `now.md` holds company focus, not a second task list.
- `projects.md` is the registry of active projects and owners.
- `02 Planning/Task Board.md` is the single live board for active tasks.
- `02 Planning/Weekly Plan.md` holds weekly commitments, not duplicate task cards.
- `03 Notes/Decisions.md` records durable why after a decision is made.
- `04 Projects/` holds local context that would clutter the root.

## Coordination Rules

- Do not let two agents edit the same file at the same time.
- Shared docs in this repo describe company state, not private scratchpads.
- Escalate strategic, financial, or destructive decisions to the CEO.
- When a task belongs to a specific role, prefer that role's prompt under `agents/`.
- Keep outputs short, operational, and easy to hand off.

## Current Team

- CEO
- COO
- Documentation
- Assistant
- Finance
- Growth
- Research

## Directory Convention

- Root files describe the company and the operating rhythm.
- `agents/<role>/AGENTS.md` contains the role prompt.
- Future Paperclip-only files like `HEARTBEAT.md`, `SOUL.md`, and `TOOLS.md` should not live in this repo.
