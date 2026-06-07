from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "hq_policy_hooks.py"
SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "05 AI Control Plane"
    / "schemas"
    / "approval-checkpoint.schema.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location("hq_policy_hooks_gate_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


hooks = load_module()


def make_request(tool_class="external_write", **overrides):
    defaults = dict(
        agent_id="agent-1",
        role_id="delivery",
        action="send_external",
        resource_scope="external:buyer-email",
        tool_class=tool_class,
        approval_class="human_before_external",
        run_id="run-1",
        step_id="step-3",
    )
    defaults.update(overrides)
    return hooks.ToolRequest(**defaults)


class PreActionGateTests(unittest.TestCase):
    def setUp(self):
        schema = __import__("json").loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.validator = Draft202012Validator(schema, format_checker=FormatChecker())

    def test_non_sensitive_tool_executes(self):
        result = hooks.pre_action_gate(make_request(tool_class="internal_write"))
        self.assertTrue(result.execute)
        self.assertIsNone(result.checkpoint)

    def test_missing_tool_class_does_not_execute(self):
        result = hooks.pre_action_gate(make_request(tool_class=""))
        self.assertFalse(result.execute)
        self.assertIsNone(result.checkpoint)
        self.assertEqual(result.reason, "missing_tool_class")

    def test_each_sensitive_class_triggers_checkpoint(self):
        for tool_class in hooks.SENSITIVE_TOOL_CLASSES:
            result = hooks.pre_action_gate(make_request(tool_class=tool_class))
            self.assertFalse(result.execute, msg=f"{tool_class} should not execute")
            self.assertIsNotNone(result.checkpoint)
            self.assertEqual(result.checkpoint["status"], "pending")
            # Generated checkpoint conforms to the schema.
            self.assertEqual(list(self.validator.iter_errors(result.checkpoint)), [])

    def test_checkpoint_carries_resumption_pointer(self):
        result = hooks.pre_action_gate(make_request())
        self.assertEqual(result.checkpoint["resumption_pointer"]["step_id"], "step-3")

    def test_pending_checkpoint_while_paused_does_not_execute(self):
        checkpoint = hooks.build_checkpoint_record(make_request())
        result = hooks.pre_action_gate(
            make_request(),
            run_state=hooks.RUN_STATE_PAUSED,
            checkpoint=checkpoint,
        )
        self.assertFalse(result.execute)
        self.assertEqual(result.reason, "pending")

    def test_approved_executes_from_step_without_auto_unpause(self):
        checkpoint = hooks.build_checkpoint_record(make_request())
        checkpoint["status"] = "decided"
        checkpoint["decision"] = "approved"
        result = hooks.pre_action_gate(
            make_request(),
            run_state=hooks.RUN_STATE_PAUSED,
            checkpoint=checkpoint,
        )
        self.assertTrue(result.execute)
        self.assertEqual(result.reason, "approved")
        self.assertEqual(result.checkpoint["resumption_pointer"]["step_id"], "step-3")

    def test_resumed_state_executes_despite_pending_checkpoint(self):
        checkpoint = hooks.build_checkpoint_record(make_request())
        self.assertEqual(checkpoint["status"], "pending")
        result = hooks.pre_action_gate(
            make_request(),
            run_state=hooks.RUN_STATE_RESUMED,
            checkpoint=checkpoint,
        )
        self.assertTrue(result.execute)
        self.assertEqual(result.reason, "run_resumed")

    def test_rejected_does_not_execute(self):
        checkpoint = hooks.build_checkpoint_record(make_request())
        checkpoint["status"] = "decided"
        checkpoint["decision"] = "rejected"
        result = hooks.pre_action_gate(make_request(), checkpoint=checkpoint)
        self.assertFalse(result.execute)
        self.assertEqual(result.reason, "rejected")

    def test_blocked_does_not_execute(self):
        checkpoint = hooks.build_checkpoint_record(make_request())
        checkpoint["status"] = "decided"
        checkpoint["decision"] = "blocked"
        result = hooks.pre_action_gate(make_request(), checkpoint=checkpoint)
        self.assertFalse(result.execute)
        self.assertEqual(result.reason, "blocked")

    def test_mcp_or_builtin_tool_still_gated(self):
        # An MCP/built-in tool request still carries tool_class and is gated.
        result = hooks.pre_action_gate(
            make_request(tool_class="money_movement", action="charge_card")
        )
        self.assertFalse(result.execute)
        self.assertIsNotNone(result.checkpoint)

    def test_determinism(self):
        req = make_request(tool_class="public_publish")
        a = hooks.pre_action_gate(req)
        b = hooks.pre_action_gate(req)
        self.assertEqual(a.as_dict(), b.as_dict())


if __name__ == "__main__":
    unittest.main()
