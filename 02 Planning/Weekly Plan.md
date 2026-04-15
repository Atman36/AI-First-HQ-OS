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
  - First real governed loop completed on a live founder request through AI Operations Lead -> Governor -> Delivery -> Documentation
  - First weekly metric review generated from live telemetry instead of chat reconstruction
  - Stage 2 write boundaries narrowed to HQ-internal writes only; customer-facing sends and deploys remain human-reviewed
- Still active work:
  - Decide whether the autonomous spend envelope should remain at EUR 0 or become a bounded approved amount
  - Keep telemetry coverage reliable on non-done active tasks as the next founder requests enter the queue
  - Repeat the governed loop on the next founder request without bypassing the queue
- Blockers:
  - The spend envelope is still provisional
  - External connector policy is intentionally blocked pending another stable weekly review
- Money signal:
  - The current gain is founder leverage and lower coordination cost; no non-zero autonomous spend is justified yet
- Next 3 priorities:
  1. Close the remaining spend-envelope decision with CEO and Finance.
  2. Keep telemetry coverage explicit on each non-done active task as new work enters the queue.
  3. Run the next founder request through the same governed loop.

### Threshold Interpretation From Live Telemetry

- No metric thresholds were breached on the first live slice.
- Interpretation: this proves the operating loop is viable, but one fast internal sample is not enough evidence to expand autonomy beyond the current Stage 2 boundaries.

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
