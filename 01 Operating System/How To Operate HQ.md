# How To Operate HQ

This is the practical order for updating HQ in the AI-first version.

## Core Principle

- Write the smallest durable update in the highest-value source first.
- Update machine-readable task state before updating human-readable mirrors.
- Keep private runtime outside tracked company truth.
- Treat `reports/` and research drafts as support input until their conclusions are summarized into tracked truth.

## Private Runtime vs Shared State

- Shared HQ files explain company state, decisions, accepted execution, and the control plane.
- `.hq/` is private runtime only: handoffs, probe outputs, telemetry, reflections, evals, releases, and local continuation state.
- `.hq/reflections/` stores raw structured reflections after work; `.hq/improvements/` stores weekly synthesis and manual candidate improvements.
- Do not use `.hq/` as a second project registry or durable company memory layer.
- Do not use shared Markdown files as private continuation logs when `.hq/handoffs/` is the right home.

## Fill Order

### 1. Set direction

1. `now.md`
2. `projects.md`
3. `routines.md` if the operating cadence changed
4. `stack.md` if tooling or control boundaries changed
5. `03 Notes/Decisions.md` and `03 Notes/Open Decisions.md` for durable why and unresolved choices

### 2. Update the control plane

1. `05 AI Control Plane/active-work.json`
2. `05 AI Control Plane/operating-policies.json` when authority or risk policy changes
3. `05 AI Control Plane/workflow-registry.json` when workflow states or handoffs change
4. `05 AI Control Plane/metrics-registry.json` when review metrics change

### 3. Render the human mirror

- Run `python3 scripts/hq_control_plane.py sync`
- This validates the control plane and re-renders `02 Planning/Task Board.md`

### 4. Execute the work

- Route through AI Operations Lead
- Check through Governor when policy or risk requires it
- Let the specialist owner execute
- Let Documentation sync accepted results back into shared truth

### 5. Run the weekly metric review

- Run `python3 scripts/hq_telemetry.py weekly-metrics --since YYYY-MM-DD --until YYYY-MM-DD`
- Use the telemetry review as the weekly metric layer instead of reconstructing the week from chat history
- Escalate threshold breaches through AI Operations Lead and Governor before increasing autonomy

### 6. Write runtime artifacts

- `.hq/handoffs/` for continuity
- `.hq/state/` for capability probes
- `.hq/telemetry/` for events
- `.hq/reflections/` for lessons
- `.hq/evals/` and `.hq/releases/` for controlled rollout work

## Private Runtime Minimum Working Set

1. `.hq/handoffs/<task>/LATEST.md` when work is handed off or paused
2. `.hq/state/capabilities.json` when routing depends on a specific local tool
3. `.hq/reflections/YYYY-MM/YYYY-MM-DD.jsonl` when agents log task-level reflections
4. `.hq/telemetry/reviews/LATEST.md` when the weekly metric review is generated from live telemetry
5. `.hq/improvements/LATEST.md` when the reflection review produces candidate improvements for manual review
