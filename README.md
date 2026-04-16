# AI-First HQ OS

![AI-First](https://img.shields.io/badge/Operating%20Model-AI--First-111111)
![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)
![Markdown](https://img.shields.io/badge/Docs-Markdown-000000?logo=markdown&logoColor=white)
![Codex](https://img.shields.io/badge/Built%20with-Codex-412991)

AI-First operating system for running a small company with Markdown source of truth, agent prompts, governance rules, and Python scripts for control-plane workflows, telemetry, and safe delegation.

## Overview

This repository packages a reusable AI-first company operating system:

- Markdown files hold human-readable operating truth
- `05 AI Control Plane/` holds machine-readable workflows, policies, metrics, and task state
- `agents/` contains role prompts for specialized execution
- `scripts/` provides validation, telemetry, runtime helpers, and publication guardrails
- `.hq/` is reserved for private local runtime artifacts and must never enter public git history

## Features

- AI-first control plane for governed delegation
- role-based agent prompts
- machine-readable workflow and policy layer
- telemetry and runtime helper scripts
- public-safety validation for GitHub publication
- public-safe example planning and decision files

## Repository Structure

- `AGENTS.md` shared repository rules
- `agents/*/AGENTS.md` role-specific prompts
- `05 AI Control Plane/` queue, workflow, policy, metric, and schema examples
- `scripts/` validation, runtime, telemetry, and publication-safety tools
- `tests/` automated coverage for core behavior
- `02 Planning/`, `03 Notes/`, `04 Projects/` public-safe example state

## Quick Start

```bash
python3 -m pip install -r requirements-dev.txt
python3 scripts/hq_control_plane.py validate
python3 scripts/hq_control_plane.py sync
python3 scripts/hq_public_safety.py
python3 scripts/hq_gate.py
```

## Core Commands

```bash
python3 scripts/hq_control_plane.py validate
python3 scripts/hq_control_plane.py sync
python3 scripts/hq_public_safety.py
python3 scripts/hq_gate.py
```

## Public GitHub Boundary

The public repository is for the system itself:

- prompts
- agents
- scripts
- schemas
- tests
- safe example docs

The public repository is not for live operating data.

Keep these private:

- `.hq/` runtime state, telemetry, handoffs, evals, reflections, releases, and local prompts
- raw customer or prospect data
- personal notes, journals, archives, and imported research dumps
- credentials, API keys, private keys, payment exports, and banking material
- temporary datasets and local environment files

If a file contains personal data, customer data, raw imports, credentials, payment artifacts, or private working memory, keep it under `.hq/` or outside this repository.

Before pushing, run `python3 scripts/hq_public_safety.py` or the full `python3 scripts/hq_gate.py`.
