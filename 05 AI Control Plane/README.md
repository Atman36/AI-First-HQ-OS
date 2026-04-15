# AI Control Plane

This folder is the machine-readable operating layer of HQ.

## Files

- `active-work.json` - live delegated-work queue
- `agent-registry.json` - role registry and authority map
- `operating-policies.json` - autonomy tiers, risk tiers, approvals, kill switches
- `workflow-registry.json` - workflow states and required task fields
- `metrics-registry.json` - primary review metrics
- `schemas/` - JSON contracts for task state and telemetry events

## Rules

- Update `active-work.json` first when delegated task state changes.
- Validate with `python3 scripts/hq_control_plane.py validate`.
- Re-render `02 Planning/Task Board.md` with `python3 scripts/hq_control_plane.py sync`.
- Do not let this folder drift from the strategic truth in root files and Notes.
