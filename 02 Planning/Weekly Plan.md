# Weekly Plan

## Week Of 2026-04-15

### Operating Objective

Move HQ from a stage-1 baseline to a stage-2 operating discipline without breaking source-of-truth discipline.

### Weekly Commitments

1. Keep strategic truth in root files and Notes.
2. Keep delegated work in `05 AI Control Plane/active-work.json`.
3. Render `Task Board.md` from the control plane.
4. Route work through AI Operations Lead -> Governor -> specialist -> Documentation.
5. Start telemetry-backed weekly metric review before adding external connectors.

### Checkpoints

- The machine-readable queue is current.
- The human-readable board reflects the queue.
- Governor reviews medium- and high-risk work before execution.
- At least one real task completes through the new control plane.
- Weekly review includes the five primary AI-first metrics.

### Risks

- Decorative AI-first language without real delegated authority
- Duplicate state between Markdown and control-plane JSON
- Governance too weak for real autonomy
- Governance too heavy for the current stage
- External writes added before logging and rollback exist

### Rule

Live delegated task movement belongs in `05 AI Control Plane/active-work.json`. This file summarizes the week; it does not replace the control plane.

### Lean Weekly Review

- Review date: 2026-04-15
- Cycle status: stage 2 foundation in progress
- Shipped work:
  - Machine-readable control plane installed
  - Governor role added
  - Task board can be rendered from the queue
  - Telemetry script and validation path added
  - AI Operations Lead role embedded as the standing operating owner
  - Weekly metric review contract added for telemetry-backed review
- Still active work:
  - Run the first real governed operating loop
  - Resolve approval thresholds and external-write policy
  - Start collecting weekly metrics from live work instead of chat reconstruction
- Blockers:
  - Approval thresholds are still provisional
  - External connector policy is intentionally blocked
- Money signal:
  - The expected gain is founder leverage and lower coordination cost, not immediate revenue yet
- Next 3 priorities:
  1. Run one real task through the new control plane.
  2. Run the first telemetry-backed weekly metric review.
  3. Calibrate Governor approval thresholds with the founder.

### Primary Metrics This Review Must Cover

- Autonomous completion rate
- Human escalation rate
- Decision latency hours
- Documentation lag hours
- Rework or rollback rate

### Operating Discipline Signals

- Telemetry coverage rate
- Eval coverage rate
- Memory hygiene exceptions
