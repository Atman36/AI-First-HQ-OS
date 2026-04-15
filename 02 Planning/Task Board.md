# Task Board

> Generated from `05 AI Control Plane/active-work.json`. Do not edit this board by hand; run `python3 scripts/hq_control_plane.py sync` after queue changes.

- Updated At: 2026-04-15
- Operating Mode: ai-first-stage-1
- Objective: Install an AI-first control plane and run the first governed operating loop

## Success Criteria
- one real task runs through COO -> Governor -> specialist -> Documentation
- the queue stays current in active-work.json
- Task Board.md is rendered from the queue
- telemetry captures routing, execution, acceptance, and sync events

## This Week
- [ ] Run one real company task through COO -> Governor -> specialist -> Documentation
  - ID: run-first-governed-loop | Owner: coo | Accepts: ceo | Risk: medium | Autonomy: A2
  - Project: HQ Bootstrap
  - Support: governor, delivery, documentation
  - Next: Pick a real founder request and execute it through the new control plane without bypasses.
  - Done when: One task completes with queue state, acceptance, board sync, and telemetry events.
  - Primary update file: `05 AI Control Plane/active-work.json`
  - Align: `02 Planning/Weekly Plan.md`, `03 Notes/Decisions.md`, `04 Projects/HQ Bootstrap.md`
- [ ] Calibrate Governor approval thresholds and external action policy
  - ID: calibrate-approval-thresholds | Owner: governor | Accepts: ceo | Risk: high | Autonomy: A1
  - Project: HQ Bootstrap
  - Support: ceo, finance
  - Next: Resolve open decisions about budget, external sends, deploy authority, and connector write access.
  - Done when: `03 Notes/Open Decisions.md` is reduced and `operating-policies.json` reflects approved thresholds.
  - Primary update file: `03 Notes/Open Decisions.md`
  - Align: `05 AI Control Plane/operating-policies.json`, `03 Notes/Decisions.md`

## Waiting
- [ ] Connect email, calendar, and CRM writes only behind explicit Governor-reviewed connectors
  - ID: connect-external-systems-under-governance | Owner: delivery | Accepts: ceo | Risk: high | Autonomy: A3
  - Project: HQ Bootstrap
  - Support: governor, assistant, finance, growth
  - Next: Do not connect external write surfaces until thresholds, logging, and rollback rules are agreed.
  - Done when: At least one external connector is enabled with audit logging, review, and rollback notes.
  - Primary update file: `stack.md`
  - Align: `05 AI Control Plane/operating-policies.json`, `04 Projects/HQ Bootstrap.md`

## Done
- [x] Install the machine-readable AI control plane and generated board
  - ID: install-control-plane | Owner: delivery | Accepts: ceo | Risk: medium | Autonomy: A2
  - Project: HQ Bootstrap
  - Support: coo, documentation
  - Next: Use the control plane on live work instead of treating it as architecture-only.
  - Done when: `05 AI Control Plane/` exists, validates, and `Task Board.md` is rendered from it.
  - Primary update file: `05 AI Control Plane/active-work.json`
  - Align: `02 Planning/Task Board.md`, `AGENTS.md`, `01 Operating System/AI-First Operating Model.md`
  - Completed at: 2026-04-15
- [x] Add telemetry, validation, and tests for the HQ runtime
  - ID: install-telemetry-and-validation | Owner: delivery | Accepts: governor | Risk: medium | Autonomy: A2
  - Project: HQ Bootstrap
  - Support: governor, documentation
  - Next: Start writing real events from live work into `.hq/telemetry/`.
  - Done when: Validation passes, telemetry events can be written, and tests cover the new runtime surfaces.
  - Primary update file: `scripts/hq_control_plane.py`
  - Align: `scripts/hq_telemetry.py`, `tests/test_hq_control_plane.py`, `tests/test_hq_telemetry.py`
  - Completed at: 2026-04-15
