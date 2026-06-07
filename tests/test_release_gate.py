from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "hq_gate.py"


def load_module():
    spec = importlib.util.spec_from_file_location("hq_gate_release_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gate = load_module()


def valid_manifest(**overrides):
    manifest = {
        "change_type": "policy",
        "affected_files": ["05 AI Control Plane/operating-policies.json"],
        "rollback_path": "git revert <sha>",
        "eval_or_review_signal": "governor review recorded",
        "permission_expansion": False,
        "human_approval_id": None,
    }
    manifest.update(overrides)
    return manifest


class ReleaseGateEvidenceTests(unittest.TestCase):
    def test_valid_manifest_passes(self):
        self.assertEqual(gate.evaluate_release_gate(valid_manifest()), [])

    def test_invalid_change_type_blocks(self):
        reasons = gate.evaluate_release_gate(valid_manifest(change_type="config"))
        self.assertTrue(any("change_type" in r for r in reasons))

    def test_missing_affected_files_blocks(self):
        reasons = gate.evaluate_release_gate(valid_manifest(affected_files=[]))
        self.assertTrue(any("affected_files" in r for r in reasons))

    def test_missing_rollback_path_blocks(self):
        reasons = gate.evaluate_release_gate(valid_manifest(rollback_path="  "))
        self.assertTrue(any("rollback_path" in r for r in reasons))

    def test_missing_eval_signal_blocks(self):
        reasons = gate.evaluate_release_gate(valid_manifest(eval_or_review_signal=""))
        self.assertTrue(any("eval_or_review_signal" in r for r in reasons))


class PermissionExpansionTests(unittest.TestCase):
    def test_manifest_expansion_without_approval_blocks(self):
        reasons = gate.evaluate_release_gate(
            valid_manifest(permission_expansion=True, human_approval_id=None)
        )
        self.assertTrue(any("permission_expansion" in r for r in reasons))

    def test_manifest_expansion_with_approval_passes(self):
        reasons = gate.evaluate_release_gate(
            valid_manifest(permission_expansion=True, human_approval_id="appr-1")
        )
        self.assertEqual(reasons, [])

    def test_redundant_layer_blocks_when_manifest_flag_is_wrong(self):
        # Manifest claims no expansion, but the derived diff widens grants.
        reasons = gate.evaluate_release_gate(
            valid_manifest(permission_expansion=False, human_approval_id=None),
            derived_permission_expansion=True,
        )
        self.assertTrue(any("derived permission expansion" in r for r in reasons))

    def test_redundant_layer_passes_with_approval(self):
        reasons = gate.evaluate_release_gate(
            valid_manifest(permission_expansion=False, human_approval_id="appr-2"),
            derived_permission_expansion=True,
        )
        self.assertEqual(reasons, [])


class DeriveExpansionTests(unittest.TestCase):
    def test_new_grant_row_is_expansion(self):
        prev = [
            {"agent_id": "*", "role_id": "delivery", "resource_scope": "a:b", "action": "x", "approval_class": "auto_low_risk"}
        ]
        curr = prev + [
            {"agent_id": "*", "role_id": "growth", "resource_scope": "c:d", "action": "y", "approval_class": "auto_low_risk"}
        ]
        self.assertTrue(gate.derive_permission_expansion(prev, curr))

    def test_no_change_is_not_expansion(self):
        rows = [
            {"agent_id": "*", "role_id": "delivery", "resource_scope": "a:b", "action": "x", "approval_class": "auto_low_risk"}
        ]
        self.assertFalse(gate.derive_permission_expansion(rows, list(rows)))

    def test_removed_grant_is_not_expansion(self):
        prev = [
            {"agent_id": "*", "role_id": "delivery", "resource_scope": "a:b", "action": "x", "approval_class": "auto_low_risk"},
            {"agent_id": "*", "role_id": "growth", "resource_scope": "c:d", "action": "y", "approval_class": "auto_low_risk"},
        ]
        curr = prev[:1]
        self.assertFalse(gate.derive_permission_expansion(prev, curr))

    def test_new_capability_scope_is_expansion(self):
        prev_caps = [{"role_id": "delivery", "resource_scopes": ["a:b"], "tool_classes": ["internal_write"]}]
        curr_caps = [{"role_id": "delivery", "resource_scopes": ["a:b", "x:y"], "tool_classes": ["internal_write"]}]
        self.assertTrue(
            gate.derive_permission_expansion(None, None, prev_caps, curr_caps)
        )

    def test_release_gate_command_blocks_capability_expansion_diff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "manifest.json"
            previous_registry = root / "previous-registry.json"
            current_registry = root / "current-registry.json"
            manifest.write_text(
                json.dumps(valid_manifest(permission_expansion=False)),
                encoding="utf-8",
            )
            previous_registry.write_text(
                json.dumps(
                    {
                        "capability_grants": [
                            {
                                "role_id": "delivery",
                                "resource_scopes": ["a:b"],
                                "tool_classes": ["internal_write"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            current_registry.write_text(
                json.dumps(
                    {
                        "capability_grants": [
                            {
                                "role_id": "delivery",
                                "resource_scopes": ["a:b", "x:y"],
                                "tool_classes": ["internal_write"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            args = SimpleNamespace(
                manifest=str(manifest),
                previous_grants=None,
                current_grants=None,
                previous_registry=str(previous_registry),
                current_registry=str(current_registry),
            )

            self.assertEqual(gate.release_gate_command(args), 1)


class HumanOnlyCategoryTests(unittest.TestCase):
    def test_external_send_without_approval_blocks(self):
        reasons = gate.evaluate_release_gate(
            valid_manifest(human_only_categories=["external_send"], human_approval_id=None)
        )
        self.assertTrue(any("human-only" in r for r in reasons))

    def test_human_only_with_approval_passes(self):
        reasons = gate.evaluate_release_gate(
            valid_manifest(
                human_only_categories=["money_commitment", "schema_meaning_change"],
                human_approval_id="appr-3",
            )
        )
        self.assertEqual(reasons, [])

    def test_determinism(self):
        manifest = valid_manifest(permission_expansion=True)
        self.assertEqual(
            gate.evaluate_release_gate(manifest),
            gate.evaluate_release_gate(manifest),
        )


if __name__ == "__main__":
    unittest.main()
