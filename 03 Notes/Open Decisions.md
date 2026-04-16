# Open Decisions

## 2026-04-16

### Should The Public And Private Operating Layers Split Into Separate Repositories

- Decision needed: whether HQ should stay as one local-first repository with strong public-safety rules, or whether the live private operating layer should move into a separate private repository later.
- Why this is open: one repository is simpler to operate, but a future split may reduce the chance of accidental leakage as the system grows.
- Current rule: keep private runtime and live operating memory under `.hq/` and block those paths from tracked history.

### How Much Example State Should Ship Publicly

- Decision needed: how much sample planning and project state the public repo should include by default.
- Why this is open: more examples improve onboarding, but too much example state increases maintenance and can blur the line between template and live operations.
- Current rule: keep only public-safe examples that explain the system clearly.
