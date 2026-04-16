# Decisions

## 2026-04-14

### Lean HQ Structure

- Decision: keep shared company state in the HQ repository and keep private runtime under `.hq/`.
- Reason: the system needs one inspectable shared truth and one private runtime, not mixed memory.

### Single Primary Update File

- Decision: every active task must name one primary update file.
- Reason: this reduces drift and makes delegated work easier to accept and document.

### Delivery Role

- Decision: keep a dedicated Delivery role for bounded implementation work.
- Reason: the system needs a default execution owner between routing and documentation.

## 2026-04-15

### HQ Must Become AI-First, Not AI-Themed

- Decision: treat HQ as an AI-first operating system, not as a note vault with AI around it.
- Reason: the structure should support delegated authority, clear boundaries, and repeatable operations.

### Install A Machine-Readable Control Plane

- Decision: keep `05 AI Control Plane/` as the tracked machine-readable layer for active work, authority, workflows, policies, and metrics.
- Reason: AI cannot operate reliably from free-form Markdown alone.

### Machine-Readable Queue Becomes Primary For Delegated Work

- Decision: use `05 AI Control Plane/active-work.json` as the primary queue for delegated work and render `02 Planning/Task Board.md` from it.
- Reason: the board should stay readable without becoming a second source of truth.

### Add Governor As A Standing Role

- Decision: keep Governor responsible for policy enforcement, approval gates, kill switches, and rollback triggers.
- Reason: governed autonomy needs a standing control role.

### Runtime Memory Boundary

- Decision: telemetry, handoffs, reflections, evals, and other runtime continuity stay under `.hq/`; only accepted conclusions move into tracked truth.
- Reason: this keeps shared state clean and public-safe.

## 2026-04-16

### Public Git History Must Exclude User And Customer Data

- Decision: keep tracked HQ history limited to system files, agent instructions, scripts, tests, and public-safe example docs; user data, customer data, raw imports, credentials, payment artifacts, and local runtime memory must stay under `.hq/` or outside the repo.
- Reason: HQ is intended for public GitHub publication, so privacy boundaries must be explicit and enforceable.

### Public Repo Ships Examples, Not Live Internal State

- Decision: tracked planning, project, and decision files in the public repository should demonstrate the HQ format without carrying live company strategy, customer context, or private working memory.
- Reason: the public repo should teach the system, not publish the operator's internal state.

### Publication Safety Must Be Automated

- Decision: add a publication-safety check to local and CI validation so blocked paths, sensitive local artifacts, and obvious secrets fail before push.
- Reason: repository privacy should depend on automation, not on manual memory during commits.

### Founder Revenue Sprint Starts With Security Questionnaire Deal Velocity Pilot

- Decision: treat `AI Security Questionnaire Automation` as the first commercial wedge and sell it first as a human-reviewed `Security Questionnaire Deal Velocity Pilot`.
- Reason: this path sits on an already standardized buyer workflow, ties directly to active revenue friction, supports manual-first delivery, and compounds into reusable answer libraries and trust operations.

### Legal Vertical RAG Stays A Parked Challenger

- Decision: keep `Legal Vertical RAG` as the strongest challenger, but do not make it the active first build track.
- Reason: the market is real, but first revenue there is more credibility-heavy, more custom, and more governance-sensitive than the security wedge.

### Cross-Border Monetization Remains Counsel-Gated

- Decision: keep `foreign-entity + non-RU banking` as the default scaling direction, but treat contracting, sanctions screening, tax, and processor eligibility as unresolved until human legal and tax review is complete.
- Reason: the route is directionally better than direct Russia-based billing, but it is not an accepted operating fact yet.
