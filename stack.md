# Stack

## Codex

- Purpose: implementation, writing, local analysis, structured editing
- Strengths: reads repo instructions, edits files well, works directly in the shared root
- Can also run bounded subagents and use skills on demand during a live session
- Limits: should not be used as the only memory system

## Paperclip

- Purpose: orchestration, delegation, task routing, scheduled execution
- Strengths: agent coordination, reporting lines, future heartbeat workflows
- Limits: keep private agent memory outside this repo

## Rule Of Use

- Use Codex for direct work in this repository
- Use COO as the default dispatcher inside HQ
- Use Delivery as the default execution owner for implementation work that is more than documentation
- Use Codex subagents and skills for bounded execution support
- Use Paperclip later as the durable external coordinator that points agents to these same role files
- When work depends on a specific CLI, runner, or agent surface, confirm local availability before routing the workflow through it
- Record repo-local private runtime state only under `.hq/`
- Do not let multiple agents edit the same file concurrently
- Escalate high-risk decisions to CEO

## Capability Probe

- Treat `python3 scripts/hq_runtime.py probe ...` as the default cheap probe before routing a workflow through `codex`, `claude`, or another local runner
- A tool is considered usable only after it is both visible in `PATH` and responsive to a cheap probe such as `--help`
- Store probe results in `.hq/state/capabilities.json`, not in shared source-of-truth files

## Private Runtime Contract

- `.hq/handoffs/` stores task-scoped handoff files between agents and sessions
- `.hq/state/` stores lightweight runtime state such as capability probe results
- `.hq/logs/`, `.hq/memory/`, and `.hq/journals/` are private operational space, not company memory
- Shared decisions, project status, and accepted outcomes must still be rolled back into tracked HQ files

## Founder Working Defaults

- Default language: Russian
- Default response style: direct, concrete, concise by default, with examples only when they improve execution quality
- Default decision support: offer 2-3 concrete options with a clear next step or DoD instead of open-ended brainstorming
- Default execution bias: keep WIP tight and prefer one clearly finished slice over several partially open ones

## Founder Tool Context

- Assume a macOS-based workflow built around Obsidian, Telegram, GitHub, and AI-assisted local work
- Prefer suggestions that fit the current working stack: React, Vite, Tailwind, Next.js, Python, Node.js, Vercel, Supabase, n8n
- Treat ChatGPT, Claude, Codex, Cursor, v0, and Perplexity as normal parts of the toolchain, not edge cases that require explanation
