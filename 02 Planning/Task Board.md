# Task Board

> Generated from `05 AI Control Plane/active-work.json`. Do not edit this board by hand; run `python3 scripts/hq_control_plane.py sync` after queue changes.

- Updated At: 2026-04-15
- Operating Mode: ai-first-stage-2-foundation
- Objective: Install the Stage 2 operating discipline, prove the governed loop is repeatable, and tighten repeated-work verification

## Success Criteria
- AI Operations Lead replaces the stage-1 AI COO role across docs and control-plane contracts
- two real tasks run through AI Operations Lead -> Governor -> specialist -> Documentation
- the queue stays current in active-work.json and Task Board.md is rendered from it
- weekly metrics can be generated from telemetry and active-work state
- telemetry captures routing, execution, acceptance, sync, and lightweight eval signals
- weekly review requires a passing local task-cycle signal on repeated AI-Operations-led internal execution slices

## Waiting
- [ ] Connect email, calendar, and CRM writes only behind explicit Governor-reviewed connectors
  - ID: connect-external-systems-under-governance | Owner: delivery | Accepts: ceo | Risk: high | Autonomy: A3
  - Project: HQ Bootstrap
  - Support: ai_operations_lead, governor, assistant, finance, growth
  - Next: Keep external write surfaces blocked while the autonomous spend envelope stays at EUR 0, then revisit one narrow connector only after another stable weekly review and connector-specific rollback notes.
  - Done when: At least one external connector is enabled with audit logging, review, and rollback notes.
  - Primary update file: `stack.md`
  - Align: `05 AI Control Plane/operating-policies.json`, `04 Projects/HQ Bootstrap.md`

## Done
- [x] Install the machine-readable AI control plane and generated board
  - ID: install-control-plane | Owner: delivery | Accepts: ceo | Risk: medium | Autonomy: A2
  - Project: HQ Bootstrap
  - Support: ai_operations_lead, documentation
  - Next: Use the control plane on live work instead of treating it as architecture-only.
  - Done when: `05 AI Control Plane/` exists, validates, and `Task Board.md` is rendered from it.
  - Primary update file: `05 AI Control Plane/active-work.json`
  - Align: `02 Planning/Task Board.md`, `AGENTS.md`, `01 Operating System/AI-First Operating Model.md`
  - Completed at: 2026-04-15
- [x] Add telemetry, validation, and tests for the HQ runtime
  - ID: install-telemetry-and-validation | Owner: delivery | Accepts: governor | Risk: medium | Autonomy: A2
  - Project: HQ Bootstrap
  - Support: ai_operations_lead, governor, documentation
  - Next: Start writing real events from live work into `.hq/telemetry/`.
  - Done when: Validation passes, telemetry events can be written, and tests cover the new runtime surfaces.
  - Primary update file: `scripts/hq_control_plane.py`
  - Align: `scripts/hq_telemetry.py`, `tests/test_hq_control_plane.py`, `tests/test_hq_telemetry.py`
  - Completed at: 2026-04-15
- [x] Replace the stage-1 AI COO role with AI Operations Lead and tighten Stage 2 operating contracts
  - ID: embed-ai-operations-lead-and-stage-2-foundation | Owner: delivery | Accepts: ceo | Risk: medium | Autonomy: A2
  - Project: HQ Bootstrap
  - Support: ai_operations_lead, governor, documentation
  - Next: Run a real work item through the updated routing and weekly-review discipline.
  - Done when: Operating docs, role prompts, control-plane contracts, and runtime review contracts all reference AI Operations Lead consistently.
  - Primary update file: `05 AI Control Plane/agent-registry.json`
  - Align: `01 Operating System/AI-First Operating Model.md`, `01 Operating System/Agent Routing.md`, `05 AI Control Plane/workflow-registry.json`, `05 AI Control Plane/metrics-registry.json`, `05 AI Control Plane/operating-policies.json`
  - Completed at: 2026-04-15
- [x] Run one real company task through AI Operations Lead -> Governor -> specialist -> Documentation
  - ID: run-first-governed-loop | Owner: ai_operations_lead | Accepts: ceo | Risk: medium | Autonomy: A2
  - Project: HQ Bootstrap
  - Support: governor, delivery, documentation
  - Next: Repeat the same governed route on the next founder request and use the telemetry baseline to tighten the remaining thresholds.
  - Done when: One task completes with queue state, acceptance, board sync, telemetry coverage, and a weekly metric-review entry.
  - Primary update file: `05 AI Control Plane/active-work.json`
  - Align: `02 Planning/Weekly Plan.md`, `04 Projects/HQ Bootstrap.md`
  - Completed at: 2026-04-15
- [x] Run the first weekly metric review from telemetry and threshold rules
  - ID: start-weekly-metric-review-from-telemetry | Owner: ai_operations_lead | Accepts: governor | Risk: medium | Autonomy: A2
  - Project: HQ Bootstrap
  - Support: governor, documentation, finance
  - Next: Use weekly review breaches as operating follow-through, not as a second reporting layer.
  - Done when: A weekly telemetry review is generated and used as the metric layer of the weekly operating review.
  - Primary update file: `05 AI Control Plane/metrics-registry.json`
  - Align: `routines.md`, `02 Planning/Weekly Plan.md`, `scripts/hq_telemetry.py`
  - Completed at: 2026-04-15
- [x] Lock the remaining autonomous spend envelope after the first live weekly review
  - ID: calibrate-approval-thresholds | Owner: governor | Accepts: ceo | Risk: high | Autonomy: A1
  - Project: HQ Bootstrap
  - Support: ceo, finance, ai_operations_lead
  - Next: Re-open only if a specific connector or operating need justifies non-zero spend and another stable telemetry-backed review supports it.
  - Done when: The spend envelope is explicitly approved or intentionally held at zero in policies and Notes.
  - Primary update file: `03 Notes/Open Decisions.md`
  - Align: `05 AI Control Plane/operating-policies.json`, `03 Notes/Decisions.md`
  - Completed at: 2026-04-15
- [x] Run a second live governed loop and verify the full task cycle locally
  - ID: verify-second-governed-loop | Owner: ai_operations_lead | Accepts: ceo | Risk: medium | Autonomy: A2
  - Project: HQ Bootstrap
  - Support: governor, delivery, documentation
  - Next: Use this second live proof to choose one smallest practical repeated-work verification slice without changing spend or connector policy.
  - Done when: The second live item completes with queue state, Governor review, execution, acceptance, documentation sync, telemetry coverage, and a local task-cycle verification result.
  - Primary update file: `05 AI Control Plane/active-work.json`
  - Align: `scripts/hq_telemetry.py`, `tests/test_hq_telemetry.py`, `02 Planning/Weekly Plan.md`, `04 Projects/HQ Bootstrap.md`
  - Completed at: 2026-04-15
- [x] Require task-cycle coverage in weekly review for repeated internal governed work
  - ID: require-task-cycle-on-repeated-internal-work | Owner: ai_operations_lead | Accepts: ceo | Risk: medium | Autonomy: A2
  - Project: HQ Bootstrap
  - Support: governor, delivery, documentation
  - Next: Keep this check attached to repeated internal governed slices while spend stays at EUR 0 and connectors remain blocked.
  - Done when: Weekly review reports a repeated internal task-cycle coverage signal and breaches if a repeated governed internal slice lacks a passing local check.
  - Primary update file: `05 AI Control Plane/metrics-registry.json`
  - Align: `05 AI Control Plane/operating-policies.json`, `05 AI Control Plane/workflow-registry.json`, `scripts/hq_telemetry.py`, `tests/test_hq_telemetry.py`, `02 Planning/Weekly Plan.md`, `04 Projects/HQ Bootstrap.md`
  - Completed at: 2026-04-15
