# Reference Patterns — Agent Permission Governance

This is the distilled, tracked summary of patterns adopted from local reference
projects. It uses generic descriptors only: no project names, directory names,
or other identifying labels appear here. Raw, project-identifying notes live
under the git-ignored `.hq/` runtime path.

Every pattern below maps to exactly one of the five permission-governance
primitives. Patterns that could not be mapped to a primitive were excluded.

## 1. Permission model

- A relationship-and-tuple authorization style informs the explicit grant
  records: each authorization is a discrete row of `(agent, role, scope,
  action, approval_class)` rather than implicit, role-only permissions.
- A deny record always overrides a matching grant, mirroring the
  "explicit deny wins" convention seen in mature authorization systems.
- Namespaced, hierarchical resource scopes allow a parent grant to be inherited
  by a child scope, keeping the grant table small.

## 2. Decision function

- A single, pure decision entry point returns an allow/deny result plus a
  machine-readable reason code, following the "policy decision point" pattern.
- A fixed deny-precedence order makes two evaluators agree on the same reason
  code when several deny conditions hold at once.
- Determinism is treated as a hard requirement: identical inputs and state
  always produce the identical decision, with no model-judged branches.

## 3. Pre-action gate

- Sensitive operations are intercepted before execution and converted into a
  pending approval checkpoint, following the "human-in-the-loop interrupt"
  pattern.
- Approval is modeled as continuation: a run pauses at the gate and resumes
  from a recorded step pointer once a decision is returned.
- Tool calls from external tool servers and built-in model tools are routed
  through the same gate so nothing bypasses policy.

## 4. Run receipt

- A normalized, append-only record links a run to its task, agent, evidence,
  and outcomes, following structured run/trace export conventions.
- Tracked output is scrubbed of secrets and volatile timestamp-only fields and
  serialized with stable key order for clean diffs.
- Raw execution exhaust stays in private runtime storage; only a compact,
  publicly-safe receipt surface is eligible for tracking.

## 5. Release gate

- Changes that alter repeated agent behavior are classified and gated before
  landing, following "evaluation-before-release" conventions.
- Required evidence (change type, affected files, rollback path, eval/review
  signal) is enforced deterministically.
- A redundant enforcement layer re-derives permission expansion from the actual
  change diff, so a wrong manifest flag cannot let a silent expansion through.
