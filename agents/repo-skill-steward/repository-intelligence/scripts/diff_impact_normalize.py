#!/usr/bin/env python3
"""Normalize local semantic impact into evidence-backed cross-repository blast radius."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlparse


SCHEMA_VERSION = 1
CHANGE_TYPES = {"add", "modify", "delete", "rename", "version-change"}
SURFACE_KINDS = {
    "file", "symbol", "contract", "http-api", "event", "schema",
    "package", "cli", "storage", "custom",
}
CLAIM_STATES = {"observed", "inferred"}
CONTRACT_SURFACES = {
    "contract", "http-api", "event", "schema", "package", "cli", "storage", "custom"
}
SEVERITIES = {"breaking", "warning", "info"}
IMPACT_LEVELS = {"unknown", "low", "medium", "high", "critical"}


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


def _repo_map(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    repos = _list(registry.get("repositories"), "registry.repositories")
    out: dict[str, dict[str, Any]] = {}
    for i, raw in enumerate(repos):
        if not isinstance(raw, dict):
            raise ValueError(f"registry.repositories[{i}] must be an object")
        rid = _text(raw.get("repository_id"), f"registry.repositories[{i}].repository_id")
        if rid in out:
            raise ValueError(f"duplicate repository_id: {rid}")
        out[rid] = raw
    return out


def _contract_map(contracts: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for i, raw in enumerate(_list(contracts.get("contracts"), "contracts.contracts")):
        if not isinstance(raw, dict):
            raise ValueError(f"contracts.contracts[{i}] must be an object")
        cid = _text(raw.get("contract_id"), f"contracts.contracts[{i}].contract_id")
        if cid in out:
            raise ValueError(f"duplicate contract_id: {cid}")
        out[cid] = raw
    return out


def _safe_location(uri: str, repository_root: str | None, private: bool) -> str:
    """Return a persistable file location without leaking private absolute roots."""
    raw = str(uri or "").strip()
    if not raw:
        return "unknown"

    parsed = urlparse(raw)
    path_text = unquote(parsed.path) if parsed.scheme == "file" else raw
    candidate = Path(path_text)

    if repository_root:
        root = Path(repository_root).resolve()
        try:
            return candidate.resolve().relative_to(root).as_posix()
        except (ValueError, OSError):
            if private:
                digest = hashlib.sha256(path_text.encode("utf-8")).hexdigest()[:10]
                return f"private-path-{digest}/{candidate.name}"

    if private and candidate.is_absolute():
        digest = hashlib.sha256(path_text.encode("utf-8")).hexdigest()[:10]
        return f"private-path-{digest}/{candidate.name}"

    return PurePosixPath(path_text.replace("\\", "/")).as_posix()


def _normalize_local_impact(
    local: dict[str, Any],
    where: str,
    *,
    private: bool,
) -> dict[str, Any]:
    evidence = _list(local.get("evidence"), f"{where}.evidence")
    if evidence and not all(isinstance(x, str) and x.strip() for x in evidence):
        raise ValueError(f"{where}.evidence must contain strings")
    evidence = sorted(set(str(x).strip() for x in evidence if str(x).strip()))

    repository_root = str(local.get("repository_root", "")).strip() or None

    symbols = sorted({
        _text(x, f"{where}.symbols[]")
        for x in _list(local.get("symbols"), f"{where}.symbols")
    })
    steps = _list(local.get("steps"), f"{where}.steps")
    if not all(isinstance(x, str) and x.strip() for x in steps):
        raise ValueError(f"{where}.steps must contain step IDs")
    steps = sorted(set(x.strip() for x in steps))

    files: set[str] = set()
    tests: set[str] = set()
    severity_counts = {"breaking": 0, "warning": 0, "info": 0}

    direct = _list(local.get("directImpact"), f"{where}.directImpact")
    for i, item in enumerate(direct):
        if not isinstance(item, dict):
            raise ValueError(f"{where}.directImpact[{i}] must be an object")
        severity = _text(item.get("severity"), f"{where}.directImpact[{i}].severity")
        if severity not in SEVERITIES:
            raise ValueError(f"{where}.directImpact[{i}]: invalid severity")
        severity_counts[severity] += 1
        files.add(_safe_location(
            str(item.get("uri", "")),
            repository_root,
            private,
        ))

    indirect = _list(local.get("indirectImpact"), f"{where}.indirectImpact")
    for i, item in enumerate(indirect):
        if not isinstance(item, dict):
            raise ValueError(f"{where}.indirectImpact[{i}] must be an object")
        severity = _text(item.get("severity"), f"{where}.indirectImpact[{i}].severity")
        if severity not in SEVERITIES:
            raise ValueError(f"{where}.indirectImpact[{i}]: invalid severity")
        severity_counts[severity] += 1
        files.add(_safe_location(
            str(item.get("uri", "")),
            repository_root,
            private,
        ))

    affected_tests = _list(local.get("affectedTests"), f"{where}.affectedTests")
    for i, item in enumerate(affected_tests):
        if not isinstance(item, dict):
            raise ValueError(f"{where}.affectedTests[{i}] must be an object")
        name = str(item.get("testName", "")).strip()
        uri = str(item.get("uri", "")).strip()
        if name:
            tests.add(name)
        if uri:
            files.add(_safe_location(uri, repository_root, private))

    for raw_file in _list(local.get("files"), f"{where}.files"):
        files.add(_safe_location(_text(raw_file, f"{where}.files[]"), repository_root, private))

    for raw_test in _list(local.get("tests"), f"{where}.tests"):
        tests.add(_text(raw_test, f"{where}.tests[]"))

    summary = local.get("summary", {})
    if summary is None:
        summary = {}
    if not isinstance(summary, dict):
        raise ValueError(f"{where}.summary must be an object")

    return {
        "provider": str(local.get("provider", "")).strip() or None,
        "evidence": evidence,
        "symbols": symbols,
        "steps": steps,
        "files": sorted(x for x in files if x != "unknown"),
        "tests": sorted(tests),
        "severity_counts": severity_counts,
        "provider_summary": {
            "filesAffected": int(summary.get("filesAffected", len(files))),
            "breakingChanges": int(summary.get("breakingChanges", severity_counts["breaking"])),
            "warnings": int(summary.get("warnings", severity_counts["warning"])),
        },
    }


def _impact_level(
    *,
    mapped: bool,
    compatibility: str,
    change_type: str,
    impacted_contracts: set[str],
    impacted_flows: set[str],
    review_repos: set[str],
    local: dict[str, Any],
) -> str:
    if not mapped:
        return "unknown"
    if compatibility == "version-mismatch":
        return "critical"
    if impacted_contracts and len(review_repos) > 1 and change_type in {"delete", "version-change"}:
        return "critical"
    if impacted_contracts and (impacted_flows or len(review_repos) > 1):
        return "high"
    if local["provider_summary"]["breakingChanges"] > 0:
        return "high"
    if impacted_flows or len(review_repos) > 1 or local["provider_summary"]["warnings"] > 0:
        return "medium"
    return "low"


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

    repos = _repo_map(registry)
    contract_by_id = _contract_map(contracts)

    steps: dict[str, dict[str, Any]] = {}
    for i, raw in enumerate(_list(flows.get("steps"), "flows.steps")):
        if not isinstance(raw, dict):
            raise ValueError(f"flows.steps[{i}] must be an object")
        sid = _text(raw.get("step_id"), f"flows.steps[{i}].step_id")
        if sid in steps:
            raise ValueError(f"duplicate step_id: {sid}")
        steps[sid] = raw

    edges: dict[str, dict[str, Any]] = {}
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
    seen_changes: set[str] = set()
    all_impacted_repos: set[str] = set()
    all_impacted_contracts: set[str] = set()
    all_impacted_flows: set[str] = set()
    all_impacted_steps: set[str] = set()
    all_affected_files: set[str] = set()
    all_affected_tests: set[str] = set()
    incomplete: list[dict[str, Any]] = []

    for index, raw in enumerate(raw_changes):
        if not isinstance(raw, dict):
            raise ValueError(f"changes[{index}] must be an object")
        where = f"changes[{index}]"
        change_id = _text(raw.get("change_id"), f"{where}.change_id")
        if change_id in seen_changes:
            raise ValueError(f"duplicate change_id: {change_id}")
        seen_changes.add(change_id)

        repository_id = _text(raw.get("repository_id"), f"{where}.repository_id")
        if repository_id not in repos:
            raise ValueError(f"{change_id}: unknown repository_id {repository_id}")
        private = repos[repository_id].get("visibility") in {"private", "internal"}

        change_type = _text(raw.get("change_type"), f"{where}.change_type")
        if change_type not in CHANGE_TYPES:
            raise ValueError(f"{change_id}: unsupported change_type")
        surface_kind = _text(raw.get("surface_kind"), f"{where}.surface_kind")
        if surface_kind not in SURFACE_KINDS:
            raise ValueError(f"{change_id}: unsupported surface_kind")
        identifier = _text(raw.get("identifier"), f"{where}.identifier")
        state, evidence, rationale = _claim(raw, where)

        local_raw = raw.get("local_impact", {})
        if local_raw is None:
            local_raw = {}
        if not isinstance(local_raw, dict):
            raise ValueError(f"{where}.local_impact must be an object")
        local = _normalize_local_impact(local_raw, f"{where}.local_impact", private=private)

        impacted_steps: set[str] = set()
        for sid in local["steps"]:
            if sid not in steps:
                raise ValueError(f"{change_id}: unknown local impact step {sid!r}")
            if steps[sid].get("repository_id") != repository_id:
                raise ValueError(f"{change_id}: local impact step belongs to a different repository")
            impacted_steps.add(sid)

        symbol_names = set(local["symbols"])
        if surface_kind == "symbol":
            symbol_names.add(identifier)
        for sid, step in steps.items():
            if step.get("repository_id") == repository_id and step.get("symbol") in symbol_names:
                impacted_steps.add(sid)

        impacted_contracts: set[str] = set()
        contract_ids = _list(raw.get("contract_ids"), f"{where}.contract_ids")
        single_contract = str(raw.get("contract_id", "")).strip()
        if single_contract:
            contract_ids.append(single_contract)

        if surface_kind in CONTRACT_SURFACES:
            if not contract_ids:
                raise ValueError(f"{change_id}: contract surface requires contract_id or contract_ids")
        for cid_raw in contract_ids:
            cid = _text(cid_raw, f"{where}.contract_ids[]")
            contract = contract_by_id.get(cid)
            if contract is None:
                raise ValueError(f"{change_id}: unknown contract_id {cid}")
            if repository_id not in {contract.get("provider"), contract.get("consumer")}:
                raise ValueError(f"{change_id}: repository is not a party to contract {cid}")
            if surface_kind not in {"file", "symbol", "contract"} and contract.get("kind") != surface_kind:
                raise ValueError(f"{change_id}: surface_kind does not match contract kind")
            impacted_contracts.add(cid)

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

        impacted_edges = {
            eid for eid, edge in edges.items()
            if edge.get("contract_id") in impacted_contracts
        }

        impacted_flow_ids: set[str] = set()
        transitive_steps: set[str] = set()
        transitive_repos: set[str] = set()
        directly_impacted_repos: set[str] = {repository_id}

        for cid in impacted_contracts:
            contract = contract_by_id[cid]
            directly_impacted_repos.update(
                rid for rid in [contract.get("provider"), contract.get("consumer")] if rid
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

        mapped = bool(impacted_steps or impacted_contracts or local["files"] or local["tests"])
        mapping_status = "mapped" if mapped else "unmapped"
        constraints = []
        if state == "inferred":
            constraints.append("change observation is inferred")
        if not mapped:
            constraints.append("no semantic, process-step, contract, file, or test impact mapping evidence")
            incomplete.append({"change_id": change_id, "reason": "no impact mapping evidence"})
        if surface_kind == "file" and not local["evidence"] and not local["files"]:
            constraints.append("file change has no local semantic-impact evidence")
            incomplete.append({
                "change_id": change_id,
                "reason": "file change requires local semantic-impact evidence",
            })

        review_repos_set = directly_impacted_repos | transitive_repos
        impact_level = _impact_level(
            mapped=mapped,
            compatibility=compatibility,
            change_type=change_type,
            impacted_contracts=impacted_contracts,
            impacted_flows=impacted_flow_ids,
            review_repos=review_repos_set,
            local=local,
        )

        all_impacted_repos.update(review_repos_set)
        all_impacted_contracts.update(impacted_contracts)
        all_impacted_flows.update(impacted_flow_ids)
        all_impacted_steps.update(impacted_steps | transitive_steps)
        all_affected_files.update(f"{repository_id}:{p}" for p in local["files"])
        all_affected_tests.update(f"{repository_id}:{t}" for t in local["tests"])

        normalized_changes.append({
            "change_id": change_id,
            "repository_id": repository_id,
            "change_type": change_type,
            "surface_kind": surface_kind,
            "identifier": identifier,
            "state": state,
            "evidence": sorted(set(evidence + local["evidence"])),
            "rationale": rationale,
            "mapping_status": mapping_status,
            "impact_level": impact_level,
            "local_impact": {
                "provider": local["provider"],
                "files": local["files"],
                "symbols": local["symbols"],
                "tests": local["tests"],
                "severity_counts": local["severity_counts"],
                "provider_summary": local["provider_summary"],
            },
            "direct_steps": sorted(impacted_steps),
            "transitive_steps": sorted(transitive_steps - impacted_steps),
            "impacted_contracts": sorted(impacted_contracts),
            "impacted_flows": sorted(impacted_flow_ids),
            "review_repositories": sorted(review_repos_set),
            "compatibility": compatibility,
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
            "scope": "repository",
            "repository_id": rid,
            "reason": "repository participates in direct or transitive blast radius",
        })
    for cid in sorted(all_impacted_contracts):
        test_scopes.append({
            "scope": "contract",
            "contract_id": cid,
            "reason": "contract compatibility/regression validation required",
        })
    for fid in sorted(all_impacted_flows):
        test_scopes.append({
            "scope": "flow",
            "flow_id": fid,
            "reason": "end-to-end regression validation required",
        })
    for test in sorted(all_affected_tests):
        rid, name = test.split(":", 1)
        test_scopes.append({
            "scope": "test",
            "repository_id": rid,
            "test": name,
            "reason": "local semantic impact identified this test",
        })

    status = "partial-evidence" if incomplete_unique else "verified"
    version_mismatch_changes = [
        c["change_id"] for c in normalized_changes if c["compatibility"] == "version-mismatch"
    ]

    level_order = {"unknown": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
    overall_level = max(
        (c["impact_level"] for c in normalized_changes),
        key=lambda x: level_order[x],
        default="unknown",
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "context": "C002",
        "workspace_id": workspace_id,
        "status": status,
        "impact_level": overall_level,
        "changes": sorted(normalized_changes, key=lambda x: x["change_id"]),
        "blast_radius": {
            "repositories": sorted(all_impacted_repos),
            "contracts": sorted(all_impacted_contracts),
            "flows": sorted(all_impacted_flows),
            "steps": sorted(all_impacted_steps),
            "files": sorted(all_affected_files),
            "tests": sorted(all_affected_tests),
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
            "affected_files": len(all_affected_files),
            "affected_tests": len(all_affected_tests),
            "version_mismatches": len(version_mismatch_changes),
            "incomplete_evidence": len(incomplete_unique),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    out = [
        "# Cross-Repository Diff Impact",
        "",
        f"- Workspace: {report['workspace_id']}",
        f"- Status: {report['status']}",
        f"- Overall impact: {report['impact_level'].upper()}",
        f"- Changes: {report['summary']['changes']}",
        f"- Impacted repositories: {report['summary']['impacted_repositories']}",
        f"- Impacted contracts: {report['summary']['impacted_contracts']}",
        f"- Impacted flows: {report['summary']['impacted_flows']}",
        f"- Affected tests: {report['summary']['affected_tests']}",
        "",
    ]
    for change in report["changes"]:
        out.extend([
            f"## {change['change_id']} — {change['surface_kind']} / {change['change_type']}",
            "",
            f"- Repository: {change['repository_id']}",
            f"- Identifier: {change['identifier']}",
            f"- Mapping: {change['mapping_status']}",
            f"- Impact level: {change['impact_level']}",
            f"- Compatibility: {change['compatibility']}",
            f"- Review repositories: {', '.join(change['review_repositories']) or 'None'}",
            f"- Impacted flows: {', '.join(change['impacted_flows']) or 'None'}",
            f"- Affected tests: {', '.join(change['local_impact']['tests']) or 'None'}",
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
