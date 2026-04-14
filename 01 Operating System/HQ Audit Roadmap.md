# HQ Audit Roadmap

This file tracks which audit findings are still relevant after the 2026-04-14 cleanup pass.

## Closed Now

- Role prompts were rebound to the actual working files: `Task Board`, `Weekly Plan`, `Inbox`, `Decisions`, and relevant project pages.
- File ownership is clearer now: `now.md` = focus, `projects.md` = registry, `Task Board.md` = live execution, `Weekly Plan.md` = weekly commitments, `Decisions.md` = historical why.
- `Task Board.md` now uses an Obsidian kanban-compatible format, based on the existing external kanban board pattern.
- The minimum dispatch schema now exists on the board itself: owner, project, next step, done when, update file, accepts result.
- Private absolute CEO paths were removed from the shared home page.
- Template placement is clearer, and a lean `Daily Ops Template` now exists.

## Partially Closed

- Support-role landing zones were weak. This is better now because Finance, Growth, and Research are pointed toward project pages and decision records, but dedicated sections are still not defined.
- COO and Documentation were potential bottlenecks. This is better now because the handoff contract is explicit and fast-track routing is allowed for bounded work, but it still needs one live operating cycle to prove it.
- `projects.md` and `04 Projects/` still describe the same project from two levels. This is acceptable for now because the contract is clearer, but it should be revisited if project pages start duplicating the registry.
- Weekly review ambiguity is reduced because `Weekly Plan` is no longer a second task board, but the actual repeatable weekly review ritual is still not validated.

## Still Relevant

- Root clutter is still real. `deep-research-report.md` and `Без названия 25.md` are still in the root and should be either moved, renamed, or intentionally integrated.
- The project layer is still thin. That is acceptable with one active initiative, but once there are multiple active projects, each project page will need a more useful local structure.
- The real test has not happened yet. HQ still needs one live, revenue-linked or operating task to pass through the full cycle without drift.

## Not A Priority Right Now

- A separate orchestrator agent. The current problem was ambiguity, not missing orchestration infrastructure.
- Heavy migration of personal-vault logic such as energy routing, confidence scoring, or deep personal planning mechanics.
- New top-level entities like `people.md`, `channels.md`, or extra systems folders before there is repeated real usage.

## Next Recommended Moves

1. Choose one 7-day operating objective and route it through the board end-to-end.
2. After that cycle, decide whether root clutter should be cleaned by moving or renaming the two long root documents.
3. Keep `projects.md` as the registry unless real project pages start carrying enough signal to justify a simplification.
4. Add dedicated project-page sections for support notes only if Finance, Growth, or Research start writing there regularly.
