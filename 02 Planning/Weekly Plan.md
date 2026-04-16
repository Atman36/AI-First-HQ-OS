# Weekly Plan

## Week Of 2026-04-16

### Operating Objective

Prepare HQ for public GitHub publication without leaking private runtime state, live company data, or local operating artifacts.

### Weekly Commitments

1. Keep delegated work in `05 AI Control Plane/active-work.json`.
2. Render `Task Board.md` from the control plane.
3. Rewrite `README.md` for public readers.
4. Replace live internal operating examples with public-safe examples.
5. Add a publication-safety gate to local validation and CI.
6. Keep `.hq/` and other sensitive local artifacts out of tracked history.
7. Keep the founder revenue sprint narrowed to the security questionnaire pilot and document only accepted conclusions in tracked files.

### Checkpoints

- The machine-readable queue is current.
- The human-readable board reflects the queue.
- Public-facing docs describe the framework, not live private operations.
- Validation fails if blocked private paths or secret material are tracked.

### Risks

- Publishing live operating data instead of reusable framework state
- Duplicate state between Markdown and control-plane JSON
- Weak publication rules that rely on memory instead of automation
- Sensitive local files being committed before review
- Founder revenue work drifting back into broad portfolio analysis instead of a single sellable wedge
- Cross-border contracting assumptions being treated as solved before counsel-backed validation

### Rule

Live delegated task movement belongs in `05 AI Control Plane/active-work.json`. This file summarizes the week; it does not replace the control plane.

### Lean Weekly Review

- Review date: 2026-04-16
- Cycle status: public GitHub hardening in progress
- Shipped work:
  - public-facing README rewritten
  - tracked example state sanitized for public publication
  - publication-safety checks added to the validation gate
- Still active work:
  - keep the blocked-path and secret scanner aligned with real project usage
  - improve public onboarding without reintroducing live private context
  - keep the founder revenue sprint documented as accepted management truth only, not as a raw research dump
- Blockers:
  - none inside the repository itself
- Next 3 priorities:
  1. Keep publication guardrails strict as the repo evolves.
 2. Keep the founder revenue sprint narrowed to a human-reviewed security questionnaire pilot.
 3. Keep all live operating memory under `.hq/`.
