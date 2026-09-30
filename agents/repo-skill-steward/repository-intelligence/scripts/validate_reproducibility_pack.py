#!/usr/bin/env python3
"""Validate a C003 Repository Intelligence reproducibility pack."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("build_reproducibility_pack", HERE / "build_reproducibility_pack.py")
BUILD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(BUILD)

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


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected JSON object")
    return data


def _fingerprint_without_field(pack: dict[str, Any]) -> str:
    body = dict(pack)
    body.pop("pack_fingerprint", None)
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate(pack: dict[str, Any], repo_root: Path, spec_path: Path) -> dict[str, Any]:
    expected = BUILD.build(repo_root, spec_path)
    checks: dict[str, bool] = {}

    checks["schema"] = pack.get("schema_version") == 1 and pack.get("context") == "C003"
    checks["source_revision"] = pack.get("source", {}).get("revision") == expected["source"]["revision"]
    checks["source_tree"] = pack.get("source", {}).get("tree_hash") == expected["source"]["tree_hash"]
    checks["source_clean"] = pack.get("source", {}).get("clean") is True and expected["source"]["clean"] is True
    checks["spec_integrity"] = pack.get("spec") == expected["spec"]
    checks["file_manifest"] = pack.get("files") == expected["files"]
    checks["external_tools"] = pack.get("external_tools") == expected["external_tools"]
    checks["verified_runs"] = pack.get("verified_runs") == expected["verified_runs"]
    checks["runtime_proofs"] = pack.get("runtime_proofs") == expected["runtime_proofs"]
    checks["reproduction_commands"] = pack.get("reproduction_commands") == expected["reproduction_commands"]
    checks["pack_fingerprint"] = (
        pack.get("pack_fingerprint") == expected["pack_fingerprint"]
        and pack.get("pack_fingerprint") == _fingerprint_without_field(pack)
    )

    tools = pack.get("external_tools", [])
    checks["tool_integrity_declared"] = (
        isinstance(tools, list)
        and bool(tools)
        and all(
            isinstance(tool, dict)
            and str(tool.get("name", "")).strip()
            and str(tool.get("version", "")).strip()
            and str(tool.get("source", "")).strip()
            and str(tool.get("immutable_ref", "")).strip()
            and str(tool.get("integrity", "")).strip()
            for tool in tools
        )
    )

    runs = pack.get("verified_runs", [])
    checks["run_evidence_verified"] = (
        isinstance(runs, list)
        and bool(runs)
        and all(
            isinstance(item, dict)
            and item.get("status") == "verified"
            and isinstance(item.get("run_id"), int)
            and item["run_id"] > 0
            for item in runs
        )
    )

    proofs = pack.get("runtime_proofs", [])
    checks["blocked_runtime_proofs_are_explicit"] = (
        isinstance(proofs, list)
        and all(
            isinstance(item, dict)
            and item.get("status") in {"verified", "blocked"}
            and (
                item.get("status") != "blocked"
                or bool(str(item.get("blocker", "")).strip())
            )
            for item in proofs
        )
    )

    serialized = json.dumps(pack, sort_keys=True)
    checks["no_sensitive_markers"] = not any(marker in serialized for marker in SENSITIVE_MARKERS)
    checks["no_absolute_paths"] = not any(marker in serialized for marker in ABSOLUTE_PATH_MARKERS)

    blockers = sorted(key for key, value in checks.items() if not value)
    return {
        "schema_version": 1,
        "context": "C003",
        "milestone": "reproducibility-pack",
        "status": "verified" if not blockers else "blocked",
        "checks": checks,
        "source_revision": expected["source"]["revision"],
        "pack_fingerprint": pack.get("pack_fingerprint"),
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pack", type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-verified", action="store_true")
    args = parser.parse_args()

    result = validate(_load(args.pack), args.repo_root, args.spec)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.require_verified and result["status"] != "verified":
        return 18
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
