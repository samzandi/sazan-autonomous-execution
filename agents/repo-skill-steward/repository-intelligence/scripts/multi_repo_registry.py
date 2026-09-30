#!/usr/bin/env python3
"""Build a privacy-safe multi-repository registry and cross-repository contract graph."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
VISIBILITIES = {"public", "private", "internal", "local-fixture"}
CONTRACT_KINDS = {"http-api", "event", "schema", "package", "cli", "storage", "custom"}
CLAIM_STATES = {"observed", "inferred"}
REQUIREMENT_SCOPES = {"internal", "external"}
PRIVATE_ID = re.compile(r"^repo_[A-Za-z0-9_-]{4,64}$")


def _text(value: Any, name: str) -> str:
    out = str(value or "").strip()
    if not out:
        raise ValueError(f"{name} is required")
    return out


def _list(value: Any, name: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list")
    return value


def _public_id(source: str) -> str:
    digest = hashlib.sha256(source.lower().encode("utf-8")).hexdigest()[:12]
    return f"public_{digest}"


def _contract_id(provider: str, consumer: str, key: str, kind: str) -> str:
    material = f"{provider}\0{consumer}\0{key}\0{kind}".encode("utf-8")
    return "contract_" + hashlib.sha256(material).hexdigest()[:16]


def _normalize_claim(item: dict[str, Any], where: str, *, requirement: bool) -> dict[str, Any]:
    key = _text(item.get("key"), f"{where}.key")
    kind = _text(item.get("kind"), f"{where}.kind")
    if kind not in CONTRACT_KINDS:
        raise ValueError(f"{where}.kind unsupported: {kind}")

    state = _text(item.get("state", "observed"), f"{where}.state")
    if state not in CLAIM_STATES:
        raise ValueError(f"{where}.state must be observed or inferred")

    evidence = _list(item.get("evidence"), f"{where}.evidence")
    if not evidence or not all(isinstance(x, str) and x.strip() for x in evidence):
        raise ValueError(f"{where}: evidence is required")

    rationale = str(item.get("rationale", "")).strip()
    if state == "inferred" and not rationale:
        raise ValueError(f"{where}: inferred contract observation requires rationale")

    result = {
        "key": key,
        "kind": kind,
        "version": str(item.get("version", "unspecified")).strip() or "unspecified",
        "surface": str(item.get("surface", "")).strip(),
        "state": state,
        "evidence": sorted(set(x.strip() for x in evidence)),
        "rationale": rationale,
    }

    if requirement:
        scope = _text(item.get("scope", "internal"), f"{where}.scope")
        if scope not in REQUIREMENT_SCOPES:
            raise ValueError(f"{where}.scope must be internal or external")
        result["scope"] = scope
        hint = str(item.get("provider_hint", "")).strip()
        result["provider_hint"] = hint or None
    return result


def _versions_compatible(provided: str, required: str) -> bool:
    if required in {"*", "unspecified"}:
        return True
    if provided == "unspecified":
        return required == "unspecified"
    return provided == required


def build(workspace: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if workspace.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("schema_version must be 1")
    workspace_id = _text(workspace.get("workspace_id"), "workspace_id")
    raw_repos = _list(workspace.get("repositories"), "repositories")
    if len(raw_repos) < 2:
        raise ValueError("multi-repository registry requires at least two repositories")

    repos: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for index, raw in enumerate(raw_repos):
        if not isinstance(raw, dict):
            raise ValueError(f"repositories[{index}] must be an object")
        visibility = _text(raw.get("visibility"), f"repositories[{index}].visibility")
        if visibility not in VISIBILITIES:
            raise ValueError(f"repositories[{index}]: unsupported visibility")

        revision = _text(raw.get("revision"), f"repositories[{index}].revision")
        source = str(raw.get("source", "")).strip()
        explicit_id = str(raw.get("repository_id", "")).strip()

        if visibility in {"private", "internal"}:
            if not explicit_id or not PRIVATE_ID.fullmatch(explicit_id):
                raise ValueError(
                    f"repositories[{index}]: private/internal repository requires stable opaque repository_id"
                )
            repository_id = explicit_id
            persisted_source = None
        else:
            if not source:
                raise ValueError(f"repositories[{index}].source is required")
            repository_id = explicit_id or _public_id(source)
            persisted_source = source

        if repository_id in seen_ids:
            raise ValueError(f"duplicate repository_id: {repository_id}")
        seen_ids.add(repository_id)

        raw_provides = _list(raw.get("provides"), f"{repository_id}.provides")
        raw_requires = _list(raw.get("requires"), f"{repository_id}.requires")
        if any(not isinstance(x, dict) for x in raw_provides):
            raise ValueError(f"{repository_id}.provides entries must be objects")
        if any(not isinstance(x, dict) for x in raw_requires):
            raise ValueError(f"{repository_id}.requires entries must be objects")

        provides = [
            _normalize_claim(x, f"{repository_id}.provides[{i}]", requirement=False)
            for i, x in enumerate(raw_provides)
        ]
        requires = [
            _normalize_claim(x, f"{repository_id}.requires[{i}]", requirement=True)
            for i, x in enumerate(raw_requires)
        ]

        repos.append({
            "repository_id": repository_id,
            "visibility": visibility,
            "source": persisted_source,
            "revision": revision,
            "provides": sorted(provides, key=lambda x: (x["key"], x["kind"], x["version"])),
            "requires": sorted(requires, key=lambda x: (x["key"], x["kind"], x["version"])),
        })

    by_id = {r["repository_id"]: r for r in repos}
    providers: dict[tuple[str, str], list[tuple[str, dict[str, Any]]]] = {}
    for repo in repos:
        for item in repo["provides"]:
            providers.setdefault((item["key"], item["kind"]), []).append((repo["repository_id"], item))

    contracts: list[dict[str, Any]] = []
    external_requirements: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []

    for consumer in repos:
        consumer_id = consumer["repository_id"]
        for req in consumer["requires"]:
            key = (req["key"], req["kind"])
            candidates = list(providers.get(key, []))
            hint = req.get("provider_hint")
            if hint:
                if hint not in by_id:
                    raise ValueError(f"{consumer_id}: provider_hint references unknown repository_id {hint}")
                candidates = [c for c in candidates if c[0] == hint]

            if req["scope"] == "external":
                external_requirements.append({
                    "consumer": consumer_id,
                    "key": req["key"],
                    "kind": req["kind"],
                    "version": req["version"],
                    "evidence": req["evidence"],
                })
                continue

            if not candidates:
                issue = {
                    "type": "unresolved-contract",
                    "consumer": consumer_id,
                    "key": req["key"],
                    "kind": req["kind"],
                    "required_version": req["version"],
                }
                blockers.append(issue)
                continue

            if len(candidates) > 1:
                issue = {
                    "type": "ambiguous-provider",
                    "consumer": consumer_id,
                    "key": req["key"],
                    "kind": req["kind"],
                    "providers": sorted(c[0] for c in candidates),
                }
                blockers.append(issue)
                continue

            provider_id, provided = candidates[0]
            if provider_id == consumer_id:
                issue = {
                    "type": "self-contract-not-cross-repository",
                    "consumer": consumer_id,
                    "key": req["key"],
                    "kind": req["kind"],
                }
                blockers.append(issue)
                continue

            compatible = _versions_compatible(provided["version"], req["version"])
            status = "matched" if compatible else "version-mismatch"
            claim_state = "observed" if provided["state"] == req["state"] == "observed" else "inferred"
            constraints = []
            if claim_state == "inferred":
                constraints.append("cross-repository relationship contains inferred evidence")

            contract = {
                "contract_id": _contract_id(provider_id, consumer_id, req["key"], req["kind"]),
                "provider": provider_id,
                "consumer": consumer_id,
                "key": req["key"],
                "kind": req["kind"],
                "surface": req["surface"] or provided["surface"],
                "provided_version": provided["version"],
                "required_version": req["version"],
                "status": status,
                "claim_state": claim_state,
                "evidence": sorted(set(provided["evidence"] + req["evidence"])),
                "constraints": constraints,
            }
            contracts.append(contract)
            if not compatible:
                blockers.append({
                    "type": "version-mismatch",
                    "contract_id": contract["contract_id"],
                    "provider": provider_id,
                    "consumer": consumer_id,
                    "key": req["key"],
                    "provided_version": provided["version"],
                    "required_version": req["version"],
                })

    contracts.sort(key=lambda x: (x["provider"], x["consumer"], x["key"], x["kind"]))
    blockers.sort(key=lambda x: json.dumps(x, sort_keys=True))
    external_requirements.sort(key=lambda x: (x["consumer"], x["key"], x["kind"]))

    registry_repos = []
    for repo in sorted(repos, key=lambda x: x["repository_id"]):
        registry_repos.append({
            "repository_id": repo["repository_id"],
            "visibility": repo["visibility"],
            "source": repo["source"],
            "revision": repo["revision"],
            "provides_count": len(repo["provides"]),
            "requires_count": len(repo["requires"]),
        })

    upstream: dict[str, set[str]] = {rid: set() for rid in by_id}
    downstream: dict[str, set[str]] = {rid: set() for rid in by_id}
    for contract in contracts:
        if contract["status"] == "matched":
            upstream[contract["consumer"]].add(contract["provider"])
            downstream[contract["provider"]].add(contract["consumer"])

    registry = {
        "schema_version": SCHEMA_VERSION,
        "context": "C002",
        "workspace_id": workspace_id,
        "repositories": registry_repos,
        "relationships": {
            rid: {
                "upstream": sorted(upstream[rid]),
                "downstream": sorted(downstream[rid]),
            }
            for rid in sorted(by_id)
        },
        "privacy": {
            "private_sources_persisted": False,
            "private_ids_must_be_opaque_and_stable": True,
        },
    }

    report = {
        "schema_version": SCHEMA_VERSION,
        "context": "C002",
        "workspace_id": workspace_id,
        "status": "blocked" if blockers else "verified",
        "contracts": contracts,
        "external_requirements": external_requirements,
        "blockers": blockers,
        "summary": {
            "repositories": len(repos),
            "matched_contracts": sum(1 for c in contracts if c["status"] == "matched"),
            "version_mismatches": sum(1 for c in contracts if c["status"] == "version-mismatch"),
            "external_requirements": len(external_requirements),
            "blockers": len(blockers),
        },
    }
    return registry, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--contracts", type=Path, required=True)
    parser.add_argument("--require-no-blockers", action="store_true")
    args = parser.parse_args()

    raw = json.loads(args.workspace.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("workspace must be a JSON object")

    registry, report = build(raw)
    args.registry.parent.mkdir(parents=True, exist_ok=True)
    args.contracts.parent.mkdir(parents=True, exist_ok=True)
    args.registry.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.contracts.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.require_no_blockers and report["blockers"]:
        return 5
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
