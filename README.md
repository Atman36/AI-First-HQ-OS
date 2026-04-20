# AI-First HQ OS

![AI-First](https://img.shields.io/badge/Operating%20Model-AI--First-111111)
![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)
![Markdown](https://img.shields.io/badge/Docs-Markdown-000000?logo=markdown&logoColor=white)
![Codex](https://img.shields.io/badge/Built%20with-Codex-412991)

AI-First operating system for running a small company with Markdown source of truth, agent prompts, governance rules, and Python scripts for control-plane workflows, telemetry, and safe delegation.

## Overview

This repository packages the reusable public shell of an AI-first company operating system:

- Live operating state stays local and out of git history
- `05 AI Control Plane/schemas/` holds reusable schemas for the local control plane
- `agents/` contains role prompts for specialized execution
- `skills/` contains reusable callable skills for slash-style invocation and UI surfacing
- `docs/` contains public-safe architecture notes and project briefs
- `scripts/` provides validation, telemetry, runtime helpers, the additive mission runtime nucleus, and publication guardrails
- `.hq/` is reserved for private local runtime artifacts and live operating state; it must never enter public git history
- large work should use a private `.hq/specs/` packet plus `.hq/handoffs/` continuity instead of reopening the whole repo context in each new chat

## Features

- AI-first control plane for governed delegation
- additive `Mission` / `Run` / `Step` / `Approval` state nucleus for durable local execution
- role-based agent prompts
- shared role-prompt skeleton with generator-backed normalization
- reusable skills with UI metadata
- machine-readable workflow and policy layer
- telemetry and runtime helper scripts
- public-safety validation for GitHub publication
- allowlist-based publication guardrails for GitHub

## Repository Structure

- `AGENTS.md` shared repository rules
- `agents/*/AGENTS.md` role-specific prompts
- `skills/*/SKILL.md` reusable skill definitions
- `05 AI Control Plane/schemas/` reusable schema definitions
- `docs/` public-safe architecture and project documentation
- `scripts/` validation, runtime, telemetry, and publication-safety tools
- `tests/` automated coverage for core behavior
- `agents/*/AGENTS.md` role prompts safe for publication
- `skills/` agent skills safe for publication
- `scripts/hq_role_prompt_scaffold.py` shared role-prompt generator for `agents/*/AGENTS.md`
- `scripts/hq_private_prompt_lint.py` local lint for private `.hq/prompts/`

## Quick Start

```bash
python3 -m pip install -r requirements-dev.txt
python3 scripts/hq_runtime.py bootstrap
python3 scripts/hq_mission_runtime.py init
python3 scripts/hq_control_plane.py validate
python3 scripts/hq_control_plane.py sync
python3 scripts/hq_control_plane.py status
python3 scripts/hq_runtime.py spec --task "Example large task" --goal "Define the next narrow slice"
python3 scripts/hq_role_prompt_scaffold.py --check
python3 -m unittest discover tests
python3 scripts/hq_public_safety.py
python3 scripts/hq_private_prompt_lint.py
python3 scripts/hq_gate.py
```

`python3 scripts/hq_runtime.py bootstrap` creates the local-only HQ scaffold that is intentionally not published to GitHub: `now.md`, `projects.md`, planning/notes/project pages, and the local control-plane JSON files.

## Core Commands

```bash
python3 scripts/hq_runtime.py bootstrap
python3 scripts/hq_mission_runtime.py init
python3 scripts/hq_control_plane.py status
python3 scripts/hq_runtime.py spec --task "Example large task"
python3 scripts/hq_runtime.py handoff --task "Example large task" --spec-file .hq/specs/example-large-task/LATEST.md
python3 scripts/hq_control_plane.py validate
python3 scripts/hq_control_plane.py sync
python3 scripts/hq_role_prompt_scaffold.py --check
python3 -m unittest discover tests
python3 scripts/hq_public_safety.py
python3 scripts/hq_private_prompt_lint.py
python3 scripts/hq_gate.py
```

The supported local test runner is `python3 -m unittest discover tests`. `pytest` is not a required project dependency or part of the official local/CI gate.

Start a new session with `python3 scripts/hq_control_plane.py status`. That command writes `.hq/state/session-bootstrap.json` and prints a compact live-state projection with:

- one `startup_focus` task with the current primary move
- up to two adjacent `support_tracks` for the same session corridor
- active tasks without `done`
- blocked tasks with a short reason
- the current `next_step` per live task
- stale spec/handoff signals in a separate block
- the recommended next command for the next slice

Use `python3 scripts/hq_control_plane.py status --json` when another script or tool needs the same projection in machine-readable form.
The same run also refreshes `.hq/state/memory-index.json` as a smaller startup capsule for future runtime consumers.

Use `spec` for large or ambiguous work. The spec is a private, task-scoped context packet under `.hq/specs/` so the next chat can read the narrow brief first instead of reloading broad bootstrap context. Use `handoff` to capture execution continuity, blockers, and next steps around that spec.

`scripts/hq_runtime.py` remains the compatibility surface for bootstrap, spec, and handoff helpers. `scripts/hq_mission_runtime.py` is the additive runtime nucleus for first-class `Mission`, `Run`, `Step`, `Approval`, and `Artifact` records; it should grow before any deep rewrite of the older helper surface.

Tracked role prompts are generated from the shared skeleton. The generated prompts now include a short `Quick Start` plus split `Always Read` / `Read When Needed` paths, so update `scripts/hq_role_prompt_scaffold.py` and regenerate instead of hand-editing `agents/*/AGENTS.md`. After changing the scaffold, run `python3 scripts/hq_role_prompt_scaffold.py --write` and then `python3 scripts/hq_role_prompt_scaffold.py --check`.

When `.hq/prompts/` exists locally, run `python3 scripts/hq_private_prompt_lint.py` to catch broken local paths, invalid absolute references, and weak audit-prompt feedback loops before relying on those prompts in a new session.

## Public GitHub Boundary

The public repository is allowlist-only. These path classes are allowed:

- `README.md`, `AGENTS.md`, `.gitignore`, `requirements-dev.txt`
- `docs/`
- `.github/workflows/`
- `agents/*/AGENTS.md`
- `skills/`
- `scripts/`
- `tests/`
- `05 AI Control Plane/schemas/`

Everything else is local-only and must not be tracked.

Keep these private:

- `.hq/` runtime state, telemetry, handoffs, evals, reflections, releases, and local prompts
- `.hq/specs/` private task packets for large work
- live operating docs such as `now.md`, `projects.md`, `routines.md`, `stack.md`, and Markdown work under `02 Planning/`, `03 Notes/`, and `04 Projects/`
- raw customer or prospect data
- personal notes, journals, archives, and imported research dumps
- credentials, API keys, private keys, payment exports, and banking material
- temporary datasets and local environment files

If a file contains personal data, customer data, raw imports, credentials, payment artifacts, or private working memory, keep it under `.hq/` or outside this repository.

Before pushing, run `python3 scripts/hq_public_safety.py` or the full `python3 scripts/hq_gate.py`.
