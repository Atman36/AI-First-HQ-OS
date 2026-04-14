# Agent Routing

This file defines how tasks are routed across the current HQ role set.

## Default Rule

- CEO sets priority and approves major tradeoffs.
- COO is the default dispatcher and execution router.
- Documentation owns shared file updates.
- Assistant handles intake and agenda shaping.
- Finance, Growth, and Research support when their expertise is required.

There is no separate standing orchestrator role yet.

## Why No Separate Orchestrator Yet

- The current team is still small.
- A dedicated orchestrator would add another management layer before the existing workflow is validated.
- The COO already owns decomposition, routing, blockers, and completion tracking.

## Routing Order

### Strategic or high-risk question

1. CEO frames the decision.
2. Finance, Growth, or Research provide supporting input if needed.
3. Documentation records the outcome.

### Operational task

1. COO breaks the task into actions.
2. COO creates or updates one task card with `owner`, `support`, `done when`, `update file`, and `accepts result`.
3. COO assigns one clear owner.
4. Supporting roles contribute bounded inputs.
5. Documentation updates only the shared records affected by execution.

### Ambiguous inbound request

1. Assistant clarifies the ask.
2. CEO decides whether it is worth doing now.
3. COO schedules or routes it.

### Fast-track for bounded work

CEO may assign a task directly to the best-fit role when all of these are already clear:

- one owner
- one target file
- a concrete done condition

COO should still align the board afterward if the work stays active.

## How Codex Should Run Agents

- Use the existing role prompts under `agents/<role>/AGENTS.md`.
- Delegate bounded work to the role that naturally owns the output.
- Do not let two agents edit the same file at the same time.
- Keep one role accountable for the final answer, even if support roles contribute.

## Practical Mapping

- Priority, approval, escalation: CEO
- Breakdown, sequencing, ownership: COO
- Shared markdown updates: Documentation
- Inbox cleanup, summaries, follow-ups: Assistant
- Money impact, expected return, spend risk: Finance
- Revenue tests, offer direction, commercial ranking: Growth
- Evidence, sourcing, comparisons, benchmarks: Research

## Handoff Rule

Every delegated task should answer these questions before work starts:

- Who owns it
- Who supports it
- What counts as done
- Which file gets updated
- Who accepts the result

## Skills And Future Orchestration

- Codex can already use skills and spawn subagents on demand.
- For this repository, skills are support tools, not a replacement for role ownership.
- If you need durable task queues, scheduled follow-ups, or background coordination, use Paperclip later as the external coordinator that points to these same role prompts.

## Trigger To Add A Real Orchestrator

Add a separate orchestrator only after at least one of these becomes true:

- More than one active project regularly needs cross-role coordination.
- Work is blocked because routing decisions are scattered across chats.
- Scheduled follow-ups or persistent queues become operationally necessary.
- COO routing becomes a bottleneck instead of a simplifier.
