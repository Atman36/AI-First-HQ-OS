from __future__ import annotations

import importlib.util
import random
import string
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "hq_permissions.py"


def load_module():
    spec = importlib.util.spec_from_file_location("hq_permissions_test_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    import sys

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


hq = load_module()


def build_model(*, grants=None, denies=None, role_ids=None, agent_role_map=None):
    return hq.PermissionModel(
        grants=grants if grants is not None else default_grants(),
        denies=denies if denies is not None else default_denies(),
        role_ids=role_ids if role_ids is not None else DEFAULT_ROLES,
        agent_role_map=agent_role_map,
    )


DEFAULT_ROLES = {
    "ai_operations_lead",
    "delivery",
    "growth",
    "governor",
    "ceo",
}


def default_grants():
    return [
        {
            "agent_id": "*",
            "role_id": "ai_operations_lead",
            "resource_scope": "hq:control-plane/task-board",
            "action": "update_task_state",
            "approval_class": "auto_low_risk",
        },
        {
            "agent_id": "*",
            "role_id": "governor",
            "resource_scope": "policy:*",
            "action": "review_policy_change",
            "approval_class": "required_review",
        },
        {
            "agent_id": "*",
            "role_id": "ceo",
            "resource_scope": "external:*",
            "action": "approve_send_or_publish",
            "approval_class": "founder_only",
        },
    ]


def default_denies():
    return [
        {
            "agent_id": "*",
            "role_id": "*",
            "resource_scope": "tool:destructive_or_payment",
            "action": "execute",
            "reason": "forbidden_without_explicit_approval",
        }
    ]


class ScopeParsingTests(unittest.TestCase):
    def test_parse_valid(self):
        scope = hq.parse_scope("hq:control-plane/task-board")
        self.assertEqual(scope.namespace, "hq")
        self.assertEqual(scope.segments, ("control-plane", "task-board"))

    def test_parse_empty_or_malformed(self):
        for raw in ("", "   ", "no-namespace", ":path", "hq:", 123, None):
            self.assertIsNone(hq.parse_scope(raw))

    def test_descendant_inheritance(self):
        parent = hq.parse_scope("policy:*")
        child = hq.parse_scope("policy:autonomy/tiers")
        self.assertTrue(hq.is_descendant_or_equal(child, parent))

    def test_disjoint_not_descendant(self):
        a = hq.parse_scope("policy:autonomy")
        b = hq.parse_scope("external:buyer")
        self.assertFalse(hq.is_descendant_or_equal(a, b))
        self.assertFalse(hq.is_descendant_or_equal(b, a))

    def test_wildcard_segment_matching(self):
        grant = hq.parse_scope("project:*/private-packet")
        req = hq.parse_scope("project:founder-sprint/private-packet")
        self.assertTrue(hq.is_descendant_or_equal(req, grant))
        mismatch = hq.parse_scope("project:founder-sprint/public-packet")
        self.assertFalse(hq.is_descendant_or_equal(mismatch, grant))


class ReasonCodeTableTests(unittest.TestCase):
    def setUp(self):
        self.model = build_model()

    def test_allow_auto_low_risk(self):
        d = hq.can(
            "ai_operations_lead",
            "update_task_state",
            "hq:control-plane/task-board",
            model=self.model,
        )
        self.assertEqual((d.decision, d.reason_code), ("allow", "allow"))

    def test_inherited_grant_via_role_and_parent_scope(self):
        d = hq.can(
            "governor",
            "review_policy_change",
            "policy:autonomy/tiers",
            model=self.model,
            approvals=["required_review"],
        )
        self.assertEqual((d.decision, d.reason_code), ("allow", "allow"))

    def test_unsatisfied_approval(self):
        d = hq.can(
            "ceo",
            "approve_send_or_publish",
            "external:buyer-email",
            model=self.model,
        )
        self.assertEqual((d.decision, d.reason_code), ("deny", "unsatisfied_approval"))

    def test_satisfied_approval(self):
        d = hq.can(
            "ceo",
            "approve_send_or_publish",
            "external:buyer-email",
            model=self.model,
            approvals=["founder_only"],
        )
        self.assertEqual(d.decision, "allow")

    def test_invalid_input_unknown_agent(self):
        d = hq.can("nobody", "update_task_state", "hq:control-plane/task-board", model=self.model)
        self.assertEqual((d.decision, d.reason_code), ("deny", "invalid_input"))

    def test_invalid_input_unknown_action(self):
        d = hq.can("governor", "mystery_action", "policy:autonomy", model=self.model)
        self.assertEqual((d.decision, d.reason_code), ("deny", "invalid_input"))

    def test_invalid_input_malformed_scope(self):
        d = hq.can("governor", "review_policy_change", "not-a-scope", model=self.model)
        self.assertEqual((d.decision, d.reason_code), ("deny", "invalid_input"))

    def test_no_matching_grant(self):
        d = hq.can(
            "ai_operations_lead",
            "review_policy_change",
            "policy:autonomy",
            model=self.model,
        )
        self.assertEqual((d.decision, d.reason_code), ("deny", "no_matching_grant"))

    def test_explicit_deny(self):
        d = hq.can(
            "delivery",
            "execute",
            "tool:destructive_or_payment",
            model=self.model,
        )
        self.assertEqual((d.decision, d.reason_code), ("deny", "explicit_deny"))


class GrantPrecedenceTests(unittest.TestCase):
    def test_direct_grant_outranks_role_grant(self):
        grants = [
            {
                "agent_id": "*",
                "role_id": "delivery",
                "resource_scope": "project:x/private-packet",
                "action": "draft_internal_material",
                "approval_class": "human_before_external",
            },
            {
                "agent_id": "agent-007",
                "role_id": "delivery",
                "resource_scope": "project:x/private-packet",
                "action": "draft_internal_material",
                "approval_class": "auto_low_risk",
            },
        ]
        model = build_model(grants=grants, denies=[], role_ids={"delivery"}, agent_role_map={"agent-007": "delivery"})
        d = hq.can("agent-007", "draft_internal_material", "project:x/private-packet", model=model)
        # direct grant (auto_low_risk) wins, so allow without approvals
        self.assertEqual(d.decision, "allow")
        self.assertEqual(d.matched_grant["approval_class"], "auto_low_risk")

    def test_deeper_scope_outranks_inherited_parent(self):
        grants = [
            {
                "agent_id": "*",
                "role_id": "governor",
                "resource_scope": "policy:*",
                "action": "review_policy_change",
                "approval_class": "founder_only",
            },
            {
                "agent_id": "*",
                "role_id": "governor",
                "resource_scope": "policy:autonomy/tiers",
                "action": "review_policy_change",
                "approval_class": "auto_low_risk",
            },
        ]
        model = build_model(grants=grants, denies=[], role_ids={"governor"})
        d = hq.can("governor", "review_policy_change", "policy:autonomy/tiers", model=model)
        self.assertEqual(d.decision, "allow")
        self.assertEqual(d.matched_grant["resource_scope"], "policy:autonomy/tiers")


class PrecedenceWhenMultipleDeniesHoldTests(unittest.TestCase):
    def test_explicit_deny_beats_unsatisfied_approval(self):
        grants = [
            {
                "agent_id": "*",
                "role_id": "ceo",
                "resource_scope": "external:*",
                "action": "send",
                "approval_class": "founder_only",
            }
        ]
        denies = [
            {
                "agent_id": "*",
                "role_id": "*",
                "resource_scope": "external:*",
                "action": "send",
                "reason": "blocked",
            }
        ]
        model = build_model(grants=grants, denies=denies, role_ids={"ceo"})
        # A grant matches but approval unsatisfied AND an explicit deny matches.
        d = hq.can("ceo", "send", "external:buyer", model=model)
        self.assertEqual(d.reason_code, "explicit_deny")

    def test_explicit_deny_beats_invalid_input(self):
        denies = [
            {
                "agent_id": "*",
                "role_id": "*",
                "resource_scope": "tool:destructive_or_payment",
                "action": "execute",
                "reason": "forbidden",
            }
        ]
        model = build_model(grants=[], denies=denies, role_ids={"delivery"})
        # Unknown agent (would be invalid_input) but explicit deny is wildcard.
        d = hq.can("unknown-agent", "execute", "tool:destructive_or_payment", model=model)
        self.assertEqual(d.reason_code, "explicit_deny")

    def test_too_broad_scope_beats_unsatisfied_approval(self):
        d = hq.can(
            "ceo",
            "approve_send_or_publish",
            ["external:a", "external:b"],
            model=build_model(),
        )
        self.assertEqual(d.reason_code, "too_broad_scope")


class ScopeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.model = build_model()

    def test_multi_scope_denied_as_too_broad(self):
        d = hq.can(
            "governor",
            "review_policy_change",
            ["policy:a", "policy:b"],
            model=self.model,
        )
        self.assertEqual((d.decision, d.reason_code), ("deny", "too_broad_scope"))

    def test_request_broader_than_task_scope_denied(self):
        d = hq.can(
            "governor",
            "review_policy_change",
            "policy:autonomy",
            model=self.model,
            task_scope="policy:autonomy/tiers",
            approvals=["required_review"],
        )
        self.assertEqual((d.decision, d.reason_code), ("deny", "too_broad_scope"))

    def test_request_within_task_scope_allowed(self):
        d = hq.can(
            "governor",
            "review_policy_change",
            "policy:autonomy/tiers",
            model=self.model,
            task_scope="policy:autonomy",
            approvals=["required_review"],
        )
        self.assertEqual(d.decision, "allow")


class InheritedForbiddenApprovalTests(unittest.TestCase):
    def test_inherited_forbidden_allows_with_explicit_approval(self):
        grants = [
            {
                "agent_id": "*",
                "role_id": "delivery",
                "resource_scope": "tool:*",
                "action": "execute",
                "approval_class": "forbidden_without_explicit_approval",
            }
        ]
        model = build_model(grants=grants, denies=[], role_ids={"delivery"})
        # Without approval -> deny
        d_no = hq.can("delivery", "execute", "tool:payment/charge", model=model)
        self.assertEqual(d_no.reason_code, "unsatisfied_approval")
        # With explicit approval -> allow (inherited treated like a direct grant of that class)
        d_yes = hq.can(
            "delivery",
            "execute",
            "tool:payment/charge",
            model=model,
            approvals=["forbidden_without_explicit_approval"],
        )
        self.assertEqual(d_yes.decision, "allow")


class DeterminismPropertyTests(unittest.TestCase):
    def test_identical_inputs_identical_decision(self):
        model = build_model()
        rng = random.Random(1234)
        agents = list(DEFAULT_ROLES) + ["unknown", ""]
        actions = ["update_task_state", "review_policy_change", "approve_send_or_publish", "execute", "x"]
        scopes = [
            "hq:control-plane/task-board",
            "policy:autonomy/tiers",
            "external:buyer",
            "tool:destructive_or_payment",
            "garbage",
        ]
        for _ in range(500):
            agent = rng.choice(agents)
            action = rng.choice(actions)
            scope = rng.choice(scopes)
            approvals = rng.choice([None, ["founder_only"], ["required_review"]])
            d1 = hq.can(agent, action, scope, model=model, approvals=approvals)
            d2 = hq.can(agent, action, scope, model=model, approvals=approvals)
            self.assertEqual(d1.as_dict(), d2.as_dict())


class DenyByDefaultPropertyTests(unittest.TestCase):
    def test_random_unknown_triples_never_allow(self):
        model = build_model()
        rng = random.Random(99)

        def rand_token():
            return "".join(rng.choice(string.ascii_lowercase) for _ in range(8))

        for _ in range(500):
            agent = rand_token()
            action = rand_token()
            scope = f"{rand_token()}:{rand_token()}/{rand_token()}"
            d = hq.can(agent, action, scope, model=model)
            self.assertEqual(d.decision, "deny")


if __name__ == "__main__":
    unittest.main()
