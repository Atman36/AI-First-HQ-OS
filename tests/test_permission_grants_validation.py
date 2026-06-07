from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "hq_control_plane.py"


def load_module():
    spec = importlib.util.spec_from_file_location("hq_control_plane_perm_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cp = load_module()


def registry():
    return {
        "version": 1,
        "updated_at": "2026-06-07",
        "roles": [
            {"id": "delivery", "display_name": "Delivery", "role_type": "ai", "default_autonomy_tier": "A2", "mission": "x"},
            {"id": "governor", "display_name": "Governor", "role_type": "ai", "default_autonomy_tier": "A3", "mission": "x"},
        ],
    }


class PermissionGrantsValidationTests(unittest.TestCase):
    def test_known_role_passes(self):
        ctx = cp.ValidationContext()
        grants = {
            "version": 1,
            "updated_at": "2026-06-07",
            "grants": [
                {"agent_id": "*", "role_id": "delivery", "resource_scope": "a:b", "action": "x", "approval_class": "auto_low_risk"}
            ],
            "denies": [],
        }
        cp.validate_permission_grants(grants, registry(), ctx)
        self.assertEqual(ctx.issues, [])

    def test_wildcard_role_allowed(self):
        ctx = cp.ValidationContext()
        grants = {
            "grants": [],
            "denies": [
                {"agent_id": "*", "role_id": "*", "resource_scope": "tool:x", "action": "execute", "reason": "r"}
            ],
        }
        cp.validate_permission_grants(grants, registry(), ctx)
        self.assertEqual(ctx.issues, [])

    def test_unknown_role_is_validation_error(self):
        ctx = cp.ValidationContext()
        grants = {
            "grants": [
                {"agent_id": "*", "role_id": "ghost", "resource_scope": "a:b", "action": "x", "approval_class": "auto_low_risk"}
            ],
            "denies": [],
        }
        cp.validate_permission_grants(grants, registry(), ctx)
        self.assertTrue(ctx.issues)
        self.assertIn("ghost", str(ctx.issues[0]))
        self.assertIn("role_id", str(ctx.issues[0]))


if __name__ == "__main__":
    unittest.main()
