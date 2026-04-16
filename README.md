# AI-First HQ OS

AI-First operating system for running a small company with Markdown source of truth, agent prompts, governance rules, and Python scripts for control-plane workflows, telemetry, and safe delegation.

## Suggested GitHub Metadata

- Name: `AI-First HQ OS`
- Repository slug: `ai-first-hq-os`
- Description: `AI-First operating system for running a small company with Markdown truth, agent prompts, governance rules, and Python scripts for control-plane workflows, telemetry, and safe delegation.`

## What This Repository Contains

- reusable AI-first operating model docs
- machine-readable control-plane examples in `05 AI Control Plane/`
- agent prompts in `agents/`
- local automation and validation scripts in `scripts/`
- tests for the control plane, runtime helpers, telemetry, and publication guardrails
- public-safe example planning and decision files

## What Must Stay Private

These paths and artifact types are intentionally excluded from public git history:

- `.hq/` runtime state, telemetry, handoffs, evals, reflections, releases, and local prompts
- raw customer or prospect data
- personal notes, journals, archives, and imported research dumps
- credentials, API keys, private keys, payment exports, and banking material
- temporary datasets and local environment files

If a file contains personal data, customer data, raw imports, credentials, payment artifacts, or private working memory, keep it under `.hq/` or outside this repository.

## Repository Layout

- `AGENTS.md`: shared operating rules for the repository
- `agents/*/AGENTS.md`: role-specific prompts
- `05 AI Control Plane/`: queue, workflow, policy, metric, and schema examples
- `scripts/`: validation, runtime, telemetry, and publication-safety tools
- `tests/`: automated coverage for core behavior
- `02 Planning/`, `03 Notes/`, `04 Projects/`: public-safe example state that shows how HQ is meant to be used

## Quick Start

```bash
python3 -m pip install -r requirements-dev.txt
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

The public repository is not for live operating data. Before pushing, run `python3 scripts/hq_public_safety.py` or the full `python3 scripts/hq_gate.py`.
