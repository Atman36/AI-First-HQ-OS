---
kanban-plugin: board
---

# Task Board

## Inbox

## This Week

- [ ] Close the first HQ operating cycle by 2026-04-21
  - Owner: COO
  - Project: HQ Bootstrap
  - Support: Documentation and Finance, with Growth or Research only if the cycle exposes a real need
  - Next step: Hold the single active operating card steady, then close the cycle with one lean weekly review and next 3 priorities.
  - Done when: The cycle ends with a weekly review, next 3 priorities, and explicit notes about what still broke.
  - Primary update file: `02 Planning/Weekly Plan.md`
  - Then align: `03 Notes/Decisions.md`, `04 Projects/HQ Bootstrap.md`
  - Accepts result: CEO
- [ ] Watch for real routing bottlenecks before changing roles or routines
  - Owner: COO
  - Project: HQ Bootstrap
  - Support: Documentation
  - Next step: Treat Documentation load at cycle close as a watchpoint, not a confirmed bottleneck, unless updates start queueing behind one owner.
  - Done when: The cycle closes with explicit proof of either "no bottleneck" or one concrete routing failure.
  - Primary update file: `03 Notes/Decisions.md`
  - Then align: `04 Projects/HQ Bootstrap.md`
  - Accepts result: CEO

## Today

- [x] 2026-04-14: Defined the 7-day operating objective for 2026-04-14 to 2026-04-21
  - Owner: CEO
  - Project: HQ Bootstrap
  - Next step: Keep the objective aligned across root, planning, and project files.
  - Done when: `now.md`, `projects.md`, and `02 Planning/Weekly Plan.md` all point to the same cycle.
  - Primary update file: `now.md`
  - Then align: `projects.md`, `02 Planning/Weekly Plan.md`
  - Accepts result: CEO
- [x] 2026-04-14: Locked the minimum weekly review format
  - Owner: COO
  - Project: HQ Bootstrap
  - Support: Documentation, Finance
  - Next step: Use the lean review first and expand only if real usage proves it insufficient.
  - Done when: `routines.md` and `90 Templates/Weekly Review Template.md` describe the same lean review output.
  - Primary update file: `routines.md`
  - Then align: `90 Templates/Weekly Review Template.md`
  - Accepts result: CEO
- [x] 2026-04-14: Added project-level support-note sections for HQ Bootstrap
  - Owner: Documentation
  - Project: HQ Bootstrap
  - Next step: Keep Finance, Growth, and Research inputs on the project page instead of in standalone root notes.
  - Done when: The active project page has clear sections for risks, dependencies, and support-role inputs.
  - Primary update file: `04 Projects/HQ Bootstrap.md`
  - Accepts result: COO
- [x] 2026-04-14: Moved root clutter into a local archive outside git tracking
  - Owner: CEO
  - Project: HQ Bootstrap
  - Next step: Keep long-form drafts and archived notes in `99 Archive/`, not in the root.
  - Done when: The two root draft files are renamed, moved into `99 Archive/`, and the archive is ignored by git.
  - Primary update file: `.gitignore`
  - Then align: `01 Operating System/HQ Audit Roadmap.md`
  - Accepts result: CEO
- [x] 2026-04-14: Filled the first lean weekly review snapshot inside the current cycle files
  - Owner: Documentation
  - Project: HQ Bootstrap
  - Support: COO, Finance
  - Next step: Keep the review embedded in the weekly summary until real usage proves a separate note is necessary.
  - Done when: `Weekly Plan.md` carries the weekly summary while `Decisions.md` and `HQ Bootstrap.md` hold only durable why and project-local context without creating a new file.
  - Primary update file: `02 Planning/Weekly Plan.md`
  - Then align: `03 Notes/Decisions.md`, `04 Projects/HQ Bootstrap.md`
  - Accepts result: COO
- [x] 2026-04-14: Confirmed `Task Board.md` remains the only live task board
  - Owner: Documentation
  - Project: HQ Bootstrap
  - Next step: If a task moves, update this board first and keep `Weekly Plan.md` as a summary only.
  - Done when: `Task Board.md` remains the only live task board for active work.
  - Primary update file: `02 Planning/Task Board.md`
  - Accepts result: COO
- [x] 2026-04-14: Made role prompts repo-relative for Codex and portable runners
  - Owner: Documentation
  - Project: HQ Bootstrap
  - Next step: Keep shared role prompts path-agnostic so Codex and future runners can read the same repo without local machine assumptions.
  - Done when: role prompts read shared files by repo-relative path instead of one local `/Users/...` path.
  - Primary update file: `agents/README.md`
  - Then align: `agents/*/AGENTS.md`
  - Accepts result: COO
- [x] 2026-04-14: Added Delivery as the default bounded execution role
  - Owner: CEO
  - Project: HQ Bootstrap
  - Support: COO, Documentation
  - Next step: Use Delivery for automation specs, implementation plans, and project execution work that is more than documentation.
  - Done when: `agents/delivery/AGENTS.md`, `AGENTS.md`, and routing docs describe one clear execution role between COO and Documentation.
  - Primary update file: `agents/delivery/AGENTS.md`
  - Then align: `AGENTS.md`, `01 Operating System/Agent Routing.md`, `projects.md`
  - Accepts result: CEO
- [x] 2026-04-14: Tightened the task contract around one primary update file
  - Owner: COO
  - Project: HQ Bootstrap
  - Support: Documentation
  - Next step: Keep one primary update file on each active card and align secondary files only after result acceptance.
  - Done when: shared operating rules, task template, and active cards use the same primary-file contract.
  - Primary update file: `AGENTS.md`
  - Then align: `01 Operating System/How To Operate HQ.md`, `90 Templates/Task Template.md`, `02 Planning/Task Board.md`
  - Accepts result: CEO

## Waiting

- [ ] Introduce Paperclip orchestration after manual routing is stable
  - Owner: CEO
  - Project: HQ Bootstrap
  - Next step: Revisit only after 1-2 successful manual operating cycles.
  - Done when: Manual routing no longer feels like the bottleneck.
  - Primary update file: `stack.md`
  - Then align: `agents/`
  - Accepts result: CEO

## Done

- [x] 2026-04-14: Created the initial HQ folder structure for Obsidian
- [x] 2026-04-14: Split shared company workspace from private CEO memory
- [x] 2026-04-14: Rewrote role prompts against the real working files
- [x] 2026-04-14: Locked the file contract between root files, planning, notes, and project pages
- [x] 2026-04-14: Converted the task board to an Obsidian kanban-compatible format

## Archive


%% kanban:settings
```
{"kanban-plugin":"board"}
```
%%
