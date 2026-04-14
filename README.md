# HQ

Shared HQ workspace for Codex now and Paperclip later.

## Goal

Use one project root for shared company state and separate agent-specific homes for private memory.

## How To Use

- Run Codex from this directory when you want repo-scoped instructions.
- Open this folder in Obsidian if you want a readable company vault.
- Use the root `AGENTS.md` as the common policy layer.
- Use `agents/*/AGENTS.md` as role prompts for specialized runs.
- When Paperclip is connected, point each agent to the matching file in `agents/`.

## Source Of Truth

These files stay in the repository root and should not be moved:

- `now.md` - current focus
- `projects.md` - active projects
- `routines.md` - daily and weekly rhythms
- `stack.md` - tool rules
- `agents/` - role prompts

## Obsidian Layer

Additional folders provide a cleaner writing and reading experience:

- `00 Home.md` - vault entry point
- `01 Operating System/` - navigation and operating rules
- `02 Planning/` - shared task board, weekly plan, backlog
- `03 Notes/` - inbox and decision log
- `04 Projects/` - project pages
- `90 Templates/` - reusable note templates

## Recommended Split

- Shared project root: this repo
- Agent private memory: outside this repo
- No concurrent edits to the same file from multiple agents
