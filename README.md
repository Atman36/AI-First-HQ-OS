# AI-First HQ OS

![AI-First](https://img.shields.io/badge/Operating%20Model-AI--First-111111)
![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)
![Markdown](https://img.shields.io/badge/Docs-Markdown-000000?logo=markdown&logoColor=white)
![Codex](https://img.shields.io/badge/Built%20with-Codex-412991)

AI-First operating system for running a small company with Markdown source of truth, agent prompts, and an agent control plane: deny-by-default permissions, runtime governance, telemetry, and a feedback loop for safe delegation.

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
- deny-by-default permission model with a `can()` decision function and capability grants
- pre-action approval gates with approval-as-continuation and RESUMED-state handling
- byte-stable, secret-scrubbed run receipts for an audit trail
- release gate with required-evidence checks and diff-based permission-expansion enforcement
- short feedback loop: per-run receipts, baseline/best metrics, and a review-due trigger
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
- `scripts/hq_role_prompt_scaffold.py` shared role-prompt generator for `agents/*/AGENTS.md`
- `scripts/hq_private_prompt_lint.py` local lint for private `.hq/prompts/`
- `scripts/hq_permissions.py` deny-by-default `can()` authorization decisions
- `scripts/hq_policy_hooks.py` pre-action gates, approval checkpoints, and run receipts
- `scripts/hq_feedback_loop.py` per-run feedback receipts, metrics, and the review-due trigger
- `scripts/hq_gate.py` release gate with required-evidence and permission-expansion checks
- `scripts/hq_reference_scan.py` reference-pattern analysis with a dynamic identifier scan

## Quick Start

```bash
python3 -m venv .venv && source .venv/bin/activate  # needed when system Python is externally managed (PEP 668)
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
python3 scripts/hq_permissions.py check --agent ai_operations_lead --action update_task_state --scope hq:control-plane/task-board
python3 scripts/hq_feedback_loop.py summary
python3 scripts/hq_feedback_loop.py review-status
python3 -m unittest discover tests
python3 scripts/hq_public_safety.py
python3 scripts/hq_private_prompt_lint.py
python3 scripts/hq_gate.py
```

The supported local test runner is `python3 -m unittest discover tests`. `pytest` is not a required project dependency or part of the official local/CI gate.

Start a new session with `python3 scripts/hq_control_plane.py status`. That command writes `.hq/state/session-bootstrap.json` and prints a compact live-state projection with:

- one `startup_focus` task with the current primary move
- up to two adjacent `support_tracks`, preferring the same project corridor before cross-project fallback
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

## Permissions and Governance

Agent authority is least-privilege and policy-as-code. The agent registry carries `capability_grants`, and `05 AI Control Plane/permission-grants.json` holds the grant/deny table (live data files are gitignored, so CI bootstrap samples mirror them).

- `python3 scripts/hq_permissions.py check ...` evaluates a single request through `can()`: deny-by-default, fixed deny precedence (`explicit_deny` > `invalid_input` > `too_broad_scope` > `unsatisfied_approval` > `no_matching_grant`), scope-hierarchy inheritance, and a frozen `Decision`.
- Pre-action gates in `scripts/hq_policy_hooks.py` enforce approval checkpoints, approval-as-continuation, and `RESUMED`-state handling before risky steps run.
- Every governed step can emit a byte-stable, secret- and timestamp-scrubbed run receipt under `.hq/receipts/` for an audit trail.
- `python3 scripts/hq_gate.py` runs the release gate: required-evidence checks plus a redundant diff-based permission-expansion enforcement layer that requires a recorded human approval for any widened grant.

Relevant schemas (draft 2020-12, `additionalProperties: false`): `permission-grants`, `approval-checkpoint`, `run-receipt`, `agent-release`, and the `capability_grants` extension to `agent-registry`.

## Feedback Loop

The control plane keeps a short feedback loop on disk so execution learns across sessions instead of relying on chat memory:

- governed runs auto-write append-only receipts (`before`/`after`) under `.hq/telemetry/feedback-loop/`, linked by attempt id
- receipts carry a numeric metric plus direction, so `summary` reports baseline, best, and latest delta per task
- `python3 scripts/hq_feedback_loop.py review-status` reports whether a review is due — immediately on any adverse outcome, or by cadence after a batch of clean successes (`HQ_FEEDBACK_REVIEW_CADENCE`, default 5); `mark-reviewed` resets it
- the aggregated summary and review signal are surfaced in `status`, `.hq/state/session-bootstrap.json`, and the memory index so they survive context compaction

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
