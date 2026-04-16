# Task Board

> Generated from `05 AI Control Plane/active-work.json`. Do not edit this board by hand; run `python3 scripts/hq_control_plane.py sync` after queue changes.

- Updated At: 2026-04-16
- Operating Mode: ai-first-stage-2-foundation
- Objective: Prepare HQ for public GitHub publication without leaking private runtime or live operating data

## Success Criteria
- README explains the public AI-first project clearly
- tracked example docs are public-safe and reusable
- Task Board.md is rendered from active-work.json
- local and CI validation fail on blocked private paths, sensitive local artifacts, and obvious secrets
- no tracked git history contains private runtime, customer data, personal data, or credentials

## Done
- [x] Install the machine-readable AI control plane and generated board
  - ID: install-control-plane | Manager: ai_operations_lead | Owner: delivery | Accepts: ceo | Risk: medium | Autonomy: A2
  - Project: AI-First HQ OS
  - Support: ai_operations_lead, documentation
  - Next: Use the control plane as the primary queue instead of treating it as architecture-only.
  - Done when: `05 AI Control Plane/` exists, validates, and `Task Board.md` is rendered from it.
  - Primary update file: `05 AI Control Plane/active-work.json`
  - Align: `02 Planning/Task Board.md`, `AGENTS.md`, `01 Operating System/AI-First Operating Model.md`
  - Completed at: 2026-04-15
- [x] Add telemetry, validation, and tests for the HQ runtime
  - ID: install-telemetry-and-validation | Manager: ai_operations_lead | Owner: delivery | Accepts: governor | Risk: medium | Autonomy: A2
  - Project: AI-First HQ OS
  - Support: ai_operations_lead, governor, documentation
  - Next: Keep runtime data under `.hq/` and out of tracked history.
  - Done when: Validation passes, telemetry events can be written, and tests cover the runtime surfaces.
  - Primary update file: `scripts/hq_control_plane.py`
  - Align: `scripts/hq_telemetry.py`, `tests/test_hq_control_plane.py`, `tests/test_hq_telemetry.py`
  - Completed at: 2026-04-15
- [x] Replace the stage-1 AI COO role with AI Operations Lead and tighten Stage 2 operating contracts
  - ID: embed-ai-operations-lead-and-stage-2-foundation | Manager: ai_operations_lead | Owner: delivery | Accepts: ceo | Risk: medium | Autonomy: A2
  - Project: AI-First HQ OS
  - Support: ai_operations_lead, governor, documentation
  - Next: Keep the public operating contract consistent across docs and prompts.
  - Done when: Operating docs, role prompts, control-plane contracts, and review contracts reference AI Operations Lead consistently.
  - Primary update file: `05 AI Control Plane/agent-registry.json`
  - Align: `01 Operating System/AI-First Operating Model.md`, `01 Operating System/Agent Routing.md`, `05 AI Control Plane/workflow-registry.json`, `05 AI Control Plane/metrics-registry.json`, `05 AI Control Plane/operating-policies.json`
  - Completed at: 2026-04-15
- [x] Rewrite the README and example state for public GitHub readers
  - ID: rewrite-public-readme-and-example-state | Manager: ai_operations_lead | Owner: documentation | Accepts: governor | Risk: medium | Autonomy: A2
  - Project: Public GitHub Hardening
  - Support: governor, delivery
  - Next: Keep example state public-safe as the project evolves.
  - Done when: README, planning docs, project docs, and notes explain the framework without exposing live private operations.
  - Primary update file: `README.md`
  - Align: `now.md`, `projects.md`, `02 Planning/Weekly Plan.md`, `03 Notes/Decisions.md`, `03 Notes/Open Decisions.md`, `04 Projects/Founder Revenue Sprint.md`
  - Completed at: 2026-04-16
- [x] Add a publication-safety gate for blocked paths, sensitive local artifacts, and secrets
  - ID: add-publication-safety-gate | Manager: ai_operations_lead | Owner: delivery | Accepts: governor | Risk: medium | Autonomy: A2
  - Project: Public GitHub Hardening
  - Support: ai_operations_lead, governor, documentation
  - Next: Keep the blocked-path rules and secret patterns aligned with real repository usage.
  - Done when: Local and CI validation fail if blocked private paths, sensitive local artifacts, or obvious secrets are tracked.
  - Primary update file: `scripts/hq_gate.py`
  - Align: `scripts/hq_public_safety.py`, `.github/workflows/hq-gate.yml`, `tests/test_hq_public_safety.py`, `.gitignore`
  - Completed at: 2026-04-16
