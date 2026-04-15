# HQ AI-First Roadmap

## Purpose

Turn the current stage-1 control-plane baseline into the real operating engine of the company without adding premature complexity.

## Nearest Stage 2 Foundation Now

- Replace the stage-1 AI COO role with `AI Operations Lead` as the single operating role for orchestration, observability, eval discipline, memory hygiene, escalation thresholds, and runtime quality.
- Keep the existing three workflows, but make their acceptance and telemetry contracts explicit.
- Make weekly metric review run from telemetry and control-plane state instead of chat reconstruction.
- Add lightweight eval discipline for repeated work and control-plane changes without building a heavy QA platform.
- Keep external writes blocked until one narrow connector can be approved with policy, audit logging, and rollback notes.

## 0-30 Days

### Goal

Prove one governed loop on real founder work.

### Deliverables

- Run 1-3 real founder tasks through `AI Operations Lead -> Governor -> specialist -> Documentation`
- Keep `05 AI Control Plane/active-work.json` as the live queue for delegated work
- Log routing, execution, approval, acceptance, and sync events into `.hq/telemetry/`
- Finalize the first approval thresholds for external writes, deploys, spend, and human-only boundaries
- Use the five primary metrics in the weekly review

### Exit Criteria

- At least one task completes through the control plane without bypassing it
- `02 Planning/Task Board.md` stays rendered from the queue
- `03 Notes/Open Decisions.md` is reduced on the highest-risk policy questions

## Gate Before Further Expansion

- Before starting the next expansion tasks, add one more real founder or internal HQ work item and run it through the current governed loop.
- Verify locally that queue state, Governor review, execution, acceptance, documentation sync, and telemetry coverage all work on that live item.
- Only after that verification choose the next smallest expansion slice, such as a connector policy, repeated-work eval tightening, or another autonomy change.

## 31-90 Days

### Goal

Turn the baseline into a reliable operating discipline.

### Deliverables

- Formalize 2-3 stable machine-readable workflows for recurring work classes
- Embed `AI Operations Lead` as the operating owner instead of keeping a generic AI COO label
- Add lightweight acceptance and eval checks for repeated task types
- Start a mandatory weekly metric review from telemetry instead of chat memory
- Enable one limited external write surface only behind Governor-reviewed policy and rollback rules
- Track founder hours recovered, rework rate, and documentation lag

### Exit Criteria

- Weekly review uses real telemetry rather than manual reconstruction
- AI Operations Lead owns queue health, observability, and runtime discipline without duplicating Governor
- One external action surface is governed end to end
- Recurring work has explicit acceptance checks instead of ad hoc review

## 91-180 Days

### Goal

Make HQ the operating backbone rather than a documentation layer with AI around it.

### Deliverables

- Connect selected external systems behind explicit policy, audit logging, and rollback notes
- Add release and rollback discipline for AI-driven operational changes
- Review policies monthly and tighten or relax autonomy based on evidence
- Link finance, growth, and workflow metrics to business outcomes
- Remove routine founder bypasses that skip the queue or decision layer

### Exit Criteria

- Control-plane usage is the default path for standard operating work
- Policy changes are driven by telemetry and review, not ad hoc preference
- External automation remains bounded, reversible, and auditable

## Not Yet

- Autonomous production deploys
- Unreviewed external messaging
- Unrestricted spend
- Heavy memory infrastructure
- Overengineered multi-agent orchestration
- Self-modifying policy loops
