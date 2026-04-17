#!/usr/bin/env python3
"""Explicit runtime policy and hook seams for HQ execution governance."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


REPO_ROOT = Path(
    os.environ.get("HQ_POLICY_HOOKS_REPO_ROOT", Path(__file__).resolve().parents[1])
).resolve()
SCHEMA_DIR = REPO_ROOT / "05 AI Control Plane" / "schemas"
POLICY_SCHEMA_PATH = SCHEMA_DIR / "runtime-policy.schema.json"
HOOK_SCHEMA_PATH = SCHEMA_DIR / "runtime-hook.schema.json"
DECISION_ORDER = {
    "allow": 0,
    "allow_with_review": 1,
    "pause_for_founder_approval": 2,
    "block": 3,
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_schema(payload: dict[str, Any], schema_path: Path, label: str) -> None:
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path))
    if errors:
        error = errors[0]
        path = ".".join(str(part) for part in error.absolute_path)
        raise ValueError(f"{label} failed schema validation at {path or '<root>'}: {error.message}")


def parse_json_object(value: str) -> dict[str, Any]:
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise argparse.ArgumentTypeError("JSON payload must be an object")
    return payload


def tokenize(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in shlex.split(str(value)) if item.strip()]


def policy_request_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "action": [item.strip() for item in args.action if item.strip()],
        "path": str(args.path or "").strip(),
        "namespace": str(args.namespace or "").strip(),
        "tool_name": str(args.tool_name or "").strip(),
        "call_id": str(args.call_id or "").strip(),
        "risk_tier": str(args.risk_tier or "").strip(),
        "autonomy_tier": str(args.autonomy_tier or "").strip(),
    }


def rule_matches(rule: dict[str, Any], request: dict[str, Any]) -> bool:
    action = request.get("action", [])
    prefix = [str(item).strip() for item in rule.get("action_prefix", []) if str(item).strip()]
    if not prefix or action[: len(prefix)] != prefix:
        return False

    path_prefixes = [str(item).strip() for item in rule.get("path_prefixes", []) if str(item).strip()]
    if path_prefixes:
        path_value = str(request.get("path") or "").strip()
        if not path_value or not any(path_value.startswith(prefix) for prefix in path_prefixes):
            return False

    namespaces = [str(item).strip() for item in rule.get("namespaces", []) if str(item).strip()]
    if namespaces:
        namespace_value = str(request.get("namespace") or "").strip()
        if not namespace_value or namespace_value not in namespaces:
            return False

    tool_names = [str(item).strip() for item in rule.get("tool_names", []) if str(item).strip()]
    if tool_names:
        tool_name = str(request.get("tool_name") or "").strip()
        if not tool_name or tool_name not in tool_names:
            return False

    call_id_prefixes = [
        str(item).strip() for item in rule.get("call_id_prefixes", []) if str(item).strip()
    ]
    if call_id_prefixes:
        call_id = str(request.get("call_id") or "").strip()
        if not call_id or not any(call_id.startswith(prefix) for prefix in call_id_prefixes):
            return False

    risk_tiers = [str(item).strip() for item in rule.get("risk_tiers", []) if str(item).strip()]
    if risk_tiers and str(request.get("risk_tier") or "").strip() not in risk_tiers:
        return False

    autonomy_tiers = [
        str(item).strip() for item in rule.get("autonomy_tiers", []) if str(item).strip()
    ]
    if autonomy_tiers and str(request.get("autonomy_tier") or "").strip() not in autonomy_tiers:
        return False

    return True


def validate_policy_examples(policy: dict[str, Any]) -> None:
    for rule in policy.get("rules", []):
        if not isinstance(rule, dict):
            continue
        template_request = {
            "path": str((rule.get("path_prefixes") or [""])[0] or ""),
            "namespace": str((rule.get("namespaces") or [""])[0] or ""),
            "tool_name": str((rule.get("tool_names") or [""])[0] or ""),
            "call_id": str((rule.get("call_id_prefixes") or [""])[0] or ""),
            "risk_tier": str((rule.get("risk_tiers") or [""])[0] or ""),
            "autonomy_tier": str((rule.get("autonomy_tiers") or [""])[0] or ""),
        }
        for example in rule.get("match", []) or []:
            request = dict(template_request)
            request["action"] = tokenize(example)
            if not rule_matches(rule, request):
                raise ValueError(f"policy rule `{rule.get('id', '<unknown>')}` failed `match` example")
        for example in rule.get("not_match", []) or []:
            request = dict(template_request)
            request["action"] = tokenize(example)
            if rule_matches(rule, request):
                raise ValueError(f"policy rule `{rule.get('id', '<unknown>')}` failed `not_match` example")


def load_policy(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    validate_schema(payload, POLICY_SCHEMA_PATH, "runtime_policy")
    validate_policy_examples(payload)
    return payload


def evaluate_policy(policy: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    matched_rules: list[dict[str, Any]] = []
    effective_decision = str(policy.get("default_decision") or "allow").strip()
    for rule in policy.get("rules", []):
        if not isinstance(rule, dict) or not rule_matches(rule, request):
            continue
        decision = str(rule.get("decision") or "allow").strip()
        matched_rules.append(
            {
                "id": rule.get("id", ""),
                "decision": decision,
                "justification": str(rule.get("justification") or "").strip(),
                "actionPrefix": rule.get("action_prefix", []),
                "namespace": str(request.get("namespace") or "").strip(),
                "toolName": str(request.get("tool_name") or "").strip(),
                "callId": str(request.get("call_id") or "").strip(),
            }
        )
        if DECISION_ORDER[decision] > DECISION_ORDER[effective_decision]:
            effective_decision = decision
    return {
        "action": request.get("action", []),
        "path": request.get("path", ""),
        "namespace": str(request.get("namespace") or "").strip(),
        "toolName": str(request.get("tool_name") or "").strip(),
        "callId": str(request.get("call_id") or "").strip(),
        "matchedRules": matched_rules,
        "decision": effective_decision,
    }


def extract_action_tokens(payload: dict[str, Any]) -> list[str]:
    action = payload.get("action")
    if isinstance(action, list):
        return tokenize(action)
    if isinstance(action, str):
        return tokenize(action)
    return []


def hook_matches(hook: dict[str, Any], event: str, payload: dict[str, Any]) -> bool:
    if str(hook.get("event") or "").strip() != event:
        return False

    action_prefixes = hook.get("action_prefixes", []) or []
    if action_prefixes:
        action = extract_action_tokens(payload)
        normalized_prefixes = [tokenize(prefix) for prefix in action_prefixes]
        if not any(action[: len(prefix)] == prefix for prefix in normalized_prefixes if prefix):
            return False

    decisions = [str(item).strip() for item in hook.get("decisions", []) if str(item).strip()]
    if decisions and str(payload.get("decision") or "").strip() not in decisions:
        return False

    namespaces = [str(item).strip() for item in hook.get("namespaces", []) if str(item).strip()]
    if namespaces and str(payload.get("namespace") or "").strip() not in namespaces:
        return False

    tool_names = [str(item).strip() for item in hook.get("tool_names", []) if str(item).strip()]
    if tool_names and str(payload.get("tool_name") or "").strip() not in tool_names:
        return False

    call_id_prefixes = [
        str(item).strip() for item in hook.get("call_id_prefixes", []) if str(item).strip()
    ]
    if call_id_prefixes:
        call_id = str(payload.get("call_id") or "").strip()
        if not call_id or not any(call_id.startswith(prefix) for prefix in call_id_prefixes):
            return False

    statuses = [str(item).strip() for item in hook.get("statuses", []) if str(item).strip()]
    if statuses and str(payload.get("status") or "").strip() not in statuses:
        return False

    return True


def load_hooks(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    validate_schema(payload, HOOK_SCHEMA_PATH, "runtime_hooks")
    return payload


def run_hook(command: list[str], payload: dict[str, Any]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": (completed.stdout or "").strip(),
        "stderr": (completed.stderr or "").strip(),
    }


def validate_policy_command(args: argparse.Namespace) -> int:
    try:
        load_policy(Path(args.policy_file))
    except (OSError, ValueError) as exc:
        print(f"error={exc}")
        return 2
    print("runtime_policy=ok")
    return 0


def check_policy_command(args: argparse.Namespace) -> int:
    try:
        policy = load_policy(Path(args.policy_file))
        result = evaluate_policy(policy, policy_request_from_args(args))
    except (OSError, ValueError) as exc:
        print(f"error={exc}")
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def validate_hooks_command(args: argparse.Namespace) -> int:
    try:
        load_hooks(Path(args.hooks_file))
    except (OSError, ValueError) as exc:
        print(f"error={exc}")
        return 2
    print("runtime_hooks=ok")
    return 0


def emit_hooks_command(args: argparse.Namespace) -> int:
    try:
        hooks = load_hooks(Path(args.hooks_file))
    except (OSError, ValueError) as exc:
        print(f"error={exc}")
        return 2

    payload = dict(args.payload or {})
    payload["event"] = args.event
    executed: list[dict[str, Any]] = []
    for hook in hooks.get("hooks", []):
        if not isinstance(hook, dict) or not hook_matches(hook, args.event, payload):
            continue
        result = run_hook([str(item) for item in hook.get("command", [])], payload)
        executed.append(
            {
                "id": hook.get("id", ""),
                "event": hook.get("event", ""),
                "result": result,
            }
        )
        if result["returncode"] != 0 and bool(hook.get("stop_on_error")):
            print(json.dumps({"matchedHooks": executed, "stopped": True}, ensure_ascii=False, indent=2))
            return result["returncode"] or 1

    print(
        json.dumps(
            {
                "event": args.event,
                "matchedHooks": executed,
                "count": len(executed),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate explicit HQ runtime policy and hooks.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_policy = subparsers.add_parser("validate-policy", help="Validate a runtime policy file.")
    validate_policy.add_argument("--policy-file", required=True, help="Path to the runtime policy JSON.")
    validate_policy.set_defaults(func=validate_policy_command)

    check_policy = subparsers.add_parser("check", help="Evaluate one action against a runtime policy.")
    check_policy.add_argument("--policy-file", required=True, help="Path to the runtime policy JSON.")
    check_policy.add_argument("action", nargs="+", help="Action tokens to evaluate.")
    check_policy.add_argument("--path", help="Optional target path associated with the action.")
    check_policy.add_argument("--namespace", help="Optional approval namespace.")
    check_policy.add_argument("--tool-name", help="Optional tool or action name inside the namespace.")
    check_policy.add_argument("--call-id", help="Optional call-scoped identifier.")
    check_policy.add_argument("--risk-tier", help="Optional risk tier filter input.")
    check_policy.add_argument("--autonomy-tier", help="Optional autonomy tier filter input.")
    check_policy.set_defaults(func=check_policy_command)

    validate_hooks = subparsers.add_parser("validate-hooks", help="Validate a runtime hooks file.")
    validate_hooks.add_argument("--hooks-file", required=True, help="Path to the runtime hooks JSON.")
    validate_hooks.set_defaults(func=validate_hooks_command)

    emit_hooks = subparsers.add_parser("emit", help="Emit one hook event and run matching commands.")
    emit_hooks.add_argument("--hooks-file", required=True, help="Path to the runtime hooks JSON.")
    emit_hooks.add_argument(
        "--event",
        required=True,
        choices=[
            "session_start",
            "run_started",
            "run_checkpointed",
            "agent_started",
            "agent_finished",
            "agent_handoff",
            "pre_action",
            "post_action",
            "approval_requested",
            "handoff_written",
            "run_interrupted",
            "run_resumed",
            "run_finished",
        ],
    )
    emit_hooks.add_argument(
        "--payload",
        type=parse_json_object,
        default={},
        help="Inline JSON payload delivered to matching hooks over stdin.",
    )
    emit_hooks.set_defaults(func=emit_hooks_command)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
