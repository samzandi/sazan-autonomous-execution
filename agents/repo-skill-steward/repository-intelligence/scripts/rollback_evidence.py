#!/usr/bin/env python3
"""Validate C003 failure/rollback evidence deterministically."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
ALLOWED_ISOLATION = {"git-worktree"}
ALLOWED_ROLLBACK_METHODS = {"git-reset-hard-to-verified-revision", "worktree-recreate-from-verified-revision"}
SENSITIVE_MARKERS = (
    "secret-owner",
    "private-payments-worker",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "sk-proj-",
    "sk-ant-",
)
ABSOLUTE_PATH_MARKERS = ("/home/", "/tmp/", "/Users/", "C:\\")


def _text(value: Any, name: str) -> str:
    out = str(value or "").strip()
    if not out:
        raise ValueError(f"{name} is required")
    return out


def _obj(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _evidence(value: Any, name: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list")
    out = sorted({_text(item, f"{name}[]") for item in value})
    return out


def _fingerprint(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate(receipt: dict[str, Any]) -> dict[str, Any]:
    if receipt.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("schema_version must be 1")

    transaction_id = _text(receipt.get("transaction_id"), "transaction_id")
    repository_id = _text(receipt.get("repository_id"), "repository_id")

    isolation = _obj(receipt.get("isolation"), "isolation")
    rollback_point = _obj(receipt.get("rollback_point"), "rollback_point")
    failure = _obj(receipt.get("failure"), "failure")
    mutation = _obj(receipt.get("mutation"), "mutation")
    rollback = _obj(receipt.get("rollback"), "rollback")
    post = _obj(receipt.get("post_rollback"), "post_rollback")
    private_data = _obj(receipt.get("private_data"), "private_data")

    checks: dict[str, bool] = {}

    isolation_mode = _text(isolation.get("mode"), "isolation.mode")
    checks["isolated_worktree"] = isolation_mode in ALLOWED_ISOLATION
    checks["isolation_evidence"] = bool(_evidence(isolation.get("evidence", []), "isolation.evidence"))

    rollback_revision = _text(rollback_point.get("revision"), "rollback_point.revision")
    rollback_tree = _text(rollback_point.get("tree_hash"), "rollback_point.tree_hash")
    checks["rollback_point_recorded"] = bool(rollback_revision and rollback_tree)
    checks["rollback_point_evidence"] = bool(
        _evidence(rollback_point.get("evidence", []), "rollback_point.evidence")
    )

    failure_status = _text(failure.get("status"), "failure.status")
    exit_code = failure.get("exit_code")
    checks["failure_observed"] = (
        failure_status == "observed"
        and isinstance(exit_code, int)
        and not isinstance(exit_code, bool)
        and exit_code != 0
    )
    checks["failure_evidence"] = bool(_evidence(failure.get("evidence", []), "failure.evidence"))
    _text(failure.get("command"), "failure.command")

    mutation_revision = _text(mutation.get("revision"), "mutation.revision")
    checks["mutation_is_distinct"] = mutation_revision != rollback_revision
    checks["mutation_evidence"] = bool(_evidence(mutation.get("evidence", []), "mutation.evidence"))

    method = _text(rollback.get("method"), "rollback.method")
    target_revision = _text(rollback.get("target_revision"), "rollback.target_revision")
    checks["rollback_method_allowed"] = method in ALLOWED_ROLLBACK_METHODS
    checks["rollback_target_matches"] = target_revision == rollback_revision
    checks["rollback_action_evidence"] = bool(
        _evidence(rollback.get("evidence", []), "rollback.evidence")
    )

    final_revision = _text(post.get("revision"), "post_rollback.revision")
    final_tree = _text(post.get("tree_hash"), "post_rollback.tree_hash")
    checks["revision_restored"] = final_revision == rollback_revision
    checks["tree_restored"] = final_tree == rollback_tree
    checks["worktree_clean"] = post.get("clean_worktree") is True
    checks["parent_workspace_unchanged"] = post.get("parent_workspace_unchanged") is True

    validation = _obj(post.get("functional_validation"), "post_rollback.functional_validation")
    checks["functional_validation_passed"] = (
        validation.get("status") == "passed"
        and bool(_evidence(validation.get("evidence", []), "post_rollback.functional_validation.evidence"))
    )

    checks["private_data_compliant"] = (
        private_data.get("status") == "compliant"
        and bool(_evidence(private_data.get("evidence", []), "private_data.evidence"))
    )

    serialized = json.dumps(receipt, sort_keys=True)
    checks["no_sensitive_markers"] = not any(marker in serialized for marker in SENSITIVE_MARKERS)
    checks["no_absolute_paths_persisted"] = not any(marker in serialized for marker in ABSOLUTE_PATH_MARKERS)

    blockers = sorted(key for key, passed in checks.items() if not passed)
    verified = not blockers
    core = {
        "transaction_id": transaction_id,
        "repository_id": repository_id,
        "rollback_revision": rollback_revision,
        "rollback_tree": rollback_tree,
        "mutation_revision": mutation_revision,
        "checks": checks,
        "blockers": blockers,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "context": "C003",
        "milestone": "failure-rollback-evidence",
        "status": "verified" if verified else "blocked",
        "transaction_id": transaction_id,
        "repository_id": repository_id,
        "checks": checks,
        "rollback": {
            "method": method,
            "rollback_revision": rollback_revision,
            "rollback_tree": rollback_tree,
            "mutation_revision": mutation_revision,
            "final_revision": final_revision,
            "final_tree": final_tree,
        },
        "blockers": blockers,
        "evidence_fingerprint": _fingerprint(core),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-verified", action="store_true")
    args = parser.parse_args()

    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    if not isinstance(receipt, dict):
        raise ValueError("receipt must be an object")
    result = validate(receipt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.require_verified and result["status"] != "verified":
        return 16
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
