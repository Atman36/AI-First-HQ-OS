# HQ Shared Instructions

This repository is the shared project root for the HQ system.

It is designed to work in two modes:

1. Codex runs directly from this folder and reads `AGENTS.md` files by directory scope.
2. Paperclip agents can later point their `instructionsFilePath` to the same files under `agents/*/AGENTS.md`.

## Source Of Truth

Shared company artifacts live in this root:

1. `now.md`
2. `projects.md`
3. `routines.md`
4. `stack.md`
5. `agents/`

Personal memory, heartbeats, and private notes for future Paperclip agents must stay outside this repo in each agent home directory.

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
