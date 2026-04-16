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

### Which Exact B2B SaaS Slice Converts Fastest For The Pilot

- Decision needed: whether the first target should center on security-led teams, revenue-led teams, or founder-led teams inside the upmarket B2B SaaS segment.
- Why this is open: the current ICP is directionally strong but still too broad to assume the best buyer, budget owner, and trigger motion.
- Current rule: keep the pilot focused on growth-stage B2B SaaS moving upmarket and validate the sharpest slice through live conversations.

### What Minimum Trust Pack Clears Early Buyer Objections

- Decision needed: what minimum set of security, privacy, retention, and contracting artifacts is enough to let a new vendor handle sensitive security materials for a pilot.
- Why this is open: trust burden is the largest near-term risk to the selected wedge, and the current answer is still directional rather than proven.
- Current rule: keep human review in the loop and avoid autonomy claims until the trust pack is validated in live sales.

### Which Foreign-Entity And Banking Route Is Actually Viable

- Decision needed: which jurisdiction, bank, payment processor, and contracting model can support US/EU sales without creating legal, tax, or sanctions-screening surprises.
- Why this is open: entity formation alone may not solve procurement acceptance, provider onboarding, or tax consequences.
- Current rule: treat the route as a gating dependency, not as a solved operational fact.
