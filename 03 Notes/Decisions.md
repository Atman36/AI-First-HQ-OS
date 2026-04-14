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
