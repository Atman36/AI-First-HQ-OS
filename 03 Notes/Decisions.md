# Decisions

## 2026-04-14

### Lean HQ Structure

- Decision: keep shared company state in the HQ repository and keep private runtime under `.hq/`.
- Reason: the company needs one inspectable shared truth and one private runtime, not mixed memory.

### Single Primary Update File

- Decision: every active task must name one primary update file.
- Reason: this reduces drift and makes delegated work easier to accept and document.

### Delivery Role

- Decision: keep a dedicated Delivery role for bounded implementation work.
- Reason: the system needs a default execution owner between routing and documentation.

## 2026-04-15

### HQ Must Become AI-First, Not AI-Themed

- Decision: treat HQ as the future operating system of the company, not as a note vault with AI around it.
- Reason: the current structure is good for clarity but not yet strong enough for delegated authority, AI routing, or scalable operations.

### Install A Machine-Readable Control Plane

- Decision: add `05 AI Control Plane/` as the tracked machine-readable layer for active work, authority, workflows, policies, and metrics.
- Reason: AI cannot operate reliably from free-form Markdown alone.

### Machine-Readable Queue Becomes Primary For Delegated Work

- Decision: use `05 AI Control Plane/active-work.json` as the primary queue for delegated work and render `02 Planning/Task Board.md` from it.
- Reason: the old board was readable but not executable.

### Add Governor As A Standing Role

- Decision: add Governor as the role responsible for policy enforcement, approval gates, kill switches, and rollback triggers.
- Reason: without a control role, the system would have routing but no governed autonomy.

### Introduce Autonomy And Risk Tiers

- Decision: every delegated task must carry both a risk tier and an autonomy tier.
- Reason: AI-first execution needs explicit boundaries, not implied trust.

### Humans Stay In Strategy And Risk-Sensitive Control

- Decision: keep CEO and human reviewers in strategy, budget, legal/public commitments, destructive actions, hiring, and overrides.
- Reason: the project is early; full autonomy here would be reckless and unnecessary.

### Add Telemetry Before External Connectors

- Decision: do not connect external write surfaces until telemetry, approval policy, and rollback rules exist.
- Reason: external autonomy without logging and intervention paths would create hidden operational risk.

### Replace Stage-1 AI COO With AI Operations Lead

- Decision: replace the stage-1 AI COO role with `AI Operations Lead` as the one standing operating role for orchestration, observability, eval discipline, memory hygiene, escalation thresholds, and runtime quality.
- Reason: the system needs one explicit operating owner for Stage 2, not duplicated routing authority between a generic COO label and a new operations role.

### Weekly Metric Review Must Come From Telemetry

- Decision: run the weekly metric review from `.hq/telemetry/` and control-plane state instead of reconstructing the week from chat memory.
- Reason: Stage 2 discipline requires inspectable evidence, threshold breaches, and carry-forward actions grounded in runtime data.

### Stage 2 Internal Writes Stay Inside HQ

- Decision: in Stage 2, AI may write only to tracked files in this repository and private runtime artifacts under `.hq/` when the task is scoped and accepted.
- Reason: the first governed loop proved repo-internal execution and documentation sync; broader write autonomy still lacks surface-specific audit and rollback rules.

### External And Customer-Facing Writes Stay Blocked

- Decision: email, calendar, CRM, and other customer-facing or external sends stay draft-only and require human review before execution.
- Reason: internal operating proof is enough to run the loop inside HQ, but it is not evidence for asymmetric external-message risk.

### Deployment Authority Stays Human-Only In Stage 2

- Decision: Delivery may prepare code, PRs, release notes, and rollback plans, but production-affecting deploys remain human-only.
- Reason: the new operating loop improves internal execution, not the safety of autonomous production changes.

### Runtime Memory Boundary Is Good Enough For Stage 2

- Decision: telemetry, handoffs, reflections, evals, and other runtime continuity stay under `.hq/`; only accepted conclusions move into tracked truth.
- Reason: the first live governed loop confirmed that this split keeps shared state clean without adding a second memory layer.

### Autonomous Spend Envelope Stays At EUR 0 In Stage 2 Foundation

- Decision: keep the autonomous spend envelope at `EUR 0` for the whole Stage 2 foundation; any company spend or money movement still needs fresh CEO approval.
- Reason: the first telemetry-backed weekly review did not justify non-zero autonomous spend, and there is still no connector-specific audit or rollback path that would make autonomous spend safe.
