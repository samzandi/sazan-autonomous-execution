#!/usr/bin/env python3
"""Fail-closed C003 stable-release readiness evaluator."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
REQUIRED_GATES = (
    "c002_complete",
    "codex_runtime",
    "claude_runtime",
    "live_provider_parity",
    "failure_rollback",
    "reproducibility",
    "security",
    "privacy",
    "license",
    "verifier",
)
ALLOWED_GATE_STATES = {"verified", "blocked", "pending"}
SENSITIVE_MARKERS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "sk-proj-",
    "sk-ant-",
    "secret-owner",
    "private-payments-worker",
)


def _text(value: Any, name: str) -> str:
    out = str(value or "").strip()
    if not out:
        raise ValueError(f"{name} is required")
    return out


def _obj(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _list(value: Any, name: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list")
    return value


def _evidence(gate: dict[str, Any], name: str) -> list[str]:
    raw = _list(gate.get("evidence"), f"gates.{name}.evidence")
    return sorted({_text(item, f"gates.{name}.evidence[]") for item in raw})


def _canonical_fingerprint(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def evaluate(package: dict[str, Any]) -> dict[str, Any]:
    if package.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("schema_version must be 1")
    if package.get("context") != "C003":
        raise ValueError("context must be C003")

    candidate = _obj(package.get("candidate"), "candidate")
    candidate_name = _text(candidate.get("name"), "candidate.name")
    channel = _text(candidate.get("channel"), "candidate.channel")
    if channel != "stable":
        raise ValueError("candidate.channel must be stable")

    gates = _obj(package.get("gates"), "gates")
    missing = [name for name in REQUIRED_GATES if name not in gates]
    extras = sorted(set(gates) - set(REQUIRED_GATES))
    if missing:
        raise ValueError(f"missing gates: {', '.join(missing)}")
    if extras:
        raise ValueError(f"unsupported gates: {', '.join(extras)}")

    blockers: list[str] = []
    gate_receipts: dict[str, dict[str, Any]] = {}
    for name in REQUIRED_GATES:
        gate = _obj(gates[name], f"gates.{name}")
        status = _text(gate.get("status"), f"gates.{name}.status")
        if status not in ALLOWED_GATE_STATES:
            raise ValueError(f"invalid gate state for {name}: {status}")
        evidence = _evidence(gate, name)
        if not evidence:
            blockers.append(f"{name}: evidence is missing")

        gate_blockers = sorted({
            _text(item, f"gates.{name}.blockers[]")
            for item in _list(gate.get("blockers"), f"gates.{name}.blockers")
        })
        if status == "verified" and gate_blockers:
            blockers.append(f"{name}: verified gate cannot contain blockers")
        if status != "verified":
            blockers.append(f"{name}: gate status is {status}")
            if not gate_blockers:
                blockers.append(f"{name}: non-verified gate must explain its blocker")
        gate_receipts[name] = {
            "status": status,
            "evidence": evidence,
            "blockers": gate_blockers,
        }

    open_blockers = sorted({
        _text(item, "open_blockers[]")
        for item in _list(package.get("open_blockers"), "open_blockers")
    })
    blockers.extend(f"open-blocker: {item}" for item in open_blockers)

    serialized = json.dumps(package, sort_keys=True)
    if any(marker in serialized for marker in SENSITIVE_MARKERS):
        blockers.append("sensitive or private marker found in release evidence")

    blockers = sorted(set(blockers))
    ready = not blockers
    decision = "eligible-for-parent-release-review" if ready else "blocked"

    normalized = {
        "candidate": {"name": candidate_name, "channel": channel},
        "gates": gate_receipts,
        "open_blockers": open_blockers,
        "decision": decision,
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "context": "C003",
        "milestone": "release-readiness",
        "candidate": normalized["candidate"],
        "decision": decision,
        "ready": ready,
        "auto_release": False,
        "parent_release_approval_required": ready,
        "gate_receipts": gate_receipts,
        "open_blockers": open_blockers,
        "blockers": blockers,
        "readiness_fingerprint": _canonical_fingerprint(normalized),
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# C003 Release Readiness",
        "",
        f"- Decision: **{result['decision']}**",
        f"- Ready: **{str(result['ready']).lower()}**",
        f"- Auto-release: **{str(result['auto_release']).lower()}**",
        f"- Parent release approval required: **{str(result['parent_release_approval_required']).lower()}**",
        "",
        "## Gates",
        "",
    ]
    for name, receipt in result["gate_receipts"].items():
        lines.append(f"- {name}: {receipt['status']}")
    lines.extend(["", "## Blockers", ""])
    if result["blockers"]:
        lines.extend(f"- {item}" for item in result["blockers"])
    else:
        lines.append("- None.")
    lines.extend(["", f"Readiness fingerprint: {result['readiness_fingerprint']}", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--json", dest="json_out", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()

    package = json.loads(args.evidence.read_text(encoding="utf-8"))
    if not isinstance(package, dict):
        raise ValueError("evidence must be a JSON object")
    result = evaluate(package)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown.write_text(render_markdown(result), encoding="utf-8")

    if args.require_ready and not result["ready"]:
        return 19
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
