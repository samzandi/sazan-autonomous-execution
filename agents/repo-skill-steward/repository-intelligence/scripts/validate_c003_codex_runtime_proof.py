#!/usr/bin/env python3
"""Validate and normalize C003 live Codex runtime-proof evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SENSITIVE_MARKERS = (
    "secret-owner",
    "private-payments-worker",
    "OPENAI_API_KEY",
    "sk-proj-",
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
    codex_output: dict[str, Any],
    baseline: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    checks: dict[str, bool] = {}

    checks["codex_status_verified"] = codex_output.get("status") == "verified"

    runtime = codex_output.get("runtime", {})
    checks["runtime_name_codex"] = isinstance(runtime, dict) and runtime.get("name") == "codex"
    checks["repository_head_matches"] = (
        isinstance(runtime, dict)
        and runtime.get("repository_head") == metadata.get("head_sha")
        and codex_output.get("checks", {}).get("repository_head_matches") is True
    )
    checks["model_matches"] = (
        isinstance(runtime, dict)
        and runtime.get("model") == metadata.get("model")
    )

    cli_version = str(metadata.get("codex_cli_version", ""))
    expected_cli = str(metadata.get("expected_codex_version", ""))
    checks["cli_version_matches"] = bool(expected_cli) and expected_cli in cli_version

    baseline_checks = baseline.get("checks", {})
    baseline_summary = baseline.get("summary", {})
    orchestration = baseline_summary.get("orchestration", {}) if isinstance(baseline_summary, dict) else {}
    checks["baseline_verified"] = (
        baseline.get("status") == "verified"
        and isinstance(baseline_checks, dict)
        and all(value is True for value in baseline_checks.values())
    )
    checks["parent_review_boundary"] = (
        orchestration.get("status") == "ready-for-parent-review"
        and baseline_checks.get("no_auto_promotion") is True
        and codex_output.get("checks", {}).get("parent_review_gate_observed") is True
        and codex_output.get("checks", {}).get("auto_promotion_disabled") is True
    )
    checks["focused_tests_reported"] = (
        codex_output.get("checks", {}).get("c002_end_to_end_passed") is True
        and codex_output.get("checks", {}).get("c002_orchestration_passed") is True
    )
    checks["private_identity_redaction"] = (
        baseline_checks.get("private_identity_redacted") is True
        and codex_output.get("checks", {}).get("private_identity_redaction_observed") is True
    )
    checks["workspace_unchanged"] = (
        codex_output.get("checks", {}).get("workspace_unchanged") is True
    )

    evidence = codex_output.get("evidence", [])
    checks["evidence_present"] = isinstance(evidence, list) and len(evidence) >= 4
    blockers = codex_output.get("blockers", [])
    checks["no_codex_blockers"] = isinstance(blockers, list) and not blockers

    serialized = json.dumps(
        {"codex_output": codex_output, "baseline": baseline, "metadata": metadata},
        sort_keys=True,
    )
    checks["no_sensitive_markers"] = not any(marker in serialized for marker in SENSITIVE_MARKERS)

    verified = all(checks.values())
    return {
        "schema_version": 1,
        "context": "C003",
        "milestone": "codex-runtime-proof",
        "status": "verified" if verified else "blocked",
        "checks": checks,
        "runtime": {
            "name": "codex",
            "codex_cli_version": cli_version,
            "expected_codex_version": expected_cli,
            "model": metadata.get("model"),
            "action_commit": metadata.get("action_commit"),
            "repository_head": metadata.get("head_sha"),
        },
        "baseline": {
            "status": baseline.get("status"),
            "sha256": metadata.get("baseline_sha256"),
            "orchestration_status": orchestration.get("status"),
        },
        "codex_evidence": evidence if isinstance(evidence, list) else [],
        "blockers": [] if verified else sorted(
            key for key, value in checks.items() if not value
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex-output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--require-verified", action="store_true")
    args = parser.parse_args()

    codex_output = _load(args.codex_output)
    baseline = _load(args.baseline)
    metadata = _load(args.metadata)

    actual_baseline_sha = _sha256(args.baseline)
    expected_baseline_sha = str(metadata.get("baseline_sha256", ""))
    if expected_baseline_sha != actual_baseline_sha:
        raise ValueError("baseline SHA-256 does not match runtime metadata")

    report = validate(codex_output, baseline, metadata)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.require_verified and report["status"] != "verified":
        return 13
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
