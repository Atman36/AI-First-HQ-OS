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
- Use Codex subagents and skills for bounded execution support
- Use Paperclip later as the durable external coordinator that points agents to these same role files
- Do not let multiple agents edit the same file concurrently
- Escalate high-risk decisions to CEO
