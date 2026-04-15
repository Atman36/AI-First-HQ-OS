# Weekly Plan

## Week Of 2026-04-15

### Operating Objective

Move HQ from a documentation-first operating system to an AI-first control plane without breaking source-of-truth discipline.

### Weekly Commitments

1. Keep strategic truth in root files and Notes.
2. Keep delegated work in `05 AI Control Plane/active-work.json`.
3. Render `Task Board.md` from the control plane.
4. Route work through COO -> Governor -> specialist -> Documentation.
5. Start telemetry before adding external connectors.

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
- Cycle status: stage 1 in progress
- Shipped work:
  - Machine-readable control plane installed
  - Governor role added
  - Task board can be rendered from the queue
  - Telemetry script and validation path added
- Still active work:
  - Run the first real governed operating loop
  - Resolve approval thresholds and external-write policy
  - Start collecting metrics from live work
- Blockers:
  - Approval thresholds are still provisional
  - External connector policy is intentionally blocked
- Money signal:
  - The expected gain is founder leverage and lower coordination cost, not immediate revenue yet
- Next 3 priorities:
  1. Run one real task through the new control plane.
  2. Calibrate Governor approval thresholds with the founder.
  3. Start weekly metric collection from telemetry.

### Primary Metrics This Review Must Cover

- Autonomous completion rate
- Human escalation rate
- Decision latency hours
- Documentation lag hours
- Rework or rollback rate
