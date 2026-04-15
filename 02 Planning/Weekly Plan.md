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
  - Autonomous spend envelope closed at `EUR 0` for the Stage 2 foundation
  - Second real governed loop completed on a new founder request with a local task-cycle verification check covering queue state, policy gate, execution, acceptance, documentation sync, and telemetry coverage
  - Weekly review now treats `task-cycle` as a required signal on repeated AI-Operations-led internal execution slices and breaches if a repeated slice lacks a passing local check
- Still active work:
  - Keep telemetry coverage reliable on non-done active tasks as the next founder requests enter the queue
  - Keep repeated internal governed work on the new `task-cycle` coverage rule as the next founder requests enter the queue
  - Keep external connector expansion blocked until another stable weekly review and a connector-specific policy slice exist
- Blockers:
  - No blocking open decision remains inside Stage 2 foundation
  - External connector policy is intentionally blocked pending another stable weekly review and a concrete use case
- Money signal:
  - The current gain is founder leverage and lower coordination cost; autonomous spend remains fixed at `EUR 0`
- Next 3 priorities:
  1. Keep telemetry coverage explicit on each non-done active task as new work enters the queue.
  2. Keep `task-cycle` attached to repeated internal governed work instead of opening a connector or autonomy expansion.
  3. Revisit connector policy only when there is one narrow use case with rollback notes.

### Threshold Interpretation From Live Telemetry

- No metric thresholds were breached on the first two live slices.
- Interpretation: this proves the operating loop is repeatable on internal work, but it is still not evidence for connector expansion, non-zero spend, or broader autonomy.

### Primary Metrics This Review Must Cover

- Autonomous completion rate
- Human escalation rate
- Decision latency hours
- Documentation lag hours
- Rework or rollback rate

### Operating Discipline Signals

- Telemetry coverage rate
- Eval coverage rate
- Repeated internal task-cycle rate
- Memory hygiene exceptions
