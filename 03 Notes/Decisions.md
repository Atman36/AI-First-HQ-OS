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
