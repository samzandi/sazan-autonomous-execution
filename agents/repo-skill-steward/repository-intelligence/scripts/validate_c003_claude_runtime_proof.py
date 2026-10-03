#!/usr/bin/env python3
"""Validate C003 live Claude Code runtime-proof evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SENSITIVE_MARKERS = (
    "secret-owner",
    "private-payments-worker",
    "ANTHROPIC_API_KEY",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "sk-ant-",
)


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return data


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate(
    claude_output: dict[str, Any],
    baseline: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    checks: dict[str, bool] = {}

    runtime = claude_output.get("runtime", {})
    output_checks = claude_output.get("checks", {})
    baseline_checks = baseline.get("checks", {})
    summary = baseline.get("summary", {})
    orchestration = summary.get("orchestration", {}) if isinstance(summary, dict) else {}

    checks["claude_status_verified"] = claude_output.get("status") == "verified"
    checks["runtime_name_claude_code"] = (
        isinstance(runtime, dict) and runtime.get("name") == "claude-code"
    )
    checks["repository_head_matches"] = (
        isinstance(runtime, dict)
        and runtime.get("repository_head") == metadata.get("head_sha")
        and isinstance(output_checks, dict)
        and output_checks.get("repository_head_matches") is True
    )
    checks["model_matches"] = (
        isinstance(runtime, dict)
        and runtime.get("model") == metadata.get("model")
    )
    cli_version = str(runtime.get("cli_version", "")) if isinstance(runtime, dict) else ""
    expected_cli = str(metadata.get("expected_claude_code_version", ""))
    checks["cli_version_matches"] = bool(expected_cli) and expected_cli in cli_version

    checks["baseline_verified"] = (
        baseline.get("status") == "verified"
        and isinstance(baseline_checks, dict)
        and all(value is True for value in baseline_checks.values())
    )
    checks["focused_tests_reported"] = (
        isinstance(output_checks, dict)
        and output_checks.get("c002_end_to_end_passed") is True
        and output_checks.get("c002_orchestration_passed") is True
    )
    checks["parent_review_boundary"] = (
        orchestration.get("status") == "ready-for-parent-review"
        and baseline_checks.get("no_auto_promotion") is True
        and output_checks.get("parent_review_gate_observed") is True
        and output_checks.get("auto_promotion_disabled") is True
    )
    checks["private_identity_redaction"] = (
        baseline_checks.get("private_identity_redacted") is True
        and output_checks.get("private_identity_redaction_observed") is True
    )
    checks["workspace_unchanged"] = output_checks.get("workspace_unchanged") is True

    evidence = claude_output.get("evidence", [])
    checks["evidence_present"] = isinstance(evidence, list) and len(evidence) >= 4
    blockers = claude_output.get("blockers", [])
    checks["no_claude_blockers"] = isinstance(blockers, list) and not blockers

    serialized = json.dumps(
        {"claude_output": claude_output, "baseline": baseline, "metadata": metadata},
        sort_keys=True,
    )
    checks["no_sensitive_markers"] = not any(marker in serialized for marker in SENSITIVE_MARKERS)

    verified = all(checks.values())
    return {
        "schema_version": 1,
        "context": "C003",
        "milestone": "claude-code-runtime-proof",
        "status": "verified" if verified else "blocked",
        "checks": checks,
        "runtime": {
            "name": "claude-code",
            "cli_version": cli_version,
            "expected_claude_code_version": expected_cli,
            "model": metadata.get("model"),
            "action_commit": metadata.get("action_commit"),
            "repository_head": metadata.get("head_sha"),
        },
        "baseline": {
            "status": baseline.get("status"),
            "sha256": metadata.get("baseline_sha256"),
            "orchestration_status": orchestration.get("status"),
        },
        "claude_evidence": evidence if isinstance(evidence, list) else [],
        "blockers": [] if verified else sorted(
            key for key, value in checks.items() if not value
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--claude-output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--require-verified", action="store_true")
    args = parser.parse_args()

    claude_output = _load(args.claude_output)
    baseline = _load(args.baseline)
    metadata = _load(args.metadata)

    if _sha256(args.baseline) != str(metadata.get("baseline_sha256", "")):
        raise ValueError("baseline SHA-256 does not match runtime metadata")

    report = validate(claude_output, baseline, metadata)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.require_verified and report["status"] != "verified":
        return 14
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
