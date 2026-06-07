from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


CONTROL_PLANE = Path(__file__).resolve().parents[1] / "05 AI Control Plane"
GRANTS_PATH = CONTROL_PLANE / "permission-grants.json"
GRANTS_SCHEMA_PATH = CONTROL_PLANE / "schemas" / "permission-grants.schema.json"

EXPECTED_GRANTS = {
    ("ai_operations_lead", "update_task_state"): "auto_low_risk",
    ("delivery", "draft_internal_material"): "auto_low_risk",
    ("growth", "prepare_founder_review"): "human_before_external",
    ("governor", "review_policy_change"): "required_review",
    ("ceo", "approve_send_or_publish"): "founder_only",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class PermissionGrantsDataTests(unittest.TestCase):
    def setUp(self):
        self.data = load(GRANTS_PATH)
        schema = load(GRANTS_SCHEMA_PATH)
        self.validator = Draft202012Validator(schema, format_checker=FormatChecker())

    def test_data_matches_schema(self):
        self.assertEqual(list(self.validator.iter_errors(self.data)), [])

    def test_expected_grant_rows_present_with_correct_approval_class(self):
        actual = {
            (g["role_id"], g["action"]): g["approval_class"]
            for g in self.data["grants"]
        }
        for key, approval_class in EXPECTED_GRANTS.items():
            self.assertIn(key, actual, msg=f"missing grant {key}")
            self.assertEqual(actual[key], approval_class)

    def test_exactly_five_example_grants(self):
        self.assertEqual(len(self.data["grants"]), 5)

    def test_destructive_or_payment_deny_resolves_to_forbidden(self):
        denies = self.data["denies"]
        umbrella = [
            d for d in denies if d["resource_scope"] == "tool:destructive_or_payment"
        ]
        self.assertEqual(len(umbrella), 1)
        self.assertEqual(umbrella[0]["reason"], "forbidden_without_explicit_approval")
        self.assertEqual(umbrella[0]["agent_id"], "*")
        self.assertEqual(umbrella[0]["role_id"], "*")

    def test_no_destructive_or_payment_tool_class(self):
        # destructive_or_payment is an umbrella resource scope, not an eighth tool class.
        for grant in self.data["grants"]:
            self.assertNotEqual(grant["resource_scope"], "tool:destructive_or_payment")


if __name__ == "__main__":
    unittest.main()
