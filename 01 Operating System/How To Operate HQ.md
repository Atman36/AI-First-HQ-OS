# How To Operate HQ

This is the practical order for filling shared HQ files during normal work.

## Core Principle

- Write the smallest durable update in the highest-value source-of-truth file first.
- Use planning and notes as working surfaces, not as replacements for root state.
- Keep private continuity outside this repository.
- Treat `reports/` and ignored research drafts as reference material until their conclusions are summarized back into a source-of-truth file.

## File Contract

- `now.md` = current company focus and operating objective.
- `projects.md` = active project registry, status, owner, and next step.
- `02 Planning/Task Board.md` = single live execution board for active work.
- `02 Planning/Weekly Plan.md` = weekly commitments and weekly summary, not a second board.
- `03 Notes/Decisions.md` = durable why after decisions are accepted.
- `04 Projects/...` = local detail, risks, dependencies, support inputs, and implementation context. It should not mirror the full weekly summary.

Every active task card on `Task Board` should have:

- `Owner`
- `Project`
- `Next step`
- `Done when`
- `Primary update file`
- `Accepts result`

Optional fields when needed:

- `Support`
- `Then align`

## Fill Order

### 1. Set direction

Update these files first when priorities or company focus change:

1. [[now]]
2. [[projects]]
3. [[routines]] if the operating rhythm changed
4. [[stack]] if tool boundaries or orchestration changed

### 2. Turn direction into executable work

Once the priority is clear, fill the shared execution layer:

1. [[02 Planning/Weekly Plan|Weekly Plan]] for the current week's commitments and summary
2. [[02 Planning/Task Board|Task Board]] for live task movement and ownership
3. [[04 Projects/README|Project page]] for project-specific detail when the task belongs to an active project

### 3. Capture incoming work and decisions

Use notes only for the right kind of information:

1. [[03 Notes/Inbox|Inbox]] for raw incoming requests, loose ideas, and unclear asks
2. [[03 Notes/Decisions|Decisions]] for durable decisions after they are made

After capture:

- Move actionable work into `Task Board` or a project page.
- Reflect strategic outcomes back into `now.md` or `projects.md`.

## Event-Based Workflow

### New task arrives

1. Put it in `03 Notes/Inbox.md` if it is still vague.
2. CEO decides whether it matters now.
3. COO converts it into a task on `02 Planning/Task Board.md` with owner, project, next step, done when, primary update file, and accepting role.
4. Add project detail in `04 Projects/...` if the work is large enough to need a dedicated page.
5. Documentation updates the affected shared files after the work lands.

### New project starts

1. Add or update the project in `projects.md`.
2. Create the detailed page in `04 Projects/`.
3. Add the weekly commitment to `Weekly Plan` and the active work to `Task Board`.
4. Update `now.md` if the project changes company focus.

### Decision is made

1. Record the decision in `03 Notes/Decisions.md`.
2. Update the affected source-of-truth file:
   `now.md`, `projects.md`, `routines.md`, or `stack.md`.
3. Update the project page if the decision is project-specific.

### End of day

1. COO updates task status.
2. Documentation aligns the durable files that changed.
3. CEO confirms the next priority in `now.md` if it changed.

### End of week

1. Complete `Weekly Plan`.
2. Clean `Task Board`.
3. Log durable decisions.
4. Roll project state back into `projects.md` and keep the project page local.

## Minimal Working Set

If you want the smallest possible shared workflow, keep these current:

1. [[now]]
2. [[projects]]
3. [[02 Planning/Task Board|Task Board]]
4. [[03 Notes/Decisions|Decisions]]

Everything else should support these files, not compete with them.
