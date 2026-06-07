from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


CONTROL_PLANE = Path(__file__).resolve().parents[1] / "05 AI Control Plane"
REGISTRY_PATH = CONTROL_PLANE / "agent-registry.json"
REGISTRY_SCHEMA_PATH = CONTROL_PLANE / "schemas" / "agent-registry.schema.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class CapabilityGrantsTests(unittest.TestCase):
    def setUp(self):
        self.registry = load(REGISTRY_PATH)
        self.schema = load(REGISTRY_SCHEMA_PATH)
        self.validator = Draft202012Validator(self.schema, format_checker=FormatChecker())

    def test_registry_still_validates(self):
        self.assertEqual(list(self.validator.iter_errors(self.registry)), [])

    def test_capability_grants_present(self):
        self.assertIn("capability_grants", self.registry)
        self.assertTrue(self.registry["capability_grants"])

    def test_capability_grants_reference_known_roles(self):
        role_ids = {role["id"] for role in self.registry["roles"]}
        for grant in self.registry["capability_grants"]:
            self.assertIn(
                grant["role_id"],
                role_ids,
                msg=f"capability grant references unknown role: {grant['role_id']}",
            )

    def test_canonical_ai_operations_lead_id(self):
        role_ids = {role["id"] for role in self.registry["roles"]}
        self.assertIn("ai_operations_lead", role_ids)
        self.assertNotIn("ai-ops-lead", role_ids)
        grant_roles = {g["role_id"] for g in self.registry["capability_grants"]}
        self.assertIn("ai_operations_lead", grant_roles)

    def test_principal_contract_unchanged_fields(self):
        contract = self.registry["principal_contract"]
        self.assertIn("required_identity_fields", contract)
        self.assertIn("default_constraints", contract)

    def test_schema_rejects_unknown_grant_field(self):
        registry = load(REGISTRY_PATH)
        registry["capability_grants"][0]["unexpected"] = "x"
        self.assertTrue(list(self.validator.iter_errors(registry)))

    def test_schema_rejects_invalid_approval_class(self):
        registry = load(REGISTRY_PATH)
        registry["capability_grants"][0]["approval_class"] = "bogus"
        self.assertTrue(list(self.validator.iter_errors(registry)))


if __name__ == "__main__":
    unittest.main()
