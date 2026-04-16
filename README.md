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
- `scripts/` provides validation, telemetry, runtime helpers, and publication guardrails
- `.hq/` is reserved for private local runtime artifacts and live operating state; it must never enter public git history

## Features

- AI-first control plane for governed delegation
- role-based agent prompts
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
- `scripts/` validation, runtime, telemetry, and publication-safety tools
- `tests/` automated coverage for core behavior
- `agents/*/AGENTS.md` role prompts safe for publication
- `skills/` agent skills safe for publication

## Quick Start

```bash
python3 -m pip install -r requirements-dev.txt
python3 scripts/hq_runtime.py bootstrap
python3 scripts/hq_control_plane.py validate
python3 scripts/hq_control_plane.py sync
python3 -m unittest
python3 scripts/hq_public_safety.py
python3 scripts/hq_gate.py
```

`python3 scripts/hq_runtime.py bootstrap` creates the local-only HQ scaffold that is intentionally not published to GitHub: `now.md`, `projects.md`, planning/notes/project pages, and the local control-plane JSON files.

## Core Commands

```bash
python3 scripts/hq_runtime.py bootstrap
python3 scripts/hq_control_plane.py validate
python3 -m unittest
python3 scripts/hq_public_safety.py
python3 scripts/hq_gate.py
```

## Public GitHub Boundary

The public repository is allowlist-only. These path classes are allowed:

- `README.md`, `AGENTS.md`, `.gitignore`, `requirements-dev.txt`
- `.github/workflows/`
- `agents/*/AGENTS.md`
- `skills/`
- `scripts/`
- `tests/`
- `05 AI Control Plane/schemas/`

Everything else is local-only and must not be tracked.

Keep these private:

- `.hq/` runtime state, telemetry, handoffs, evals, reflections, releases, and local prompts
- live operating docs such as `now.md`, `projects.md`, `routines.md`, `stack.md`, and Markdown work under `02 Planning/`, `03 Notes/`, and `04 Projects/`
- raw customer or prospect data
- personal notes, journals, archives, and imported research dumps
- credentials, API keys, private keys, payment exports, and banking material
- temporary datasets and local environment files

If a file contains personal data, customer data, raw imports, credentials, payment artifacts, or private working memory, keep it under `.hq/` or outside this repository.

Before pushing, run `python3 scripts/hq_public_safety.py` or the full `python3 scripts/hq_gate.py`.
