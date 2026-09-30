#!/usr/bin/env python3
"""Normalize repository diffs into evidence-backed cross-repository blast radius."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
CHANGE_TYPES = {"add", "modify", "delete", "rename", "version-change"}
SURFACE_KINDS = {
    "file", "symbol", "contract", "http-api", "event", "schema",
    "package", "cli", "storage", "custom",
}
CLAIM_STATES = {"observed", "inferred"}
CONTRACT_SURFACES = {"contract", "http-api", "event", "schema", "package", "cli", "storage", "custom"}


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


def _claim(raw: dict[str, Any], where: str) -> tuple[str, list[str], str]:
    state = _text(raw.get("state", "observed"), f"{where}.state")
    if state not in CLAIM_STATES:
        raise ValueError(f"{where}.state must be observed or inferred")
    evidence = _list(raw.get("evidence"), f"{where}.evidence")
    if not evidence or not all(isinstance(x, str) and x.strip() for x in evidence):
        raise ValueError(f"{where}: evidence is required")
    rationale = str(raw.get("rationale", "")).strip()
    if state == "inferred" and not rationale:
        raise ValueError(f"{where}: inferred change requires rationale")
    return state, sorted(set(x.strip() for x in evidence)), rationale


def _repo_ids(registry: dict[str, Any]) -> set[str]:
    repos = _list(registry.get("repositories"), "registry.repositories")
    ids = set()
    for i, raw in enumerate(repos):
        if not isinstance(raw, dict):
            raise ValueError(f"registry.repositories[{i}] must be an object")
        ids.add(_text(raw.get("repository_id"), f"registry.repositories[{i}].repository_id"))
    return ids


def _contract_map(contracts: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out = {}
    for i, raw in enumerate(_list(contracts.get("contracts"), "contracts.contracts")):
        if not isinstance(raw, dict):
            raise ValueError(f"contracts.contracts[{i}] must be an object")
        cid = _text(raw.get("contract_id"), f"contracts.contracts[{i}].contract_id")
        if cid in out:
            raise ValueError(f"duplicate contract_id: {cid}")
        out[cid] = raw
    return out


def normalize(
    registry: dict[str, Any],
    contracts: dict[str, Any],
    flows: dict[str, Any],
    changes: dict[str, Any],
) -> dict[str, Any]:
    for name, payload in [
        ("registry", registry),
        ("contracts", contracts),
        ("flows", flows),
        ("changes", changes),
    ]:
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"{name}.schema_version must be 1")

    workspace_id = _text(registry.get("workspace_id"), "registry.workspace_id")
    for name, payload in [("contracts", contracts), ("flows", flows), ("changes", changes)]:
        if payload.get("workspace_id") != workspace_id:
            raise ValueError(f"workspace_id mismatch: {name}")

    repo_ids = _repo_ids(registry)
    contract_by_id = _contract_map(contracts)

    steps = {}
    for i, raw in enumerate(_list(flows.get("steps"), "flows.steps")):
        if not isinstance(raw, dict):
            raise ValueError(f"flows.steps[{i}] must be an object")
        sid = _text(raw.get("step_id"), f"flows.steps[{i}].step_id")
        if sid in steps:
            raise ValueError(f"duplicate step_id: {sid}")
        steps[sid] = raw

    edges = {}
    for i, raw in enumerate(_list(flows.get("edges"), "flows.edges")):
        if not isinstance(raw, dict):
            raise ValueError(f"flows.edges[{i}] must be an object")
        eid = _text(raw.get("edge_id"), f"flows.edges[{i}].edge_id")
        if eid in edges:
            raise ValueError(f"duplicate edge_id: {eid}")
        edges[eid] = raw

    flow_records = []
    for i, raw in enumerate(_list(flows.get("flows"), "flows.flows")):
        if not isinstance(raw, dict):
            raise ValueError(f"flows.flows[{i}] must be an object")
        flow_records.append(raw)

    raw_changes = _list(changes.get("changes"), "changes.changes")
    if not raw_changes:
        raise ValueError("changes.changes must not be empty")

    normalized_changes = []
    all_impacted_repos: set[str] = set()
    all_impacted_contracts: set[str] = set()
    all_impacted_flows: set[str] = set()
    all_impacted_steps: set[str] = set()
    incomplete: list[dict[str, Any]] = []
    related_test_targets: set[str] = set()

    for index, raw in enumerate(raw_changes):
        if not isinstance(raw, dict):
            raise ValueError(f"changes[{index}] must be an object")
        where = f"changes[{index}]"
        change_id = _text(raw.get("change_id"), f"{where}.change_id")
        repository_id = _text(raw.get("repository_id"), f"{where}.repository_id")
        if repository_id not in repo_ids:
            raise ValueError(f"{change_id}: unknown repository_id {repository_id}")
        change_type = _text(raw.get("change_type"), f"{where}.change_type")
        if change_type not in CHANGE_TYPES:
            raise ValueError(f"{change_id}: unsupported change_type")
        surface_kind = _text(raw.get("surface_kind"), f"{where}.surface_kind")
        if surface_kind not in SURFACE_KINDS:
            raise ValueError(f"{change_id}: unsupported surface_kind")
        identifier = _text(raw.get("identifier"), f"{where}.identifier")
        state, evidence, rationale = _claim(raw, where)

        local = raw.get("local_impact", {})
        if local is None:
            local = {}
        if not isinstance(local, dict):
            raise ValueError(f"{where}.local_impact must be an object")
        local_evidence = _list(local.get("evidence"), f"{where}.local_impact.evidence")
        if local_evidence and not all(isinstance(x, str) and x.strip() for x in local_evidence):
            raise ValueError(f"{where}.local_impact.evidence must contain strings")
        local_evidence = sorted(set(str(x).strip() for x in local_evidence if str(x).strip()))

        impacted_steps: set[str] = set()
        explicit_steps = _list(local.get("steps"), f"{where}.local_impact.steps")
        for sid in explicit_steps:
            if not isinstance(sid, str) or sid not in steps:
                raise ValueError(f"{change_id}: unknown local impact step {sid!r}")
            if steps[sid].get("repository_id") != repository_id:
                raise ValueError(f"{change_id}: local impact step belongs to a different repository")
            impacted_steps.add(sid)

        symbol_names = set()
        explicit_symbols = _list(local.get("symbols"), f"{where}.local_impact.symbols")
        for symbol in explicit_symbols:
            symbol_names.add(_text(symbol, f"{where}.local_impact.symbols[]"))

        local_files = sorted(set(
            _text(value, f"{where}.local_impact.files[]")
            for value in _list(local.get("files"), f"{where}.local_impact.files")
        ))
        local_tests = sorted(set(
            _text(value, f"{where}.local_impact.tests[]")
            for value in _list(local.get("tests"), f"{where}.local_impact.tests")
        ))

        if surface_kind == "symbol":
            symbol_names.add(identifier)

        for sid, step in steps.items():
            if step.get("repository_id") == repository_id and step.get("symbol") in symbol_names:
                impacted_steps.add(sid)

        impacted_contracts: set[str] = set()
        contract_id = str(raw.get("contract_id", "")).strip()
        if surface_kind in CONTRACT_SURFACES:
            if not contract_id:
                raise ValueError(f"{change_id}: contract surface requires contract_id")
            contract = contract_by_id.get(contract_id)
            if contract is None:
                raise ValueError(f"{change_id}: unknown contract_id {contract_id}")
            if repository_id not in {contract.get("provider"), contract.get("consumer")}:
                raise ValueError(f"{change_id}: repository is not a party to contract {contract_id}")
            if surface_kind != "contract" and contract.get("kind") != surface_kind:
                raise ValueError(f"{change_id}: surface_kind does not match contract kind")
            impacted_contracts.add(contract_id)

        compatibility = "not-applicable"
        if change_type == "version-change" and impacted_contracts:
            new_version = _text(raw.get("new_version"), f"{where}.new_version")
            mismatch = False
            for cid in impacted_contracts:
                contract = contract_by_id[cid]
                required = str(contract.get("required_version", "unspecified"))
                if required not in {"*", "unspecified", new_version}:
                    mismatch = True
            compatibility = "version-mismatch" if mismatch else "compatible-with-recorded-requirement"

        impacted_edges: set[str] = set()
        for eid, edge in edges.items():
            if edge.get("contract_id") in impacted_contracts:
                impacted_edges.add(eid)

        impacted_flow_ids: set[str] = set()
        transitive_steps: set[str] = set()
        transitive_repos: set[str] = set()
        directly_impacted_repos: set[str] = {repository_id}

        for cid in impacted_contracts:
            contract = contract_by_id[cid]
            directly_impacted_repos.update(
                r for r in [contract.get("provider"), contract.get("consumer")] if r
            )

        for flow in flow_records:
            flow_id = _text(flow.get("flow_id"), "flow.flow_id")
            path = _list(flow.get("steps"), f"{flow_id}.steps")
            edge_ids = _list(flow.get("edge_ids"), f"{flow_id}.edge_ids")

            impact_positions: list[int] = []
            for sid in impacted_steps:
                if sid in path:
                    impact_positions.append(path.index(sid))
            for eid in impacted_edges:
                if eid in edge_ids:
                    # Edge index i connects path[i] -> path[i+1]; both boundary sides need review.
                    impact_positions.append(edge_ids.index(eid))

            if not impact_positions:
                continue

            impacted_flow_ids.add(flow_id)
            start = min(impact_positions)
            for sid in path[start:]:
                transitive_steps.add(sid)
                rid = steps.get(sid, {}).get("repository_id")
                if rid:
                    transitive_repos.add(rid)

        mapped = bool(impacted_steps or impacted_contracts)
        mapping_status = "mapped" if mapped else "unmapped"
        constraints = []
        if state == "inferred":
            constraints.append("change observation is inferred")
        if not mapped:
            constraints.append("no symbol/process-step or contract mapping evidence")
            incomplete.append({
                "change_id": change_id,
                "reason": "no impact mapping evidence",
            })
        if surface_kind == "file" and not local_evidence:
            constraints.append("file change has no local semantic-impact evidence")
            incomplete.append({
                "change_id": change_id,
                "reason": "file change requires local semantic-impact evidence",
            })

        review_repos = sorted(directly_impacted_repos | transitive_repos)
        all_impacted_repos.update(review_repos)
        all_impacted_contracts.update(impacted_contracts)
        all_impacted_flows.update(impacted_flow_ids)
        all_impacted_steps.update(impacted_steps | transitive_steps)

        related_test_targets.update(local_tests)

        normalized_changes.append({
            "change_id": change_id,
            "repository_id": repository_id,
            "change_type": change_type,
            "surface_kind": surface_kind,
            "identifier": identifier,
            "state": state,
            "evidence": sorted(set(evidence + local_evidence)),
            "rationale": rationale,
            "mapping_status": mapping_status,
            "direct_steps": sorted(impacted_steps),
            "transitive_steps": sorted(transitive_steps - impacted_steps),
            "impacted_contracts": sorted(impacted_contracts),
            "impacted_flows": sorted(impacted_flow_ids),
            "review_repositories": review_repos,
            "compatibility": compatibility,
            "local_impact": {
                "symbols": sorted(symbol_names),
                "files": local_files,
                "tests": local_tests,
                "evidence": local_evidence,
            },
            "constraints": sorted(set(constraints)),
        })

    incomplete_unique = []
    seen = set()
    for item in incomplete:
        key = (item["change_id"], item["reason"])
        if key not in seen:
            seen.add(key)
            incomplete_unique.append(item)

    test_scopes = []
    for rid in sorted(all_impacted_repos):
        test_scopes.append({
            "repository_id": rid,
            "reason": "repository participates in direct or transitive blast radius",
        })
    for cid in sorted(all_impacted_contracts):
        test_scopes.append({
            "contract_id": cid,
            "reason": "contract compatibility/regression validation required",
        })
    for fid in sorted(all_impacted_flows):
        test_scopes.append({
            "flow_id": fid,
            "reason": "end-to-end regression validation required",
        })
    for target in sorted(related_test_targets):
        test_scopes.append({
            "test_target": target,
            "reason": "related local test from semantic diff evidence",
        })

    status = "partial-evidence" if incomplete_unique else "verified"
    version_mismatch_changes = [
        c["change_id"] for c in normalized_changes if c["compatibility"] == "version-mismatch"
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "context": "C002",
        "workspace_id": workspace_id,
        "status": status,
        "changes": sorted(normalized_changes, key=lambda x: x["change_id"]),
        "blast_radius": {
            "repositories": sorted(all_impacted_repos),
            "contracts": sorted(all_impacted_contracts),
            "flows": sorted(all_impacted_flows),
            "steps": sorted(all_impacted_steps),
        },
        "compatibility_findings": {
            "version_mismatch_changes": sorted(version_mismatch_changes),
        },
        "test_review_scope": test_scopes,
        "incomplete_evidence": incomplete_unique,
        "summary": {
            "changes": len(normalized_changes),
            "impacted_repositories": len(all_impacted_repos),
            "impacted_contracts": len(all_impacted_contracts),
            "impacted_flows": len(all_impacted_flows),
            "impacted_steps": len(all_impacted_steps),
            "version_mismatches": len(version_mismatch_changes),
            "incomplete_evidence": len(incomplete_unique),
            "related_test_targets": len(related_test_targets),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    out = [
        "# Cross-Repository Diff Impact",
        "",
        f"- Workspace: {report['workspace_id']}",
        f"- Status: {report['status']}",
        f"- Changes: {report['summary']['changes']}",
        f"- Impacted repositories: {report['summary']['impacted_repositories']}",
        f"- Impacted contracts: {report['summary']['impacted_contracts']}",
        f"- Impacted flows: {report['summary']['impacted_flows']}",
        "",
    ]
    for change in report["changes"]:
        out.extend([
            f"## {change['change_id']} — {change['surface_kind']} / {change['change_type']}",
            "",
            f"- Repository: {change['repository_id']}",
            f"- Identifier: {change['identifier']}",
            f"- Mapping: {change['mapping_status']}",
            f"- Compatibility: {change['compatibility']}",
            f"- Review repositories: {', '.join(change['review_repositories']) or 'None'}",
            f"- Impacted flows: {', '.join(change['impacted_flows']) or 'None'}",
        ])
        if change["constraints"]:
            out.append(f"- Constraints: {'; '.join(change['constraints'])}")
        out.append("")
    if report["incomplete_evidence"]:
        out.extend(["## Incomplete evidence", ""])
        for item in report["incomplete_evidence"]:
            out.append(f"- {item['change_id']}: {item['reason']}")
        out.append("")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("registry", type=Path)
    parser.add_argument("contracts", type=Path)
    parser.add_argument("flows", type=Path)
    parser.add_argument("changes", type=Path)
    parser.add_argument("--json", dest="json_out", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()

    inputs = [
        json.loads(args.registry.read_text(encoding="utf-8")),
        json.loads(args.contracts.read_text(encoding="utf-8")),
        json.loads(args.flows.read_text(encoding="utf-8")),
        json.loads(args.changes.read_text(encoding="utf-8")),
    ]
    report = normalize(*inputs)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown.write_text(render_markdown(report), encoding="utf-8")

    if args.require_complete and report["status"] != "verified":
        return 7
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
