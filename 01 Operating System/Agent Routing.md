# Agent Routing

This file defines how work is routed in the AI-first HQ.

## Default Rule

- CEO owns direction, approvals, and overrides.
- AI Operations Lead is the default operating router.
- Governor enforces risk policy and approval gates.
- Delivery owns bounded execution.
- Documentation syncs accepted results into shared truth.
- Assistant, Finance, Growth, and Research support when their expertise is needed.

`AI Operations Lead` replaces the stage-1 AI COO role. Do not run both as parallel standing operators.

## Automatic Entry Routing

1. Send it to CEO if priority, scope, tradeoff, budget, or policy is unclear.
2. Send it to AI Operations Lead if the decision exists but the work still needs owner, risk tier, autonomy tier, task state, telemetry expectations, or weekly-review follow-through.
3. Send it to Governor if the task touches approvals, external writes, policy exceptions, or rollback triggers.
4. Send it to Delivery or another specialist role if the task is already scoped and policy-cleared.
5. Send it to Documentation only after the result is accepted and shared truth needs alignment.

## Minimum Task Contract

Every delegated task must answer these questions before execution starts:

- Who manages routing and coordination
- Who owns it
- Who supports it
- What counts as done
- Which primary update file changes first
- Who accepts the result
- Which workflow governs it
- Which risk tier applies
- Which autonomy tier applies
- Which telemetry or eval signals prove it happened safely

## Handoff Shape Between Agents

Every handoff should include:

- objective or decision
- owner
- done condition
- primary update file
- accepting role
- risk tier
- autonomy tier
- telemetry or eval expectation
- blockers or policy concerns

Private continuation belongs in `.hq/handoffs/<task>/`.

## Role Split

- `manager` owns routing, coordination, and operating follow-through for the task.
- `owner` executes the current slice of work.
- `accepts_result` decides whether the outcome is accepted.
- Default Stage 2 pattern: `AI Operations Lead` manages, `Delivery` or a specialist executes, and the named accepting role reviews the result.
