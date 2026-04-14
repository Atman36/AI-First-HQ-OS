# Agents

These prompts are shared role definitions.

## Intended Usage

- Codex: open or run from a role directory so the local `AGENTS.md` applies
- Paperclip: map each agent's instructions path to the matching file here
- All prompts should read shared files by repo-relative path, not machine-specific absolute paths

## Start Order

1. CEO
2. COO
3. Delivery
4. Documentation
5. Assistant
6. Finance
7. Growth
8. Research

## Rule

Do not add more standing agents unless a repeated execution gap appears.

## Routing Rule

- CEO decides.
- COO dispatches.
- Delivery owns bounded implementation work.
- Documentation updates shared records after acceptance.
- Other roles support where needed.

If orchestration is needed during a Codex session, use the current role prompts directly instead of adding a new standing orchestrator by default.
