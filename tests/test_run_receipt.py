from __future__ import annotations

import importlib.util
import json
import random
import string
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "hq_permissions.py"


def load_module():
    spec = importlib.util.spec_from_file_location("hq_permissions_receipt_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


hq = load_module()


def valid_receipt():
    return {
        "schema_version": 1,
        "entity_type": "run_receipt",
        "run_id": "run-1",
        "task_id": "task-1",
        "agent_id": "agent-1",
        "role_id": "delivery",
        "steps": [{"id": "s1", "summary": "did a thing"}],
        "sources": ["doc-a"],
        "approvals": [],
        "changed_artifacts": ["file-x"],
        "verification_checks": ["tests"],
        "open_questions": [],
    }


class NormalizeReceiptTests(unittest.TestCase):
    def test_byte_identical_round_trip(self):
        receipt = valid_receipt()
        first = hq.normalize_receipt(receipt)
        second = hq.normalize_receipt(json.loads(first))
        self.assertEqual(first, second)

    def test_key_order_is_stable_regardless_of_input_order(self):
        receipt = valid_receipt()
        shuffled = dict(reversed(list(receipt.items())))
        self.assertEqual(hq.normalize_receipt(receipt), hq.normalize_receipt(shuffled))

    def test_normalization_strips_secret_and_timestamp_keys(self):
        receipt = valid_receipt()
        receipt["created_at"] = "2026-06-07T00:00:00Z"
        receipt["api_key"] = "sk-should-be-dropped"
        receipt["steps"][0]["token"] = "secret-value"
        output = hq.normalize_receipt(receipt)
        self.assertNotIn("created_at", output)
        self.assertNotIn("api_key", output)
        self.assertNotIn("token", output)
        self.assertNotIn("secret-value", output)

    def test_property_repeated_normalization_byte_identical(self):
        rng = random.Random(7)

        def rand_str():
            return "".join(rng.choice(string.ascii_letters) for _ in range(6))

        for _ in range(200):
            receipt = valid_receipt()
            receipt["steps"] = [{"id": rand_str(), "note": rand_str()} for _ in range(rng.randint(0, 4))]
            receipt["sources"] = [rand_str() for _ in range(rng.randint(0, 3))]
            a = hq.normalize_receipt(receipt)
            b = hq.normalize_receipt(json.loads(a))
            self.assertEqual(a, b)


class ValidateReceiptTests(unittest.TestCase):
    def test_valid_receipt_passes(self):
        hq.validate_receipt(valid_receipt())  # should not raise

    def test_missing_identifier_rejected(self):
        for field in ("run_id", "task_id", "agent_id", "role_id"):
            receipt = valid_receipt()
            del receipt[field]
            with self.assertRaises(hq.ReceiptError) as ctx:
                hq.validate_receipt(receipt)
            self.assertEqual(ctx.exception.field, field)

    def test_missing_collection_rejected(self):
        for field in ("steps", "sources", "approvals", "changed_artifacts", "verification_checks", "open_questions"):
            receipt = valid_receipt()
            del receipt[field]
            with self.assertRaises(hq.ReceiptError) as ctx:
                hq.validate_receipt(receipt)
            self.assertEqual(ctx.exception.field, field)

    def test_secret_bearing_field_rejected(self):
        receipt = valid_receipt()
        receipt["sources"] = [{"access_key": "AKIA..."}]
        with self.assertRaises(hq.ReceiptError) as ctx:
            hq.validate_receipt(receipt)
        self.assertIn("access_key", ctx.exception.field)

    def test_timestamp_only_field_rejected(self):
        receipt = valid_receipt()
        receipt["updated_at"] = "2026-06-07T00:00:00Z"
        with self.assertRaises(hq.ReceiptError) as ctx:
            hq.validate_receipt(receipt)
        self.assertIn("updated_at", ctx.exception.field)

    def test_validation_does_not_mutate_raw_trace(self):
        receipt = valid_receipt()
        receipt["updated_at"] = "2026-06-07T00:00:00Z"
        before = json.dumps(receipt, sort_keys=True)
        with self.assertRaises(hq.ReceiptError):
            hq.validate_receipt(receipt)
        self.assertEqual(json.dumps(receipt, sort_keys=True), before)

    def test_receipt_path_under_hq_receipts(self):
        path = hq.receipt_path("run-42")
        self.assertEqual(path.parent.name, "receipts")
        self.assertEqual(path.parent.parent.name, ".hq")


if __name__ == "__main__":
    unittest.main()
