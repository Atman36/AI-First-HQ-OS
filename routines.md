# Routines

## Daily

### Morning

- Assistant captures inbound requests and clarifies missing context.
- COO updates `05 AI Control Plane/active-work.json` for new or changed delegated work.
- Governor checks high-risk or policy-sensitive items before execution starts.
- CEO reviews only exceptions, strategic choices, or blocked high-risk work.

### During The Day

- AI roles execute low- and medium-risk work inside the control plane.
- Delivery, Research, Finance, Growth, and Assistant do bounded specialist work.
- Documentation syncs accepted outputs back into shared truth.
- Governor watches for policy gaps, missing approvals, rollback triggers, and repeated rework.

### End Of Day

- COO reviews blocked tasks, queue health, and cycle time.
- Documentation re-renders `Task Board.md` if task state changed.
- Governor reviews escalations, override events, and telemetry gaps.
- CEO reviews only the exceptions that still need a human decision.

## Weekly

### Lean Weekly Review

- Owner: COO
- Control and safety support: Governor
- Business support: Finance
- Shared truth support: Documentation
- Approver of next priorities: CEO
- Inputs: `05 AI Control Plane/`, `02 Planning/Weekly Plan.md`, `03 Notes/Decisions.md`, `03 Notes/Open Decisions.md`, active project pages, and `.hq/telemetry/`
- Output: one weekly review with shipped work, still active work, blockers, money signal, and the five primary AI-first metrics

### Review Checks

- Autonomous completion rate
- Human escalation rate
- Decision latency
- Documentation lag
- Rework or rollback rate

### Guardrail Rule

Do not add a second reporting layer. Weekly review should interpret the control plane and telemetry, not duplicate them.
