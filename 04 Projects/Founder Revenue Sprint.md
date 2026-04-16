# Public Launch Hardening

## Status

- Active

## Goal

- Keep the repository ready for public GitHub use.
- Preserve the reusable AI-first operating system while keeping private runtime and live operating data local.

## Owner

- AI Operations Lead

## Supporting Roles

- Governor
- Delivery
- Documentation

## Why This Project Exists

- HQ should be publishable as a reusable system, not only as an internal workspace.
- Public readers need clear examples, strong boundaries, and working validation scripts.
- Private notes, runtime memory, customer data, and credentials must stay outside tracked history.

## Scope

- Rewrite the public README.
- Keep example planning and decision files public-safe.
- Add automated publication-safety checks.
- Keep `.hq/` and other blocked private paths out of git history.

## Operating Rules For This Project

- Tracked files should explain the framework, not expose live operator context.
- Private runtime artifacts stay under `.hq/`.
- Raw research dumps, prospect lists, contracts, billing data, and credentials stay outside the public repo.
- Any new blocked private artifact class should be added to `.gitignore` and the publication-safety gate.

## Immediate Next Slice

- Keep validation aligned with real repository usage.
- Tighten the boundary when new private artifact patterns appear.

## Primary Update File

- `04 Projects/Founder Revenue Sprint.md`
