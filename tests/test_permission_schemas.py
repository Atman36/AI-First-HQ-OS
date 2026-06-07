from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "05 AI Control Plane" / "schemas"


def load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def validator_for(name: str) -> Draft202012Validator:
    schema = load_schema(name)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def failing_fields(validator: Draft202012Validator, payload: dict) -> set[str]:
    fields: set[str] = set()
    for error in validator.iter_errors(payload):
        path = list(error.absolute_path)
        if path:
            fields.add(str(path[-1]))
        else:
            # required/property errors at the root report the missing key in the message.
            fields.add(error.message)
    return fields


def valid_permission_grants() -> dict:
    return {
        "version": 1,
        "updated_at": "2026-06-07",
        "grants": [
            {
                "agent_id": "*",
                "role_id": "ai_operations_lead",
                "resource_scope": "hq:control-plane/task-board",
                "action": "update_task_state",
                "approval_class": "auto_low_risk",
            }
        ],
        "denies": [
            {
                "agent_id": "*",
                "role_id": "*",
                "resource_scope": "tool:destructive_or_payment",
                "action": "execute",
                "reason": "forbidden_without_explicit_approval",
            }
        ],
    }


def valid_approval_checkpoint() -> dict:
    return {
        "schema_version": 1,
        "entity_type": "approval_checkpoint",
        "id": "chk-1",
        "run_id": "run-1",
        "step_id": "step-3",
        "agent_id": "agent-1",
        "role_id": "delivery",
        "action": "send_external",
        "resource_scope": "external:buyer-email",
        "tool_class": "external_write",
        "approval_class": "human_before_external",
        "status": "pending",
        "decision": "",
        "resumption_pointer": {"step_id": "step-3"},
    }


def valid_run_receipt() -> dict:
    return {
        "schema_version": 1,
        "entity_type": "run_receipt",
        "run_id": "run-1",
        "task_id": "task-1",
        "agent_id": "agent-1",
        "role_id": "delivery",
        "steps": [],
        "sources": [],
        "approvals": [],
        "changed_artifacts": [],
        "verification_checks": [],
        "open_questions": [],
    }


def valid_agent_release() -> dict:
    return {
        "change_type": "policy",
        "affected_files": ["05 AI Control Plane/operating-policies.json"],
        "rollback_path": "git revert <sha>",
        "eval_or_review_signal": "governor review recorded",
        "permission_expansion": False,
        "human_approval_id": None,
    }


class PermissionGrantsSchemaTests(unittest.TestCase):
    def setUp(self):
        self.validator = validator_for("permission-grants.schema.json")

    def test_valid_payload_accepted(self):
        self.assertEqual(list(self.validator.iter_errors(valid_permission_grants())), [])

    def test_invalid_approval_class_rejected(self):
        payload = valid_permission_grants()
        payload["grants"][0]["approval_class"] = "totally_made_up"
        fields = failing_fields(self.validator, payload)
        self.assertIn("approval_class", fields)

    def test_missing_required_grant_field_rejected(self):
        payload = valid_permission_grants()
        del payload["grants"][0]["action"]
        errors = list(self.validator.iter_errors(payload))
        self.assertTrue(any("action" in error.message for error in errors))

    def test_additional_property_rejected(self):
        payload = valid_permission_grants()
        payload["grants"][0]["extra"] = "nope"
        self.assertTrue(list(self.validator.iter_errors(payload)))


class ApprovalCheckpointSchemaTests(unittest.TestCase):
    def setUp(self):
        self.validator = validator_for("approval-checkpoint.schema.json")

    def test_valid_payload_accepted(self):
        self.assertEqual(list(self.validator.iter_errors(valid_approval_checkpoint())), [])

    def test_missing_resumption_pointer_step_id_rejected(self):
        payload = valid_approval_checkpoint()
        payload["resumption_pointer"] = {}
        errors = list(self.validator.iter_errors(payload))
        self.assertTrue(any("step_id" in error.message for error in errors))

    def test_invalid_tool_class_rejected(self):
        payload = valid_approval_checkpoint()
        payload["tool_class"] = "not_sensitive"
        fields = failing_fields(self.validator, payload)
        self.assertIn("tool_class", fields)


class RunReceiptSchemaTests(unittest.TestCase):
    def setUp(self):
        self.validator = validator_for("run-receipt.schema.json")

    def test_valid_payload_accepted(self):
        self.assertEqual(list(self.validator.iter_errors(valid_run_receipt())), [])

    def test_missing_linkage_field_rejected(self):
        for field in (
            "run_id",
            "task_id",
            "agent_id",
            "role_id",
            "steps",
            "sources",
            "approvals",
            "changed_artifacts",
            "verification_checks",
            "open_questions",
        ):
            payload = valid_run_receipt()
            del payload[field]
            errors = list(self.validator.iter_errors(payload))
            self.assertTrue(
                any(field in error.message for error in errors),
                msg=f"expected rejection naming {field}",
            )

    def test_additional_property_rejected(self):
        payload = valid_run_receipt()
        payload["secret_token"] = "sk-abc"
        self.assertTrue(list(self.validator.iter_errors(payload)))


class AgentReleaseSchemaTests(unittest.TestCase):
    def setUp(self):
        self.validator = validator_for("agent-release.schema.json")

    def test_valid_payload_accepted(self):
        self.assertEqual(list(self.validator.iter_errors(valid_agent_release())), [])

    def test_invalid_change_type_rejected(self):
        payload = valid_agent_release()
        payload["change_type"] = "config"
        fields = failing_fields(self.validator, payload)
        self.assertIn("change_type", fields)

    def test_missing_rollback_path_rejected(self):
        payload = valid_agent_release()
        del payload["rollback_path"]
        errors = list(self.validator.iter_errors(payload))
        self.assertTrue(any("rollback_path" in error.message for error in errors))


if __name__ == "__main__":
    unittest.main()
