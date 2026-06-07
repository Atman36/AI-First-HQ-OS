#!/usr/bin/env python3
"""Run the official HQ validation gate locally or in CI."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]

# Change types that classify a change as an Agent_Release.
AGENT_RELEASE_CHANGE_TYPES = ("prompt", "role", "policy", "schema", "tool_permission")

# Categories that always require a recorded human approval before landing.
HUMAN_ONLY_RELEASE_SIGNALS = (
    "external_send",
    "public_material",
    "money_commitment",
    "legal_commitment",
    "hiring_action",
    "safety_rule_change",
    "tool_permission_expansion",
    "schema_meaning_change",
)


class ReleaseGateError(Exception):
    """Raised when an Agent_Release fails the release gate."""


def _is_nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def derive_permission_expansion(
    previous_grants: list[dict[str, Any]] | None,
    current_grants: list[dict[str, Any]] | None,
    previous_capability_grants: list[dict[str, Any]] | None = None,
    current_capability_grants: list[dict[str, Any]] | None = None,
) -> bool:
    """Re-derive whether a change widens permissions, independent of the manifest.

    Returns True when the current grant/capability tables contain any grant or
    resource scope not present in the previous tables. This is the redundant
    enforcement signal: it does not trust the manifest's ``permission_expansion``
    flag.
    """

    def grant_keys(rows: list[dict[str, Any]] | None) -> set[tuple]:
        keys: set[tuple] = set()
        for row in rows or []:
            keys.add(
                (
                    str(row.get("agent_id", "")),
                    str(row.get("role_id", "")),
                    str(row.get("resource_scope", "")),
                    str(row.get("action", "")),
                    str(row.get("approval_class", "")),
                )
            )
        return keys

    def capability_keys(rows: list[dict[str, Any]] | None) -> set[tuple]:
        keys: set[tuple] = set()
        for row in rows or []:
            scopes = tuple(sorted(str(s) for s in row.get("resource_scopes", []) or []))
            tools = tuple(sorted(str(t) for t in row.get("tool_classes", []) or []))
            keys.add((str(row.get("role_id", "")), scopes, tools))
        return keys

    new_grant_rows = grant_keys(current_grants) - grant_keys(previous_grants)
    new_capability_rows = capability_keys(current_capability_grants) - capability_keys(
        previous_capability_grants
    )
    return bool(new_grant_rows or new_capability_rows)


def evaluate_release_gate(
    manifest: dict[str, Any],
    *,
    derived_permission_expansion: bool | None = None,
) -> list[str]:
    """Return a deterministic list of blocking reasons for an Agent_Release.

    An empty list means the release passes. The manifest is validated for
    required evidence; permission expansion without a recorded human approval
    blocks; and a redundant layer blocks when the derived expansion contradicts
    the manifest flag.
    """

    reasons: list[str] = []

    change_type = str(manifest.get("change_type", "")).strip()
    if change_type not in AGENT_RELEASE_CHANGE_TYPES:
        reasons.append(
            f"change_type must be one of {', '.join(AGENT_RELEASE_CHANGE_TYPES)}"
        )

    affected_files = manifest.get("affected_files")
    if not isinstance(affected_files, list) or not any(
        _is_nonempty_str(item) for item in affected_files
    ):
        reasons.append("affected_files must list at least one file")

    if not _is_nonempty_str(manifest.get("rollback_path")):
        reasons.append("rollback_path is required")

    if not _is_nonempty_str(manifest.get("eval_or_review_signal")):
        reasons.append("eval_or_review_signal is required")

    human_approval = manifest.get("human_approval_id")
    has_human_approval = _is_nonempty_str(human_approval)

    manifest_expansion = bool(manifest.get("permission_expansion"))

    # Primary block: manifest declares expansion without human approval.
    if manifest_expansion and not has_human_approval:
        reasons.append("permission_expansion requires a recorded human_approval_id")

    # Redundant enforcement: derived expansion overrides a wrong manifest flag.
    if derived_permission_expansion and not has_human_approval:
        reasons.append(
            "derived permission expansion (from grant diff) requires a recorded "
            "human_approval_id"
        )

    # Human-only categories always require a recorded human approval.
    human_only = [
        signal
        for signal in manifest.get("human_only_categories", []) or []
        if str(signal).strip() in HUMAN_ONLY_RELEASE_SIGNALS
    ]
    if human_only and not has_human_approval:
        reasons.append(
            "human-only categories require a recorded human_approval_id: "
            + ", ".join(sorted(set(human_only)))
        )

    return reasons


def release_gate_command(args: argparse.Namespace) -> int:
    try:
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[fail] release-gate: {exc}", flush=True)
        return 2

    derived = None
    previous_capability_grants = None
    current_capability_grants = None
    if args.previous_registry and args.current_registry:
        try:
            prev_registry = json.loads(Path(args.previous_registry).read_text(encoding="utf-8"))
            curr_registry = json.loads(Path(args.current_registry).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[fail] release-gate: {exc}", flush=True)
            return 2
        previous_capability_grants = prev_registry.get("capability_grants")
        current_capability_grants = curr_registry.get("capability_grants")

    if args.previous_grants and args.current_grants:
        try:
            prev = json.loads(Path(args.previous_grants).read_text(encoding="utf-8"))
            curr = json.loads(Path(args.current_grants).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[fail] release-gate: {exc}", flush=True)
            return 2
        derived = derive_permission_expansion(
            prev.get("grants"),
            curr.get("grants"),
            previous_capability_grants,
            current_capability_grants,
        )
    elif args.previous_registry and args.current_registry:
        derived = derive_permission_expansion(
            None,
            None,
            previous_capability_grants,
            current_capability_grants,
        )

    reasons = evaluate_release_gate(manifest, derived_permission_expansion=derived)
    if reasons:
        print("[fail] release-gate", flush=True)
        for reason in reasons:
            print(f"- {reason}", flush=True)
        return 1
    print("release_gate=ok", flush=True)
    return 0


def build_commands() -> list[tuple[str, list[str]]]:
    commands = [
        ("public-safety", [sys.executable, "scripts/hq_public_safety.py"]),
        ("reference-scan", [sys.executable, "scripts/hq_reference_scan.py", "scan"]),
        ("instruction-lint", [sys.executable, "scripts/hq_instruction_lint.py"]),
        ("generated-check", [sys.executable, "scripts/hq_control_plane.py", "generated-check"]),
        ("ruff", [sys.executable, "-m", "ruff", "check", "--select", "F,E9", "scripts", "tests"]),
    ]
    if (REPO_ROOT / ".hq" / "prompts").exists():
        commands.append(("private-prompt-lint", [sys.executable, "scripts/hq_private_prompt_lint.py"]))
    commands.extend(
        [
            ("tests", [sys.executable, "-m", "unittest", "discover", "tests"]),
            ("control-plane", [sys.executable, "scripts/hq_control_plane.py", "validate"]),
        ]
    )
    return commands


def run_full_gate() -> int:
    for name, command in build_commands():
        print(f"[run] {name}: {' '.join(command)}", flush=True)
        completed = subprocess.run(command, check=False)
        if completed.returncode != 0:
            print(f"[fail] {name}: exit_code={completed.returncode}", flush=True)
            return completed.returncode
    print("gate=ok", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = []

    if argv and argv[0] == "release-gate":
        parser = argparse.ArgumentParser(prog="hq_gate.py release-gate")
        parser.add_argument("--manifest", required=True, help="Path to the release manifest JSON.")
        parser.add_argument(
            "--previous-grants",
            default=None,
            help="Path to the previous permission-grants.json (for diff-based enforcement).",
        )
        parser.add_argument(
            "--current-grants",
            default=None,
            help="Path to the current permission-grants.json (for diff-based enforcement).",
        )
        parser.add_argument(
            "--previous-registry",
            default=None,
            help="Path to the previous agent-registry.json (for capability_grants diff enforcement).",
        )
        parser.add_argument(
            "--current-registry",
            default=None,
            help="Path to the current agent-registry.json (for capability_grants diff enforcement).",
        )
        args = parser.parse_args(argv[1:])
        return release_gate_command(args)

    return run_full_gate()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
