from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

# Add scripts to sys.path so modules in scripts/ can find each other
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

SCRIPT_PATH = SCRIPTS_DIR / "hq_telemetry_review.py"

def load_module(temp_root: Path):
    os.environ["HQ_TELEMETRY_REPO_ROOT"] = str(temp_root)
    os.environ["HQ_RUNTIME_PRIVATE_ROOT"] = str(temp_root / ".hq")
    
    # Force reload of related modules to pick up env changes
    for mod in ["hq_io", "hq_telemetry_store", "hq_telemetry_review"]:
        sys.modules.pop(mod, None)
        
    spec = importlib.util.spec_from_file_location("hq_telemetry_review", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module

class HqTelemetryReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_dir.name)
        (self.temp_root / "05 AI Control Plane").mkdir(parents=True, exist_ok=True)
        self.module = load_module(self.temp_root)

    def tearDown(self):
        os.environ.pop("HQ_TELEMETRY_REPO_ROOT", None)
        os.environ.pop("HQ_RUNTIME_PRIVATE_ROOT", None)
        self.temp_dir.cleanup()

    def test_init(self):
        self.assertEqual(self.module.REPO_ROOT, self.temp_root.resolve())

    def test_normalize_list(self):
        self.assertEqual(self.module.normalize_list(None), [])
        self.assertEqual(self.module.normalize_list([]), [])
        self.assertEqual(self.module.normalize_list([" a ", "b", " a", ""]), ["a", "b"])

    def test_normalize_contract_set(self):
        self.assertEqual(self.module.normalize_contract_set(None), set())
        self.assertEqual(self.module.normalize_contract_set([]), set())
        self.assertEqual(self.module.normalize_contract_set([" a ", "b", " "]), {"a", "b"})
        self.assertEqual(self.module.normalize_contract_set("not a list"), set())

    def test_round_metric(self):
        self.assertIsNone(self.module.round_metric(None))
        self.assertEqual(self.module.round_metric(1.23456), 1.2346)
        self.assertEqual(self.module.round_metric(1.2), 1.2)

    def test_median_hours(self):
        self.assertIsNone(self.module.median_hours([]))
        self.assertEqual(self.module.median_hours([10.0]), 10.0)
        self.assertEqual(self.module.median_hours([10.0, 20.0]), 15.0)
        self.assertEqual(self.module.median_hours([30.0, 10.0, 20.0]), 20.0)
        self.assertEqual(self.module.median_hours([10.0, 20.0, 30.0, 40.0]), 25.0)

    def test_ratio_result(self):
        self.assertEqual(
            self.module.ratio_result("m1", 1, 2),
            {"id": "m1", "value": 0.5, "numerator": 1, "denominator": 2}
        )
        self.assertEqual(
            self.module.ratio_result("m2", 1, 0),
            {"id": "m2", "value": None, "numerator": 1, "denominator": 0}
        )

    def test_hours_result(self):
        self.assertEqual(
            self.module.hours_result("m1", [10.0, 20.0]),
            {"id": "m1", "value": 15.0, "sample_size": 2}
        )
        self.assertEqual(
            self.module.hours_result("m2", []),
            {"id": "m2", "value": None, "sample_size": 0}
        )

    def test_scalar_result(self):
        self.assertEqual(self.module.scalar_result("m1", 10.5), {"id": "m1", "value": 10.5})
        self.assertEqual(self.module.scalar_result("m2", None), {"id": "m2", "value": None})

    def test_bool_from_metadata(self):
        metadata = {"a": True, "b": False, "c": 1}
        self.assertTrue(self.module.bool_from_metadata(metadata, "a"))
        self.assertFalse(self.module.bool_from_metadata(metadata, "b"))
        self.assertTrue(self.module.bool_from_metadata(metadata, "c"))
        self.assertTrue(self.module.bool_from_metadata(metadata, "missing", "a"))
        self.assertFalse(self.module.bool_from_metadata(metadata, "missing"))

    def test_numeric_from_metadata(self):
        metadata = {"a": 10, "b": 20.5, "c": "30", "d": "invalid"}
        self.assertEqual(self.module.numeric_from_metadata(metadata, "a"), 10.0)
        self.assertEqual(self.module.numeric_from_metadata(metadata, "b"), 20.5)
        self.assertEqual(self.module.numeric_from_metadata(metadata, "c"), 30.0)
        self.assertIsNone(self.module.numeric_from_metadata(metadata, "d"))
        self.assertEqual(self.module.numeric_from_metadata(metadata, "missing", "b"), 20.5)
        self.assertIsNone(self.module.numeric_from_metadata(metadata, "missing"))

    def test_evaluate_threshold(self):
        self.assertEqual(self.module.evaluate_threshold(10, None), "no_threshold")
        self.assertEqual(self.module.evaluate_threshold(None, {"comparison": "<", "value": 10}), "insufficient_data")
        
        t = {"comparison": "<", "value": 10}
        self.assertEqual(self.module.evaluate_threshold(5, t), "ok")
        self.assertEqual(self.module.evaluate_threshold(10, t), "breached")
        
        t = {"comparison": "<=", "value": 10}
        self.assertEqual(self.module.evaluate_threshold(10, t), "ok")
        self.assertEqual(self.module.evaluate_threshold(11, t), "breached")
        
        t = {"comparison": "=", "value": 10}
        self.assertEqual(self.module.evaluate_threshold(10, t), "ok")
        self.assertEqual(self.module.evaluate_threshold(11, t), "breached")
        
        t = {"comparison": ">=", "value": 10}
        self.assertEqual(self.module.evaluate_threshold(10, t), "ok")
        self.assertEqual(self.module.evaluate_threshold(9, t), "breached")
        
        t = {"comparison": ">", "value": 10}
        self.assertEqual(self.module.evaluate_threshold(11, t), "ok")
        self.assertEqual(self.module.evaluate_threshold(10, t), "breached")
        
        self.assertEqual(self.module.evaluate_threshold(10, {"comparison": "??", "value": 10}), "invalid_threshold")

    def test_format_metric_value(self):
        self.assertEqual(self.module.format_metric_value(None, "ratio"), "n/a")
        self.assertEqual(self.module.format_metric_value(0.1234, "ratio"), "12.3%")
        self.assertEqual(self.module.format_metric_value(1.234, "hours"), "1.23h")
        self.assertEqual(self.module.format_metric_value(1.234, "scalar"), "1.23")

    def test_event_actor(self):
        self.assertEqual(self.module.event_actor(None), "")
        self.assertEqual(self.module.event_actor({}), "")
        self.assertEqual(self.module.event_actor({"agent": " alice "}), "alice")

    def test_build_role_types(self):
        registry = {
            "roles": [
                {"id": "r1", "role_type": "ai"},
                {"id": "r2", "role_type": "human"},
                {"id": " ", "role_type": "ai"},
            ]
        }
        (self.temp_root / "05 AI Control Plane" / "agent-registry.json").write_text(json.dumps(registry))
        self.assertEqual(self.module.build_role_types(), {"r1": "ai", "r2": "human", "": "ai"})

    def test_build_active_tasks(self):
        active_work = {
            "tasks": [
                {"id": "t1", "column": "waiting"},
                {"id": "t2", "column": "done"},
                {"id": " "},
            ]
        }
        (self.temp_root / "05 AI Control Plane" / "active-work.json").write_text(json.dumps(active_work))
        tasks = self.module.build_active_tasks()
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks["t1"]["column"], "waiting")
        self.assertEqual(tasks["t2"]["column"], "done")

    def test_is_current_active_task(self):
        self.assertTrue(self.module.is_current_active_task({"column": "waiting"}))
        self.assertTrue(self.module.is_current_active_task({"column": "executing"}))
        self.assertFalse(self.module.is_current_active_task({"column": "done"}))
        self.assertTrue(self.module.is_current_active_task({}))

    def test_build_metric_registry(self):
        metrics = {
            "primary_metrics": [{"id": "m1"}],
            "secondary_metrics": [{"id": "m2"}]
        }
        (self.temp_root / "05 AI Control Plane" / "metrics-registry.json").write_text(json.dumps(metrics))
        items = self.module.build_metric_registry()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["id"], "m1")
        self.assertEqual(items[1]["id"], "m2")

    def test_build_workflow_registry(self):
        registry = {
            "workflows": [
                {"id": "w1", "name": "Workflow 1"},
                {"id": " "},
                "not a dict"
            ]
        }
        (self.temp_root / "05 AI Control Plane" / "workflow-registry.json").write_text(json.dumps(registry))
        workflows = self.module.build_workflow_registry()
        self.assertEqual(len(workflows), 1)
        self.assertEqual(workflows["w1"]["name"], "Workflow 1")

    def test_build_telemetry_contract(self):
        registry = {
            "telemetry": {
                "event_types": ["e1"],
                "statuses": ["s1"],
                "event_sets": {"set1": ["e1"]},
                "status_sets": {"sset1": ["s1"]}
            }
        }
        (self.temp_root / "05 AI Control Plane" / "workflow-registry.json").write_text(json.dumps(registry))
        contract = self.module.build_telemetry_contract()
        self.assertEqual(contract["event_types"], {"e1"})
        self.assertEqual(contract["statuses"], {"s1"})
        self.assertEqual(contract["event_sets"]["set1"], {"e1"})
        self.assertEqual(contract["status_sets"]["sset1"], {"s1"})

    def test_event_type_in(self):
        registry = {"telemetry": {"event_sets": {"completion": ["done"]}}}
        (self.temp_root / "05 AI Control Plane" / "workflow-registry.json").write_text(json.dumps(registry))
        self.assertTrue(self.module.event_type_in({"event_type": "done"}, "completion"))
        self.assertFalse(self.module.event_type_in({"event_type": "start"}, "completion"))

    def test_status_in(self):
        registry = {"telemetry": {"status_sets": {"ready": ["approved"]}}}
        (self.temp_root / "05 AI Control Plane" / "workflow-registry.json").write_text(json.dumps(registry))
        self.assertTrue(self.module.status_in({"status": "approved"}, "ready"))
        self.assertFalse(self.module.status_in({"status": "blocked"}, "ready"))

    def test_task_risk(self):
        active_tasks = {"t1": {"risk_tier": "high"}, "t2": {}}
        grouped_events = {"t2": [{"risk_tier": "medium"}]}
        self.assertEqual(self.module.task_risk("t1", grouped_events, active_tasks), "high")
        self.assertEqual(self.module.task_risk("t2", grouped_events, active_tasks), "medium")
        self.assertEqual(self.module.task_risk("t3", grouped_events, active_tasks), "")

    def test_is_completed_event(self):
        registry = {"telemetry": {"event_sets": {"completion": ["done"]}, "status_sets": {"completion": ["accepted"]}}}
        (self.temp_root / "05 AI Control Plane" / "workflow-registry.json").write_text(json.dumps(registry))
        self.assertTrue(self.module.is_completed_event({"event_type": "done"}))
        self.assertTrue(self.module.is_completed_event({"status": "accepted"}))
        self.assertFalse(self.module.is_completed_event({"event_type": "start"}))

    def test_is_ready_event(self):
        registry = {"telemetry": {"event_sets": {"ready": ["approved"]}, "status_sets": {"ready": ["ready"]}}}
        (self.temp_root / "05 AI Control Plane" / "workflow-registry.json").write_text(json.dumps(registry))
        self.assertTrue(self.module.is_ready_event({"event_type": "approved"}))
        self.assertTrue(self.module.is_ready_event({"status": "ready"}))
        self.assertFalse(self.module.is_ready_event({"event_type": "done"}))

    def test_is_eval_signal(self):
        registry = {"telemetry": {"event_sets": {"eval": ["eval_run"]}}}
        (self.temp_root / "05 AI Control Plane" / "workflow-registry.json").write_text(json.dumps(registry))
        self.assertTrue(self.module.is_eval_signal({"event_type": "eval_run"}))
        self.assertTrue(self.module.is_eval_signal({"metadata": {"acceptance_check": True}}))
        self.assertFalse(self.module.is_eval_signal({"event_type": "start"}))

    def test_is_repeated_internal_task(self):
        valid_task = {
            "task_cycle_required": True,
            "column": "done",
            "workflow": "intake-to-execution",
            "owner": "ai_operations_lead",
            "autonomy_tier": "A2",
            "risk_tier": "low"
        }
        self.assertTrue(self.module.is_repeated_internal_task(valid_task))
        self.assertFalse(self.module.is_repeated_internal_task({**valid_task, "column": "waiting"}))
        self.assertFalse(self.module.is_repeated_internal_task({**valid_task, "risk_tier": "high"}))

    def test_repeated_internal_task_ids(self):
        active_tasks = {
            "t1": {
                "task_cycle_required": True,
                "column": "done",
                "workflow": "intake-to-execution",
                "owner": "ai_operations_lead",
                "autonomy_tier": "A2",
                "risk_tier": "low"
            },
            "t2": {"column": "waiting"}
        }
        self.assertEqual(self.module.repeated_internal_task_ids(active_tasks), {"t1"})

    def test_build_review_payload(self):
        (self.temp_root / "05 AI Control Plane" / "agent-registry.json").write_text(json.dumps({
            "roles": [{"id": "alice", "role_type": "ai"}]
        }))
        (self.temp_root / "05 AI Control Plane" / "active-work.json").write_text(json.dumps({
            "tasks": [{"id": "t1", "owner": "alice", "column": "executing", "workflow": "w1", "risk_tier": "low"}]
        }))
        (self.temp_root / "05 AI Control Plane" / "metrics-registry.json").write_text(json.dumps({
            "primary_metrics": [
                {
                    "id": "telemetry_coverage_rate",
                    "unit": "ratio",
                    "threshold": {"comparison": ">=", "value": 0.5}
                }
            ]
        }))
        (self.temp_root / "05 AI Control Plane" / "workflow-registry.json").write_text(json.dumps({
            "workflows": [{"id": "w1", "required_telemetry_events": []}],
            "telemetry": {"event_sets": {"completion": ["done"]}}
        }))

        telemetry_dir = self.temp_root / ".hq" / "telemetry" / "2026-04"
        telemetry_dir.mkdir(parents=True, exist_ok=True)
        events = [
            {"task_id": "t1", "event_type": "start", "created_at": "2026-04-16T10:00:00Z"}
        ]
        (telemetry_dir / "2026-04-16.jsonl").write_text("\n".join(json.dumps(e) for e in events))

        payload = self.module.build_review_payload(date(2026, 4, 16), date(2026, 4, 16))
        self.assertEqual(payload["total_events"], 1)
        self.assertEqual(payload["active_tasks"], 1)
        self.assertEqual(payload["tasks_seen_in_telemetry"], 1)
        
        metrics = {m["id"]: m for m in payload["metrics"]}
        self.assertEqual(metrics["telemetry_coverage_rate"]["value"], 1.0)
        self.assertEqual(metrics["telemetry_coverage_rate"]["threshold_status"], "ok")

    def test_render_review_markdown(self):
        review = {
            "generated_at": "2026-04-16T12:00:00Z",
            "window": {"since": "2026-04-09", "until": "2026-04-16"},
            "total_events": 100,
            "tasks_seen_in_telemetry": 10,
            "active_tasks": 5,
            "breached_metrics": ["m1"],
            "event_type_counts": {"start": 50, "done": 50},
            "metrics": [
                {
                    "id": "m1",
                    "unit": "ratio",
                    "value": 0.1,
                    "threshold_status": "breached",
                    "threshold": {"comparison": ">=", "value": 0.5},
                    "action_if_breached": "Fix it"
                }
            ],
            "missing_telemetry_task_ids": ["t5"],
            "repeated_internal_work": {
                "required_task_cycle_task_ids": ["t1"],
                "task_cycle_missing_task_ids": ["t1"]
            }
        }
        markdown = self.module.render_review_markdown(review)
        self.assertIn("# Weekly Telemetry Metrics Review", markdown)
        self.assertIn("Total events: 100", markdown)
        self.assertIn("- m1: 10.0% | Status: breached | Threshold: >= 0.5", markdown)
        self.assertIn("Action: Fix it", markdown)
        self.assertIn("Missing telemetry on active tasks: t5", markdown)
        self.assertIn("Missing or failing task-cycle: t1", markdown)

    def test_build_task_cycle_report(self):
        active_work = {
            "tasks": [
                {
                    "id": "t1",
                    "title": "Task 1",
                    "workflow": "w1",
                    "owner": "alice",
                    "support": ["bob"],
                    "accepts_result": "charlie",
                    "column": "done",
                    "completed_at": "2026-04-16"
                }
            ]
        }
        (self.temp_root / "05 AI Control Plane" / "active-work.json").write_text(json.dumps(active_work))
        
        workflow_registry = {
            "workflows": [
                {"id": "w1", "required_telemetry_events": ["route", "start", "acceptance"]}
            ]
        }
        (self.temp_root / "05 AI Control Plane" / "workflow-registry.json").write_text(json.dumps(workflow_registry))
        
        # We need to mock load_task_events as it calls iter_event_files which we haven't mocked yet
        # But we can just write some files
        telemetry_dir = self.temp_root / ".hq" / "telemetry" / "2026-04"
        telemetry_dir.mkdir(parents=True, exist_ok=True)
        events = [
            {"task_id": "t1", "event_type": "route", "agent": "ai_operations_lead", "created_at": "2026-04-16T10:00:00Z"},
            {"task_id": "t1", "event_type": "policy_check", "agent": "governor", "created_at": "2026-04-16T10:02:00Z"},
            {"task_id": "t1", "event_type": "start", "agent": "alice", "created_at": "2026-04-16T10:05:00Z"},
            {"task_id": "t1", "event_type": "acceptance", "agent": "charlie", "created_at": "2026-04-16T10:10:00Z"},
            {"task_id": "t1", "event_type": "sync", "agent": "documentation", "created_at": "2026-04-16T10:15:00Z"}
        ]
        (telemetry_dir / "2026-04-16.jsonl").write_text("\n".join(json.dumps(e) for e in events))
        
        report = self.module.build_task_cycle_report("t1")
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["task_id"], "t1")
        self.assertTrue(report["queue_state_ok"])
        self.assertEqual(report["missing_required_events"], [])

        # Test failure - missing event
        workflow_registry["workflows"][0]["required_telemetry_events"].append("extra_event")
        (self.temp_root / "05 AI Control Plane" / "workflow-registry.json").write_text(json.dumps(workflow_registry))
        report = self.module.build_task_cycle_report("t1")
        self.assertEqual(report["status"], "failed")
        self.assertIn("extra_event", report["missing_required_events"])

if __name__ == "__main__":
    unittest.main()
