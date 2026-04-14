# Decisions

## 2026-04-14

### Shared vs Private Memory Split

- Decision: keep shared company state in the HQ repository and keep CEO continuity outside the repository.
- Reason: shared files need to stay clean and team-visible, while session memory and private operating context should remain separate.

### Obsidian Layer

- Decision: keep the existing root source-of-truth files untouched and add a navigation layer with numbered folders.
- Reason: this preserves current HQ rules while making the vault easier to browse and extend.

### First 7-Day Operating Objective

- Decision: use the HQ audit follow-through as the first 7-day operating objective for 2026-04-14 to 2026-04-21.
- Reason: it turns the audit into real operating work and tests whether the file contract survives one bounded live cycle.

### Weekly Review Format

- Decision: keep the weekly review lean with shipped work, still active work, blockers, money signal, and next 3 priorities.
- Reason: HQ needs one repeatable close-the-week ritual, but it should not become a second task board or a reporting burden.

### Root Clutter Handling

- Decision: move archived drafts and long-form notes out of the root into a local `99 Archive/` folder that is ignored by git.
- Reason: the root should stay reserved for active source-of-truth files and navigation, not for old drafts or large reference notes.

### First Bottleneck Check

- Decision: do not treat COO or Documentation as a confirmed bottleneck yet; keep it as a live watchpoint through the rest of the 2026-04-14 to 2026-04-21 cycle.
- Reason: the current cycle shows real setup progress, but only one part of the workflow looks fragile so far: Documentation may become overloaded at cycle close if several shared files must be updated manually in one pass.

### Project Page Scope

- Decision: keep `projects.md` as the project registry and keep `04 Projects/HQ Bootstrap.md` limited to project-local context, dependencies, support-role inputs, and implementation detail.
- Reason: this preserves one clear registry at the root while preventing the project page from turning into a second copy of company-level status or weekly commitments.

### Portable Role Prompts

- Decision: use repo-relative file paths in `agents/*/AGENTS.md`.
- Reason: the HQ repo is shared across Codex and future runners, so prompts must not depend on one local machine path.

### Primary Update File Rule

- Decision: each active task card should name one primary update file; other shared files align only after the result is accepted.
- Reason: live cards already touched several files, so the contract needed one explicit first-write rule to reduce drift and closeout load.

### Delivery Role

- Decision: add a Delivery role for bounded implementation and project execution work that is more than documentation.
- Reason: the company had routing, support, and record-keeping roles, but no default execution owner between COO and Documentation.

### Audit Review File Status

- Decision: treat `01 Operating System/HQ Audit Roadmap.md` as a dated review snapshot, not a live tracker.
- Reason: live state already belongs in `Task Board.md`, `Weekly Plan.md`, `Decisions.md`, and the active project page.
