---
name: hq-research-router
description: Use when a deep research report, GPT analysis pack, synthesis document, or external research artifact arrives and needs to be routed into the HQ operating system. Routes to DEEP_RESEARCH_INDEX.md, active-work.json, .hq/specs/, or .hq/handoffs/ depending on action type.
---

# HQ Research Router

Use this skill as the single intake workflow for processing incoming research packets. A research packet is any document produced outside a live session that carries strategic, technical, or operational intelligence: deep research reports, GPT analysis packs, competitive audits, synthesis docs, or founder-run analysis outputs.

## Read First

- `AGENTS.md`
- `python3 scripts/hq_control_plane.py status`
- `reports/DEEP_RESEARCH_INDEX.md`
- `05 AI Control Plane/active-work.json` when the packet implies a new task
- `05 AI Control Plane/operating-policies.json` when the packet implies a risk or approval change

## Trigger Shape

Use this skill for requests like:
- "I have a new deep research report"
- "route this analysis pack"
- "add this to the index"
- "process this GPT output"
- "file this research"

## Routing Decision Tree

For each incoming packet, apply this decision in order:

1. **Rename first**: If the filename is ambiguous or contains special characters (e.g., "— копия", "copy"), rename to `YYYY-MM-DD-<slug>.md` matching the content topic and file date.
2. **Index it**: Add an entry to `reports/DEEP_RESEARCH_INDEX.md` under the correct thematic section with a one-paragraph description of what the packet contains and when it supersedes or supplements prior research.
3. **Extract tasks**: If the packet identifies gaps, required actions, or next steps that cross the task-acceptance bar (owner, risk tier, autonomy tier, workflow, next step, done-when), create or update tasks in `05 AI Control Plane/active-work.json` using the `$hq-task-lifecycle` skill.
4. **Write spec/handoff**: If the packet is too large to embed in a task but contains bounded execution context, write a spec or handoff under `.hq/specs/<slug>/LATEST.md` using the `$hq-spec-handoff-writer` skill. Link it from the active-work task.
5. **Retire superseded entries**: If the packet supersedes an existing index entry, mark the old entry with a `> Superseded by:` callout rather than deleting it.
6. **Run validate**: After any `active-work.json` change, run `python3 scripts/hq_control_plane.py validate`.

## Default Workflow

1. Identify the packet type, source path, and whether it is approved for tracked publication.
2. Choose exactly one primary route: index-only, task update, spec/handoff, or founder-only decision.
3. Apply the routing decision tree above without copying raw private research into tracked truth.
4. Run validation when the queue changes and report any remaining founder-only decision.

## Guardrails

- Never commit the raw research packet to public git unless it is explicitly approved for publication (most deep-research content in `reports/deep-research/` is private-path-blocked by `hq_public_safety.py`).
- Do not summarize directly into source-of-truth operating files (`now.md`, `projects.md`, `routines.md`) without founder review; write a handoff instead.
- Do not create active-work tasks without all required contract fields.
- Keep prospect names, customer data, and financial details out of the index entries.

## Expected Output Shape

- File renamed: old name → new name
- Index entry added: section, title, one-line summary
- Tasks created or updated: task ids, workflow state
- Spec/handoff written: path
- Validate result:
- Remaining founder-only decision:
