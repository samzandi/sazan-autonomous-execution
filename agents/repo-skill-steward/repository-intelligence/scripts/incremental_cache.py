#!/usr/bin/env python3
"""Evidence-backed incremental cache receipts for C002 Repository Intelligence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
DECISIONS = {"hit", "miss"}
REUSE_POLICIES = {"same-revision-only", "fingerprint-stable-cross-revision"}


def _text(value: Any, name: str) -> str:
    out = str(value or "").strip()
    if not out:
        raise ValueError(f"{name} is required")
    return out


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def normalize_dependencies(value: Any) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("dependencies must be a list")
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for i, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise ValueError(f"dependencies[{i}] must be an object")
        name = _text(raw.get("name"), f"dependencies[{i}].name")
        fingerprint = _text(raw.get("fingerprint"), f"dependencies[{i}].fingerprint")
        if name in seen:
            raise ValueError(f"duplicate dependency name: {name}")
        seen.add(name)
        out.append({"name": name, "fingerprint": fingerprint})
    return sorted(out, key=lambda x: x["name"])


def normalize_descriptor(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("descriptor must be an object")
    if raw.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
        raise ValueError("unsupported cache descriptor schema version")

    reuse_policy = _text(
        raw.get("reuse_policy", "fingerprint-stable-cross-revision"),
        "reuse_policy",
    )
    if reuse_policy not in REUSE_POLICIES:
        raise ValueError("unsupported reuse_policy")

    descriptor = {
        "schema_version": SCHEMA_VERSION,
        "repository_id": _text(raw.get("repository_id"), "repository_id"),
        "revision": _text(raw.get("revision"), "revision"),
        "stage": _text(raw.get("stage"), "stage"),
        "provider": _text(raw.get("provider"), "provider"),
        "provider_version": _text(raw.get("provider_version"), "provider_version"),
        "provider_contract": _text(raw.get("provider_contract"), "provider_contract"),
        "stage_input_fingerprint": _text(
            raw.get("stage_input_fingerprint"), "stage_input_fingerprint"
        ),
        "policy_fingerprint": _text(
            raw.get("policy_fingerprint"), "policy_fingerprint"
        ),
        "implementation_fingerprint": _text(
            raw.get("implementation_fingerprint"), "implementation_fingerprint"
        ),
        "dependencies": normalize_dependencies(raw.get("dependencies")),
        "reuse_policy": reuse_policy,
    }
    return descriptor


def cache_identity(descriptor: dict[str, Any]) -> dict[str, Any]:
    """Return the fields that determine semantic cache compatibility.

    Revision is provenance, not part of the cross-revision semantic identity.
    """
    d = normalize_descriptor(descriptor)
    return {
        "schema_version": SCHEMA_VERSION,
        "repository_id": d["repository_id"],
        "stage": d["stage"],
        "provider": d["provider"],
        "provider_version": d["provider_version"],
        "provider_contract": d["provider_contract"],
        "stage_input_fingerprint": d["stage_input_fingerprint"],
        "policy_fingerprint": d["policy_fingerprint"],
        "implementation_fingerprint": d["implementation_fingerprint"],
        "dependencies": d["dependencies"],
    }


def cache_key(descriptor: dict[str, Any]) -> str:
    return "cache_" + sha256_json(cache_identity(descriptor))[:24]


def create_entry(
    descriptor: dict[str, Any],
    result_fingerprint: str,
    *,
    artifacts: list[dict[str, Any]] | None = None,
    evidence: list[str] | None = None,
) -> dict[str, Any]:
    d = normalize_descriptor(descriptor)
    result_fingerprint = _text(result_fingerprint, "result_fingerprint")

    normalized_artifacts: list[dict[str, str]] = []
    for i, raw in enumerate(artifacts or []):
        if not isinstance(raw, dict):
            raise ValueError(f"artifacts[{i}] must be an object")
        normalized_artifacts.append({
            "name": _text(raw.get("name"), f"artifacts[{i}].name"),
            "fingerprint": _text(
                raw.get("fingerprint"), f"artifacts[{i}].fingerprint"
            ),
        })
    normalized_artifacts.sort(key=lambda x: x["name"])

    normalized_evidence = sorted({
        _text(item, "evidence[]") for item in (evidence or [])
    })

    return {
        "schema_version": SCHEMA_VERSION,
        "cache_key": cache_key(d),
        "descriptor": d,
        "result_fingerprint": result_fingerprint,
        "artifacts": normalized_artifacts,
        "evidence": normalized_evidence,
    }


def evaluate(entry: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(entry, dict) or entry.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported cache entry schema version")
    stored = normalize_descriptor(entry.get("descriptor", {}))
    now = normalize_descriptor(current)

    reasons: list[str] = []

    exact_fields = [
        "repository_id",
        "stage",
        "provider",
        "provider_version",
        "provider_contract",
        "stage_input_fingerprint",
        "policy_fingerprint",
        "implementation_fingerprint",
        "dependencies",
    ]
    for field in exact_fields:
        if stored[field] != now[field]:
            reasons.append(f"{field}-changed")

    if now["reuse_policy"] == "same-revision-only" and stored["revision"] != now["revision"]:
        reasons.append("revision-changed-under-same-revision-policy")

    expected_key = cache_key(stored)
    if entry.get("cache_key") != expected_key:
        reasons.append("stored-cache-key-integrity-failed")

    if not str(entry.get("result_fingerprint", "")).strip():
        reasons.append("missing-result-fingerprint")

    decision = "miss" if reasons else "hit"
    cross_revision = stored["revision"] != now["revision"]

    return {
        "schema_version": SCHEMA_VERSION,
        "decision": decision,
        "cache_key": expected_key,
        "source_revision": stored["revision"],
        "current_revision": now["revision"],
        "cross_revision_reuse": decision == "hit" and cross_revision,
        "reasons": sorted(set(reasons)),
        "result_fingerprint": entry.get("result_fingerprint"),
        "artifacts": entry.get("artifacts", []),
        "evidence": entry.get("evidence", []),
    }


def dependency_fingerprint(receipts: list[dict[str, Any]]) -> str:
    normalized = []
    for i, raw in enumerate(receipts):
        if not isinstance(raw, dict):
            raise ValueError(f"receipts[{i}] must be an object")
        normalized.append({
            "name": _text(raw.get("name"), f"receipts[{i}].name"),
            "fingerprint": _text(
                raw.get("fingerprint"), f"receipts[{i}].fingerprint"
            ),
        })
    normalized.sort(key=lambda x: x["name"])
    return sha256_json(normalized)


def fingerprint_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    key_cmd = sub.add_parser("key")
    key_cmd.add_argument("descriptor", type=Path)

    check_cmd = sub.add_parser("check")
    check_cmd.add_argument("entry", type=Path)
    check_cmd.add_argument("descriptor", type=Path)
    check_cmd.add_argument("--output", type=Path, required=True)
    check_cmd.add_argument("--require-hit", action="store_true")

    args = parser.parse_args()

    if args.command == "key":
        descriptor = json.loads(args.descriptor.read_text(encoding="utf-8"))
        print(cache_key(descriptor))
        return 0

    entry = json.loads(args.entry.read_text(encoding="utf-8"))
    descriptor = json.loads(args.descriptor.read_text(encoding="utf-8"))
    report = evaluate(entry, descriptor)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.require_hit and report["decision"] != "hit":
        return 9
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
