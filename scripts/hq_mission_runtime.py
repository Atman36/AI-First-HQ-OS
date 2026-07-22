#!/usr/bin/env python3
"""Additive mission runtime nucleus for durable local Mission/Run/Step state."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

DEFAULT_REPO_ROOT = Path(
    os.environ.get("HQ_MISSION_RUNTIME_REPO_ROOT", Path(__file__).resolve().parents[1])
).resolve()
os.environ.setdefault("HQ_TELEMETRY_REPO_ROOT", str(DEFAULT_REPO_ROOT))

from hq_io import append_jsonl, write_json
from hq_feedback_loop import build_iteration_payload as build_feedback_iteration_payload
import hq_policy_hooks
from hq_telemetry_store import append_event as append_telemetry_event
from hq_telemetry_store import ensure_runtime as ensure_telemetry_runtime
from hq_telemetry_store import event_file_for_timestamp as telemetry_event_file_for_timestamp


REPO_ROOT = DEFAULT_REPO_ROOT
PRIVATE_ROOT = Path(os.environ.get("HQ_RUNTIME_PRIVATE_ROOT", REPO_ROOT / ".hq")).resolve()
CONTROL_PLANE_DIR = REPO_ROOT / "05 AI Control Plane" / "schemas"
EXECUTION_CONFIG_PATH = REPO_ROOT / "05 AI Control Plane" / "execution-config.json"
RUNTIME_ROOT = PRIVATE_ROOT / "state" / "mission-runtime"
RUNTIME_DIRS = {
    "threads": PRIVATE_ROOT / "state" / "threads",
    "missions": RUNTIME_ROOT / "missions",
    "runs": RUNTIME_ROOT / "runs",
    "steps": RUNTIME_ROOT / "steps",
    "checkpoints": RUNTIME_ROOT / "checkpoints",
    "resume_status": RUNTIME_ROOT / "resume-status",
    "approvals": RUNTIME_ROOT / "approvals",
    "handoffs": RUNTIME_ROOT / "handoffs",
    "artifacts": RUNTIME_ROOT / "artifacts",
    "events": RUNTIME_ROOT / "events",
    "execution_envs": PRIVATE_ROOT / "runs",
}
ENTITY_SCHEMA_PATHS = {
    "thread": CONTROL_PLANE_DIR / "thread.schema.json",
    "mission": CONTROL_PLANE_DIR / "mission.schema.json",
    "run": CONTROL_PLANE_DIR / "run.schema.json",
    "step": CONTROL_PLANE_DIR / "step.schema.json",
    "checkpoint": CONTROL_PLANE_DIR / "checkpoint.schema.json",
    "resume-status": CONTROL_PLANE_DIR / "resume-status.schema.json",
    "approval": CONTROL_PLANE_DIR / "approval.schema.json",
    "handoff": CONTROL_PLANE_DIR / "handoff.schema.json",
    "artifact": CONTROL_PLANE_DIR / "artifact.schema.json",
}
TELEMETRY_SCHEMA_PATH = CONTROL_PLANE_DIR / "telemetry-event.schema.json"
RUNTIME_EVENT_SCHEMA_PATH = CONTROL_PLANE_DIR / "runtime-event.schema.json"
TRACE_STATE_SCHEMA_PATH = CONTROL_PLANE_DIR / "trace-state.schema.json"
APPROVAL_KEY_SCHEMA_PATH = CONTROL_PLANE_DIR / "approval-key.schema.json"
VERIFICATION_STATE_SCHEMA_PATH = CONTROL_PLANE_DIR / "verification-state.schema.json"
INTERRUPTION_STATE_SCHEMA_PATH = CONTROL_PLANE_DIR / "interruption-state.schema.json"
EXECUTION_CONTEXT_SCHEMA_PATH = CONTROL_PLANE_DIR / "execution-context.schema.json"
ALLOWED_STEP_STATUSES = {
    "planned",
    "running",
    "completed",
    "blocked",
    "waiting_approval",
    "failed",
    "skipped",
}
ALLOWED_ERROR_TYPES = {"", "transient", "recoverable", "user_fixable", "unexpected"}
ALLOWED_EVENT_PRIVACY_CLASSES = {"public", "internal", "sensitive"}
ALLOWED_RUN_BUDGET_KEYS = {"max_steps", "max_failed_steps"}
MAX_TRANSIENT_RETRIES = 2
ALLOWED_APPROVAL_DECISIONS = {"approved", "rejected", "blocked"}
ALLOWED_POLICY_ACTIONS = {"allow", "allow_with_review", "pause_for_founder_approval", "block"}
ALLOWED_VERIFICATION_STATUSES = {"pending", "changes_requested", "verified", "failed"}
ALLOWED_VERIFICATION_STAGE_TYPES = {"review", "approval"}
ALLOWED_VERIFICATION_DECISIONS = {"", "approved", "changes_requested"}
ALLOWED_INTERRUPTION_STATUSES = {"none", "interrupted"}
ALLOWED_THREAD_STATUSES = {"active", "idle", "paused", "interrupted", "archived"}
ALLOWED_HANDOFF_STATUSES = {
    "ready_for_handoff",
    "in_progress",
    "paused",
    "completed",
    "blocked",
    "cancelled",
}
ACTIVE_RUN_STATUSES = {"running", "waiting_approval", "blocked", "interrupted"}
TERMINAL_RUN_STATUSES = {"completed", "failed", "blocked", "cancelled"}
QUEUED_RUN_STATUS = "queued"
DEFAULT_CHILD_BLOCKED_TOOL_CLASSES = [
    "delegation",
    "user_interaction",
    "shared_memory_write",
    "external_side_effect",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify(value: str) -> str:
    chunks: list[str] = []
    current: list[str] = []
    for char in value.lower().strip():
        if char.isalnum():
            current.append(char)
            continue
        if current:
            chunks.append("".join(current))
            current = []
    if current:
        chunks.append("".join(current))
    return "-".join(chunks) or "item"


def make_id(prefix: str, label: str) -> str:
    return f"{prefix}-{slugify(label)}-{uuid.uuid4().hex[:8]}"


def parse_json_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise argparse.ArgumentTypeError("JSON payload must be an object")
    return payload


def parse_verification_stage(value: str) -> dict[str, str]:
    text = str(value or "").strip()
    if not text:
        raise argparse.ArgumentTypeError("verification stage must not be empty")
    if text.startswith("{"):
        payload = parse_json_object(text)
        stage_type = str(payload.get("type") or "").strip()
        participant = str(payload.get("participant") or "").strip()
        stage_id = str(payload.get("id") or "").strip()
    else:
        stage_type, separator, participant = text.partition(":")
        if not separator:
            raise argparse.ArgumentTypeError(
                "verification stage must use TYPE:PARTICIPANT, e.g. review:documentation"
            )
        stage_type = stage_type.strip()
        participant = participant.strip()
        stage_id = ""
    if not stage_type or not participant:
        raise argparse.ArgumentTypeError("verification stage requires both type and participant")
    return {"id": stage_id, "type": stage_type, "participant": participant}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_payload_against_schema(
    payload: dict[str, Any],
    schema_path: Path,
    *,
    label: str,
) -> None:
    if not schema_path.exists():
        raise ValueError(f"{label} schema not found: {schema_path}")
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path))
    if errors:
        error = errors[0]
        path = ".".join(str(item) for item in error.absolute_path)
        raise ValueError(f"{label} failed schema validation at {path or '<root>'}: {error.message}")


def validate_entity_payload(payload: dict[str, Any], entity_type: str) -> None:
    schema_path = ENTITY_SCHEMA_PATHS.get(entity_type)
    if schema_path is None:
        raise ValueError(f"unsupported entity_type: {entity_type}")
    validate_payload_against_schema(payload, schema_path, label=entity_type)


def validate_telemetry_payload(payload: dict[str, Any]) -> None:
    validate_payload_against_schema(payload, TELEMETRY_SCHEMA_PATH, label="telemetry_event")


def normalize_string_list(values: list[str] | None) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        items.append(text)
    return items


def normalize_verification_stages(payload: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for index, raw_stage in enumerate(payload or [], start=1):
        if not isinstance(raw_stage, dict):
            raise ValueError("verification stages must be objects")
        stage_type = str(raw_stage.get("type") or "").strip()
        participant = str(raw_stage.get("participant") or "").strip()
        stage_id = str(raw_stage.get("id") or f"{stage_type}-{index}").strip()
        if stage_type not in ALLOWED_VERIFICATION_STAGE_TYPES:
            raise ValueError(
                "verification stage type must be one of: "
                + ", ".join(sorted(ALLOWED_VERIFICATION_STAGE_TYPES))
            )
        if not participant:
            raise ValueError("verification stage participant is required")
        if not stage_id:
            raise ValueError("verification stage id is required")
        if stage_id in seen_ids:
            raise ValueError(f"duplicate verification stage id: {stage_id}")
        seen_ids.add(stage_id)
        normalized.append(
            {
                "id": stage_id,
                "type": stage_type,
                "participant": participant,
            }
        )
    return normalized


def verification_stage_by_id(
    stages: list[dict[str, str]],
    stage_id: str,
) -> dict[str, str] | None:
    return next((stage for stage in stages if stage["id"] == stage_id), None)


def next_verification_stage(
    stages: list[dict[str, str]],
    completed_stage_ids: list[str],
) -> dict[str, str] | None:
    completed = set(completed_stage_ids)
    return next((stage for stage in stages if stage["id"] not in completed), None)


def normalize_verification_state(
    payload: dict[str, Any] | None,
    *,
    stages: list[dict[str, Any]] | None = None,
    default_return_target: str = "",
) -> dict[str, Any]:
    raw = payload or {}
    normalized_stages = normalize_verification_stages(stages)
    metadata = raw.get("metadata", {})
    completed_stage_ids = normalize_string_list(
        raw.get("completed_stage_ids") if isinstance(raw.get("completed_stage_ids"), list) else []
    )
    normalized = {
        "status": str(raw.get("status") or "pending").strip(),
        "step_id": str(raw.get("step_id") or "").strip(),
        "summary": str(raw.get("summary") or "").strip(),
        "evidence": normalize_string_list(
            raw.get("evidence") if isinstance(raw.get("evidence"), list) else []
        ),
        "verified_at": str(raw.get("verified_at") or "").strip(),
        "verified_by": str(raw.get("verified_by") or "").strip(),
        "current_stage_id": str(raw.get("current_stage_id") or "").strip(),
        "current_stage_type": str(raw.get("current_stage_type") or "").strip(),
        "current_participant": str(raw.get("current_participant") or "").strip(),
        "return_target": str(raw.get("return_target") or default_return_target).strip(),
        "completed_stage_ids": completed_stage_ids,
        "last_decision": str(raw.get("last_decision") or "").strip(),
        "last_decision_note": str(raw.get("last_decision_note") or "").strip(),
        "metadata": metadata if isinstance(metadata, dict) else {},
    }
    if normalized["status"] not in ALLOWED_VERIFICATION_STATUSES:
        raise ValueError(
            "verification status must be one of: "
            + ", ".join(sorted(ALLOWED_VERIFICATION_STATUSES))
        )
    if normalized["last_decision"] not in ALLOWED_VERIFICATION_DECISIONS:
        raise ValueError(
            "verification decision must be one of: "
            + ", ".join(sorted(ALLOWED_VERIFICATION_DECISIONS))
        )
    if normalized_stages:
        valid_stage_ids = {stage["id"] for stage in normalized_stages}
        invalid_completed_stage_ids = [
            stage_id
            for stage_id in normalized["completed_stage_ids"]
            if stage_id not in valid_stage_ids
        ]
        if invalid_completed_stage_ids:
            raise ValueError(
                "verification completed_stage_ids reference unknown stages: "
                + ", ".join(invalid_completed_stage_ids)
            )

        current_stage = verification_stage_by_id(
            normalized_stages,
            normalized["current_stage_id"],
        )
        if normalized["current_stage_id"] and current_stage is None:
            raise ValueError(
                f"verification current_stage_id references unknown stage: {normalized['current_stage_id']}"
            )
        if current_stage is None and normalized["status"] in {"pending", "changes_requested"}:
            current_stage = next_verification_stage(
                normalized_stages,
                normalized["completed_stage_ids"],
            )
            if current_stage is not None:
                normalized["current_stage_id"] = current_stage["id"]
        if current_stage is not None:
            normalized["current_stage_type"] = current_stage["type"]
            if normalized["status"] == "changes_requested":
                normalized["current_participant"] = (
                    normalized["current_participant"] or normalized["return_target"]
                )
            else:
                normalized["current_participant"] = (
                    normalized["current_participant"] or current_stage["participant"]
                )
        else:
            normalized["current_stage_id"] = ""
            normalized["current_stage_type"] = ""
            if normalized["status"] != "changes_requested":
                normalized["current_participant"] = ""
    else:
        normalized["current_stage_id"] = ""
        normalized["current_stage_type"] = ""
        normalized["current_participant"] = ""
        normalized["completed_stage_ids"] = []
        normalized["last_decision"] = ""
        normalized["last_decision_note"] = ""
    validate_payload_against_schema(
        normalized,
        VERIFICATION_STATE_SCHEMA_PATH,
        label="verification_state",
    )
    return normalized


def normalize_interruption_state(payload: dict[str, Any] | None) -> dict[str, Any]:
    raw = payload or {}
    metadata = raw.get("metadata", {})
    normalized = {
        "status": str(raw.get("status") or "none").strip(),
        "reason": str(raw.get("reason") or "").strip(),
        "requested_by": str(raw.get("requested_by") or "").strip(),
        "interrupted_at": str(raw.get("interrupted_at") or "").strip(),
        "resume_from_step_id": str(raw.get("resume_from_step_id") or "").strip(),
        "checkpoint_id": str(raw.get("checkpoint_id") or "").strip(),
        "checkpoint_path": str(raw.get("checkpoint_path") or "").strip(),
        "metadata": metadata if isinstance(metadata, dict) else {},
    }
    if normalized["status"] not in ALLOWED_INTERRUPTION_STATUSES:
        raise ValueError(
            "interruption status must be one of: "
            + ", ".join(sorted(ALLOWED_INTERRUPTION_STATUSES))
        )
    validate_payload_against_schema(
        normalized,
        INTERRUPTION_STATE_SCHEMA_PATH,
        label="interruption_state",
    )
    return normalized


def path_reference(path: Path | str) -> str:
    candidate = Path(path).resolve()
    try:
        return candidate.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return candidate.as_posix()


def execution_env_root(run_id: str) -> Path:
    return RUNTIME_DIRS["execution_envs"] / run_id


def normalize_execution_context(payload: dict[str, Any] | None) -> dict[str, Any]:
    raw = payload or {}
    metadata = raw.get("metadata", {})
    blocked_tool_classes = raw.get("blocked_tool_classes", [])
    normalized = {
        "scope": str(raw.get("scope") or "none").strip(),
        "session_id": str(raw.get("session_id") or "").strip(),
        "work_dir": str(raw.get("work_dir") or "").strip(),
        "runtime_home": str(raw.get("runtime_home") or "").strip(),
        "runtime_home_mode": str(raw.get("runtime_home_mode") or "none").strip(),
        "parent_session_id": str(raw.get("parent_session_id") or "").strip(),
        "blocked_tool_classes": normalize_string_list(
            blocked_tool_classes if isinstance(blocked_tool_classes, list) else []
        ),
        "metadata": metadata if isinstance(metadata, dict) else {},
    }
    validate_payload_against_schema(
        normalized,
        EXECUTION_CONTEXT_SCHEMA_PATH,
        label="execution_context",
    )
    return normalized


def prepare_execution_context(
    *,
    run_id: str,
    session_id: str = "",
    work_dir: str = "",
    runtime_home: str = "",
    runtime_home_mode: str = "scoped",
    parent_session_id: str = "",
    blocked_tool_classes: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    env_root = execution_env_root(run_id)
    env_root.mkdir(parents=True, exist_ok=True)

    resolved_work_dir = Path(work_dir).resolve() if work_dir else (env_root / "workdir").resolve()
    resolved_work_dir.mkdir(parents=True, exist_ok=True)

    normalized_runtime_home_mode = str(runtime_home_mode or "none").strip() or "none"
    if normalized_runtime_home_mode not in {"none", "scoped"}:
        raise ValueError("runtime_home_mode must be one of: none, scoped")

    runtime_home_value = ""
    if normalized_runtime_home_mode == "scoped":
        resolved_runtime_home = (
            Path(runtime_home).resolve() if runtime_home else (env_root / "codex-home").resolve()
        )
        resolved_runtime_home.mkdir(parents=True, exist_ok=True)
        runtime_home_value = path_reference(resolved_runtime_home)

    blocked = normalize_string_list(blocked_tool_classes)
    scope = "child_isolated" if parent_session_id else "isolated"
    if parent_session_id and not blocked:
        blocked = list(DEFAULT_CHILD_BLOCKED_TOOL_CLASSES)

    return normalize_execution_context(
        {
            "scope": scope,
            "session_id": session_id or run_id,
            "work_dir": path_reference(resolved_work_dir),
            "runtime_home": runtime_home_value,
            "runtime_home_mode": normalized_runtime_home_mode,
            "parent_session_id": parent_session_id,
            "blocked_tool_classes": blocked,
            "metadata": metadata or {},
        }
    )


def build_resume_fingerprint(payload: dict[str, Any]) -> str:
    fingerprint_payload = {
        "trace_entity": str(payload.get("trace_entity") or "").strip(),
        "trace_id": str(payload.get("trace_id") or "").strip(),
        "grouping_entity": str(payload.get("grouping_entity") or "").strip(),
        "grouping_id": str(payload.get("grouping_id") or "").strip(),
        "current_step_id": str(payload.get("current_step_id") or "").strip(),
        "resume_from_step_id": str(payload.get("resume_from_step_id") or "").strip(),
        "checkpoint_id": str(payload.get("checkpoint_id") or "").strip(),
        "checkpoint_path": str(payload.get("checkpoint_path") or "").strip(),
        "handoff_id": str(payload.get("handoff_id") or "").strip(),
        "handoff_path": str(payload.get("handoff_path") or "").strip(),
        "resume_packet_path": str(payload.get("resume_packet_path") or "").strip(),
        "session_id": str(payload.get("session_id") or "").strip(),
        "work_dir": str(payload.get("work_dir") or "").strip(),
    }
    return hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]


def normalize_trace_state(
    payload: dict[str, Any] | None,
    *,
    grouping_id: str,
    default_trace_id: str = "",
    snapshot_at: str | None = None,
) -> dict[str, Any]:
    raw = payload or {}
    metadata = raw.get("metadata", {})
    normalized = {
        "trace_entity": str(raw.get("trace_entity") or "run").strip(),
        "trace_id": str(raw.get("trace_id") or default_trace_id).strip(),
        "grouping_entity": str(raw.get("grouping_entity") or "thread").strip(),
        "grouping_id": str(raw.get("grouping_id") or grouping_id).strip(),
        "current_step_id": str(raw.get("current_step_id") or "").strip(),
        "resume_from_step_id": str(raw.get("resume_from_step_id") or "").strip(),
        "checkpoint_id": str(raw.get("checkpoint_id") or "").strip(),
        "checkpoint_path": str(raw.get("checkpoint_path") or "").strip(),
        "handoff_id": str(raw.get("handoff_id") or "").strip(),
        "handoff_path": str(raw.get("handoff_path") or "").strip(),
        "resume_packet_path": str(
            raw.get("resume_packet_path") or raw.get("handoff_path") or ""
        ).strip(),
        "snapshot_at": str(raw.get("snapshot_at") or snapshot_at or utc_now()).strip(),
        "resume_fingerprint": "",
        "metadata": metadata if isinstance(metadata, dict) else {},
    }
    normalized["resume_fingerprint"] = build_resume_fingerprint(normalized)
    validate_payload_against_schema(normalized, TRACE_STATE_SCHEMA_PATH, label="trace_state")
    return normalized


def normalize_approval_key(payload: dict[str, Any] | None) -> dict[str, Any]:
    raw = payload or {}
    metadata = raw.get("metadata", {})
    normalized = {
        "kind": str(raw.get("kind") or "runtime_action").strip(),
        "namespace": str(raw.get("namespace") or "hq.runtime").strip(),
        "name": str(raw.get("name") or "runtime").strip(),
        "call_id": str(raw.get("call_id") or "").strip(),
        "action": normalize_string_list(raw.get("action") if isinstance(raw.get("action"), list) else []),
        "metadata": metadata if isinstance(metadata, dict) else {},
    }
    if not normalized["action"]:
        normalized["action"] = ["allow"]
    validate_payload_against_schema(normalized, APPROVAL_KEY_SCHEMA_PATH, label="approval_key")
    return normalized


def runtime_policy_path() -> Path:
    configured = str(os.environ.get("HQ_RUNTIME_POLICY_FILE") or "").strip()
    if configured:
        path = Path(configured)
        return path if path.is_absolute() else (REPO_ROOT / path).resolve()
    return PRIVATE_ROOT / "runtime" / "policy.json"


def load_runtime_policy() -> tuple[dict[str, Any] | None, str]:
    path = runtime_policy_path()
    if not path.exists():
        return None, ""
    return hq_policy_hooks.load_policy(path), path_reference(path)


def build_step_policy_summary(decision: str, tool_classes: list[str], blocked_tool_classes: list[str]) -> str:
    tool_label = ", ".join(tool_classes) if tool_classes else "no explicit tool classes"
    if decision == "allow_with_review":
        return f"Tool policy requires review for: {tool_label}."
    if decision == "pause_for_founder_approval":
        return f"Tool policy paused execution pending approval for: {tool_label}."
    if decision == "block":
        if blocked_tool_classes:
            blocked_label = ", ".join(blocked_tool_classes)
            return f"Tool policy blocked execution for: {blocked_label}."
        return f"Tool policy blocked execution for: {tool_label}."
    return f"Tool policy allowed: {tool_label}."


def evaluate_step_tool_policy(
    *,
    step_id: str,
    step_key: str,
    run: dict[str, Any],
    allowed_tool_classes: list[str] | None,
) -> dict[str, Any]:
    requested_tool_classes = normalize_string_list(allowed_tool_classes)
    execution_context = run.get("execution_context", {})
    blocked_tool_classes = normalize_string_list(
        execution_context.get("blocked_tool_classes")
        if isinstance(execution_context, dict) and isinstance(execution_context.get("blocked_tool_classes"), list)
        else []
    )
    directly_blocked = [item for item in requested_tool_classes if item in blocked_tool_classes]
    matched_rules: list[dict[str, Any]] = []
    effective_decision = "allow"
    decision_sources: list[str] = []

    for tool_class in directly_blocked:
        matched_rules.append(
            {
                "id": "execution-context-blocked-tool-class",
                "decision": "block",
                "justification": "Run execution_context blocks this tool class.",
                "actionPrefix": ["hq", "step", "tool", tool_class],
                "namespace": "hq.step.tool_policy",
                "toolName": tool_class,
                "callId": step_id,
            }
        )
    if directly_blocked:
        effective_decision = "block"
        decision_sources.append("execution_context")

    policy, policy_file = load_runtime_policy()
    if policy is not None:
        for tool_class in requested_tool_classes:
            result = hq_policy_hooks.evaluate_policy(
                policy,
                {
                    "action": ["hq", "step", "tool", tool_class],
                    "path": "",
                    "namespace": "hq.step.tool_policy",
                    "tool_name": tool_class,
                    "call_id": step_id,
                    "risk_tier": "",
                    "autonomy_tier": "",
                },
            )
            if result["matchedRules"]:
                decision_sources.append("runtime_policy")
                matched_rules.extend(result["matchedRules"])
            if (
                hq_policy_hooks.DECISION_ORDER[result["decision"]]
                > hq_policy_hooks.DECISION_ORDER[effective_decision]
            ):
                effective_decision = str(result["decision"]).strip()

    if not decision_sources:
        decision_sources.append("default")
    summary = build_step_policy_summary(
        effective_decision,
        requested_tool_classes,
        directly_blocked,
    )
    return {
        "allowed_tool_classes": requested_tool_classes,
        "policy_action": effective_decision,
        "policy_context": {
            "step_key": step_key,
            "requested_tool_classes": requested_tool_classes,
            "blocked_tool_classes": directly_blocked,
            "matched_rules": matched_rules,
            "decision_sources": normalize_string_list(decision_sources),
            "policy_file": policy_file,
            "summary": summary,
            "review_required": effective_decision == "allow_with_review",
            "tripwire_triggered": effective_decision in {"pause_for_founder_approval", "block"},
            "approval_id": "",
        },
    }


def ensure_runtime() -> None:
    for path in RUNTIME_DIRS.values():
        path.mkdir(parents=True, exist_ok=True)
    ensure_telemetry_runtime()


def runtime_hooks_path() -> Path:
    configured = str(os.environ.get("HQ_RUNTIME_HOOKS_FILE") or "").strip()
    if configured:
        path = Path(configured)
        return path if path.is_absolute() else (REPO_ROOT / path).resolve()
    return PRIVATE_ROOT / "runtime" / "hooks.json"


def mission_path(mission_id: str) -> Path:
    return RUNTIME_DIRS["missions"] / f"{mission_id}.json"


def thread_path(thread_id: str) -> Path:
    return RUNTIME_DIRS["threads"] / f"{thread_id}.json"


def run_path(run_id: str) -> Path:
    return RUNTIME_DIRS["runs"] / f"{run_id}.json"


def step_path(step_id: str) -> Path:
    return RUNTIME_DIRS["steps"] / f"{step_id}.json"


def checkpoint_path(checkpoint_id: str) -> Path:
    return RUNTIME_DIRS["checkpoints"] / f"{checkpoint_id}.json"


def resume_status_path(run_id: str) -> Path:
    return RUNTIME_DIRS["resume_status"] / f"{run_id}.json"


def approval_path(approval_id: str) -> Path:
    return RUNTIME_DIRS["approvals"] / f"{approval_id}.json"


def handoff_path(handoff_id: str) -> Path:
    return RUNTIME_DIRS["handoffs"] / f"{handoff_id}.json"


def artifact_path(artifact_id: str) -> Path:
    return RUNTIME_DIRS["artifacts"] / f"{artifact_id}.json"


def event_file_for_timestamp(timestamp: str) -> Path:
    day = timestamp[:10]
    month = day[:7]
    return RUNTIME_DIRS["events"] / month / f"{day}.jsonl"


# Map terminal run statuses onto the feedback-loop status taxonomy so finished
# runs become explicit loop outcomes rather than a flat "didn't work".
RUN_STATUS_TO_FEEDBACK = {
    "completed": "done",
    "failed": "technical_error",
    "blocked": "blocked_by_policy",
    "cancelled": "rolled_back",
}
FEEDBACK_FINISH_NEXT_FOCUS = {
    "done": "Review the outcome and choose the next task.",
    "technical_error": "Investigate the failure, then retry or escalate.",
    "blocked_by_policy": "Resolve the policy block or obtain the required approval.",
    "rolled_back": "Re-plan the approach after the rollback.",
}
FEEDBACK_MAX_BYTES = 5 * 1024 * 1024
FEEDBACK_MAX_RECORDS = 5000


def feedback_loop_path_for(timestamp: str) -> Path:
    return PRIVATE_ROOT / "telemetry" / "feedback-loop" / f"{timestamp[:7]}.jsonl"


def _write_feedback_receipt(payload: dict[str, Any]) -> None:
    append_jsonl(
        feedback_loop_path_for(str(payload.get("created_at") or utc_now())),
        payload,
        max_bytes=FEEDBACK_MAX_BYTES,
        max_records=FEEDBACK_MAX_RECORDS,
    )


def _feedback_hypothesis(mission: dict[str, Any]) -> str:
    return f"Advancing the task via mission: {mission.get('title') or mission.get('id') or 'mission'}"


def record_run_feedback_start(
    *, mission: dict[str, Any], run_id: str, actor: str, created_at: str
) -> str:
    """Best-effort `before` receipt; only governed (task-linked) runs are recorded.

    Returns the receipt id so the matching finish receipt can link to it, or ""
    when nothing was recorded. Never raises — telemetry must not break a run.
    """
    task_id = str(mission.get("source_task_id") or "").strip()
    if not task_id:
        return ""
    try:
        payload = build_feedback_iteration_payload(
            task_id=task_id,
            hypothesis=_feedback_hypothesis(mission),
            action=f"Started run {run_id}",
            metric="run_outcome",
            status="running",
            evidence=[f"run_id={run_id}"],
            touched_files=[],
            next_focus="Complete the run and record verification.",
            rollback_reason="",
            actor=actor or mission.get("owner") or "runtime",
            created_at=created_at,
        )
        _write_feedback_receipt(payload)
        return str(payload["id"])
    except Exception:
        return ""


def record_run_feedback_finish(
    *, mission: dict[str, Any], run: dict[str, Any], status: str, parent_id: str
) -> str:
    """Best-effort `after` receipt closing the attempt opened at run start."""
    task_id = str(mission.get("source_task_id") or "").strip()
    if not task_id:
        return ""
    feedback_status = RUN_STATUS_TO_FEEDBACK.get(status, "technical_error")
    verification = str((run.get("verification_state") or {}).get("status") or "-")
    try:
        payload = build_feedback_iteration_payload(
            task_id=task_id,
            hypothesis=_feedback_hypothesis(mission),
            action=f"Finished run {run['id']} with status '{status}'",
            metric="run_outcome",
            status=feedback_status,
            evidence=[f"run_status={status}", f"verification={verification}"],
            touched_files=[],
            next_focus=FEEDBACK_FINISH_NEXT_FOCUS.get(feedback_status, "Choose the next task."),
            rollback_reason="Run cancelled." if feedback_status == "rolled_back" else "",
            actor=run.get("actor") or mission.get("owner") or "runtime",
            parent_id=parent_id,
        )
        _write_feedback_receipt(payload)
        return str(payload["id"])
    except Exception:
        return ""


def record_event(
    *,
    event_type: str,
    entity_id: str,
    summary: str,
    payload: dict[str, Any] | None = None,
    actor: str = "",
    correlation_id: str = "",
    causation_id: str = "",
    privacy_class: str = "internal",
) -> dict[str, Any]:
    if privacy_class not in ALLOWED_EVENT_PRIVACY_CLASSES:
        raise ValueError(
            "event privacy_class must be one of: "
            + ", ".join(sorted(ALLOWED_EVENT_PRIVACY_CLASSES))
        )
    created_at = utc_now()
    event = {
        "schema_version": 1,
        "id": str(uuid.uuid4()),
        "created_at": created_at,
        "event_type": event_type,
        "entity_id": entity_id,
        "actor": str(actor or "").strip() or "runtime",
        "correlation_id": str(correlation_id or "").strip(),
        "causation_id": str(causation_id or "").strip(),
        "privacy_class": privacy_class,
        "summary": summary,
        "payload": payload or {},
    }
    validate_payload_against_schema(event, RUNTIME_EVENT_SCHEMA_PATH, label="runtime_event")
    append_jsonl(event_file_for_timestamp(created_at), event)
    return event


def emit_runtime_telemetry(
    *,
    event_type: str,
    status: str,
    summary: str,
    actor: str,
    mission_id: str = "",
    thread_id: str = "",
    source_task_id: str = "",
    workflow: str = "",
    run_id: str = "",
    step_id: str = "",
    approval_id: str = "",
    handoff_id: str = "",
    artifact_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    created_at = utc_now()
    payload: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "created_at": created_at,
        "event_type": event_type,
        "agent": actor or "runtime",
        "role": actor or "",
        "task_id": source_task_id or mission_id or thread_id or event_type,
        "thread_id": thread_id,
        "mission_id": mission_id,
        "run_id": run_id,
        "step_id": step_id,
        "approval_id": approval_id,
        "handoff_id": handoff_id,
        "artifact_id": artifact_id,
        "status": status,
        "summary": summary,
        "workflow": workflow,
        "metadata": metadata or {},
    }
    payload = {key: value for key, value in payload.items() if value != "" or key == "metadata"}
    validate_telemetry_payload(payload)
    append_telemetry_event(telemetry_event_file_for_timestamp(created_at), payload)


def emit_runtime_hook_event(
    *,
    event: str,
    action: list[str],
    status: str,
    summary: str,
    actor: str,
    decision: str = "",
    thread_id: str = "",
    mission_id: str = "",
    run_id: str = "",
    step_id: str = "",
    approval_id: str = "",
    handoff_id: str = "",
    namespace: str = "hq.mission_runtime",
    tool_name: str = "",
    call_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    hooks_path = runtime_hooks_path()
    if not hooks_path.exists():
        return []
    hooks = hq_policy_hooks.load_hooks(hooks_path)
    payload: dict[str, Any] = {
        "action": normalize_string_list(action),
        "status": status,
        "summary": summary,
        "actor": actor or "runtime",
        "decision": decision,
        "thread_id": thread_id,
        "mission_id": mission_id,
        "run_id": run_id,
        "step_id": step_id,
        "approval_id": approval_id,
        "handoff_id": handoff_id,
        "namespace": namespace,
        "tool_name": tool_name,
        "call_id": call_id,
        "metadata": metadata or {},
        "event": event,
    }
    payload = {
        key: value
        for key, value in payload.items()
        if key in {"action", "metadata", "event"} or value not in ("", [])
    }
    executed: list[dict[str, Any]] = []
    for hook in hooks.get("hooks", []):
        if not isinstance(hook, dict) or not hq_policy_hooks.hook_matches(hook, event, payload):
            continue
        result = hq_policy_hooks.run_hook([str(item) for item in hook.get("command", [])], payload)
        executed.append(
            {
                "id": str(hook.get("id") or "").strip(),
                "event": event,
                "result": result,
            }
        )
        if result["returncode"] != 0 and bool(hook.get("stop_on_error")):
            raise RuntimeError(
                f"runtime hook `{hook.get('id', '<unknown>')}` failed for event `{event}`"
            )
    return executed


def write_entity(path: Path, payload: dict[str, Any]) -> None:
    trace_state = payload.get("trace_state")
    if trace_state is not None:
        validate_payload_against_schema(trace_state, TRACE_STATE_SCHEMA_PATH, label="trace_state")
    verification_state = payload.get("verification_state")
    if verification_state is not None:
        validate_payload_against_schema(
            verification_state,
            VERIFICATION_STATE_SCHEMA_PATH,
            label="verification_state",
        )
    interruption_state = payload.get("interruption_state")
    if interruption_state is not None:
        validate_payload_against_schema(
            interruption_state,
            INTERRUPTION_STATE_SCHEMA_PATH,
            label="interruption_state",
        )
    execution_context = payload.get("execution_context")
    if execution_context is not None:
        validate_payload_against_schema(
            execution_context,
            EXECUTION_CONTEXT_SCHEMA_PATH,
            label="execution_context",
        )
    if str(payload.get("entity_type") or "").strip() == "approval":
        validate_payload_against_schema(
            payload.get("approval_key", {}),
            APPROVAL_KEY_SCHEMA_PATH,
            label="approval_key",
        )
    validate_entity_payload(payload, str(payload.get("entity_type") or "").strip())
    write_json(path, payload)


def upgrade_entity_payload(payload: dict[str, Any], entity_type: str) -> dict[str, Any]:
    upgraded = dict(payload)
    snapshot_at = str(upgraded.get("updated_at") or upgraded.get("created_at") or utc_now()).strip()
    if entity_type == "thread":
        upgraded.setdefault("latest_handoff_id", "")
        upgraded.setdefault("latest_checkpoint_id", "")
        upgraded.setdefault("latest_checkpoint_path", "")
        upgraded.setdefault("latest_resume_status_path", "")
        upgraded["interruption_state"] = normalize_interruption_state(
            upgraded.get("interruption_state", {})
        )
        upgraded["execution_context"] = normalize_execution_context(
            upgraded.get("execution_context", {})
        )
        upgraded["trace_state"] = normalize_trace_state(
            upgraded.get("trace_state", {}),
            grouping_id=str(upgraded.get("id") or "").strip(),
            default_trace_id=str(upgraded.get("active_run_id") or "").strip(),
            snapshot_at=snapshot_at,
        )
    elif entity_type == "run":
        upgraded["budgets"] = normalize_run_budgets(upgraded.get("budgets"))
        upgraded.setdefault("handoff_ids", [])
        upgraded.setdefault("latest_checkpoint_id", "")
        upgraded.setdefault("latest_checkpoint_path", "")
        upgraded.setdefault("resume_status_path", "")
        upgraded["verification_stages"] = normalize_verification_stages(
            upgraded.get("verification_stages", [])
        )
        upgraded["interruption_state"] = normalize_interruption_state(
            upgraded.get("interruption_state", {})
        )
        upgraded["execution_context"] = normalize_execution_context(
            upgraded.get("execution_context", {})
        )
        upgraded["verification_state"] = normalize_verification_state(
            upgraded.get("verification_state", {}),
            stages=upgraded["verification_stages"],
            default_return_target=str(upgraded.get("actor") or "").strip(),
        )
        upgraded["trace_state"] = normalize_trace_state(
            upgraded.get("trace_state", {}),
            grouping_id=str(upgraded.get("thread_id") or "").strip(),
            default_trace_id=str(upgraded.get("id") or "").strip(),
            snapshot_at=snapshot_at,
        )
    elif entity_type == "step":
        upgraded["allowed_tool_classes"] = normalize_string_list(
            upgraded.get("allowed_tool_classes")
            if isinstance(upgraded.get("allowed_tool_classes"), list)
            else []
        )
        upgraded["policy_action"] = str(upgraded.get("policy_action") or "allow").strip() or "allow"
        if upgraded["policy_action"] not in ALLOWED_POLICY_ACTIONS:
            raise ValueError(
                "step policy_action must be one of: " + ", ".join(sorted(ALLOWED_POLICY_ACTIONS))
            )
        upgraded["policy_context"] = (
            upgraded.get("policy_context", {})
            if isinstance(upgraded.get("policy_context"), dict)
            else {}
        )
    elif entity_type == "approval":
        upgraded["approval_key"] = normalize_approval_key(
            upgraded.get("approval_key", {})
            or {
                "kind": "runtime_action",
                "namespace": "hq.runtime",
                "name": str(upgraded.get("policy_action") or "approval").strip(),
                "call_id": "",
                "action": [str(upgraded.get("policy_action") or "allow").strip()],
            }
        )
        upgraded["tool_scope"] = normalize_string_list(
            upgraded.get("tool_scope") if isinstance(upgraded.get("tool_scope"), list) else []
        )
        upgraded["policy_context"] = (
            upgraded.get("policy_context", {})
            if isinstance(upgraded.get("policy_context"), dict)
            else {}
        )
    elif entity_type == "checkpoint":
        upgraded["execution_context"] = normalize_execution_context(
            upgraded.get("execution_context", {})
        )
        upgraded["trace_state"] = normalize_trace_state(
            upgraded.get("trace_state", {}),
            grouping_id=str(upgraded.get("thread_id") or "").strip(),
            default_trace_id=str(upgraded.get("run_id") or "").strip(),
            snapshot_at=str(upgraded.get("created_at") or snapshot_at).strip(),
        )
        upgraded["referenced_file_digests"] = (
            upgraded.get("referenced_file_digests", {})
            if isinstance(upgraded.get("referenced_file_digests"), dict)
            else {}
        )
        upgraded["replay_basis"] = (
            upgraded.get("replay_basis", {})
            if isinstance(upgraded.get("replay_basis"), dict)
            else {}
        )
    elif entity_type == "resume-status":
        upgraded["resume_plan"] = (
            upgraded.get("resume_plan", {})
            if isinstance(upgraded.get("resume_plan"), dict)
            else {}
        )
        upgraded["stale_inputs"] = normalize_string_list(
            upgraded.get("stale_inputs") if isinstance(upgraded.get("stale_inputs"), list) else []
        )
    return upgraded


def require_file(path: Path, label: str, expected_entity_type: str | None = None) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"{label} not found: {path.stem}")
    payload = load_json(path)
    entity_type = expected_entity_type or str(payload.get("entity_type") or label).strip()
    payload = upgrade_entity_payload(payload, entity_type)
    validate_entity_payload(payload, entity_type)
    if expected_entity_type and payload.get("entity_type") != expected_entity_type:
        raise ValueError(f"{label} has unexpected entity_type: {payload.get('entity_type')}")
    return payload


def load_entity_safe(path: Path, entity_type: str) -> tuple[dict[str, Any] | None, str]:
    try:
        payload = load_json(path)
        payload = upgrade_entity_payload(payload, entity_type)
        validate_entity_payload(payload, entity_type)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, str(exc)
    return payload, ""


def create_thread_record(
    *,
    title: str,
    owner: str = "",
    status: str = "active",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if status not in ALLOWED_THREAD_STATUSES:
        raise ValueError("thread status must be one of: " + ", ".join(sorted(ALLOWED_THREAD_STATUSES)))
    created_at = utc_now()
    payload = {
        "schema_version": 1,
        "entity_type": "thread",
        "id": make_id("thread", title),
        "title": title.strip(),
        "owner": owner.strip(),
        "status": status,
        "mission_ids": [],
        "active_mission_id": "",
        "active_run_id": "",
        "latest_handoff_id": "",
        "latest_checkpoint_id": "",
        "latest_checkpoint_path": "",
        "latest_resume_status_path": "",
        "latest_spec_path": "",
        "latest_handoff_path": "",
        "resume_packet_path": "",
        "interruption_state": normalize_interruption_state({}),
        "execution_context": normalize_execution_context({}),
        "trace_state": {},
        "created_at": created_at,
        "updated_at": created_at,
        "metadata": metadata or {},
    }
    payload["trace_state"] = normalize_trace_state({}, grouping_id=payload["id"], snapshot_at=created_at)
    write_entity(thread_path(payload["id"]), payload)
    record_event(
        event_type="thread_created",
        entity_id=payload["id"],
        summary=f"Created execution thread '{payload['title']}'.",
        payload={"owner": payload["owner"]},
        actor=payload["owner"] or "runtime",
        correlation_id=payload["id"],
    )
    emit_runtime_telemetry(
        event_type="thread_created",
        status=payload["status"],
        summary=f"Created execution thread '{payload['title']}'.",
        actor=payload["owner"] or "runtime",
        thread_id=payload["id"],
        metadata={"entity_type": "thread"},
    )
    return payload


def update_thread_context(
    thread_id: str,
    *,
    mission_id: str | None = None,
    run_id: str | None = None,
    handoff_id: str | None = None,
    checkpoint_id: str | None = None,
    spec_path: str | None = None,
    handoff_path: str | None = None,
    checkpoint_path: str | None = None,
    resume_packet_path: str | None = None,
    resume_status_path: str | None = None,
    status: str | None = None,
    execution_context: dict[str, Any] | None = None,
    interruption_state: dict[str, Any] | None = None,
    trace_state: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    thread = require_file(thread_path(thread_id), "thread", "thread")
    updated_at = utc_now()
    change_summary: list[str] = []
    if mission_id:
        thread["mission_ids"] = list(dict.fromkeys([*thread.get("mission_ids", []), mission_id]))
        thread["active_mission_id"] = mission_id
        change_summary.append(f"mission={mission_id}")
    if run_id is not None:
        thread["active_run_id"] = run_id
        change_summary.append(f"run={run_id or 'cleared'}")
    if handoff_id is not None:
        thread["latest_handoff_id"] = handoff_id
        change_summary.append(f"handoff_id={handoff_id or 'cleared'}")
    if checkpoint_id is not None:
        thread["latest_checkpoint_id"] = checkpoint_id
        change_summary.append(f"checkpoint_id={checkpoint_id or 'cleared'}")
    if spec_path:
        thread["latest_spec_path"] = spec_path
        change_summary.append("spec")
    if handoff_path:
        thread["latest_handoff_path"] = handoff_path
        change_summary.append("handoff")
    if checkpoint_path is not None:
        thread["latest_checkpoint_path"] = checkpoint_path
        change_summary.append("checkpoint")
    if resume_packet_path:
        thread["resume_packet_path"] = resume_packet_path
        change_summary.append("resume")
    if resume_status_path is not None:
        thread["latest_resume_status_path"] = resume_status_path
        change_summary.append("resume_status")
    if status:
        if status not in ALLOWED_THREAD_STATUSES:
            raise ValueError("thread status must be one of: " + ", ".join(sorted(ALLOWED_THREAD_STATUSES)))
        thread["status"] = status
        change_summary.append(f"status={status}")
    if execution_context is not None:
        thread["execution_context"] = normalize_execution_context(execution_context)
        change_summary.append("execution_context")
    if interruption_state is not None:
        thread["interruption_state"] = normalize_interruption_state(interruption_state)
        change_summary.append("interruption_state")
    if trace_state is not None:
        trace_state_payload = dict(trace_state)
        if execution_context is not None:
            trace_state_payload["session_id"] = thread["execution_context"]["session_id"]
            trace_state_payload["work_dir"] = thread["execution_context"]["work_dir"]
        thread["trace_state"] = normalize_trace_state(
            trace_state_payload,
            grouping_id=thread["id"],
            default_trace_id=thread.get("active_run_id", ""),
            snapshot_at=updated_at,
        )
        change_summary.append("trace_state")
    elif change_summary:
        current_trace_state = normalize_trace_state(
            thread.get("trace_state", {}),
            grouping_id=thread["id"],
            default_trace_id=thread.get("active_run_id", ""),
            snapshot_at=updated_at,
        )
        if handoff_id is not None:
            current_trace_state["handoff_id"] = thread["latest_handoff_id"]
        if handoff_path:
            current_trace_state["handoff_path"] = handoff_path
        if checkpoint_id is not None:
            current_trace_state["checkpoint_id"] = thread["latest_checkpoint_id"]
        if checkpoint_path is not None:
            current_trace_state["checkpoint_path"] = checkpoint_path
        if resume_packet_path:
            current_trace_state["resume_packet_path"] = resume_packet_path
        if execution_context is not None:
            current_trace_state["session_id"] = thread["execution_context"]["session_id"]
            current_trace_state["work_dir"] = thread["execution_context"]["work_dir"]
        current_trace_state["snapshot_at"] = updated_at
        current_trace_state["resume_fingerprint"] = build_resume_fingerprint(current_trace_state)
        thread["trace_state"] = normalize_trace_state(
            current_trace_state,
            grouping_id=thread["id"],
            default_trace_id=current_trace_state.get("trace_id", ""),
            snapshot_at=updated_at,
        )
    if metadata:
        merged_metadata = dict(thread.get("metadata", {}))
        merged_metadata.update(metadata)
        thread["metadata"] = merged_metadata
        change_summary.append("metadata")
    thread["updated_at"] = updated_at
    write_entity(thread_path(thread["id"]), thread)
    if change_summary:
        summary = "Updated thread context: " + ", ".join(change_summary)
        record_event(
            event_type="thread_updated",
            entity_id=thread["id"],
            summary=summary,
            payload={
                "mission_id": mission_id or "",
                "run_id": run_id or "",
                "handoff_id": handoff_id or "",
                "checkpoint_id": checkpoint_id or "",
                "spec_path": spec_path or "",
                "handoff_path": handoff_path or "",
                "checkpoint_path": checkpoint_path or "",
            },
            actor=thread["owner"] or "runtime",
            correlation_id=thread["id"],
        )
        emit_runtime_telemetry(
            event_type="thread_updated",
            status=thread["status"],
            summary=summary,
            actor=thread["owner"] or "runtime",
            thread_id=thread["id"],
            mission_id=thread["active_mission_id"],
            run_id=thread["active_run_id"],
            handoff_id=thread["latest_handoff_id"],
            metadata={"entity_type": "thread", "resume_fingerprint": thread["trace_state"]["resume_fingerprint"]},
        )
    return thread


def create_mission(args: argparse.Namespace) -> dict[str, Any]:
    if args.thread_id:
        thread = require_file(thread_path(args.thread_id), "thread", "thread")
    else:
        thread = create_thread_record(
            title=args.thread_title or args.title,
            owner=str(args.owner or args.manager or "").strip(),
            metadata={"created_for": "mission"},
        )
    mission_id = make_id("mission", args.title)
    created_at = utc_now()
    payload = {
        "schema_version": 1,
        "entity_type": "mission",
        "id": mission_id,
        "thread_id": thread["id"],
        "title": args.title.strip(),
        "goal": str(args.goal or "").strip(),
        "workflow": str(args.workflow or "").strip(),
        "project": str(args.project or "").strip(),
        "owner": str(args.owner or "").strip(),
        "manager": str(args.manager or "").strip(),
        "accepts_result": str(args.accepts_result or "").strip(),
        "source_task_id": str(args.source_task_id or "").strip(),
        "status": "planned",
        "latest_run_id": "",
        "run_ids": [],
        "created_at": created_at,
        "updated_at": created_at,
        "metadata": args.metadata or {},
    }
    write_entity(mission_path(mission_id), payload)
    update_thread_context(
        thread["id"],
        mission_id=mission_id,
        status="active",
    )
    record_event(
        event_type="mission_created",
        entity_id=mission_id,
        summary=f"Created mission '{payload['title']}'.",
        payload={
            "workflow": payload["workflow"],
            "source_task_id": payload["source_task_id"],
            "thread_id": payload["thread_id"],
        },
        actor=payload["owner"] or payload["manager"] or "runtime",
        correlation_id=payload["thread_id"],
    )
    emit_runtime_telemetry(
        event_type="mission_created",
        status=payload["status"],
        summary=f"Created mission '{payload['title']}'.",
        actor=payload["owner"] or payload["manager"] or "runtime",
        thread_id=payload["thread_id"],
        mission_id=payload["id"],
        source_task_id=payload["source_task_id"],
        workflow=payload["workflow"],
        metadata={"entity_type": "mission"},
    )
    return payload


def create_mission_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    payload = create_mission(args)
    print(f"mission_id={payload['id']}")
    print(f"thread_id={payload['thread_id']}")
    print(f"mission_file={mission_path(payload['id'])}")
    return 0


def create_thread_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    try:
        payload = create_thread_record(
            title=args.title,
            owner=str(args.owner or "").strip(),
            status=args.status,
            metadata=args.metadata or {},
        )
    except ValueError as exc:
        print(f"error={exc}")
        return 2
    print(f"thread_id={payload['id']}")
    print(f"thread_file={thread_path(payload['id'])}")
    return 0


def link_thread_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    try:
        execution_context = None
        if any(
            [
                args.session_id,
                args.work_dir,
                args.runtime_home,
                args.runtime_home_mode,
                args.parent_session_id,
                args.blocked_tool_class,
            ]
        ):
            thread = require_file(thread_path(args.thread_id), "thread", "thread")
            existing_context = dict(thread.get("execution_context", {}))
            execution_context = normalize_execution_context(
                {
                    **existing_context,
                    "session_id": str(args.session_id or existing_context.get("session_id", "")).strip(),
                    "work_dir": str(args.work_dir or existing_context.get("work_dir", "")).strip(),
                    "runtime_home": str(
                        args.runtime_home or existing_context.get("runtime_home", "")
                    ).strip(),
                    "runtime_home_mode": str(
                        args.runtime_home_mode or existing_context.get("runtime_home_mode", "none")
                    ).strip(),
                    "parent_session_id": str(
                        args.parent_session_id or existing_context.get("parent_session_id", "")
                    ).strip(),
                    "blocked_tool_classes": (
                        args.blocked_tool_class
                        if args.blocked_tool_class
                        else existing_context.get("blocked_tool_classes", [])
                    ),
                    "metadata": existing_context.get("metadata", {}),
                    "scope": (
                        "child_isolated"
                        if str(
                            args.parent_session_id or existing_context.get("parent_session_id", "")
                        ).strip()
                        else (
                            existing_context.get("scope", "isolated")
                            if str(args.session_id or args.work_dir or args.runtime_home).strip()
                            else existing_context.get("scope", "none")
                        )
                    ),
                }
            )
        payload = update_thread_context(
            args.thread_id,
            mission_id=args.mission_id,
            run_id=args.run_id,
            spec_path=args.spec_path,
            handoff_path=args.handoff_path,
            resume_packet_path=args.resume_packet_path,
            status=args.status,
            execution_context=execution_context,
            metadata=args.metadata or {},
        )
    except ValueError as exc:
        print(f"error={exc}")
        return 2
    print(f"thread_id={payload['id']}")
    print(f"thread_file={thread_path(payload['id'])}")
    return 0


def show_thread_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    try:
        payload = require_file(thread_path(args.thread_id), "thread", "thread")
    except ValueError as exc:
        print(f"error={exc}")
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def queued_runs_for_thread(thread_id: str) -> list[dict[str, Any]]:
    queued_runs: list[dict[str, Any]] = []
    for candidate in sorted(RUNTIME_DIRS["runs"].glob("*.json")):
        payload = require_file(candidate, "run", "run")
        if payload["thread_id"] != thread_id or payload["status"] != QUEUED_RUN_STATUS:
            continue
        queued_runs.append(payload)
    queued_runs.sort(
        key=lambda item: (
            str(item.get("created_at") or ""),
            str(item.get("id") or ""),
        )
    )
    return queued_runs


def summarize_queued_run(run: dict[str, Any]) -> dict[str, Any]:
    queue_metadata = run.get("metadata", {}).get("queue", {})
    if not isinstance(queue_metadata, dict):
        queue_metadata = {}
    return {
        "run_id": run["id"],
        "mission_id": run["mission_id"],
        "thread_id": run["thread_id"],
        "actor": run["actor"],
        "loop": run["loop"],
        "status": run["status"],
        "created_at": run["created_at"],
        "updated_at": run["updated_at"],
        "queued_at": str(queue_metadata.get("queued_at") or "").strip(),
        "rebased_at": str(queue_metadata.get("rebased_at") or "").strip(),
        "queued_after_run_id": str(queue_metadata.get("queued_after_run_id") or "").strip(),
        "strategy": str(queue_metadata.get("strategy") or "").strip(),
    }


def rebase_queued_runs_after_dispatch(
    *,
    thread_id: str,
    active_run_id: str,
    updated_at: str,
) -> None:
    for queued_run in queued_runs_for_thread(thread_id):
        if queued_run["id"] == active_run_id:
            continue
        metadata = dict(queued_run.get("metadata", {}))
        queue_metadata = dict(metadata.get("queue", {}))
        queue_metadata["queued_after_run_id"] = active_run_id
        queue_metadata["rebased_at"] = updated_at
        metadata["queue"] = queue_metadata
        queued_run["metadata"] = metadata
        queued_run["updated_at"] = updated_at
        write_entity(run_path(queued_run["id"]), queued_run)


def emit_run_lifecycle(
    *,
    event_type: str,
    status: str,
    summary: str,
    action: list[str],
    hook_event: str,
    run: dict[str, Any],
    mission: dict[str, Any],
    thread: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> None:
    record_event(
        event_type=event_type,
        entity_id=run["id"],
        summary=summary,
        payload={"mission_id": mission["id"], "actor": run["actor"], "thread_id": thread["id"]},
        actor=run["actor"] or mission["owner"] or "runtime",
        correlation_id=run["id"],
    )
    emit_runtime_telemetry(
        event_type=event_type,
        status=status,
        summary=summary,
        actor=run["actor"] or mission["owner"] or "runtime",
        thread_id=thread["id"],
        mission_id=mission["id"],
        source_task_id=mission["source_task_id"],
        workflow=mission["workflow"],
        run_id=run["id"],
        metadata={"entity_type": "run", **(metadata or {})},
    )
    emit_runtime_hook_event(
        event=hook_event,
        action=action,
        status=status,
        summary=summary,
        actor=run["actor"] or mission["owner"] or "runtime",
        thread_id=thread["id"],
        mission_id=mission["id"],
        run_id=run["id"],
        tool_name="run",
        call_id=run["id"],
        metadata={"loop": run["loop"], **(metadata or {})},
    )


def activate_queued_run(
    run: dict[str, Any],
    *,
    thread: dict[str, Any],
    mission: dict[str, Any],
    activated_by: str,
    activated_at: str | None = None,
) -> dict[str, Any]:
    if run["status"] != QUEUED_RUN_STATUS:
        raise ValueError(f"run status must be '{QUEUED_RUN_STATUS}', got '{run['status']}'")
    active_run_id = str(thread.get("active_run_id") or "").strip()
    if active_run_id:
        active_run = require_file(run_path(active_run_id), "run", "run")
        if active_run["status"] in ACTIVE_RUN_STATUSES:
            raise ValueError(
                f"thread already has active run {active_run_id} with status '{active_run['status']}'"
            )
    now = activated_at or utc_now()
    run["status"] = "running"
    run["updated_at"] = now
    run["interruption_state"] = normalize_interruption_state({})
    queue_metadata = dict(run.get("metadata", {}).get("queue", {}))
    queue_metadata["activated_at"] = now
    queue_metadata["activated_by"] = activated_by
    metadata = dict(run.get("metadata", {}))
    metadata["queue"] = queue_metadata
    run["metadata"] = metadata
    trace_state = dict(run.get("trace_state", {}))
    trace_state["trace_id"] = run["id"]
    trace_state["session_id"] = run["execution_context"]["session_id"]
    trace_state["work_dir"] = run["execution_context"]["work_dir"]
    trace_state["snapshot_at"] = now
    run["trace_state"] = normalize_trace_state(
        trace_state,
        grouping_id=run["thread_id"],
        default_trace_id=run["id"],
        snapshot_at=now,
    )
    write_entity(run_path(run["id"]), run)
    mission["latest_run_id"] = run["id"]
    mission["status"] = "active"
    mission["updated_at"] = now
    write_entity(mission_path(mission["id"]), mission)
    update_thread_context(
        thread["id"],
        mission_id=mission["id"],
        run_id=run["id"],
        status="active",
        execution_context=run["execution_context"],
        trace_state=run["trace_state"],
    )
    rebase_queued_runs_after_dispatch(
        thread_id=thread["id"],
        active_run_id=run["id"],
        updated_at=now,
    )
    emit_run_lifecycle(
        event_type="run_dispatched",
        status=run["status"],
        summary=f"Dispatched queued run for mission '{mission['title']}'.",
        action=["hq", "run", "dispatch"],
        hook_event="run_dispatched",
        run=run,
        mission=mission,
        thread=thread,
        metadata={"queue_activated_by": activated_by},
    )
    emit_run_lifecycle(
        event_type="run_started",
        status=run["status"],
        summary=f"Activated queued run for mission '{mission['title']}'.",
        action=["hq", "run", "dispatch"],
        hook_event="run_started",
        run=run,
        mission=mission,
        thread=thread,
        metadata={"queue_activated_by": activated_by},
    )
    return run


def start_run(args: argparse.Namespace) -> dict[str, Any]:
    mission = require_file(mission_path(args.mission_id), "mission", "mission")
    thread = require_file(thread_path(mission["thread_id"]), "thread", "thread")
    busy_strategy = str(getattr(args, "if_busy", None) or "reject").strip()
    active_run_id = str(thread.get("active_run_id") or "").strip()
    active_run: dict[str, Any] | None = None
    if active_run_id:
        active_run = require_file(run_path(active_run_id), "run", "run")
        if active_run["status"] in ACTIVE_RUN_STATUSES:
            if busy_strategy != "queue":
                raise ValueError(
                    f"thread already has active run {active_run_id} with status '{active_run['status']}'"
                )
    run_id = make_id("run", f"{mission['title']}-{args.actor or 'runtime'}")
    created_at = utc_now()
    execution_context = prepare_execution_context(
        run_id=run_id,
        session_id=str(getattr(args, "session_id", None) or "").strip(),
        work_dir=str(getattr(args, "work_dir", None) or "").strip(),
        runtime_home=str(getattr(args, "runtime_home", None) or "").strip(),
        runtime_home_mode=str(getattr(args, "runtime_home_mode", None) or "scoped").strip(),
        parent_session_id=str(getattr(args, "parent_session_id", None) or "").strip(),
        blocked_tool_classes=getattr(args, "blocked_tool_class", None) or [],
    )
    verification_stages = normalize_verification_stages(
        getattr(args, "verification_stage", None) or []
    )
    actor = str(args.actor or "").strip()
    if verification_stages and not actor:
        raise ValueError("verification stages require a run actor to set the return target")
    budgets = load_default_run_budgets()
    budgets.update(
        normalize_run_budgets(
            {
                "max_steps": getattr(args, "max_steps", None) or 0,
                "max_failed_steps": getattr(args, "max_failed_steps", None) or 0,
            }
        )
    )
    run_status = "running"
    metadata = dict(args.metadata or {})
    if active_run is not None and active_run["status"] in ACTIVE_RUN_STATUSES:
        run_status = QUEUED_RUN_STATUS
        metadata["queue"] = {
            "strategy": busy_strategy,
            "queued_at": created_at,
            "queued_after_run_id": active_run["id"],
        }
    if run_status == "running":
        feedback_iteration_id = record_run_feedback_start(
            mission=mission,
            run_id=run_id,
            actor=actor,
            created_at=created_at,
        )
        if feedback_iteration_id:
            metadata["feedback_iteration_id"] = feedback_iteration_id
    payload = {
        "schema_version": 1,
        "entity_type": "run",
        "id": run_id,
        "thread_id": mission["thread_id"],
        "mission_id": mission["id"],
        "status": run_status,
        "actor": actor,
        "loop": str(args.loop or "").strip(),
        "current_step_id": "",
        "resume_from_step_id": "",
        "last_successful_step_id": "",
        "step_ids": [],
        "approval_ids": [],
        "handoff_ids": [],
        "artifact_ids": [],
        "verification_stages": verification_stages,
        "budgets": budgets,
        "checkpoint_count": 0,
        "latest_checkpoint_id": "",
        "latest_checkpoint_path": "",
        "resume_status_path": "",
        "interruption_state": normalize_interruption_state({}),
        "execution_context": execution_context,
        "verification_state": normalize_verification_state(
            {},
            stages=verification_stages,
            default_return_target=actor,
        ),
        "trace_state": normalize_trace_state(
            {
                "trace_id": run_id,
                "session_id": execution_context["session_id"],
                "work_dir": execution_context["work_dir"],
            },
            grouping_id=thread["id"],
            default_trace_id=run_id,
            snapshot_at=created_at,
        ),
        "started_at": created_at,
        "finished_at": "",
        "created_at": created_at,
        "updated_at": created_at,
        "metadata": metadata,
    }
    write_entity(run_path(run_id), payload)
    mission["latest_run_id"] = run_id
    mission["run_ids"] = list(dict.fromkeys([*mission.get("run_ids", []), run_id]))
    mission["status"] = "active"
    mission["updated_at"] = created_at
    write_entity(mission_path(mission["id"]), mission)
    if payload["status"] == QUEUED_RUN_STATUS:
        emit_run_lifecycle(
            event_type="run_queued",
            status=payload["status"],
            summary=f"Queued run for mission '{mission['title']}' behind active run '{active_run_id}'.",
            action=["hq", "run", "queue"],
            hook_event="run_queued",
            run=payload,
            mission=mission,
            thread=thread,
            metadata={"queued_after_run_id": active_run_id},
        )
        return payload
    update_thread_context(
        thread["id"],
        mission_id=mission["id"],
        run_id=run_id,
        status="active",
        execution_context=execution_context,
        trace_state=payload["trace_state"],
    )
    emit_run_lifecycle(
        event_type="run_started",
        status=payload["status"],
        summary=f"Started run for mission '{mission['title']}'.",
        action=["hq", "run", "start"],
        hook_event="run_started",
        run=payload,
        mission=mission,
        thread=thread,
    )
    return payload


def ensure_packet_runtime(
    *,
    thread_id: str,
    task: str,
    owner: str = "",
    goal: str = "",
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Ensure a thread has first-class Mission/Run state for packet writes."""

    thread = require_file(thread_path(thread_id), "thread", "thread")
    mission_id = str(thread.get("active_mission_id") or "").strip()
    if mission_id:
        mission = require_file(mission_path(mission_id), "mission", "mission")
    else:
        mission = create_mission(
            argparse.Namespace(
                title=task,
                goal=goal or task,
                workflow="task-packet-runtime",
                project="",
                owner=str(owner or "").strip(),
                manager="",
                accepts_result=str(owner or "").strip(),
                source_task_id=slugify(task),
                thread_id=thread_id,
                thread_title="",
                metadata={"origin": "packet_runtime"},
            )
        )
        thread = require_file(thread_path(thread_id), "thread", "thread")

    run_id = str(thread.get("active_run_id") or "").strip()
    run: dict[str, Any] | None = None
    if run_id:
        run = require_file(run_path(run_id), "run", "run")
        if run["status"] not in ACTIVE_RUN_STATUSES:
            run = None

    if run is None:
        run = start_run(
            argparse.Namespace(
                mission_id=mission["id"],
                actor=str(owner or mission.get("owner") or "runtime").strip(),
                loop="spec/handoff packet runtime",
                if_busy="queue",
                session_id="",
                work_dir="",
                runtime_home="",
                runtime_home_mode="scoped",
                parent_session_id="",
                blocked_tool_class=[],
                verification_stage=[],
                metadata={"origin": "packet_runtime"},
            )
        )
        thread = require_file(thread_path(thread_id), "thread", "thread")

    return thread, mission, run


def record_packet_step(
    *,
    thread_id: str,
    task: str,
    packet_kind: str,
    packet_path: str,
    owner: str = "",
    goal: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _thread, _mission, run = ensure_packet_runtime(
        thread_id=thread_id,
        task=task,
        owner=owner,
        goal=goal,
    )
    step_key = f"{packet_kind}_packet"
    packet_metadata = {
        "origin": "packet_runtime",
        f"{packet_kind}_path": packet_path,
        **(metadata or {}),
    }
    created_at = utc_now()
    step_id = make_id("step", f"{step_key}-{owner or 'runtime'}")
    payload = {
        "schema_version": 1,
        "entity_type": "step",
        "id": step_id,
        "thread_id": run["thread_id"],
        "run_id": run["id"],
        "mission_id": run["mission_id"],
        "key": step_key,
        "actor": str(owner or run.get("actor") or "runtime").strip(),
        "status": "completed",
        "error_type": "",
        "retry_count": 0,
        "allowed_tool_classes": [],
        "policy_action": "allow",
        "policy_context": {
            "origin": "packet_runtime",
            "summary": f"Recorded {packet_kind} packet for task '{task}'.",
        },
        "summary": f"Recorded {packet_kind} packet for task '{task}'.",
        "evidence": [packet_path],
        "metadata": packet_metadata,
        "created_at": created_at,
        "updated_at": created_at,
        "completed_at": created_at,
    }
    write_entity(step_path(step_id), payload)
    run = require_file(run_path(run["id"]), "run", "run")
    run["step_ids"] = list(dict.fromkeys([*run.get("step_ids", []), step_id]))
    run["current_step_id"] = step_id
    run["updated_at"] = created_at
    trace_state = dict(run.get("trace_state", {}))
    trace_state["trace_id"] = run["id"]
    trace_state["current_step_id"] = step_id
    trace_state["snapshot_at"] = created_at
    run["trace_state"] = normalize_trace_state(
        trace_state,
        grouping_id=run["thread_id"],
        default_trace_id=run["id"],
        snapshot_at=created_at,
    )
    write_entity(run_path(run["id"]), run)
    update_thread_context(
        run["thread_id"],
        mission_id=run["mission_id"],
        run_id=run["id"],
        status="active",
        trace_state=run["trace_state"],
    )
    record_event(
        event_type="packet_step_recorded",
        entity_id=step_id,
        summary=f"Recorded {packet_kind} packet step for task '{task}'.",
        payload={"run_id": run["id"], "thread_id": run["thread_id"], "packet_path": packet_path},
        actor=payload["actor"] or "runtime",
        correlation_id=run["id"],
    )
    emit_runtime_telemetry(
        event_type="packet_step_recorded",
        status="completed",
        summary=f"Recorded {packet_kind} packet step for task '{task}'.",
        actor=payload["actor"] or "runtime",
        thread_id=run["thread_id"],
        mission_id=run["mission_id"],
        run_id=run["id"],
        step_id=step_id,
        metadata={"entity_type": "step", "step_key": step_key, "packet_path": packet_path},
    )
    return payload


def start_run_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    try:
        payload = start_run(args)
    except (ValueError, RuntimeError) as exc:
        print(f"error={exc}")
        return 2
    print(f"run_id={payload['id']}")
    print(f"status={payload['status']}")
    print(f"run_file={run_path(payload['id'])}")
    return 0


def list_queued_runs_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    if args.limit < 1:
        print("error=limit must be >= 1")
        return 2
    try:
        thread = require_file(thread_path(args.thread_id), "thread", "thread")
        queued_runs = queued_runs_for_thread(thread["id"])
    except ValueError as exc:
        print(f"error={exc}")
        return 2
    payload = {
        "thread_id": thread["id"],
        "active_run_id": str(thread.get("active_run_id") or "").strip(),
        "queued_run_count": len(queued_runs),
        "queued_runs": [summarize_queued_run(run) for run in queued_runs[: args.limit]],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def dispatch_queued_run(args: argparse.Namespace) -> int:
    ensure_runtime()
    try:
        selected_run: dict[str, Any]
        if str(getattr(args, "run_id", None) or "").strip():
            selected_run = require_file(run_path(args.run_id), "run", "run")
            if selected_run["status"] != QUEUED_RUN_STATUS:
                raise ValueError(f"run status must be '{QUEUED_RUN_STATUS}' to dispatch")
            thread = require_file(thread_path(selected_run["thread_id"]), "thread", "thread")
        else:
            thread = require_file(thread_path(args.thread_id), "thread", "thread")
            queued_runs = queued_runs_for_thread(thread["id"])
            if not queued_runs:
                raise ValueError("thread has no queued runs to dispatch")
            selected_run = queued_runs[0]
        mission = require_file(mission_path(selected_run["mission_id"]), "mission", "mission")
        payload = activate_queued_run(
            selected_run,
            thread=thread,
            mission=mission,
            activated_by=str(args.activated_by or "").strip(),
        )
    except (ValueError, RuntimeError) as exc:
        print(f"error={exc}")
        return 2
    print(f"run_id={payload['id']}")
    print(f"status={payload['status']}")
    return 0


def normalize_run_budgets(payload: dict[str, Any] | None) -> dict[str, int]:
    raw = payload or {}
    if not isinstance(raw, dict):
        raise ValueError("run budgets must be an object")
    unknown_keys = set(raw) - ALLOWED_RUN_BUDGET_KEYS
    if unknown_keys:
        raise ValueError("unsupported run budget keys: " + ", ".join(sorted(unknown_keys)))
    normalized: dict[str, int] = {}
    for key in sorted(ALLOWED_RUN_BUDGET_KEYS):
        value = raw.get(key)
        if value in (None, "", 0):
            continue
        number = int(value)
        if number < 1:
            raise ValueError(f"run budget {key} must be a positive integer")
        normalized[key] = number
    return normalized


def load_default_run_budgets() -> dict[str, int]:
    if not EXECUTION_CONFIG_PATH.exists():
        return {}
    execution_config = load_json(EXECUTION_CONFIG_PATH)
    execution_profile = execution_config.get("execution_profile") or {}
    return normalize_run_budgets(execution_profile.get("run_budgets") or {})


def exhausted_run_budget(run: dict[str, Any]) -> str:
    """Return the exhausted budget label, or "" when the run may take new steps."""
    budgets = run.get("budgets") or {}
    step_ids = run.get("step_ids", [])
    max_steps = int(budgets.get("max_steps") or 0)
    if max_steps and len(step_ids) >= max_steps:
        return f"max_steps={max_steps}"
    max_failed_steps = int(budgets.get("max_failed_steps") or 0)
    if max_failed_steps:
        failed = 0
        for step_id in step_ids:
            sp = step_path(step_id)
            if sp.exists() and load_json(sp).get("status") == "failed":
                failed += 1
        if failed >= max_failed_steps:
            return f"max_failed_steps={max_failed_steps}"
    return ""


def _count_transient_retries_for_key(run: dict[str, Any], step_key: str) -> int:
    """Count the number of consecutive transient-error retries for a step key."""
    count = 0
    for step_id in reversed(run.get("step_ids", [])):
        sp = step_path(step_id)
        if not sp.exists():
            continue
        step = load_json(sp)
        if step.get("key") != step_key:
            break
        if step.get("error_type") == "transient" and step.get("status") == "failed":
            count += 1
        else:
            break
    return count


def checkpoint_step(args: argparse.Namespace) -> dict[str, Any]:
    if args.status not in ALLOWED_STEP_STATUSES:
        raise ValueError("status must be one of: " + ", ".join(sorted(ALLOWED_STEP_STATUSES)))
    error_type = str(getattr(args, "error_type", None) or "").strip()
    if error_type and error_type not in ALLOWED_ERROR_TYPES:
        raise ValueError("error_type must be one of: " + ", ".join(sorted(ALLOWED_ERROR_TYPES - {""})))
    if error_type and args.status != "failed":
        raise ValueError("error_type can only be set when status is 'failed'")
    run = require_file(run_path(args.run_id), "run", "run")
    mission = require_file(mission_path(run["mission_id"]), "mission", "mission")

    # --- Run budget enforcement ---
    exhausted_budget = exhausted_run_budget(run)
    if exhausted_budget:
        budget_actor = str(args.actor or "").strip() or run["actor"] or "runtime"
        budget_summary = (
            f"Run budget exhausted ({exhausted_budget}); refusing new step '{args.key.strip()}'."
        )
        record_event(
            event_type="run_budget_exhausted",
            entity_id=run["id"],
            summary=budget_summary,
            payload={
                "thread_id": run["thread_id"],
                "mission_id": run["mission_id"],
                "step_key": args.key.strip(),
                "budgets": run.get("budgets", {}),
            },
            actor=budget_actor,
            correlation_id=run["id"],
        )
        emit_runtime_telemetry(
            event_type="run_budget_exhausted",
            status="blocked",
            summary=budget_summary,
            actor=budget_actor,
            thread_id=run["thread_id"],
            mission_id=mission["id"],
            source_task_id=mission["source_task_id"],
            workflow=mission["workflow"],
            run_id=run["id"],
            metadata={"entity_type": "run", "budgets": run.get("budgets", {})},
        )
        raise ValueError(
            f"run budget exhausted ({exhausted_budget}); finish or interrupt run "
            f"{run['id']}, or start a new run with a higher budget"
        )

    # --- Transient retry logic ---
    retry_count = 0
    if error_type == "transient":
        retry_count = _count_transient_retries_for_key(run, args.key.strip()) + 1
        if retry_count > MAX_TRANSIENT_RETRIES:
            error_type = "unexpected"

    step_id = make_id("step", f"{args.key}-{args.actor or 'actor'}")
    created_at = utc_now()
    tool_policy = evaluate_step_tool_policy(
        step_id=step_id,
        step_key=args.key.strip(),
        run=run,
        allowed_tool_classes=getattr(args, "allowed_tool_class", None) or [],
    )
    effective_status = args.status
    if tool_policy["policy_action"] == "block":
        effective_status = "blocked"
    elif tool_policy["policy_action"] == "pause_for_founder_approval":
        effective_status = "waiting_approval"
    payload = {
        "schema_version": 1,
        "entity_type": "step",
        "id": step_id,
        "thread_id": run["thread_id"],
        "run_id": run["id"],
        "mission_id": run["mission_id"],
        "key": args.key.strip(),
        "actor": str(args.actor or "").strip(),
        "status": effective_status,
        "error_type": error_type,
        "retry_count": retry_count,
        "allowed_tool_classes": tool_policy["allowed_tool_classes"],
        "policy_action": tool_policy["policy_action"],
        "policy_context": tool_policy["policy_context"],
        "summary": str(args.summary or "").strip(),
        "evidence": [item for item in args.evidence if item.strip()],
        "metadata": args.metadata or {},
        "created_at": created_at,
        "updated_at": created_at,
        "completed_at": created_at if effective_status == "completed" else "",
    }
    write_entity(step_path(step_id), payload)
    run["step_ids"] = list(dict.fromkeys([*run.get("step_ids", []), step_id]))
    run["current_step_id"] = step_id
    if payload["status"] == "completed":
        run["checkpoint_count"] = int(run.get("checkpoint_count", 0)) + 1
        run["resume_from_step_id"] = step_id
        run["last_successful_step_id"] = step_id
        run["status"] = "running"
    elif payload["status"] == "waiting_approval":
        run["status"] = "waiting_approval"
    elif payload["status"] == "failed" and error_type == "transient" and retry_count <= MAX_TRANSIENT_RETRIES:
        # Transient error within retry cap: keep run in running state for automatic retry
        run["status"] = "running"
    elif payload["status"] == "failed" and error_type == "recoverable":
        # Recoverable: return error as context, keep run running
        run["status"] = "running"
    elif payload["status"] == "failed" and error_type == "user_fixable":
        # User-fixable: map to existing pause_for_founder_approval pattern
        run["status"] = "waiting_approval"
    elif payload["status"] in {"blocked", "failed"}:
        run["status"] = payload["status"]
    else:
        run["status"] = "running"
    run["updated_at"] = created_at
    trace_state = dict(run.get("trace_state", {}))
    trace_state["trace_id"] = run["id"]
    trace_state["current_step_id"] = step_id
    trace_state["resume_from_step_id"] = run["resume_from_step_id"]
    trace_state["snapshot_at"] = created_at
    trace_metadata = dict(trace_state.get("metadata", {}))
    trace_state["metadata"] = reconcile_replay_metadata(
        trace_metadata,
        step=payload,
        updated_at=created_at,
    )
    run["trace_state"] = normalize_trace_state(
        trace_state,
        grouping_id=run["thread_id"],
        default_trace_id=run["id"],
        snapshot_at=created_at,
    )
    write_entity(run_path(run["id"]), run)
    if payload["status"] == "completed":
        _checkpoint, run, _thread = create_checkpoint_record(
            run=run,
            mission=mission,
            thread=require_file(thread_path(run["thread_id"]), "thread", "thread"),
            checkpoint_kind="step_completed",
            source_step_id=payload["id"],
            source_event="checkpoint-step",
            created_at=created_at,
        )
    if payload["policy_action"] == "pause_for_founder_approval":
        approval = request_approval(
            argparse.Namespace(
                run_id=run["id"],
                step_id=payload["id"],
                requested_by=payload["actor"] or run["actor"] or "runtime",
                requested_for="founder",
                policy_action=payload["policy_action"],
                summary=payload["policy_context"]["summary"],
                approval_kind="runtime_action",
                approval_namespace="hq.step.tool_policy",
                approval_name=payload["key"],
                approval_call_id=payload["id"],
                approval_action=["hq", "step", "tool_policy", payload["policy_action"]],
                metadata={"origin": "step_tool_policy"},
                tool_scope=payload["allowed_tool_classes"],
                policy_context={
                    "origin": "step_tool_policy",
                    "step_key": payload["key"],
                    "matched_rules": payload["policy_context"]["matched_rules"],
                },
            )
        )
        payload = require_file(step_path(step_id), "step", "step")
        payload["policy_context"] = dict(payload.get("policy_context", {}))
        payload["policy_context"]["approval_id"] = approval["id"]
        payload["updated_at"] = created_at
        write_entity(step_path(step_id), payload)
        run = require_file(run_path(run["id"]), "run", "run")
    update_thread_context(
        run["thread_id"],
        mission_id=mission["id"],
        run_id=run["id"],
        status="paused" if run["status"] == "waiting_approval" else "active",
        trace_state=run["trace_state"],
    )
    refresh_resume_status(run["id"])
    step_event = record_event(
        event_type="step_checkpointed",
        entity_id=step_id,
        summary=f"Recorded step '{payload['key']}' with status '{payload['status']}'.",
        payload={"run_id": run["id"], "actor": payload["actor"], "thread_id": run["thread_id"]},
        actor=payload["actor"] or run["actor"] or "runtime",
        correlation_id=run["id"],
    )
    record_event(
        event_type="step_tool_policy_evaluated",
        entity_id=step_id,
        summary=payload["policy_context"]["summary"],
        payload={
            "run_id": run["id"],
            "thread_id": run["thread_id"],
            "policy_action": payload["policy_action"],
            "allowed_tool_classes": payload["allowed_tool_classes"],
            "approval_id": str(payload["policy_context"].get("approval_id") or "").strip(),
        },
        actor=payload["actor"] or run["actor"] or "runtime",
        correlation_id=run["id"],
        causation_id=step_event["id"],
    )
    emit_runtime_telemetry(
        event_type="step_checkpointed",
        status=payload["status"],
        summary=f"Recorded step '{payload['key']}' with status '{payload['status']}'.",
        actor=payload["actor"] or run["actor"] or "runtime",
        thread_id=run["thread_id"],
        mission_id=mission["id"],
        source_task_id=mission["source_task_id"],
        workflow=mission["workflow"],
        run_id=run["id"],
        step_id=payload["id"],
        metadata={
            "entity_type": "step",
            "step_key": payload["key"],
            "policy_action": payload["policy_action"],
            "allowed_tool_classes": payload["allowed_tool_classes"],
        },
    )
    emit_runtime_telemetry(
        event_type="step_tool_policy_evaluated",
        status=payload["policy_action"],
        summary=payload["policy_context"]["summary"],
        actor=payload["actor"] or run["actor"] or "runtime",
        thread_id=run["thread_id"],
        mission_id=mission["id"],
        source_task_id=mission["source_task_id"],
        workflow=mission["workflow"],
        run_id=run["id"],
        step_id=payload["id"],
        approval_id=str(payload["policy_context"].get("approval_id") or "").strip(),
        metadata={
            "entity_type": "step",
            "step_key": payload["key"],
            "allowed_tool_classes": payload["allowed_tool_classes"],
            "blocked_tool_classes": payload["policy_context"].get("blocked_tool_classes", []),
            "matched_rules": payload["policy_context"].get("matched_rules", []),
        },
    )
    emit_runtime_hook_event(
        event="run_checkpointed",
        action=["hq", "run", "checkpoint"],
        status=payload["status"],
        summary=f"Recorded step '{payload['key']}' with status '{payload['status']}'.",
        actor=payload["actor"] or run["actor"] or "runtime",
        decision=payload["policy_action"],
        thread_id=run["thread_id"],
        mission_id=mission["id"],
        run_id=run["id"],
        step_id=payload["id"],
        tool_name=payload["key"],
        call_id=payload["id"],
        metadata={
            "step_key": payload["key"],
            "allowed_tool_classes": payload["allowed_tool_classes"],
            "policy_action": payload["policy_action"],
        },
    )
    emit_runtime_hook_event(
        event="step_tool_policy_evaluated",
        action=["hq", "step", "tool_policy", payload["policy_action"]],
        status=payload["status"],
        summary=payload["policy_context"]["summary"],
        actor=payload["actor"] or run["actor"] or "runtime",
        decision=payload["policy_action"],
        thread_id=run["thread_id"],
        mission_id=mission["id"],
        run_id=run["id"],
        step_id=payload["id"],
        approval_id=str(payload["policy_context"].get("approval_id") or "").strip(),
        namespace="hq.step.tool_policy",
        tool_name="tool_policy",
        call_id=payload["id"],
        metadata={
            "step_key": payload["key"],
            "allowed_tool_classes": payload["allowed_tool_classes"],
            "blocked_tool_classes": payload["policy_context"].get("blocked_tool_classes", []),
        },
    )
    lifecycle_event = "agent_started" if payload["status"] in {"planned", "running"} else "agent_finished"
    lifecycle_action = (
        ["hq", "agent", "start"] if lifecycle_event == "agent_started" else ["hq", "agent", "finish"]
    )
    emit_runtime_hook_event(
        event=lifecycle_event,
        action=lifecycle_action,
        status=payload["status"],
        summary=f"Agent step '{payload['key']}' is now '{payload['status']}'.",
        actor=payload["actor"] or run["actor"] or "runtime",
        decision=payload["policy_action"],
        thread_id=run["thread_id"],
        mission_id=mission["id"],
        run_id=run["id"],
        step_id=payload["id"],
        tool_name=payload["key"],
        call_id=payload["id"],
        metadata={"step_key": payload["key"]},
    )
    return payload


def checkpoint_step_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    try:
        payload = checkpoint_step(args)
    except (ValueError, RuntimeError) as exc:
        print(f"error={exc}")
        return 2
    print(f"step_id={payload['id']}")
    print(f"step_file={step_path(payload['id'])}")
    return 0


def checkpoint_history_for_run(run: dict[str, Any]) -> list[dict[str, Any]]:
    checkpoints: list[dict[str, Any]] = []
    for step_id in run.get("step_ids", []):
        step = require_file(step_path(step_id), "step", "step")
        if step["run_id"] != run["id"] or step["status"] != "completed":
            continue
        checkpoints.append(
            {
                "step_id": step["id"],
                "key": step["key"],
                "summary": step["summary"],
                "actor": step["actor"],
                "created_at": step["created_at"],
                "completed_at": step["completed_at"],
                "evidence": step.get("evidence", []),
            }
        )
    checkpoints.sort(
        key=lambda item: (
            str(item.get("completed_at") or ""),
            str(item.get("created_at") or ""),
            str(item.get("step_id") or ""),
        ),
        reverse=True,
    )
    return checkpoints


def ordered_steps_for_run(run: dict[str, Any]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for step_id in run.get("step_ids", []):
        step = require_file(step_path(step_id), "step", "step")
        if step["run_id"] == run["id"]:
            steps.append(step)
    return steps


def resolve_resume_target_step(run: dict[str, Any], resume_from_step_id: str) -> dict[str, Any]:
    target_step = require_file(step_path(resume_from_step_id), "step", "step")
    if target_step["run_id"] != run["id"]:
        raise ValueError("resume target step does not belong to the provided run")
    if target_step["status"] != "completed":
        raise ValueError("resume target step must have status 'completed'")
    return target_step


def build_replay_plan(
    run: dict[str, Any],
    *,
    resume_from_step_id: str = "",
) -> dict[str, Any]:
    target_step_id = str(resume_from_step_id or run.get("resume_from_step_id") or "").strip()
    if not target_step_id:
        return {
            "resume_from_step_id": "",
            "replay_required": False,
            "replay_step_count": 0,
            "checkpoint_count_after_target": 0,
            "steps_to_replay": [],
        }

    target_step = resolve_resume_target_step(run, target_step_id)
    ordered_steps = ordered_steps_for_run(run)
    target_index = next(
        (index for index, step in enumerate(ordered_steps) if step["id"] == target_step["id"]),
        -1,
    )
    if target_index < 0:
        raise ValueError("resume target step is missing from the run step history")

    replay_steps = ordered_steps[target_index + 1 :]
    replay_payload = [
        {
            "step_id": step["id"],
            "key": step["key"],
            "actor": step["actor"],
            "status": step["status"],
            "summary": step["summary"],
            "created_at": step["created_at"],
            "completed_at": step["completed_at"],
        }
        for step in replay_steps
    ]
    checkpoint_count_after_target = sum(1 for step in replay_steps if step["status"] == "completed")
    return {
        "resume_from_step_id": target_step["id"],
        "target_checkpoint": {
            "step_id": target_step["id"],
            "key": target_step["key"],
            "actor": target_step["actor"],
            "summary": target_step["summary"],
            "created_at": target_step["created_at"],
            "completed_at": target_step["completed_at"],
        },
        "replay_required": bool(replay_payload),
        "replay_step_count": len(replay_payload),
        "checkpoint_count_after_target": checkpoint_count_after_target,
        "steps_to_replay": replay_payload,
    }


def reconcile_replay_metadata(
    trace_metadata: dict[str, Any],
    *,
    step: dict[str, Any],
    updated_at: str,
) -> dict[str, Any]:
    replay = trace_metadata.get("replay", {})
    if not isinstance(replay, dict):
        trace_metadata.pop("replay", None)
        return trace_metadata

    replay_steps = replay.get("replay_steps", [])
    if not isinstance(replay_steps, list) or not replay_steps:
        trace_metadata.pop("replay", None)
        return trace_metadata

    next_step = replay_steps[0]
    if not isinstance(next_step, dict):
        trace_metadata.pop("replay", None)
        return trace_metadata

    expected_key = str(next_step.get("key") or "").strip()
    expected_status = str(next_step.get("status") or "").strip()
    if step["key"] != expected_key or step["status"] != expected_status:
        return trace_metadata

    remaining_steps = replay_steps[1:]
    replay["last_replayed_step_id"] = step["id"]
    replay["last_replayed_step_key"] = step["key"]
    replay["last_replayed_at"] = updated_at
    replay["remaining_replay_step_count"] = len(remaining_steps)
    replay["replay_step_ids"] = [
        str(item.get("step_id") or "").strip()
        for item in remaining_steps
        if isinstance(item, dict) and str(item.get("step_id") or "").strip()
    ]
    if remaining_steps:
        replay["replay_steps"] = remaining_steps
        replay["reconciled_at"] = updated_at
        trace_metadata["replay"] = replay
        return trace_metadata

    trace_metadata.pop("replay", None)
    trace_metadata["replay_completed_at"] = updated_at
    trace_metadata["replay_completed_from_step_id"] = str(
        replay.get("resume_from_step_id") or ""
    ).strip()
    return trace_metadata


def resolve_runtime_reference(path_value: str) -> Path | None:
    text = str(path_value or "").strip()
    if not text:
        return None
    candidate = Path(text)
    if not candidate.is_absolute():
        candidate = (REPO_ROOT / candidate).resolve()
    return candidate


def file_digest_for_reference(path_value: str) -> str:
    candidate = resolve_runtime_reference(path_value)
    if candidate is None or not candidate.exists() or not candidate.is_file():
        return ""
    try:
        return hashlib.sha256(candidate.read_bytes()).hexdigest()[:16]
    except OSError:
        return ""


def linked_recovery_paths(run: dict[str, Any], thread: dict[str, Any]) -> dict[str, str]:
    run_trace_state = run.get("trace_state", {}) if isinstance(run.get("trace_state"), dict) else {}
    latest_handoff_path = (
        str(run_trace_state.get("handoff_path") or "")
        or str(thread.get("latest_handoff_path") or "")
    ).strip()
    resume_packet_path = (
        str(run_trace_state.get("resume_packet_path") or "")
        or str(thread.get("resume_packet_path") or "")
        or latest_handoff_path
    ).strip()
    return {
        "latest_spec_path": str(thread.get("latest_spec_path") or "").strip(),
        "latest_handoff_path": latest_handoff_path,
        "resume_packet_path": resume_packet_path,
    }


def checkpoint_replay_basis(run: dict[str, Any]) -> dict[str, Any]:
    trace_state = run.get("trace_state", {}) if isinstance(run.get("trace_state"), dict) else {}
    metadata = trace_state.get("metadata", {}) if isinstance(trace_state.get("metadata"), dict) else {}
    replay = metadata.get("replay", {}) if isinstance(metadata.get("replay"), dict) else {}
    replay_basis: dict[str, Any] = {}
    if replay:
        replay_basis["replay"] = replay
    replay_completed_at = str(metadata.get("replay_completed_at") or "").strip()
    if replay_completed_at:
        replay_basis["replay_completed_at"] = replay_completed_at
    replay_completed_from_step_id = str(metadata.get("replay_completed_from_step_id") or "").strip()
    if replay_completed_from_step_id:
        replay_basis["replay_completed_from_step_id"] = replay_completed_from_step_id
    return replay_basis


def build_checkpoint_resume_plan(
    run: dict[str, Any],
    checkpoint_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resume_from_step_id = str(
        (checkpoint_record or {}).get("resume_from_step_id") or run.get("resume_from_step_id") or ""
    ).strip()
    replay_plan = build_replay_plan(run, resume_from_step_id=resume_from_step_id)
    return {
        "current_step_id": str(
            (checkpoint_record or {}).get("current_step_id") or run.get("current_step_id") or ""
        ).strip(),
        "resume_from_step_id": replay_plan["resume_from_step_id"],
        "last_successful_step_id": str(
            (checkpoint_record or {}).get("last_successful_step_id")
            or run.get("last_successful_step_id")
            or ""
        ).strip(),
        "replay_required": replay_plan["replay_required"],
        "replay_step_count": replay_plan["replay_step_count"],
        "checkpoint_count_after_target": replay_plan["checkpoint_count_after_target"],
        "steps_to_replay": replay_plan["steps_to_replay"],
    }


def load_latest_checkpoint_state(run: dict[str, Any]) -> dict[str, Any]:
    latest_checkpoint_id = str(run.get("latest_checkpoint_id") or "").strip()
    latest_checkpoint_path = str(run.get("latest_checkpoint_path") or "").strip()
    checkpoint_record: dict[str, Any] | None = None
    checkpoint_error = ""
    checkpoint_file: Path | None = None
    if latest_checkpoint_path:
        checkpoint_file = resolve_runtime_reference(latest_checkpoint_path)
    elif latest_checkpoint_id:
        checkpoint_file = checkpoint_path(latest_checkpoint_id)
        latest_checkpoint_path = path_reference(checkpoint_file)
    if checkpoint_file is not None:
        checkpoint_record, checkpoint_error = load_entity_safe(checkpoint_file, "checkpoint")
    return {
        "id": latest_checkpoint_id,
        "path": latest_checkpoint_path,
        "file": checkpoint_file,
        "record": checkpoint_record,
        "error": checkpoint_error,
    }


def analyze_checkpoint_staleness(checkpoint_record: dict[str, Any] | None) -> tuple[list[str], bool]:
    stale_inputs: list[str] = []
    if checkpoint_record is None:
        return stale_inputs, False
    for field in ("latest_spec_path", "latest_handoff_path", "resume_packet_path"):
        path_value = str(checkpoint_record.get(field) or "").strip()
        if not path_value:
            continue
        current_digest = file_digest_for_reference(path_value)
        recorded_digest = str(
            checkpoint_record.get("referenced_file_digests", {}).get(field) or ""
        ).strip()
        if not current_digest:
            stale_inputs.append(f"{field}:missing:{path_value}")
        elif recorded_digest and current_digest != recorded_digest:
            stale_inputs.append(f"{field}:digest_mismatch:{path_value}")
    needs_handoff_refresh = any(
        item.startswith("latest_handoff_path:") or item.startswith("resume_packet_path:")
        for item in stale_inputs
    )
    return stale_inputs, needs_handoff_refresh


def build_resume_status_payload(
    run: dict[str, Any],
    *,
    existing_status: dict[str, Any] | None = None,
    checkpoint_state: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
    resume_epoch: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    checkpoint = checkpoint_state or load_latest_checkpoint_state(run)
    latest_checkpoint_id = str(checkpoint.get("id") or "").strip()
    latest_checkpoint_path = str(checkpoint.get("path") or "").strip()
    checkpoint_record = checkpoint.get("record")
    checkpoint_error = str(checkpoint.get("error") or "").strip()
    stale_inputs, needs_handoff_refresh = analyze_checkpoint_staleness(checkpoint_record)

    resumable = False
    safe_to_resume = False
    if checkpoint_error:
        resume_reason = f"checkpoint invalid: {checkpoint_error}"
    elif checkpoint_record is None and (latest_checkpoint_id or latest_checkpoint_path):
        resume_reason = "checkpoint missing"
    elif run["status"] == "interrupted":
        resumable = True
        safe_to_resume = True
        if checkpoint_record is not None:
            resume_reason = "checkpoint valid for resume"
        else:
            resume_reason = "legacy interrupted run without persisted checkpoint"
        if needs_handoff_refresh:
            resume_reason = "checkpoint valid; refresh linked handoff artifacts opportunistically"
    elif run["status"] in TERMINAL_RUN_STATUSES:
        resume_reason = f"run reached terminal status '{run['status']}'"
    else:
        resume_reason = f"run is already {run['status']}"

    epoch_value = (
        int(resume_epoch)
        if resume_epoch is not None
        else int(existing_status.get("resume_epoch", 0) if existing_status else 0)
    )
    return {
        "schema_version": 1,
        "entity_type": "resume-status",
        "id": run["id"],
        "run_id": run["id"],
        "thread_id": run["thread_id"],
        "mission_id": run["mission_id"],
        "latest_checkpoint_id": latest_checkpoint_id,
        "latest_checkpoint_path": latest_checkpoint_path,
        "resumable": resumable,
        "safe_to_resume": safe_to_resume,
        "resume_reason": resume_reason,
        "needs_handoff_refresh": needs_handoff_refresh,
        "stale_inputs": stale_inputs,
        "resume_plan": build_checkpoint_resume_plan(run, checkpoint_record),
        "idempotency_key": (
            str(idempotency_key).strip()
            if idempotency_key is not None
            else str(existing_status.get("idempotency_key", "") if existing_status else "").strip()
        ),
        "resume_epoch": max(epoch_value, 0),
        "updated_at": utc_now(),
        "metadata": metadata or {},
    }


def recovery_component_payload(
    *,
    path: Path | None,
    payload: dict[str, Any] | None,
    error: str,
    summary_fields: list[str],
) -> dict[str, Any]:
    if payload is not None:
        state = "present"
    elif path is not None and path.exists():
        state = "invalid"
    else:
        state = "missing"
    summary = {
        field: payload.get(field)
        for field in summary_fields
        if payload is not None and field in payload
    }
    return {
        "state": state,
        "path": path_reference(path) if path is not None else "",
        "error": error,
        "payload": summary,
    }


def recommended_recovery_bundle_command(run: dict[str, Any], resume_status_payload: dict[str, Any]) -> str:
    run_id = run["id"]
    if resume_status_payload.get("safe_to_resume"):
        return f"python3 scripts/hq_mission_runtime.py resume-run --run-id {run_id} --resumed-by <role>"
    if str(run.get("status") or "").strip() == "interrupted":
        return f"python3 scripts/hq_mission_runtime.py show-resume-status --run-id {run_id}"
    return f"python3 scripts/hq_mission_runtime.py show-run --run-id {run_id}"


def export_recovery_bundle(run_id: str) -> dict[str, Any]:
    run = require_file(run_path(run_id), "run", "run")
    checkpoint_state = load_latest_checkpoint_state(run)
    stored_status_file = resolve_runtime_reference(str(run.get("resume_status_path") or "").strip())
    if stored_status_file is None:
        stored_status_file = resume_status_path(run["id"])
    stored_status, stored_status_error = load_entity_safe(stored_status_file, "resume-status")
    effective_resume_status = build_resume_status_payload(
        run,
        existing_status=stored_status,
        checkpoint_state=checkpoint_state,
        metadata={"source": "export-recovery-bundle", "read_only": True},
    )
    checkpoint_record = checkpoint_state.get("record")
    checkpoint_file = checkpoint_state.get("file")
    checkpoint_payload = recovery_component_payload(
        path=checkpoint_file,
        payload=checkpoint_record,
        error=str(checkpoint_state.get("error") or "").strip(),
        summary_fields=[
            "id",
            "checkpoint_kind",
            "created_at",
            "source_event",
            "current_step_id",
            "resume_from_step_id",
            "last_successful_step_id",
            "latest_spec_path",
            "latest_handoff_path",
            "resume_packet_path",
        ],
    )
    stored_status_payload = recovery_component_payload(
        path=stored_status_file,
        payload=stored_status,
        error=stored_status_error,
        summary_fields=[
            "updated_at",
            "resumable",
            "safe_to_resume",
            "resume_reason",
            "needs_handoff_refresh",
            "resume_epoch",
            "idempotency_key",
        ],
    )
    issues: list[str] = []
    should_expect_checkpoint = bool(
        checkpoint_payload["path"] or str(run.get("latest_checkpoint_id") or "").strip()
    ) or str(run.get("status") or "").strip() == "interrupted"
    should_expect_resume_status = bool(
        str(run.get("resume_status_path") or "").strip()
    ) or str(run.get("status") or "").strip() == "interrupted"
    if should_expect_checkpoint and checkpoint_payload["state"] != "present":
        issues.append(
            f"checkpoint {checkpoint_payload['state']}: {checkpoint_payload['error'] or checkpoint_payload['path'] or 'unavailable'}"
        )
    if should_expect_resume_status and stored_status_payload["state"] != "present":
        issues.append(
            f"resume-status {stored_status_payload['state']}: {stored_status_payload['error'] or stored_status_payload['path'] or 'unavailable'}"
        )
    for item in effective_resume_status.get("stale_inputs", []) or []:
        issues.append(f"stale input: {item}")
    return {
        "schema_version": 1,
        "entity_type": "recovery-bundle",
        "run": {
            "id": run["id"],
            "status": run["status"],
            "actor": str(run.get("actor") or "").strip(),
            "updated_at": str(run.get("updated_at") or "").strip(),
            "thread_id": run["thread_id"],
            "mission_id": run["mission_id"],
            "current_step_id": str(run.get("current_step_id") or "").strip(),
            "resume_from_step_id": str(run.get("resume_from_step_id") or "").strip(),
            "latest_checkpoint_id": str(run.get("latest_checkpoint_id") or "").strip(),
            "latest_checkpoint_path": str(run.get("latest_checkpoint_path") or "").strip(),
            "resume_status_path": str(run.get("resume_status_path") or "").strip(),
            "interruption_state": run.get("interruption_state", {}),
        },
        "checkpoint": checkpoint_payload,
        "resume_status": {
            "effective_source": "derived",
            "effective": effective_resume_status,
            "stored": stored_status_payload,
        },
        "resume_context": resolve_resume_context(run_id=run["id"]),
        "issues": issues,
        "recommended_next_command": recommended_recovery_bundle_command(run, effective_resume_status),
        "generated_at": utc_now(),
        "read_only": True,
    }


def create_checkpoint_record(
    *,
    run: dict[str, Any],
    mission: dict[str, Any],
    thread: dict[str, Any],
    checkpoint_kind: str,
    source_step_id: str = "",
    source_event: str = "",
    created_at: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    checkpoint_id = make_id("checkpoint", f"{run['id']}-{checkpoint_kind}")
    checkpoint_created_at = created_at or utc_now()
    linked_paths = linked_recovery_paths(run, thread)
    checkpoint_file = checkpoint_path(checkpoint_id)
    checkpoint_file_reference = path_reference(checkpoint_file)
    trace_state_payload = normalize_trace_state(
        {
            **dict(run.get("trace_state", {})),
            "trace_id": run["id"],
            "current_step_id": str(run.get("current_step_id") or "").strip(),
            "resume_from_step_id": str(run.get("resume_from_step_id") or "").strip(),
            "checkpoint_id": checkpoint_id,
            "checkpoint_path": checkpoint_file_reference,
            "handoff_path": linked_paths["latest_handoff_path"],
            "resume_packet_path": linked_paths["resume_packet_path"],
            "snapshot_at": checkpoint_created_at,
        },
        grouping_id=run["thread_id"],
        default_trace_id=run["id"],
        snapshot_at=checkpoint_created_at,
    )
    payload = {
        "schema_version": 1,
        "entity_type": "checkpoint",
        "id": checkpoint_id,
        "thread_id": run["thread_id"],
        "mission_id": run["mission_id"],
        "run_id": run["id"],
        "checkpoint_kind": checkpoint_kind,
        "current_step_id": str(run.get("current_step_id") or "").strip(),
        "resume_from_step_id": str(run.get("resume_from_step_id") or "").strip(),
        "last_successful_step_id": str(run.get("last_successful_step_id") or "").strip(),
        "replay_basis": checkpoint_replay_basis(run),
        "execution_context": normalize_execution_context(run.get("execution_context", {})),
        "trace_state": trace_state_payload,
        "latest_spec_path": linked_paths["latest_spec_path"],
        "latest_handoff_path": linked_paths["latest_handoff_path"],
        "resume_packet_path": linked_paths["resume_packet_path"],
        "referenced_file_digests": {
            label: file_digest_for_reference(path_value)
            for label, path_value in linked_paths.items()
            if path_value
        },
        "created_at": checkpoint_created_at,
        "source_step_id": str(source_step_id or "").strip(),
        "source_event": str(source_event or "").strip(),
        "metadata": {},
    }
    write_entity(checkpoint_file, payload)
    run["latest_checkpoint_id"] = checkpoint_id
    run["latest_checkpoint_path"] = checkpoint_file_reference
    run_trace_state = dict(run.get("trace_state", {}))
    run_trace_state["checkpoint_id"] = checkpoint_id
    run_trace_state["checkpoint_path"] = checkpoint_file_reference
    run_trace_state["snapshot_at"] = checkpoint_created_at
    run["trace_state"] = normalize_trace_state(
        run_trace_state,
        grouping_id=run["thread_id"],
        default_trace_id=run["id"],
        snapshot_at=checkpoint_created_at,
    )
    interruption_state = dict(run.get("interruption_state", {}))
    if str(interruption_state.get("status") or "").strip() == "interrupted":
        interruption_state["checkpoint_id"] = checkpoint_id
        interruption_state["checkpoint_path"] = checkpoint_file_reference
        run["interruption_state"] = normalize_interruption_state(interruption_state)
    run["updated_at"] = checkpoint_created_at
    write_entity(run_path(run["id"]), run)
    thread = update_thread_context(
        thread["id"],
        mission_id=mission["id"],
        run_id=run["id"] if str(thread.get("active_run_id") or "").strip() else None,
        checkpoint_id=checkpoint_id,
        checkpoint_path=checkpoint_file_reference,
        trace_state=run["trace_state"],
        interruption_state=run["interruption_state"]
        if str(run.get("interruption_state", {}).get("status") or "").strip() == "interrupted"
        else None,
    )
    return payload, run, thread


def refresh_resume_status(
    run_id: str,
    *,
    idempotency_key: str | None = None,
    resume_epoch: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run = require_file(run_path(run_id), "run", "run")
    mission = require_file(mission_path(run["mission_id"]), "mission", "mission")
    thread = require_file(thread_path(run["thread_id"]), "thread", "thread")
    status_file = resume_status_path(run["id"])
    existing_status, _ = load_entity_safe(status_file, "resume-status")
    payload = build_resume_status_payload(
        run,
        existing_status=existing_status,
        checkpoint_state=load_latest_checkpoint_state(run),
        idempotency_key=idempotency_key,
        resume_epoch=resume_epoch,
        metadata=metadata,
    )
    write_entity(status_file, payload)
    run["resume_status_path"] = path_reference(status_file)
    write_entity(run_path(run["id"]), run)
    update_thread_context(
        thread["id"],
        mission_id=mission["id"],
        resume_status_path=path_reference(status_file),
    )
    return payload


def list_checkpoints_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    if args.limit < 1:
        print("error=limit must be >= 1")
        return 2
    try:
        run = require_file(run_path(args.run_id), "run", "run")
    except ValueError as exc:
        print(f"error={exc}")
        return 2
    payload = {
        "run_id": run["id"],
        "thread_id": run["thread_id"],
        "mission_id": run["mission_id"],
        "checkpoint_count": int(run.get("checkpoint_count", 0)),
        "checkpoints": checkpoint_history_for_run(run)[: args.limit],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def plan_replay_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    try:
        run = require_file(run_path(args.run_id), "run", "run")
        replay_plan = build_replay_plan(
            run,
            resume_from_step_id=str(args.resume_from_step_id or "").strip(),
        )
    except ValueError as exc:
        print(f"error={exc}")
        return 2
    payload = {
        "run_id": run["id"],
        "thread_id": run["thread_id"],
        "mission_id": run["mission_id"],
        "current_step_id": str(run.get("current_step_id") or "").strip(),
        "stored_resume_from_step_id": str(run.get("resume_from_step_id") or "").strip(),
        "replay_plan": replay_plan,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def request_approval(args: argparse.Namespace) -> dict[str, Any]:
    if args.policy_action not in ALLOWED_POLICY_ACTIONS:
        raise ValueError(
            "policy_action must be one of: " + ", ".join(sorted(ALLOWED_POLICY_ACTIONS))
        )
    run = require_file(run_path(args.run_id), "run", "run")
    step = require_file(step_path(args.step_id), "step", "step")
    mission = require_file(mission_path(run["mission_id"]), "mission", "mission")
    if step["run_id"] != run["id"]:
        raise ValueError("step does not belong to the provided run")
    approval_id = make_id("approval", f"{step['key']}-{args.requested_by or 'requester'}")
    created_at = utc_now()
    approval_key = normalize_approval_key(
        {
            "kind": str(getattr(args, "approval_kind", None) or "runtime_action").strip(),
            "namespace": str(getattr(args, "approval_namespace", None) or "hq.runtime").strip(),
            "name": str(getattr(args, "approval_name", None) or step["key"]).strip(),
            "call_id": str(getattr(args, "approval_call_id", None) or "").strip(),
            "action": getattr(args, "approval_action", None) or [args.policy_action],
        }
    )
    tool_scope = normalize_string_list(
        getattr(args, "tool_scope", None) or step.get("allowed_tool_classes", [])
    )
    policy_context = (
        getattr(args, "policy_context", None)
        if isinstance(getattr(args, "policy_context", None), dict)
        else {}
    )
    metadata = dict(args.metadata or {})
    approval_class = str(getattr(args, "approval_class", None) or "").strip()
    expires_at = str(getattr(args, "expires_at", None) or "").strip()
    if approval_class:
        metadata["approval_class"] = approval_class
    if expires_at:
        metadata["expires_at"] = expires_at
    payload = {
        "schema_version": 1,
        "entity_type": "approval",
        "id": approval_id,
        "thread_id": run["thread_id"],
        "mission_id": run["mission_id"],
        "run_id": run["id"],
        "step_id": step["id"],
        "requested_by": str(args.requested_by or "").strip(),
        "requested_for": str(args.requested_for or "founder").strip(),
        "policy_action": args.policy_action,
        "approval_key": approval_key,
        "status": "pending",
        "decision": "",
        "tool_scope": tool_scope,
        "policy_context": policy_context,
        "summary": str(args.summary or "").strip(),
        "rationale": "",
        "requested_at": created_at,
        "updated_at": created_at,
        "decided_at": "",
        "decided_by": "",
        "metadata": metadata,
    }
    write_entity(approval_path(approval_id), payload)
    run["approval_ids"] = list(dict.fromkeys([*run.get("approval_ids", []), approval_id]))
    run["status"] = "waiting_approval"
    run["updated_at"] = created_at
    trace_state = dict(run.get("trace_state", {}))
    trace_state["trace_id"] = run["id"]
    trace_state["current_step_id"] = step["id"]
    trace_state["snapshot_at"] = created_at
    run["trace_state"] = normalize_trace_state(
        trace_state,
        grouping_id=run["thread_id"],
        default_trace_id=run["id"],
        snapshot_at=created_at,
    )
    write_entity(run_path(run["id"]), run)
    if step["status"] != "waiting_approval":
        step["status"] = "waiting_approval"
        step["updated_at"] = created_at
        write_entity(step_path(step["id"]), step)
    record_event(
        event_type="approval_requested",
        entity_id=approval_id,
        summary=f"Requested approval for step '{step['key']}'.",
        payload={
            "run_id": run["id"],
            "step_id": step["id"],
            "policy_action": args.policy_action,
            "thread_id": run["thread_id"],
        },
        actor=payload["requested_by"] or run["actor"] or "runtime",
        correlation_id=run["id"],
    )
    emit_runtime_telemetry(
        event_type="approval_requested",
        status="waiting_approval",
        summary=f"Requested approval for step '{step['key']}'.",
        actor=payload["requested_by"],
        thread_id=run["thread_id"],
        mission_id=mission["id"],
        source_task_id=mission["source_task_id"],
        workflow=mission["workflow"],
        run_id=run["id"],
        step_id=step["id"],
        approval_id=payload["id"],
        metadata={
            "entity_type": "approval",
            "policy_action": payload["policy_action"],
            "approval_namespace": approval_key["namespace"],
            "approval_name": approval_key["name"],
            "approval_call_id": approval_key["call_id"],
            "tool_scope": payload["tool_scope"],
        },
    )
    emit_runtime_hook_event(
        event="approval_requested",
        action=["hq", "approval", "request"],
        status="waiting_approval",
        summary=f"Requested approval for step '{step['key']}'.",
        actor=payload["requested_by"] or "runtime",
        decision=payload["policy_action"],
        thread_id=run["thread_id"],
        mission_id=mission["id"],
        run_id=run["id"],
        step_id=step["id"],
        approval_id=payload["id"],
        namespace=approval_key["namespace"],
        tool_name=approval_key["name"],
        call_id=approval_key["call_id"] or payload["id"],
        metadata={"policy_action": payload["policy_action"], "tool_scope": payload["tool_scope"]},
    )
    update_thread_context(
        run["thread_id"],
        mission_id=mission["id"],
        run_id=run["id"],
        status="paused",
        trace_state=run["trace_state"],
    )
    return payload


def request_approval_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    try:
        payload = request_approval(args)
    except (ValueError, RuntimeError) as exc:
        print(f"error={exc}")
        return 2
    print(f"approval_id={payload['id']}")
    print(f"approval_file={approval_path(payload['id'])}")
    return 0


def decide_approval(args: argparse.Namespace) -> dict[str, Any]:
    if args.decision not in ALLOWED_APPROVAL_DECISIONS:
        raise ValueError("decision must be one of: " + ", ".join(sorted(ALLOWED_APPROVAL_DECISIONS)))
    approval = require_file(approval_path(args.approval_id), "approval", "approval")
    run = require_file(run_path(approval["run_id"]), "run", "run")
    step = require_file(step_path(approval["step_id"]), "step", "step")
    mission = require_file(mission_path(run["mission_id"]), "mission", "mission")
    if step["run_id"] != run["id"]:
        raise ValueError("approval step does not belong to approval run")
    decided_at = utc_now()
    approval["decision"] = args.decision
    approval["status"] = "decided"
    approval["rationale"] = str(args.rationale or "").strip()
    approval["decided_by"] = str(args.decided_by or "").strip()
    approval["decided_at"] = decided_at
    approval["updated_at"] = decided_at
    write_entity(approval_path(approval["id"]), approval)
    if args.decision == "approved":
        run["status"] = "running"
    elif args.decision == "rejected":
        run["status"] = "blocked"
    else:
        run["status"] = "blocked"
    run["updated_at"] = decided_at
    trace_state = dict(run.get("trace_state", {}))
    trace_state["trace_id"] = run["id"]
    trace_state["current_step_id"] = step["id"]
    trace_state["snapshot_at"] = decided_at
    run["trace_state"] = normalize_trace_state(
        trace_state,
        grouping_id=run["thread_id"],
        default_trace_id=run["id"],
        snapshot_at=decided_at,
    )
    write_entity(run_path(run["id"]), run)
    step["metadata"] = step.get("metadata", {})
    step["metadata"]["approval_decision"] = args.decision
    step["updated_at"] = decided_at
    write_entity(step_path(step["id"]), step)
    record_event(
        event_type="approval_decided",
        entity_id=approval["id"],
        summary=f"Approval decision '{args.decision}' recorded.",
        payload={"run_id": run["id"], "step_id": step["id"], "decided_by": approval["decided_by"]},
        actor=approval["decided_by"] or "runtime",
        correlation_id=run["id"],
    )
    emit_runtime_telemetry(
        event_type="approval_decided",
        status=args.decision,
        summary=f"Approval decision '{args.decision}' recorded.",
        actor=approval["decided_by"] or "runtime",
        thread_id=run["thread_id"],
        mission_id=mission["id"],
        source_task_id=mission["source_task_id"],
        workflow=mission["workflow"],
        run_id=run["id"],
        step_id=step["id"],
        approval_id=approval["id"],
        metadata={"entity_type": "approval"},
    )
    update_thread_context(
        run["thread_id"],
        mission_id=mission["id"],
        run_id=run["id"],
        status="paused" if run["status"] == "blocked" else "active",
        trace_state=run["trace_state"],
    )
    return approval


def create_handoff_record(
    *,
    thread_id: str,
    task: str,
    session: str,
    handoff_file: str,
    owner: str = "",
    status: str = "ready_for_handoff",
    accepting_role: str = "",
    continue_from: str = "",
    spec_file: str = "",
    primary_file: str = "",
    read_first: list[str] | None = None,
    done_items: list[str] | None = None,
    next_steps: list[str] | None = None,
    important_files: list[str] | None = None,
    risks: list[str] | None = None,
    blockers: list[str] | None = None,
    notes: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if status not in ALLOWED_HANDOFF_STATUSES:
        raise ValueError("handoff status must be one of: " + ", ".join(sorted(ALLOWED_HANDOFF_STATUSES)))
    thread, mission, active_run = ensure_packet_runtime(
        thread_id=thread_id,
        task=task,
        owner=owner,
        goal=f"Handoff packet for {task}",
    )
    mission_id = mission["id"]
    run_id = active_run["id"]
    created_at = utc_now()
    handoff_id = make_id("handoff", f"{task}-{session}")
    payload = {
        "schema_version": 1,
        "entity_type": "handoff",
        "id": handoff_id,
        "thread_id": thread_id,
        "mission_id": str(mission_id or "").strip(),
        "run_id": str(run_id or "").strip(),
        "task": task.strip(),
        "session": session.strip(),
        "owner": str(owner or "").strip(),
        "status": status,
        "accepting_role": str(accepting_role or "").strip(),
        "continue_from": str(continue_from or "").strip(),
        "spec_file": str(spec_file or "").strip(),
        "primary_file": str(primary_file or "").strip(),
        "handoff_path": handoff_file.strip(),
        "read_first": normalize_string_list(read_first),
        "done_items": normalize_string_list(done_items),
        "next_steps": normalize_string_list(next_steps),
        "important_files": normalize_string_list(important_files),
        "risks": normalize_string_list(risks),
        "blockers": normalize_string_list(blockers),
        "notes": normalize_string_list(notes),
        "created_at": created_at,
        "updated_at": created_at,
        "metadata": metadata or {},
    }
    payload["metadata"]["execution_context"] = dict(thread.get("execution_context", {}))
    write_entity(handoff_path(handoff_id), payload)
    run = require_file(run_path(run_id), "run", "run")
    run["handoff_ids"] = list(dict.fromkeys([*run.get("handoff_ids", []), handoff_id]))
    trace_state = dict(run.get("trace_state", {}))
    trace_state["handoff_id"] = handoff_id
    trace_state["handoff_path"] = handoff_file
    trace_state["resume_packet_path"] = handoff_file
    trace_state["session_id"] = run["execution_context"]["session_id"]
    trace_state["work_dir"] = run["execution_context"]["work_dir"]
    trace_state["snapshot_at"] = created_at
    run["trace_state"] = normalize_trace_state(
        trace_state,
        grouping_id=thread_id,
        default_trace_id=run["id"],
        snapshot_at=created_at,
    )
    run["updated_at"] = created_at
    write_entity(run_path(run["id"]), run)
    trace_state_payload = run["trace_state"]
    update_thread_context(
        thread_id,
        mission_id=mission_id,
        run_id=run_id,
        handoff_id=handoff_id,
        handoff_path=handoff_file,
        resume_packet_path=handoff_file,
        status="paused" if payload["blockers"] else "active",
        execution_context=dict(thread.get("execution_context", {})),
        trace_state=trace_state_payload,
    )
    step = record_packet_step(
        thread_id=thread_id,
        task=task,
        packet_kind="handoff",
        packet_path=handoff_file,
        owner=owner,
        metadata={"handoff_id": handoff_id},
    )
    payload = require_file(handoff_path(handoff_id), "handoff", "handoff")
    payload["metadata"] = dict(payload.get("metadata", {}))
    payload["metadata"]["step_id"] = step["id"]
    write_entity(handoff_path(handoff_id), payload)
    record_event(
        event_type="handoff_recorded",
        entity_id=handoff_id,
        summary=f"Recorded handoff for task '{payload['task']}'.",
        payload={"thread_id": thread_id, "run_id": run_id, "handoff_path": handoff_file},
        actor=payload["owner"] or "runtime",
        correlation_id=run_id or thread_id,
    )
    emit_runtime_telemetry(
        event_type="handoff_recorded",
        status=payload["status"],
        summary=f"Recorded handoff for task '{payload['task']}'.",
        actor=payload["owner"] or "runtime",
        thread_id=thread_id,
        mission_id=payload["mission_id"],
        run_id=payload["run_id"],
        handoff_id=handoff_id,
        metadata={"entity_type": "handoff", "handoff_path": handoff_file},
    )
    emit_runtime_hook_event(
        event="agent_handoff",
        action=["hq", "agent", "handoff"],
        status=payload["status"],
        summary=f"Recorded handoff for task '{payload['task']}'.",
        actor=payload["owner"] or "runtime",
        thread_id=thread_id,
        mission_id=payload["mission_id"],
        run_id=payload["run_id"],
        handoff_id=handoff_id,
        tool_name="handoff",
        call_id=handoff_id,
        metadata={"handoff_path": handoff_file},
    )
    emit_runtime_hook_event(
        event="handoff_written",
        action=["hq", "handoff", "write"],
        status=payload["status"],
        summary=f"Wrote handoff packet for task '{payload['task']}'.",
        actor=payload["owner"] or "runtime",
        thread_id=thread_id,
        mission_id=payload["mission_id"],
        run_id=payload["run_id"],
        handoff_id=handoff_id,
        tool_name="handoff",
        call_id=handoff_id,
        metadata={"handoff_path": handoff_file},
    )
    return payload


def decide_approval_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    try:
        payload = decide_approval(args)
    except (ValueError, RuntimeError) as exc:
        print(f"error={exc}")
        return 2
    print(f"approval_id={payload['id']}")
    print(f"decision={payload['decision']}")
    return 0


def attach_artifact(args: argparse.Namespace) -> dict[str, Any]:
    run = require_file(run_path(args.run_id), "run", "run")
    step = require_file(step_path(args.step_id), "step", "step")
    mission = require_file(mission_path(run["mission_id"]), "mission", "mission")
    if step["run_id"] != run["id"]:
        raise ValueError("step does not belong to the provided run")
    artifact_id = make_id("artifact", f"{args.kind}-{Path(args.path).name}")
    created_at = utc_now()
    payload = {
        "schema_version": 1,
        "entity_type": "artifact",
        "id": artifact_id,
        "thread_id": run["thread_id"],
        "mission_id": run["mission_id"],
        "run_id": run["id"],
        "step_id": step["id"],
        "kind": str(args.kind or "").strip(),
        "path": str(args.path or "").strip(),
        "summary": str(args.summary or "").strip(),
        "created_at": created_at,
        "updated_at": created_at,
        "metadata": args.metadata or {},
    }
    write_entity(artifact_path(artifact_id), payload)
    run["artifact_ids"] = list(dict.fromkeys([*run.get("artifact_ids", []), artifact_id]))
    run["updated_at"] = created_at
    write_entity(run_path(run["id"]), run)
    record_event(
        event_type="artifact_attached",
        entity_id=artifact_id,
        summary=f"Attached artifact '{payload['kind']}'.",
        payload={
            "run_id": run["id"],
            "step_id": step["id"],
            "path": payload["path"],
            "thread_id": run["thread_id"],
        },
        actor=step["actor"] or run["actor"] or "runtime",
        correlation_id=run["id"],
    )
    emit_runtime_telemetry(
        event_type="artifact_attached",
        status="attached",
        summary=f"Attached artifact '{payload['kind']}'.",
        actor=step["actor"] or run["actor"] or "runtime",
        thread_id=run["thread_id"],
        mission_id=mission["id"],
        source_task_id=mission["source_task_id"],
        workflow=mission["workflow"],
        run_id=run["id"],
        step_id=step["id"],
        artifact_id=payload["id"],
        metadata={"entity_type": "artifact", "path": payload["path"]},
    )
    return payload


def attach_artifact_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    try:
        payload = attach_artifact(args)
    except (ValueError, RuntimeError) as exc:
        print(f"error={exc}")
        return 2
    print(f"artifact_id={payload['id']}")
    print(f"artifact_file={artifact_path(payload['id'])}")
    return 0


def verify_run(args: argparse.Namespace) -> dict[str, Any]:
    verification_status = str(args.status or "verified").strip()
    if verification_status not in {"verified", "failed", "changes_requested"}:
        raise ValueError(
            "verification status must be one of: changes_requested, failed, verified"
        )
    run = require_file(run_path(args.run_id), "run", "run")
    verification_stages = normalize_verification_stages(run.get("verification_stages", []))
    verification_state = normalize_verification_state(
        run.get("verification_state", {}),
        stages=verification_stages,
        default_return_target=run["actor"],
    )
    actor = str(args.actor or "").strip()
    summary = str(args.summary or "").strip()
    evidence = getattr(args, "evidence", []) or []
    metadata = args.metadata or {}

    step_key = "verification"
    step_status = "completed" if verification_status != "failed" else "failed"
    next_state_payload: dict[str, Any]

    if not verification_stages:
        if verification_status == "changes_requested":
            raise ValueError("changes_requested requires a configured verification stage workflow")
        next_state_payload = {
            "status": verification_status,
            "last_decision": "",
            "last_decision_note": "",
        }
    else:
        current_stage = verification_stage_by_id(
            verification_stages,
            verification_state["current_stage_id"],
        )
        if current_stage is None:
            raise ValueError("verification workflow has no active stage")

        if (
            verification_state["status"] == "changes_requested"
            and actor == verification_state["return_target"]
        ):
            if verification_status != "verified":
                raise ValueError("changes-requested work must be resubmitted with status 'verified'")
            step_key = "verification-resubmission"
            next_state_payload = {
                "status": "pending",
                "current_stage_id": current_stage["id"],
                "current_stage_type": current_stage["type"],
                "current_participant": current_stage["participant"],
                "return_target": verification_state["return_target"],
                "completed_stage_ids": verification_state["completed_stage_ids"],
                "last_decision": verification_state["last_decision"],
                "last_decision_note": verification_state["last_decision_note"],
            }
        else:
            if actor != verification_state["current_participant"]:
                raise ValueError(
                    "only the active reviewer or approver can advance the current verification stage"
                )
            step_key = f"verification-{current_stage['type']}"
            if verification_status == "changes_requested":
                if not verification_state["return_target"]:
                    raise ValueError(
                        "verification workflow has no return target for changes_requested"
                    )
                next_state_payload = {
                    "status": "changes_requested",
                    "current_stage_id": current_stage["id"],
                    "current_stage_type": current_stage["type"],
                    "current_participant": verification_state["return_target"],
                    "return_target": verification_state["return_target"],
                    "completed_stage_ids": verification_state["completed_stage_ids"],
                    "last_decision": "changes_requested",
                    "last_decision_note": summary,
                }
            elif verification_status == "failed":
                step_status = "failed"
                next_state_payload = {
                    "status": "failed",
                    "current_stage_id": current_stage["id"],
                    "current_stage_type": current_stage["type"],
                    "current_participant": actor,
                    "return_target": verification_state["return_target"],
                    "completed_stage_ids": verification_state["completed_stage_ids"],
                    "last_decision": verification_state["last_decision"],
                    "last_decision_note": verification_state["last_decision_note"],
                }
            else:
                completed_stage_ids = normalize_string_list(
                    [
                        *verification_state["completed_stage_ids"],
                        current_stage["id"],
                    ]
                )
                next_stage = next_verification_stage(verification_stages, completed_stage_ids)
                next_state_payload = {
                    "status": "verified" if next_stage is None else "pending",
                    "current_stage_id": "" if next_stage is None else next_stage["id"],
                    "current_stage_type": "" if next_stage is None else next_stage["type"],
                    "current_participant": "" if next_stage is None else next_stage["participant"],
                    "return_target": verification_state["return_target"],
                    "completed_stage_ids": completed_stage_ids,
                    "last_decision": "approved",
                    "last_decision_note": summary,
                }

    step = checkpoint_step(
        argparse.Namespace(
            run_id=args.run_id,
            key=step_key,
            actor=actor,
            status=step_status,
            error_type="",
            summary=summary,
            evidence=evidence,
            metadata=metadata,
        )
    )
    run = require_file(run_path(args.run_id), "run", "run")
    run["verification_state"] = normalize_verification_state(
        {
            "status": next_state_payload["status"],
            "step_id": step["id"],
            "summary": step["summary"],
            "evidence": step["evidence"],
            "verified_at": step["updated_at"],
            "verified_by": step["actor"],
            "current_stage_id": next_state_payload.get("current_stage_id", ""),
            "current_stage_type": next_state_payload.get("current_stage_type", ""),
            "current_participant": next_state_payload.get("current_participant", ""),
            "return_target": next_state_payload.get("return_target", ""),
            "completed_stage_ids": next_state_payload.get("completed_stage_ids", []),
            "last_decision": next_state_payload.get("last_decision", ""),
            "last_decision_note": next_state_payload.get("last_decision_note", ""),
            "metadata": step["metadata"],
        },
        stages=verification_stages,
        default_return_target=run["actor"],
    )
    run["updated_at"] = utc_now()
    write_entity(run_path(run["id"]), run)
    return run


def verify_run_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    try:
        payload = verify_run(args)
    except (ValueError, RuntimeError) as exc:
        print(f"error={exc}")
        return 2
    print(f"run_id={payload['id']}")
    print(f"verification_status={payload['verification_state']['status']}")
    print(f"verification_step_id={payload['verification_state']['step_id']}")
    return 0


def finish_run(args: argparse.Namespace) -> dict[str, Any]:
    run = require_file(run_path(args.run_id), "run", "run")
    mission = require_file(mission_path(run["mission_id"]), "mission", "mission")
    thread = require_file(thread_path(run["thread_id"]), "thread", "thread")
    verification_stages = normalize_verification_stages(run.get("verification_stages", []))
    verification_state = normalize_verification_state(
        run.get("verification_state", {}),
        stages=verification_stages,
        default_return_target=run["actor"],
    )
    if args.status == "completed" and verification_state["status"] != "verified":
        raise ValueError("run cannot be completed before a verification stage is recorded")
    if args.status == "completed" and verification_stages:
        required_stage_ids = [stage["id"] for stage in verification_stages]
        if (
            verification_state["current_stage_id"]
            or verification_state["completed_stage_ids"] != required_stage_ids
        ):
            raise ValueError("run cannot be completed before the verification stage workflow is closed")
    _checkpoint, run, thread = create_checkpoint_record(
        run=run,
        mission=mission,
        thread=thread,
        checkpoint_kind="pre_finish",
        source_event="finish-run",
    )
    finished_at = utc_now()
    run["status"] = args.status
    run["interruption_state"] = normalize_interruption_state({})
    run["finished_at"] = finished_at
    run["updated_at"] = finished_at
    trace_state = dict(run.get("trace_state", {}))
    trace_state["trace_id"] = run["id"]
    trace_state["snapshot_at"] = finished_at
    run["trace_state"] = normalize_trace_state(
        trace_state,
        grouping_id=thread["id"],
        default_trace_id=run["id"],
        snapshot_at=finished_at,
    )
    write_entity(run_path(run["id"]), run)
    record_run_feedback_finish(
        mission=mission,
        run=run,
        status=args.status,
        parent_id=str((run.get("metadata") or {}).get("feedback_iteration_id") or ""),
    )
    mission["status"] = "completed" if args.status == "completed" else args.status
    mission["updated_at"] = finished_at
    write_entity(mission_path(mission["id"]), mission)
    dispatch_actor = str(getattr(args, "dispatch_next_queued_by", None) or "").strip()
    queued_runs = queued_runs_for_thread(thread["id"]) if dispatch_actor else []
    update_thread_context(
        thread["id"],
        mission_id=mission["id"],
        run_id="",
        status="idle" if args.status == "completed" else "paused",
        interruption_state=normalize_interruption_state({}),
        trace_state=run["trace_state"],
    )
    refresh_resume_status(
        run["id"],
        metadata={"run_status": run["status"]},
    )
    record_event(
        event_type="run_finished",
        entity_id=run["id"],
        summary=f"Finished run with status '{args.status}'.",
        payload={"mission_id": mission["id"], "thread_id": thread["id"]},
        actor=run["actor"] or mission["owner"] or "runtime",
        correlation_id=run["id"],
    )
    emit_runtime_telemetry(
        event_type="run_finished",
        status=args.status,
        summary=f"Finished run with status '{args.status}'.",
        actor=run["actor"] or mission["owner"] or "runtime",
        thread_id=thread["id"],
        mission_id=mission["id"],
        source_task_id=mission["source_task_id"],
        workflow=mission["workflow"],
        run_id=run["id"],
        metadata={"entity_type": "run"},
    )
    emit_runtime_hook_event(
        event="run_finished",
        action=["hq", "run", "finish"],
        status=args.status,
        summary=f"Finished run with status '{args.status}'.",
        actor=run["actor"] or mission["owner"] or "runtime",
        thread_id=thread["id"],
        mission_id=mission["id"],
        run_id=run["id"],
        tool_name="run",
        call_id=run["id"],
        metadata={"verification_status": run["verification_state"]["status"]},
    )
    if not queued_runs:
        return {"finished_run": run}

    next_run = activate_queued_run(
        queued_runs[0],
        thread=require_file(thread_path(thread["id"]), "thread", "thread"),
        mission=require_file(mission_path(queued_runs[0]["mission_id"]), "mission", "mission"),
        activated_by=dispatch_actor,
    )
    return {
        "finished_run": run,
        "dispatched_run": next_run,
    }


def finish_run_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    try:
        payload = finish_run(args)
    except (ValueError, RuntimeError) as exc:
        print(f"error={exc}")
        return 2
    print(f"run_id={payload['finished_run']['id']}")
    print(f"status={payload['finished_run']['status']}")
    if payload.get("dispatched_run"):
        print(f"dispatched_run_id={payload['dispatched_run']['id']}")
        print(f"dispatched_run_status={payload['dispatched_run']['status']}")
    return 0


def show_run_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    try:
        payload = require_file(run_path(args.run_id), "run", "run")
    except ValueError as exc:
        print(f"error={exc}")
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def interrupt_run(args: argparse.Namespace) -> dict[str, Any]:
    run = require_file(run_path(args.run_id), "run", "run")
    if run["status"] in TERMINAL_RUN_STATUSES:
        raise ValueError(f"run already reached terminal status '{run['status']}'")
    mission = require_file(mission_path(run["mission_id"]), "mission", "mission")
    thread = require_file(thread_path(run["thread_id"]), "thread", "thread")
    interrupted_at = utc_now()
    interruption_state = normalize_interruption_state(
        {
            "status": "interrupted",
            "reason": str(args.reason or "").strip(),
            "requested_by": str(args.requested_by or "").strip(),
            "interrupted_at": interrupted_at,
            "resume_from_step_id": str(
                run.get("resume_from_step_id") or run.get("current_step_id") or ""
            ).strip(),
            "metadata": args.metadata or {},
        }
    )
    run["status"] = "interrupted"
    run["interruption_state"] = interruption_state
    run["updated_at"] = interrupted_at
    trace_state = dict(run.get("trace_state", {}))
    trace_state["trace_id"] = run["id"]
    trace_state["snapshot_at"] = interrupted_at
    trace_metadata = dict(trace_state.get("metadata", {}))
    trace_metadata["interruption"] = interruption_state
    trace_state["metadata"] = trace_metadata
    run["trace_state"] = normalize_trace_state(
        trace_state,
        grouping_id=run["thread_id"],
        default_trace_id=run["id"],
        snapshot_at=interrupted_at,
    )
    write_entity(run_path(run["id"]), run)
    _checkpoint, run, thread = create_checkpoint_record(
        run=run,
        mission=mission,
        thread=thread,
        checkpoint_kind="interrupt",
        source_event="interrupt-run",
        created_at=interrupted_at,
    )
    update_thread_context(
        thread["id"],
        mission_id=mission["id"],
        run_id=run["id"],
        status="interrupted",
        interruption_state=run["interruption_state"],
        trace_state=run["trace_state"],
    )
    refresh_resume_status(
        run["id"],
        metadata={"run_status": run["status"], "interrupted_by": interruption_state["requested_by"]},
    )
    run = require_file(run_path(run["id"]), "run", "run")
    record_event(
        event_type="run_interrupted",
        entity_id=run["id"],
        summary=f"Interrupted run '{run['id']}'.",
        payload={
            "mission_id": mission["id"],
            "thread_id": thread["id"],
            "requested_by": interruption_state["requested_by"],
        },
        actor=interruption_state["requested_by"] or run["actor"] or "runtime",
        correlation_id=run["id"],
    )
    emit_runtime_telemetry(
        event_type="run_interrupted",
        status="interrupted",
        summary=f"Interrupted run '{run['id']}'.",
        actor=interruption_state["requested_by"] or run["actor"] or "runtime",
        thread_id=thread["id"],
        mission_id=mission["id"],
        source_task_id=mission["source_task_id"],
        workflow=mission["workflow"],
        run_id=run["id"],
        step_id=run["current_step_id"],
        metadata={"entity_type": "run", "resume_from_step_id": interruption_state["resume_from_step_id"]},
    )
    emit_runtime_hook_event(
        event="run_interrupted",
        action=["hq", "run", "interrupt"],
        status="interrupted",
        summary=f"Interrupted run '{run['id']}'.",
        actor=interruption_state["requested_by"] or run["actor"] or "runtime",
        thread_id=thread["id"],
        mission_id=mission["id"],
        run_id=run["id"],
        step_id=run["current_step_id"],
        tool_name="run",
        call_id=run["id"],
        metadata={"resume_from_step_id": interruption_state["resume_from_step_id"]},
    )
    return run


def interrupt_run_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    try:
        payload = interrupt_run(args)
    except (ValueError, RuntimeError) as exc:
        print(f"error={exc}")
        return 2
    print(f"run_id={payload['id']}")
    print(f"status={payload['status']}")
    print(f"resume_from_step_id={payload['interruption_state']['resume_from_step_id']}")
    return 0


def resume_run(args: argparse.Namespace) -> dict[str, Any]:
    run = require_file(run_path(args.run_id), "run", "run")
    resume_token = str(getattr(args, "resume_token", None) or uuid.uuid4().hex[:12]).strip()
    existing_status, _ = load_entity_safe(resume_status_path(run["id"]), "resume-status")
    if run["status"] != "interrupted":
        if (
            existing_status is not None
            and resume_token
            and str(existing_status.get("idempotency_key") or "").strip() == resume_token
        ):
            return run
        refresh_resume_status(
            run["id"],
            metadata={"run_status": run["status"]},
        )
        raise ValueError(f"run status must be 'interrupted', got '{run['status']}'")
    mission = require_file(mission_path(run["mission_id"]), "mission", "mission")
    thread = require_file(thread_path(run["thread_id"]), "thread", "thread")
    if not str(run.get("latest_checkpoint_id") or "").strip() and not str(
        run.get("latest_checkpoint_path") or ""
    ).strip():
        _checkpoint, run, thread = create_checkpoint_record(
            run=run,
            mission=mission,
            thread=thread,
            checkpoint_kind="interrupt",
            source_event="resume-run-legacy-bootstrap",
        )
    pre_status = refresh_resume_status(
        run["id"],
        metadata={"run_status": run["status"]},
    )
    if not pre_status["resumable"] or not pre_status["safe_to_resume"]:
        raise ValueError(f"run is not safe to resume: {pre_status['resume_reason']}")
    existing_epoch = int(existing_status.get("resume_epoch", 0) if existing_status else 0)
    new_epoch = existing_epoch if (
        existing_status is not None
        and resume_token
        and str(existing_status.get("idempotency_key") or "").strip() == resume_token
    ) else existing_epoch + 1
    run = require_file(run_path(args.run_id), "run", "run")
    resumed_at = utc_now()
    target_step_id = str(getattr(args, "resume_from_step_id", None) or "").strip()
    replay_plan = build_replay_plan(run, resume_from_step_id=target_step_id)
    if target_step_id:
        run["resume_from_step_id"] = replay_plan["resume_from_step_id"]
        run["current_step_id"] = replay_plan["resume_from_step_id"]
    run["status"] = "running"
    run["interruption_state"] = normalize_interruption_state({})
    run["updated_at"] = resumed_at
    trace_state = dict(run.get("trace_state", {}))
    trace_state["trace_id"] = run["id"]
    trace_state["current_step_id"] = run["current_step_id"]
    trace_state["resume_from_step_id"] = run["resume_from_step_id"]
    trace_state["snapshot_at"] = resumed_at
    trace_metadata = dict(trace_state.get("metadata", {}))
    trace_metadata["resumed_by"] = str(args.resumed_by or "").strip()
    if replay_plan["replay_required"]:
        trace_metadata["replay"] = {
            "resume_from_step_id": replay_plan["resume_from_step_id"],
            "replay_steps": replay_plan["steps_to_replay"],
            "replay_step_ids": [step["step_id"] for step in replay_plan["steps_to_replay"]],
            "checkpoint_count_after_target": replay_plan["checkpoint_count_after_target"],
            "remaining_replay_step_count": replay_plan["replay_step_count"],
            "planned_at": resumed_at,
        }
    else:
        trace_metadata.pop("replay", None)
    if target_step_id:
        trace_metadata["resume_target_step_id"] = run["resume_from_step_id"]
    else:
        trace_metadata.pop("resume_target_step_id", None)
    trace_state["metadata"] = trace_metadata
    run["trace_state"] = normalize_trace_state(
        trace_state,
        grouping_id=run["thread_id"],
        default_trace_id=run["id"],
        snapshot_at=resumed_at,
    )
    write_entity(run_path(run["id"]), run)
    update_thread_context(
        thread["id"],
        mission_id=mission["id"],
        run_id=run["id"],
        status="active",
        interruption_state=normalize_interruption_state({}),
        trace_state=run["trace_state"],
    )
    record_event(
        event_type="run_resumed",
        entity_id=run["id"],
        summary=f"Resumed run '{run['id']}'.",
        payload={
            "mission_id": mission["id"],
            "thread_id": thread["id"],
            "resumed_by": str(args.resumed_by or "").strip(),
        },
        actor=str(args.resumed_by or "").strip() or run["actor"] or "runtime",
        correlation_id=run["id"],
    )
    emit_runtime_telemetry(
        event_type="run_resumed",
        status="running",
        summary=f"Resumed run '{run['id']}'.",
        actor=str(args.resumed_by or "").strip() or run["actor"] or "runtime",
        thread_id=thread["id"],
        mission_id=mission["id"],
        source_task_id=mission["source_task_id"],
        workflow=mission["workflow"],
        run_id=run["id"],
        step_id=run["current_step_id"],
        metadata={"entity_type": "run", "resume_from_step_id": run["resume_from_step_id"]},
    )
    emit_runtime_hook_event(
        event="run_resumed",
        action=["hq", "run", "resume"],
        status="running",
        summary=f"Resumed run '{run['id']}'.",
        actor=str(args.resumed_by or "").strip() or run["actor"] or "runtime",
        thread_id=thread["id"],
        mission_id=mission["id"],
        run_id=run["id"],
        step_id=run["current_step_id"],
        tool_name="run",
        call_id=run["id"],
        metadata={
            "resume_from_step_id": run["resume_from_step_id"],
            "replay_required": replay_plan["replay_required"],
            "replay_step_count": replay_plan["replay_step_count"],
        },
    )
    refresh_resume_status(
        run["id"],
        idempotency_key=resume_token,
        resume_epoch=new_epoch,
        metadata={
            "run_status": run["status"],
            "resumed_by": str(args.resumed_by or "").strip(),
            "replay_required": replay_plan["replay_required"],
        },
    )
    run = require_file(run_path(run["id"]), "run", "run")
    return run


def resume_run_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    try:
        payload = resume_run(args)
    except (ValueError, RuntimeError) as exc:
        print(f"error={exc}")
        return 2
    print(f"run_id={payload['id']}")
    print(f"status={payload['status']}")
    print(f"resume_from_step_id={payload['resume_from_step_id']}")
    return 0


def show_resume_status_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    try:
        payload = refresh_resume_status(args.run_id)
    except (ValueError, RuntimeError) as exc:
        print(f"error={exc}")
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def export_recovery_bundle_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    try:
        payload = export_recovery_bundle(args.run_id)
    except (ValueError, RuntimeError) as exc:
        print(f"error={exc}")
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def resolve_resume_context(*, thread_id: str = "", run_id: str = "") -> dict[str, Any]:
    if not thread_id and not run_id:
        raise ValueError("resume context requires either thread_id or run_id")

    run: dict[str, Any] | None = None
    if run_id:
        run = require_file(run_path(run_id), "run", "run")
        thread = require_file(thread_path(run["thread_id"]), "thread", "thread")
    else:
        thread = require_file(thread_path(thread_id), "thread", "thread")
        active_run_id = str(thread.get("active_run_id") or "").strip()
        if active_run_id:
            run = require_file(run_path(active_run_id), "run", "run")

    execution_context = (
        dict(run.get("execution_context", {}))
        if run is not None
        else dict(thread.get("execution_context", {}))
    )
    trace_state = dict(thread.get("trace_state", {}))
    if run is not None:
        trace_state["current_step_id"] = run["trace_state"]["current_step_id"]
        trace_state["resume_from_step_id"] = run["trace_state"]["resume_from_step_id"]
        trace_state["handoff_id"] = run["trace_state"]["handoff_id"] or trace_state.get("handoff_id", "")
        trace_state["handoff_path"] = run["trace_state"]["handoff_path"] or trace_state.get(
            "handoff_path", ""
        )
        trace_state["resume_packet_path"] = run["trace_state"]["resume_packet_path"] or trace_state.get(
            "resume_packet_path", ""
        )

    return {
        "thread_id": thread["id"],
        "mission_id": str(thread.get("active_mission_id") or "").strip(),
        "run_id": run["id"] if run is not None else str(thread.get("active_run_id") or "").strip(),
        "session_id": str(execution_context.get("session_id") or "").strip(),
        "work_dir": str(execution_context.get("work_dir") or "").strip(),
        "runtime_home": str(execution_context.get("runtime_home") or "").strip(),
        "runtime_home_mode": str(execution_context.get("runtime_home_mode") or "none").strip(),
        "scope": str(execution_context.get("scope") or "none").strip(),
        "parent_session_id": str(execution_context.get("parent_session_id") or "").strip(),
        "blocked_tool_classes": normalize_string_list(
            execution_context.get("blocked_tool_classes")
            if isinstance(execution_context.get("blocked_tool_classes"), list)
            else []
        ),
        "handoff_id": str(trace_state.get("handoff_id") or "").strip(),
        "handoff_path": str(trace_state.get("handoff_path") or "").strip(),
        "resume_packet_path": str(trace_state.get("resume_packet_path") or "").strip(),
        "current_step_id": str(trace_state.get("current_step_id") or "").strip(),
        "resume_from_step_id": str(trace_state.get("resume_from_step_id") or "").strip(),
        "replay": (
            dict(trace_state.get("metadata", {}).get("replay", {}))
            if isinstance(trace_state.get("metadata"), dict)
            else {}
        ),
        "replay_completed_at": (
            str(trace_state.get("metadata", {}).get("replay_completed_at") or "").strip()
            if isinstance(trace_state.get("metadata"), dict)
            else ""
        ),
        "interruption_state": (
            run["interruption_state"]
            if run is not None
            else normalize_interruption_state(thread.get("interruption_state", {}))
        ),
    }


def resume_context_command(args: argparse.Namespace) -> int:
    ensure_runtime()
    try:
        payload = resolve_resume_context(
            thread_id=str(getattr(args, "thread_id", None) or "").strip(),
            run_id=str(getattr(args, "run_id", None) or "").strip(),
        )
    except ValueError as exc:
        print(f"error={exc}")
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Additive durable mission runtime nucleus for HQ Mission/Run/Step state."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Create the mission runtime state directories.")
    init.set_defaults(func=lambda args: (ensure_runtime() or print(f"runtime_root={RUNTIME_ROOT}") or 0))

    create_thread_parser = subparsers.add_parser(
        "create-thread",
        help="Create a durable execution thread record.",
    )
    create_thread_parser.add_argument("--title", required=True, help="Thread title.")
    create_thread_parser.add_argument("--owner", help="Owning role or operator.")
    create_thread_parser.add_argument(
        "--status",
        default="active",
        choices=sorted(ALLOWED_THREAD_STATUSES),
        help="Initial thread status.",
    )
    create_thread_parser.add_argument(
        "--metadata",
        type=parse_json_object,
        help="Optional inline JSON metadata object.",
    )
    create_thread_parser.set_defaults(func=create_thread_command)

    create_mission_parser = subparsers.add_parser(
        "create-mission",
        help="Create a mission record in the local mission runtime.",
    )
    create_mission_parser.add_argument("--title", required=True, help="Mission title.")
    create_mission_parser.add_argument("--goal", help="Mission goal.")
    create_mission_parser.add_argument("--workflow", help="Workflow identifier.")
    create_mission_parser.add_argument("--project", help="Project label.")
    create_mission_parser.add_argument("--owner", help="Owner role.")
    create_mission_parser.add_argument("--manager", help="Manager role.")
    create_mission_parser.add_argument("--accepts-result", help="Accepting role.")
    create_mission_parser.add_argument("--source-task-id", help="Optional source task id.")
    create_mission_parser.add_argument(
        "--thread-id",
        help="Existing execution thread identifier. When omitted, a thread is created automatically.",
    )
    create_mission_parser.add_argument(
        "--thread-title",
        help="Optional title used only when a new thread is auto-created.",
    )
    create_mission_parser.add_argument(
        "--metadata",
        type=parse_json_object,
        help="Optional inline JSON metadata object.",
    )
    create_mission_parser.set_defaults(func=create_mission_command)

    link_thread_parser = subparsers.add_parser(
        "link-thread",
        help="Attach mission/run/spec/handoff pointers to an existing thread.",
    )
    link_thread_parser.add_argument("--thread-id", required=True, help="Thread identifier.")
    link_thread_parser.add_argument("--mission-id", help="Mission identifier to mark active.")
    link_thread_parser.add_argument("--run-id", help="Run identifier to mark active.")
    link_thread_parser.add_argument("--spec-path", help="Latest spec path for the thread.")
    link_thread_parser.add_argument("--handoff-path", help="Latest handoff path for the thread.")
    link_thread_parser.add_argument("--resume-packet-path", help="Latest resume packet path.")
    link_thread_parser.add_argument("--session-id", help="Linked execution session identifier.")
    link_thread_parser.add_argument("--work-dir", help="Linked isolated work directory.")
    link_thread_parser.add_argument("--runtime-home", help="Linked scoped runtime home path.")
    link_thread_parser.add_argument(
        "--runtime-home-mode",
        choices=["none", "scoped"],
        help="Execution runtime home mode.",
    )
    link_thread_parser.add_argument("--parent-session-id", help="Optional parent session identifier.")
    link_thread_parser.add_argument(
        "--blocked-tool-class",
        action="append",
        default=[],
        help="Repeat for each blocked tool class attached to the execution context.",
    )
    link_thread_parser.add_argument(
        "--status",
        choices=sorted(ALLOWED_THREAD_STATUSES),
        help="Optional thread status update.",
    )
    link_thread_parser.add_argument(
        "--metadata",
        type=parse_json_object,
        help="Optional inline JSON metadata object.",
    )
    link_thread_parser.set_defaults(func=link_thread_command)

    show_thread_parser = subparsers.add_parser(
        "show-thread",
        help="Render one thread record as JSON.",
    )
    show_thread_parser.add_argument("--thread-id", required=True, help="Thread identifier.")
    show_thread_parser.set_defaults(func=show_thread_command)

    start_run_parser = subparsers.add_parser(
        "start-run",
        help="Start a new run for an existing mission.",
    )
    start_run_parser.add_argument("--mission-id", required=True, help="Mission identifier.")
    start_run_parser.add_argument("--actor", help="Actor starting the run.")
    start_run_parser.add_argument("--loop", help="Loop description.")
    start_run_parser.add_argument(
        "--if-busy",
        choices=["reject", "queue"],
        default="reject",
        help="How to handle a thread that already has an active run. Defaults to reject.",
    )
    start_run_parser.add_argument("--session-id", help="Optional execution session identifier.")
    start_run_parser.add_argument("--work-dir", help="Optional isolated work directory override.")
    start_run_parser.add_argument("--runtime-home", help="Optional scoped runtime home override.")
    start_run_parser.add_argument(
        "--verification-stage",
        action="append",
        type=parse_verification_stage,
        default=[],
        help="Repeat as TYPE:PARTICIPANT, e.g. review:documentation or approval:ceo.",
    )
    start_run_parser.add_argument(
        "--runtime-home-mode",
        choices=["none", "scoped"],
        default="scoped",
        help="Execution runtime home mode. Defaults to scoped.",
    )
    start_run_parser.add_argument(
        "--parent-session-id",
        help="Optional parent session identifier for child-isolated execution.",
    )
    start_run_parser.add_argument(
        "--blocked-tool-class",
        action="append",
        default=[],
        help="Repeat for each blocked tool class attached to the execution context.",
    )
    start_run_parser.add_argument(
        "--max-steps",
        type=int,
        default=0,
        help="Optional run budget: refuse new steps once this many steps exist.",
    )
    start_run_parser.add_argument(
        "--max-failed-steps",
        type=int,
        default=0,
        help="Optional run budget: refuse new steps once this many steps failed.",
    )
    start_run_parser.add_argument(
        "--metadata",
        type=parse_json_object,
        help="Optional inline JSON metadata object.",
    )
    start_run_parser.set_defaults(func=start_run_command)

    dispatch_queued_run_parser = subparsers.add_parser(
        "dispatch-queued-run",
        help="Activate the next queued run for a thread, or a specific queued run.",
    )
    dispatch_target = dispatch_queued_run_parser.add_mutually_exclusive_group(required=True)
    dispatch_target.add_argument("--thread-id", help="Thread identifier used to pick the oldest queued run.")
    dispatch_target.add_argument("--run-id", help="Specific queued run identifier.")
    dispatch_queued_run_parser.add_argument(
        "--activated-by",
        required=True,
        help="Actor activating the queued run.",
    )
    dispatch_queued_run_parser.set_defaults(func=dispatch_queued_run)

    list_queued_runs_parser = subparsers.add_parser(
        "list-queued-runs",
        help="List queued runs for one thread in queue order.",
    )
    list_queued_runs_parser.add_argument("--thread-id", required=True, help="Thread identifier.")
    list_queued_runs_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of queued runs to return.",
    )
    list_queued_runs_parser.set_defaults(func=list_queued_runs_command)

    checkpoint_step_parser = subparsers.add_parser(
        "checkpoint-step",
        help="Record a step checkpoint for a run.",
    )
    checkpoint_step_parser.add_argument("--run-id", required=True, help="Run identifier.")
    checkpoint_step_parser.add_argument("--key", required=True, help="Step key, e.g. planner.")
    checkpoint_step_parser.add_argument("--actor", help="Actor role for the step.")
    checkpoint_step_parser.add_argument(
        "--status",
        required=True,
        choices=sorted(ALLOWED_STEP_STATUSES),
        help="Step status.",
    )
    checkpoint_step_parser.add_argument("--summary", help="Short step summary.")
    checkpoint_step_parser.add_argument(
        "--evidence",
        action="append",
        default=[],
        help="Repeat for each evidence link or artifact reference.",
    )
    checkpoint_step_parser.add_argument(
        "--metadata",
        type=parse_json_object,
        help="Optional inline JSON metadata object.",
    )
    checkpoint_step_parser.add_argument(
        "--error-type",
        choices=sorted(ALLOWED_ERROR_TYPES - {""}) + [""],
        default="",
        help="Error classification when status is failed: transient, recoverable, user_fixable, unexpected.",
    )
    checkpoint_step_parser.add_argument(
        "--allowed-tool-class",
        action="append",
        default=[],
        help="Repeat for each tool class the step is allowed to use explicitly.",
    )
    checkpoint_step_parser.set_defaults(func=checkpoint_step_command)

    verify_run_parser = subparsers.add_parser(
        "verify-run",
        help="Record a verification stage for a run before marking it completed.",
    )
    verify_run_parser.add_argument("--run-id", required=True, help="Run identifier.")
    verify_run_parser.add_argument("--actor", required=True, help="Verification actor.")
    verify_run_parser.add_argument(
        "--status",
        choices=["verified", "failed", "changes_requested"],
        default="verified",
        help="Verification outcome. Defaults to verified.",
    )
    verify_run_parser.add_argument("--summary", required=True, help="Verification result summary.")
    verify_run_parser.add_argument(
        "--evidence",
        action="append",
        default=[],
        help="Repeat for each verification artifact or command.",
    )
    verify_run_parser.add_argument(
        "--metadata",
        type=parse_json_object,
        help="Optional inline JSON metadata object.",
    )
    verify_run_parser.set_defaults(func=verify_run_command)

    request_approval_parser = subparsers.add_parser(
        "request-approval",
        help="Create a first-class approval object linked to a run step.",
    )
    request_approval_parser.add_argument("--run-id", required=True, help="Run identifier.")
    request_approval_parser.add_argument("--step-id", required=True, help="Step identifier.")
    request_approval_parser.add_argument("--requested-by", required=True, help="Requesting actor.")
    request_approval_parser.add_argument(
        "--requested-for",
        help="Approver or inbox owner. Defaults to founder.",
    )
    request_approval_parser.add_argument(
        "--policy-action",
        required=True,
        choices=sorted(ALLOWED_POLICY_ACTIONS),
        help="Policy action that triggered the approval.",
    )
    request_approval_parser.add_argument("--summary", help="Approval summary.")
    request_approval_parser.add_argument(
        "--approval-kind",
        help="Stable approval target kind. Defaults to runtime_action.",
    )
    request_approval_parser.add_argument(
        "--approval-namespace",
        help="Stable namespace for the approval target. Defaults to hq.runtime.",
    )
    request_approval_parser.add_argument(
        "--approval-name",
        help="Stable target name inside the namespace. Defaults to the step key.",
    )
    request_approval_parser.add_argument(
        "--approval-class",
        help="Permission approval class covered by this approval record.",
    )
    request_approval_parser.add_argument(
        "--expires-at",
        help="UTC expiry timestamp for permission checks, e.g. 2026-04-20T11:00:00Z.",
    )
    request_approval_parser.add_argument(
        "--approval-call-id",
        help="Optional call-scoped identifier for one approvalable action.",
    )
    request_approval_parser.add_argument(
        "--approval-action",
        action="append",
        default=[],
        help="Repeat for each action token describing the target identity.",
    )
    request_approval_parser.add_argument(
        "--tool-scope",
        action="append",
        default=[],
        help="Repeat for each tool class covered by the approval envelope.",
    )
    request_approval_parser.add_argument(
        "--policy-context",
        type=parse_json_object,
        help="Optional inline JSON policy context object.",
    )
    request_approval_parser.add_argument(
        "--metadata",
        type=parse_json_object,
        help="Optional inline JSON metadata object.",
    )
    request_approval_parser.set_defaults(func=request_approval_command)

    decide_approval_parser = subparsers.add_parser(
        "decide-approval",
        help="Record an approval decision and unblock or block the run.",
    )
    decide_approval_parser.add_argument("--approval-id", required=True, help="Approval identifier.")
    decide_approval_parser.add_argument(
        "--decision",
        required=True,
        choices=sorted(ALLOWED_APPROVAL_DECISIONS),
        help="Final approval decision.",
    )
    decide_approval_parser.add_argument("--decided-by", required=True, help="Decision maker.")
    decide_approval_parser.add_argument("--rationale", help="Decision rationale.")
    decide_approval_parser.set_defaults(func=decide_approval_command)

    attach_artifact_parser = subparsers.add_parser(
        "attach-artifact",
        help="Attach a first-class artifact to a run step.",
    )
    attach_artifact_parser.add_argument("--run-id", required=True, help="Run identifier.")
    attach_artifact_parser.add_argument("--step-id", required=True, help="Step identifier.")
    attach_artifact_parser.add_argument("--kind", required=True, help="Artifact kind.")
    attach_artifact_parser.add_argument("--path", required=True, help="Artifact path or URI.")
    attach_artifact_parser.add_argument("--summary", help="Artifact summary.")
    attach_artifact_parser.add_argument(
        "--metadata",
        type=parse_json_object,
        help="Optional inline JSON metadata object.",
    )
    attach_artifact_parser.set_defaults(func=attach_artifact_command)

    interrupt_run_parser = subparsers.add_parser(
        "interrupt-run",
        help="Interrupt a non-terminal run and preserve its resume point.",
    )
    interrupt_run_parser.add_argument("--run-id", required=True, help="Run identifier.")
    interrupt_run_parser.add_argument("--requested-by", required=True, help="Actor requesting interruption.")
    interrupt_run_parser.add_argument("--reason", help="Optional interruption reason.")
    interrupt_run_parser.add_argument(
        "--metadata",
        type=parse_json_object,
        help="Optional inline JSON metadata object.",
    )
    interrupt_run_parser.set_defaults(func=interrupt_run_command)

    resume_run_parser = subparsers.add_parser(
        "resume-run",
        help="Resume an interrupted run from its last recorded resume point.",
    )
    resume_run_parser.add_argument("--run-id", required=True, help="Run identifier.")
    resume_run_parser.add_argument("--resumed-by", required=True, help="Actor resuming the run.")
    resume_run_parser.add_argument(
        "--resume-from-step-id",
        help="Optional completed checkpoint step id to target instead of the current stored resume point.",
    )
    resume_run_parser.add_argument(
        "--resume-token",
        help="Optional idempotency token for a repeat-safe resume request.",
    )
    resume_run_parser.set_defaults(func=resume_run_command)

    show_resume_status_parser = subparsers.add_parser(
        "show-resume-status",
        help="Render the validated resume status contract for one run.",
    )
    show_resume_status_parser.add_argument("--run-id", required=True, help="Run identifier.")
    show_resume_status_parser.set_defaults(func=show_resume_status_command)

    export_recovery_bundle_parser = subparsers.add_parser(
        "export-recovery-bundle",
        help="Render a read-only recovery bundle for one run.",
    )
    export_recovery_bundle_parser.add_argument("--run-id", required=True, help="Run identifier.")
    export_recovery_bundle_parser.set_defaults(func=export_recovery_bundle_command)

    finish_run_parser = subparsers.add_parser(
        "finish-run",
        help="Mark a run as completed or otherwise terminal.",
    )
    finish_run_parser.add_argument("--run-id", required=True, help="Run identifier.")
    finish_run_parser.add_argument(
        "--status",
        required=True,
        choices=["completed", "failed", "blocked", "cancelled"],
        help="Terminal run status.",
    )
    finish_run_parser.add_argument(
        "--dispatch-next-queued-by",
        help="Optional actor to immediately activate the oldest queued run in the same thread.",
    )
    finish_run_parser.set_defaults(func=finish_run_command)

    show_run_parser = subparsers.add_parser(
        "show-run",
        help="Render one run record as JSON.",
    )
    show_run_parser.add_argument("--run-id", required=True, help="Run identifier.")
    show_run_parser.set_defaults(func=show_run_command)

    list_checkpoints_parser = subparsers.add_parser(
        "list-checkpoints",
        help="List completed checkpoint steps for a run, newest first.",
    )
    list_checkpoints_parser.add_argument("--run-id", required=True, help="Run identifier.")
    list_checkpoints_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of checkpoints to return.",
    )
    list_checkpoints_parser.set_defaults(func=list_checkpoints_command)

    plan_replay_parser = subparsers.add_parser(
        "plan-replay",
        help="Preview which later steps would be replayed from a selected completed checkpoint.",
    )
    plan_replay_parser.add_argument("--run-id", required=True, help="Run identifier.")
    plan_replay_parser.add_argument(
        "--resume-from-step-id",
        help="Optional completed checkpoint step id. Defaults to the run's stored resume point.",
    )
    plan_replay_parser.set_defaults(func=plan_replay_command)

    resume_context_parser = subparsers.add_parser(
        "resume-context",
        help="Render narrow resume linkage for a thread or run.",
    )
    resume_context_target = resume_context_parser.add_mutually_exclusive_group(required=True)
    resume_context_target.add_argument("--thread-id", help="Thread identifier.")
    resume_context_target.add_argument("--run-id", help="Run identifier.")
    resume_context_parser.set_defaults(func=resume_context_command)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = args.func(args)
    return int(result)


if __name__ == "__main__":
    raise SystemExit(main())
