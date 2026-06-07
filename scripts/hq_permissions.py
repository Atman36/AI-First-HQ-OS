#!/usr/bin/env python3
"""Deterministic deny-by-default authorization for HQ agents.

This module formalizes HQ's prose permission contracts into a callable
``can(agent_id, action, resource_scope)`` decision function plus a small
``PermissionModel`` loader. It is a pure-Python primitive: no randomness,
no clock, no network. Identical inputs and control-plane state always
produce an identical :class:`Decision`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(
    os.environ.get("HQ_CONTROL_PLANE_REPO_ROOT", Path(__file__).resolve().parents[1])
).resolve()
CONTROL_PLANE_DIR = REPO_ROOT / "05 AI Control Plane"
PERMISSION_GRANTS_PATH = CONTROL_PLANE_DIR / "permission-grants.json"
AGENT_REGISTRY_PATH = CONTROL_PLANE_DIR / "agent-registry.json"

WILDCARD = "*"

# Reason codes, ordered by deny precedence (highest precedence first).
REASON_CODES = (
    "allow",
    "explicit_deny",
    "invalid_input",
    "too_broad_scope",
    "unsatisfied_approval",
    "no_matching_grant",
)

# Approval classes that are satisfied automatically (no explicit approval needed).
AUTO_SATISFIED_APPROVAL_CLASSES = frozenset({"auto_low_risk"})


@dataclass(frozen=True)
class Decision:
    """The result of evaluating a permission request."""

    decision: str  # "allow" | "deny"
    reason_code: str  # one of REASON_CODES
    matched_grant: dict | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reason_code": self.reason_code,
            "matched_grant": self.matched_grant,
        }


@dataclass(frozen=True)
class Scope:
    """A parsed namespaced resource scope: ``namespace:seg/seg``."""

    namespace: str
    segments: tuple[str, ...]

    @property
    def depth(self) -> int:
        return len(self.segments)


def parse_scope(raw: Any) -> Scope | None:
    """Parse a scope string. Returns ``None`` when malformed/empty."""

    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text or ":" not in text:
        return None
    namespace, _, path = text.partition(":")
    namespace = namespace.strip()
    if not namespace:
        return None
    segments = tuple(part for part in path.split("/") if part != "")
    if not segments:
        return None
    return Scope(namespace=namespace, segments=segments)


def _segment_matches(grant_segment: str, request_segment: str) -> bool:
    return grant_segment == WILDCARD or grant_segment == request_segment


def is_descendant_or_equal(child: Scope, ancestor: Scope) -> bool:
    """Return whether ``child`` is the same as, or nested under, ``ancestor``.

    The ancestor's segments must be a (wildcard-aware) prefix of the child's,
    and the ancestor must be no deeper than the child.
    """

    if child.namespace != ancestor.namespace:
        return False
    if ancestor.depth > child.depth:
        return False
    return all(
        _segment_matches(ancestor.segments[i], child.segments[i])
        for i in range(ancestor.depth)
    )


class PermissionModel:
    """Loaded, immutable view of the permission grant + deny tables."""

    def __init__(
        self,
        grants: list[dict[str, Any]],
        denies: list[dict[str, Any]],
        role_ids: Iterable[str],
        agent_role_map: dict[str, str] | None = None,
    ) -> None:
        self.grants = list(grants)
        self.denies = list(denies)
        self.role_ids = set(role_ids)
        self.agent_role_map = dict(agent_role_map or {})
        self.known_actions = {
            str(row.get("action", "")).strip()
            for row in (*self.grants, *self.denies)
            if str(row.get("action", "")).strip()
        }

    def resolve_role(self, agent_id: str) -> str | None:
        """Resolve an agent id to a role id, or ``None`` when unknown."""

        if agent_id in self.agent_role_map:
            return self.agent_role_map[agent_id]
        if agent_id in self.role_ids:
            return agent_id
        return None


def load_model(
    grants_path: Path = PERMISSION_GRANTS_PATH,
    registry_path: Path = AGENT_REGISTRY_PATH,
) -> PermissionModel:
    grants_doc = json.loads(grants_path.read_text(encoding="utf-8"))
    registry_doc = json.loads(registry_path.read_text(encoding="utf-8"))
    role_ids = {
        str(role.get("id", "")).strip()
        for role in registry_doc.get("roles", [])
        if str(role.get("id", "")).strip()
    }
    return PermissionModel(
        grants=grants_doc.get("grants", []),
        denies=grants_doc.get("denies", []),
        role_ids=role_ids,
    )


def _agent_matches(row_agent_id: str, agent_id: str) -> bool:
    return row_agent_id == WILDCARD or row_agent_id == agent_id


def _role_matches(row_role_id: str, role_id: str | None) -> bool:
    if row_role_id == WILDCARD:
        return True
    return role_id is not None and row_role_id == role_id


def _deny_matches(deny: dict, agent_id: str, role_id: str | None, action: str, scope: Scope) -> bool:
    if str(deny.get("action", "")) != action:
        return False
    if not _agent_matches(str(deny.get("agent_id", "")), agent_id):
        return False
    if not _role_matches(str(deny.get("role_id", "")), role_id):
        return False
    deny_scope = parse_scope(deny.get("resource_scope"))
    if deny_scope is None:
        return False
    return is_descendant_or_equal(scope, deny_scope)


def _grant_rank(grant: dict, agent_id: str, scope: Scope) -> tuple[int, int] | None:
    """Return a precedence rank for a matching grant, or ``None`` if no match.

    Higher tuples win. First element: 1 for a direct (agent-exact) grant, 0 for
    a role/wildcard grant. Second element: the grant scope depth, so a more
    specific (deeper, exact) scope outranks an inherited parent scope.
    """

    grant_scope = parse_scope(grant.get("resource_scope"))
    if grant_scope is None:
        return None
    if not is_descendant_or_equal(scope, grant_scope):
        return None
    row_agent = str(grant.get("agent_id", ""))
    direct = 1 if (row_agent != WILDCARD and row_agent == agent_id) else 0
    return (direct, grant_scope.depth)


def _approval_satisfied(approval_class: str, approvals: Iterable[str] | None) -> bool:
    if approval_class in AUTO_SATISFIED_APPROVAL_CLASSES:
        return True
    granted = set(approvals or ())
    return approval_class in granted


def can(
    agent_id: str,
    action: str,
    resource_scope: str | list[str],
    *,
    model: PermissionModel,
    task_scope: str | None = None,
    approvals: Iterable[str] | None = None,
) -> Decision:
    """Evaluate an authorization request deterministically.

    Deny precedence (highest first):
    explicit_deny > invalid_input > too_broad_scope > unsatisfied_approval >
    no_matching_grant.
    """

    agent_norm = agent_id.strip() if isinstance(agent_id, str) else ""
    action_norm = action.strip() if isinstance(action, str) else ""

    # Normalize the requested scope(s) into a list of raw strings.
    if isinstance(resource_scope, list):
        raw_scopes = resource_scope
    else:
        raw_scopes = [resource_scope]

    parsed_scopes = [parse_scope(raw) for raw in raw_scopes]
    role_id = model.resolve_role(agent_norm) if agent_norm else None

    # 1. explicit_deny: absolute precedence over every other condition.
    if action_norm:
        for scope in parsed_scopes:
            if scope is None:
                continue
            for deny in model.denies:
                if _deny_matches(deny, agent_norm, role_id, action_norm, scope):
                    return Decision("deny", "explicit_deny", deny)

    # 2. invalid_input: unknown agent, unknown/empty action, malformed/empty scope.
    if not agent_norm or role_id is None:
        return Decision("deny", "invalid_input", None)
    if not action_norm or action_norm not in model.known_actions:
        return Decision("deny", "invalid_input", None)
    if not raw_scopes or any(scope is None for scope in parsed_scopes):
        return Decision("deny", "invalid_input", None)

    # 3. too_broad_scope: multiple independent scopes, or broader than the task.
    distinct_scopes = {(s.namespace, s.segments) for s in parsed_scopes}  # type: ignore[union-attr]
    if len(distinct_scopes) > 1:
        return Decision("deny", "too_broad_scope", None)
    scope = parsed_scopes[0]
    assert scope is not None  # narrowed by the invalid_input guard above
    if task_scope is not None:
        task = parse_scope(task_scope)
        if task is None or not is_descendant_or_equal(scope, task):
            return Decision("deny", "too_broad_scope", None)

    # 4. Find the best-matching grant (direct > role, deeper scope > inherited).
    best_grant: dict | None = None
    best_rank: tuple[int, int] | None = None
    for grant in model.grants:
        if str(grant.get("action", "")) != action_norm:
            continue
        if not _agent_matches(str(grant.get("agent_id", "")), agent_norm):
            continue
        if not _role_matches(str(grant.get("role_id", "")), role_id):
            continue
        rank = _grant_rank(grant, agent_norm, scope)
        if rank is None:
            continue
        if best_rank is None or rank > best_rank:
            best_rank = rank
            best_grant = grant

    if best_grant is None:
        return Decision("deny", "no_matching_grant", None)

    approval_class = str(best_grant.get("approval_class", ""))
    if not _approval_satisfied(approval_class, approvals):
        return Decision("deny", "unsatisfied_approval", best_grant)

    return Decision("allow", "allow", best_grant)


def _check_command(args: argparse.Namespace) -> int:
    model = load_model()
    scope: str | list[str]
    if len(args.scope) == 1:
        scope = args.scope[0]
    else:
        scope = list(args.scope)
    approvals = list(args.approval or [])
    decision = can(
        args.agent,
        args.action,
        scope,
        model=model,
        task_scope=args.task_scope,
        approvals=approvals,
    )
    print(json.dumps(decision.as_dict(), ensure_ascii=False, indent=2))
    return 0 if decision.decision == "allow" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="HQ deterministic permission checks.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="Evaluate a single authorization request.")
    check.add_argument("--agent", required=True, help="Requesting agent id.")
    check.add_argument("--action", required=True, help="Requested action.")
    check.add_argument(
        "--scope",
        required=True,
        nargs="+",
        help="Requested resource scope(s).",
    )
    check.add_argument("--task-scope", default=None, help="Active task scope, if any.")
    check.add_argument(
        "--approval",
        action="append",
        help="Approval class explicitly satisfied (repeatable).",
    )
    check.set_defaults(func=_check_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
