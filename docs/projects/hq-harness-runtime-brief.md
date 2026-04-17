# HQ Harness Runtime

Public-safe project brief for the next execution layer of AI-First HQ OS.

## Summary

HQ Harness Runtime is a Codex-native execution and governance layer for long-running AI work. Its purpose is to make agent behavior durable, inspectable, resumable, and reviewable without replacing the current HQ operating model or requiring a monolithic external framework.

The core thesis is simple: model quality matters, but production reliability now depends more on the harness around the model than on the base model itself. The product is not "another agent wrapper." The product is the runtime that manages memory, context, approvals, verification, recovery, and controlled delegation.

The next donor-driven tightening is narrow:

- add a durable private `thread_id` separate from any specific run;
- expose explicit runtime policy and hook seams outside prompts;
- keep skills as compact `SKILL.md` packets with optional `scripts/`, `references/`, and `assets/`, not local mini-frameworks.

## Why This Project Exists

Current agent systems usually fail at the same seams:

- they forget important prior context across sessions;
- they lose state in long-running work;
- they cannot reliably resume after interruption;
- they make repeated mistakes because corrections do not become durable operating knowledge;
- they blur read-only and mutating actions;
- they finish work without a verification stage;
- they produce weak audit trails for multi-step execution.

HQ already has the beginning of a durable mission runtime through first-class `Mission`, `Run`, `Step`, `Approval`, and `Artifact` records. This project extends that nucleus into a true harness runtime.

## Product Thesis

The winning architecture for HQ is:

- `Codex` as the primary execution surface;
- `HQ Harness Runtime` as the local control and durability layer;
- `05 AI Control Plane/schemas/` as the tracked contract layer;
- `.hq/` as the private runtime state store.

This project does not try to replace frontier models, replace Codex, or become a generic workflow builder. It gives HQ a governed environment in which strong models can operate reliably.

## Goals

- make long-running work resumable across sessions and interruptions;
- persist high-signal working memory without treating prompts as the source of truth;
- separate execution state from conversation history and from the durable execution thread;
- enforce risk-based approval gates for mutating and destructive actions;
- require verification before a run can be considered complete;
- support bounded delegation with explicit ownership and compact result return;
- improve observability, auditability, and replay for mission execution;
- stay additive to the current repository and script surface.

## Non-Goals

- building a generic visual workflow builder;
- replacing Codex with another chat or agent product;
- introducing a heavyweight always-on infrastructure dependency for local-first use;
- copying an external framework wholesale;
- treating vector databases or graph databases as mandatory v1 dependencies.

## Core Concepts

### 1. Runtime Memory

The runtime should maintain layered memory instead of reusing full chat transcripts as context:

- working memory: current run state, active constraints, next steps, blockers;
- episodic memory: completed steps, approvals, failures, corrections, outcome summaries;
- procedural memory: durable operating rules, conventions, recurring workflows, accepted playbooks.

The first implementation should be file-backed and human-inspectable. More advanced retrieval backends can remain optional.

### 1A. Execution Thread

The runtime should treat `thread` as the durable continuity boundary above any individual `mission` or `run`.

That thread should stay private under `.hq/state/threads/` and hold only narrow linkage:

- `thread_id`;
- active mission and run pointers;
- latest spec and handoff pointers;
- resume packet pointer;
- status and private metadata.

This preserves continuity without turning chat history into HQ source of truth.

### 2. Context Compaction

The harness should continuously convert noisy execution history into high-signal summaries so future turns load only the minimum useful context.

Compaction output should preserve:

- accepted decisions;
- unresolved blockers;
- resume pointers;
- artifacts produced;
- verification status;
- the next highest-priority action.

### 3. Verification Loop

Runs should not end directly after generation. They should pass through a verification stage that can include:

- tests, lint, schema validation, or static checks;
- artifact existence checks;
- review rubric checks;
- policy and approval validation.

### 4. Policy-Gated Tool Use

Tool actions should be classified at runtime:

- read-only;
- mutating;
- destructive or externally consequential.

Each class should map to a default policy response:

- allow;
- allow with review;
- pause for approval;
- block.

Policy should not live only in prompts. HQ should expose explicit runtime seams for:

- rule-based policy evaluation;
- pre-action hooks;
- post-action hooks;
- approval-trigger hooks;
- run-finish hooks.

### 5. Subagent Contract

Delegation should be explicit and bounded. Each subagent task should include:

- task packet;
- owned scope;
- acceptance rule;
- expected artifacts;
- compact result summary on return.

The parent run stays authoritative. Subagents do not become hidden state silos.

### 6. Skill Packaging Discipline

Skills should remain thin capability packets:

- one compact `SKILL.md`;
- optional `scripts/` for deterministic helpers;
- optional `references/` for lazy-loaded docs;
- optional `assets/` for templates or output resources.

HQ should avoid letting a skill directory grow into its own framework, docs site, or toolchain.

## V1 Scope

Version 1 should focus on six narrow capabilities:

1. file-backed layered memory for runs and missions;
2. durable execution-thread records linked to missions, runs, specs, handoffs, and telemetry;
3. context compaction and resume packets;
4. verification-before-complete pipeline;
5. explicit policy and hook seams for action classification and approvals;
6. bounded subagent handoff and result packaging.

## V1 Deliverables

- thread contract added to the private runtime and linked into the mission runtime;
- memory contract added to the mission runtime;
- compaction command and stored resume summaries;
- verification stage and verification result artifacts;
- policy gate and hook primitives for action classes;
- subagent packet schema or lightweight tracked contract;
- skill-packaging lint that preserves compact skill directories;
- targeted tests covering resume, verification, and approval behavior;
- public-safe documentation for architecture and operating assumptions.

## Suggested Milestones

### Milestone 1: Memory and Resume

- add durable execution-thread records and `thread_id` lineage;
- add working memory and resume packet generation;
- persist compact high-signal summaries per run;
- prove a run can resume from a narrow packet instead of full transcript reconstruction.

### Milestone 2: Verification and Completion Discipline

- add a formal verification stage before completion;
- store verification artifacts and statuses;
- block "completed" when required checks are missing or failing.

### Milestone 3: Policy and Delegation

- classify actions by risk;
- add approval hooks;
- move policy and hook evaluation into explicit runtime surfaces, not prompt-only rules;
- formalize subagent task packet and compact return path.

## Technical Direction

- keep the tracked contract in JSON schemas and public-safe docs;
- keep private runtime state in `.hq/`;
- prefer additive commands in `scripts/hq_mission_runtime.py` over broad rewrites;
- keep the runtime file-backed until the workflow is trusted;
- make advanced memory backends pluggable rather than mandatory.

## Donor Inputs

The project should selectively borrow ideas from:

- `openai/codex` for execution surface and workflow ergonomics, especially thread/run separation, explicit `execpolicy` and `hooks` seams, and compact skill packaging;
- `openai/openai-agents-python` for harness and sandbox patterns;
- `langchain-ai/langgraph` for persistence, interrupts, and resume semantics;
- `paperclipai/paperclip` for company-layer governance concepts;
- `pydantic/pydantic-ai` for typed contracts and safer boundaries.

The design goal is synthesis, not imitation.

## Success Criteria

- a complex task can pause and resume without reloading broad repository context;
- corrections made during one run improve future execution quality;
- risky actions consistently route through the right approval path;
- runs cannot silently complete without verification;
- delegation reduces context load instead of multiplying hidden state;
- runtime events create a usable audit trail for review and debugging.

## Open Questions

- when should memory stay file-backed, and when should a graph/vector backend become worth the operational cost?
- should the runtime expose explicit memory types in schemas now, or after one stable file-backed cycle?
- where should approval policy live long-term: inside mission runtime commands, in control-plane policy files, or in both?

## Recommendation

Build HQ Harness Runtime as the next public-facing systems project for this repository.

It is aligned with the actual direction of agent infrastructure: away from prompt-heavy demos and toward durable, governed, reviewable execution environments.
