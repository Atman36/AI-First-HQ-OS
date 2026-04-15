# Agents

These prompts are shared role definitions for the AI-first HQ.

## Start Order

1. CEO
2. AI Operations Lead
3. Governor
4. Delivery
5. Documentation
6. Assistant
7. Finance
8. Growth
9. Research

## Operating Objects

Each role works through the same five objects:

- Task state: `05 AI Control Plane/active-work.json`
- Rules: `AGENTS.md` plus `agents/<role>/AGENTS.md`
- Policies: `05 AI Control Plane/operating-policies.json`
- Workflow: `05 AI Control Plane/workflow-registry.json`
- Telemetry: `.hq/telemetry/`

## Rule

Do not add more standing agents unless a repeated execution gap appears.

## Routing Rule

- CEO decides and approves high risk.
- AI Operations Lead routes and maintains the queue, observability, and weekly metric review.
- Governor enforces policy and approval gates.
- Delivery owns bounded execution.
- Documentation updates tracked truth after acceptance.
- Other roles support where needed.
