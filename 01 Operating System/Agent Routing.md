# Agent Routing

This file defines how tasks are routed across the current HQ role set.

## Default Rule

- CEO sets priority and approves major tradeoffs.
- COO is the default dispatcher and execution router.
- Delivery owns bounded implementation and project execution work.
- Documentation owns shared file updates after the result is accepted.
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
2. COO creates or updates one task card with `owner`, `support`, `done when`, `primary update file`, and `accepts result`.
3. COO assigns one clear owner.
4. Delivery owns build or implementation work; other support roles contribute bounded inputs where relevant.
5. Documentation updates only the shared records affected after the result is accepted.

### Ambiguous inbound request

1. Assistant clarifies the ask.
2. CEO decides whether it is worth doing now.
3. COO schedules or routes it.

### Fast-track for bounded work

CEO may assign a task directly to the best-fit role when all of these are already clear:

- one owner
- one primary update file
- a concrete done condition

COO should still align the board afterward if the work stays active.

## Founder Run Pattern In Codex

1. Founder or CEO states the objective, decision, or constraint.
2. COO turns it into or updates one active card on `Task Board.md`.
3. Run support roles in parallel only for bounded work:
   - Delivery for implementation plans, automation specs, and project execution
   - Research for evidence and comparisons
   - Finance for money impact
   - Growth for revenue angle
   - Assistant for intake cleanup and agenda shaping
4. Let the execution owner finish first, then use Documentation to align shared records.

## How Codex Should Run Agents

- Use the existing role prompts under `agents/<role>/AGENTS.md`.
- Delegate bounded work to the role that naturally owns the output.
- Do not let two agents edit the same file at the same time.
- Keep one role accountable for the final answer, even if support roles contribute.

## Practical Mapping

- Priority, approval, escalation: CEO
- Breakdown, sequencing, ownership: COO
- Implementation, delivery, execution artifacts: Delivery
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
- Which primary update file changes first
- Who accepts the result
- Which files align after acceptance, if any

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
