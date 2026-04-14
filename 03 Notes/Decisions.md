# Decisions

## 2026-04-14

### Shared vs Private Memory Split

- Decision: keep shared company state in the HQ repository and keep CEO continuity outside the repository.
- Reason: shared files need to stay clean and team-visible, while session memory and private operating context should remain separate.

### Obsidian Layer

- Decision: keep the existing root source-of-truth files untouched and add a navigation layer with numbered folders.
- Reason: this preserves current HQ rules while making the vault easier to browse and extend.
