#!/usr/bin/env python3
"""Fail-closed C003 runtime/provider contract parity evaluator."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
COMMON_REQUIRED_CHECKS = (
    "repository_head_matches",
    "model_matches",
    "cli_version_matches",
    "baseline_verified",
    "parent_review_boundary",
    "focused_tests_reported",
    "private_identity_redaction",
    "workspace_unchanged",
    "evidence_present",
    "no_sensitive_markers",
)
SENSITIVE_MARKERS = (
    "secret-owner",
    "private-payments-worker",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "sk-proj-",
    "sk-ant-",
)


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return data


def _text(value: Any, name: str) -> str:
    out = str(value or "").strip()
    if not out:
        raise ValueError(f"{name} is required")
    return out


def _fingerprint(payload: Any) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _provider_summary(report: dict[str, Any], expected_name: str) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    if report.get("schema_version") != SCHEMA_VERSION:
        blockers.append(f"{expected_name}: unsupported schema_version")
    if report.get("context") != "C003":
        blockers.append(f"{expected_name}: context must be C003")
    if report.get("status") != "verified":
        blockers.append(f"{expected_name}: runtime proof status is not verified")

    runtime = report.get("runtime")
    if not isinstance(runtime, dict):
        blockers.append(f"{expected_name}: runtime object missing")
        runtime = {}

    actual_name = str(runtime.get("name", "")).strip()
    if actual_name != expected_name:
        blockers.append(
            f"{expected_name}: runtime.name mismatch: {actual_name or '<missing>'}"
        )

    head = str(runtime.get("repository_head", "")).strip()
    if not head:
        blockers.append(f"{expected_name}: repository_head missing")

    model = str(runtime.get("model", "")).strip()
    if not model:
        blockers.append(f"{expected_name}: model missing")

    cli_version = str(runtime.get("cli_version") or runtime.get("codex_cli_version") or "").strip()
    if not cli_version:
        blockers.append(f"{expected_name}: runtime CLI version missing")

    checks = report.get("checks")
    if not isinstance(checks, dict):
        blockers.append(f"{expected_name}: checks object missing")
        checks = {}

    for key in COMMON_REQUIRED_CHECKS:
        if checks.get(key) is not True:
            blockers.append(f"{expected_name}: invariant check failed: {key}")

    raw_blockers = report.get("blockers")
    if not isinstance(raw_blockers, list):
        blockers.append(f"{expected_name}: blockers must be a list")
        raw_blockers = []
    elif raw_blockers:
        blockers.append(f"{expected_name}: runtime proof contains blockers")

    baseline = report.get("baseline")
    if not isinstance(baseline, dict):
        blockers.append(f"{expected_name}: baseline object missing")
        baseline = {}

    if baseline.get("status") != "verified":
        blockers.append(f"{expected_name}: baseline status is not verified")
    if baseline.get("orchestration_status") != "ready-for-parent-review":
        blockers.append(
            f"{expected_name}: baseline orchestration did not stop at parent review"
        )
    baseline_sha = str(baseline.get("sha256", "")).strip()
    if not baseline_sha:
        blockers.append(f"{expected_name}: baseline SHA-256 missing")

    serialized = json.dumps(report, sort_keys=True)
    if any(marker in serialized for marker in SENSITIVE_MARKERS):
        blockers.append(f"{expected_name}: sensitive marker found in persisted proof")

    return {
        "runtime": expected_name,
        "repository_head": head,
        "model": model,
        "cli_version": cli_version,
        "action_commit": runtime.get("action_commit"),
        "baseline_sha256": baseline_sha,
        "orchestration_status": baseline.get("orchestration_status"),
        "proof_fingerprint": _fingerprint(report),
    }, blockers


def compare(
    codex_report: dict[str, Any],
    claude_report: dict[str, Any],
    *,
    expected_head: str | None = None,
) -> dict[str, Any]:
    codex, blockers = _provider_summary(codex_report, "codex")
    claude, claude_blockers = _provider_summary(claude_report, "claude-code")
    blockers.extend(claude_blockers)

    parity_checks = {
        "same_repository_head": (
            bool(codex["repository_head"])
            and codex["repository_head"] == claude["repository_head"]
        ),
        "same_baseline": (
            bool(codex["baseline_sha256"])
            and codex["baseline_sha256"] == claude["baseline_sha256"]
        ),
        "same_parent_review_boundary": (
            codex["orchestration_status"] == "ready-for-parent-review"
            and claude["orchestration_status"] == "ready-for-parent-review"
        ),
        "provider_models_recorded": bool(codex["model"] and claude["model"]),
        "provider_versions_recorded": bool(codex["cli_version"] and claude["cli_version"]),
    }

    if expected_head is not None:
        normalized_expected = _text(expected_head, "expected_head")
        parity_checks["expected_head_matches"] = (
            codex["repository_head"] == normalized_expected
            and claude["repository_head"] == normalized_expected
        )

    for key, value in parity_checks.items():
        if not value:
            blockers.append(f"parity check failed: {key}")

    blockers = sorted(set(blockers))
    verified = not blockers

    core = {
        "codex": codex,
        "claude_code": claude,
        "parity_checks": parity_checks,
        "blockers": blockers,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "context": "C003",
        "milestone": "runtime-provider-contract-parity",
        "status": "verified" if verified else "blocked",
        "providers": {
            "codex": codex,
            "claude_code": claude,
        },
        "parity_checks": parity_checks,
        "allowed_differences": [
            "runtime.name",
            "runtime.model",
            "runtime.cli_version",
            "runtime.action_commit",
            "proof_fingerprint",
        ],
        "required_equalities": [
            "runtime.repository_head",
            "baseline.sha256",
            "baseline.orchestration_status",
        ],
        "blockers": blockers,
        "parity_fingerprint": _fingerprint(core),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex-report", type=Path, required=True)
    parser.add_argument("--claude-report", type=Path, required=True)
    parser.add_argument("--expected-head")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-verified", action="store_true")
    args = parser.parse_args()

    result = compare(
        _load(args.codex_report),
        _load(args.claude_report),
        expected_head=args.expected_head,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.require_verified and result["status"] != "verified":
        return 15
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
