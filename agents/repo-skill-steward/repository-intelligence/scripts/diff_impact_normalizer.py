#!/usr/bin/env python3
"""Normalize repository diffs into evidence-backed cross-repository blast radius."""

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
CONTRACT_SURFACES = {"contract", "http-api", "event", "schema", "package", "cli", "storage", "custom"}
CLAIM_STATES = {"observed", "inferred"}
CONTRACT_SIDES = {"provider", "consumer", "both"}
LOCAL_RISK_LEVELS = {"low", "medium", "high", "unknown", "not-provided"}


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
        raise ValueError(f"{where}: inferred claim requires rationale")
    return state, sorted(set(x.strip() for x in evidence)), rationale


def _repo_map(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    repos: dict[str, dict[str, Any]] = {}
    for i, raw in enumerate(_list(registry.get("repositories"), "registry.repositories")):
        if not isinstance(raw, dict):
            raise ValueError(f"registry.repositories[{i}] must be an object")
        rid = _text(raw.get("repository_id"), f"registry.repositories[{i}].repository_id")
        if rid in repos:
            raise ValueError(f"duplicate repository_id: {rid}")
        repos[rid] = raw
    return repos


def _safe_location(value: str, repository_root: str | None, private: bool) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    path_text = unquote(parsed.path) if parsed.scheme == "file" else raw
    candidate = Path(path_text)
    if repository_root:
        try:
            return candidate.resolve().relative_to(Path(repository_root).resolve()).as_posix()
        except (ValueError, OSError):
            pass
    if private and candidate.is_absolute():
        digest = hashlib.sha256(path_text.encode("utf-8")).hexdigest()[:10]
        return f"private-path-{digest}/{candidate.name}"
    return PurePosixPath(path_text.replace("\\", "/")).as_posix()


def _contract_map(contracts: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for i, raw in enumerate(_list(contracts.get("contracts"), "contracts.contracts")):
        if not isinstance(raw, dict):
            raise ValueError(f"contracts.contracts[{i}] must be an object")
        cid = _text(raw.get("contract_id"), f"contracts.contracts[{i}].contract_id")
        if cid in out:
            raise ValueError(f"duplicate contract_id: {cid}")
        if raw.get("status") == "matched":
            out[cid] = raw
    return out


def _strings(value: Any, name: str) -> list[str]:
    items = _list(value, name)
    if not all(isinstance(x, str) and x.strip() for x in items):
        raise ValueError(f"{name} must contain non-empty strings")
    return sorted(set(x.strip() for x in items))


def _normalize_contract_touch(
    raw: dict[str, Any],
    where: str,
    repository_id: str,
    contract_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    cid = _text(raw.get("contract_id"), f"{where}.contract_id")
    contract = contract_by_id.get(cid)
    if contract is None:
        raise ValueError(f"{where}: unknown or unmatched contract_id {cid}")
    if repository_id not in {contract.get("provider"), contract.get("consumer")}:
        raise ValueError(f"{where}: changed repository is not a party to {cid}")

    side = _text(raw.get("side"), f"{where}.side")
    if side not in CONTRACT_SIDES:
        raise ValueError(f"{where}.side must be provider, consumer, or both")
    if side == "provider" and repository_id != contract.get("provider"):
        raise ValueError(f"{where}: provider-side touch must come from contract provider")
    if side == "consumer" and repository_id != contract.get("consumer"):
        raise ValueError(f"{where}: consumer-side touch must come from contract consumer")

    state, evidence, rationale = _claim(raw, where)
    return {
        "contract_id": cid,
        "side": side,
        "state": state,
        "evidence": evidence,
        "rationale": rationale,
    }


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
    repo_ids = set(repos)
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

    normalized_changes: list[dict[str, Any]] = []
    all_impacted_repos: set[str] = set()
    all_impacted_contracts: set[str] = set()
    all_impacted_flows: set[str] = set()
    all_impacted_steps: set[str] = set()
    all_related_tests: set[str] = set()
    all_affected_files: set[str] = set()
    incomplete: list[dict[str, str]] = []

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
            raise ValueError(f"{change_id}: unsupported change_type {change_type}")

        surface_kind = _text(raw.get("surface_kind"), f"{where}.surface_kind")
        if surface_kind not in SURFACE_KINDS:
            raise ValueError(f"{change_id}: unsupported surface_kind {surface_kind}")
        identifier = _text(raw.get("identifier"), f"{where}.identifier")
        state, evidence, rationale = _claim(raw, where)

        path = str(raw.get("path", "")).strip() or None
        symbol = str(raw.get("symbol", "")).strip() or (
            identifier if surface_kind == "symbol" else None
        )

        local = raw.get("local_impact") or {}
        if not isinstance(local, dict):
            raise ValueError(f"{where}.local_impact must be an object")

        local_evidence = _strings(local.get("evidence"), f"{where}.local_impact.evidence")
        local_symbols = _strings(local.get("symbols"), f"{where}.local_impact.symbols")
        private_repo = repos[repository_id].get("visibility") in {"private", "internal"}
        repository_root = str(local.get("repository_root", "")).strip() or None
        local_files = sorted({
            _safe_location(x, repository_root, private_repo)
            for x in _strings(local.get("files"), f"{where}.local_impact.files")
            if _safe_location(x, repository_root, private_repo)
        })
        related_tests = sorted({
            _safe_location(x, repository_root, private_repo)
            for x in _strings(local.get("tests"), f"{where}.local_impact.tests")
            if _safe_location(x, repository_root, private_repo)
        })
        direct_callers = _strings(local.get("direct_callers"), f"{where}.local_impact.direct_callers")

        risk_level = str(local.get("risk_level", "not-provided")).strip() or "not-provided"
        if risk_level not in LOCAL_RISK_LEVELS:
            raise ValueError(f"{where}.local_impact.risk_level unsupported: {risk_level}")

        impacted_steps: set[str] = set()
        for sid in _strings(local.get("steps"), f"{where}.local_impact.steps"):
            if sid not in steps:
                raise ValueError(f"{change_id}: unknown local impact step {sid}")
            if steps[sid].get("repository_id") != repository_id:
                raise ValueError(f"{change_id}: local impact step belongs to a different repository")
            impacted_steps.add(sid)

        symbol_names = set(local_symbols)
        if symbol:
            symbol_names.add(symbol)
        for sid, step in steps.items():
            if (
                step.get("repository_id") == repository_id
                and step.get("symbol")
                and step.get("symbol") in symbol_names
            ):
                impacted_steps.add(sid)

        touches: list[dict[str, Any]] = []
        raw_touches = _list(raw.get("contract_touches"), f"{where}.contract_touches")
        if any(not isinstance(x, dict) for x in raw_touches):
            raise ValueError(f"{where}.contract_touches entries must be objects")
        for i, touch in enumerate(raw_touches):
            touches.append(
                _normalize_contract_touch(
                    touch,
                    f"{where}.contract_touches[{i}]",
                    repository_id,
                    contract_by_id,
                )
            )

        top_contract_id = str(raw.get("contract_id", "")).strip()
        if surface_kind in CONTRACT_SURFACES:
            if not top_contract_id:
                raise ValueError(f"{change_id}: contract surface requires contract_id")
            contract = contract_by_id.get(top_contract_id)
            if contract is None:
                raise ValueError(f"{change_id}: unknown or unmatched contract_id {top_contract_id}")
            if surface_kind != "contract" and contract.get("kind") != surface_kind:
                raise ValueError(f"{change_id}: surface_kind does not match contract kind")
            if repository_id not in {contract.get("provider"), contract.get("consumer")}:
                raise ValueError(f"{change_id}: changed repository is not a party to contract {top_contract_id}")
            if not any(t["contract_id"] == top_contract_id for t in touches):
                side = "provider" if repository_id == contract.get("provider") else "consumer"
                touches.append({
                    "contract_id": top_contract_id,
                    "side": side,
                    "state": state,
                    "evidence": evidence,
                    "rationale": rationale,
                })

        impacted_contracts = {t["contract_id"] for t in touches}

        compatibility = "not-applicable"
        compatibility_findings: list[dict[str, Any]] = []
        if change_type == "version-change" and impacted_contracts:
            new_version = _text(raw.get("new_version"), f"{where}.new_version")
            mismatch = False
            for cid in sorted(impacted_contracts):
                contract = contract_by_id[cid]
                touch_sides = {
                    t["side"] for t in touches if t["contract_id"] == cid
                }
                provided = str(contract.get("provided_version", "unspecified"))
                required = str(contract.get("required_version", "unspecified"))

                if touch_sides == {"consumer"}:
                    ok = new_version in {"*", "unspecified", provided}
                    compared_to = provided
                    compared_field = "recorded_provided_version"
                else:
                    ok = required in {"*", "unspecified", new_version}
                    compared_to = required
                    compared_field = "recorded_required_version"

                finding = {
                    "contract_id": cid,
                    "new_version": new_version,
                    "status": "compatible" if ok else "version-mismatch",
                }
                finding[compared_field] = compared_to
                compatibility_findings.append(finding)
                mismatch = mismatch or not ok
            compatibility = "version-mismatch" if mismatch else "compatible-with-recorded-counterparty"

        impacted_edges = {
            eid
            for eid, edge in edges.items()
            if edge.get("contract_id") in impacted_contracts
        }

        directly_impacted_repos: set[str] = {repository_id}
        for cid in impacted_contracts:
            contract = contract_by_id[cid]
            directly_impacted_repos.update(
                r for r in [contract.get("provider"), contract.get("consumer")] if r
            )

        impacted_flow_ids: set[str] = set()
        transitive_steps: set[str] = set()
        transitive_repos: set[str] = set()

        for flow in flow_records:
            flow_id = _text(flow.get("flow_id"), "flow.flow_id")
            path_steps = _strings(flow.get("steps"), f"{flow_id}.steps")
            edge_ids = _strings(flow.get("edge_ids"), f"{flow_id}.edge_ids")
            impact_positions: list[int] = []

            for sid in impacted_steps:
                if sid in path_steps:
                    impact_positions.append(path_steps.index(sid))
            for eid in impacted_edges:
                if eid in edge_ids:
                    impact_positions.append(edge_ids.index(eid))

            if not impact_positions:
                continue

            impacted_flow_ids.add(flow_id)
            start = min(impact_positions)
            for sid in path_steps[start:]:
                transitive_steps.add(sid)
                rid = steps.get(sid, {}).get("repository_id")
                if rid:
                    transitive_repos.add(rid)

        mapped = bool(impacted_steps or impacted_contracts)
        constraints: list[str] = []
        if state == "inferred":
            constraints.append("change observation is inferred")
        if any(t["state"] == "inferred" for t in touches):
            constraints.append("contract-touch mapping contains inferred evidence")
        if not mapped:
            constraints.append("no symbol/process-step or contract mapping evidence")
            incomplete.append({"change_id": change_id, "reason": "no impact mapping evidence"})
        if surface_kind in {"file", "symbol"} and not local_evidence:
            constraints.append("local code change has no semantic-impact evidence")
            incomplete.append({
                "change_id": change_id,
                "reason": "file/symbol change requires local semantic-impact evidence",
            })

        review_repos = sorted(directly_impacted_repos | transitive_repos)
        combined_evidence = set(evidence + local_evidence)
        for touch in touches:
            combined_evidence.update(touch["evidence"])

        all_impacted_repos.update(review_repos)
        all_impacted_contracts.update(impacted_contracts)
        all_impacted_flows.update(impacted_flow_ids)
        all_impacted_steps.update(impacted_steps | transitive_steps)
        all_related_tests.update(related_tests)
        all_affected_files.update(local_files)

        normalized_changes.append({
            "change_id": change_id,
            "repository_id": repository_id,
            "change_type": change_type,
            "surface_kind": surface_kind,
            "identifier": identifier,
            "path": path,
            "symbol": symbol,
            "state": state,
            "evidence_confidence": "observed" if state == "observed" and not any(
                t["state"] == "inferred" for t in touches
            ) else "inferred",
            "evidence": sorted(combined_evidence),
            "rationale": rationale,
            "mapping_status": "mapped" if mapped else "unmapped",
            "local_impact": {
                "risk_level": risk_level,
                "symbols": local_symbols,
                "files": local_files,
                "related_tests": related_tests,
                "direct_callers": direct_callers,
                "direct_steps": sorted(impacted_steps),
            },
            "contract_touches": sorted(touches, key=lambda x: (x["contract_id"], x["side"])),
            "transitive_steps": sorted(transitive_steps - impacted_steps),
            "impacted_contracts": sorted(impacted_contracts),
            "impacted_flows": sorted(impacted_flow_ids),
            "review_repositories": review_repos,
            "compatibility": compatibility,
            "compatibility_findings": compatibility_findings,
            "constraints": sorted(set(constraints)),
        })

    incomplete_unique: list[dict[str, str]] = []
    seen_incomplete: set[tuple[str, str]] = set()
    for item in incomplete:
        key = (item["change_id"], item["reason"])
        if key not in seen_incomplete:
            seen_incomplete.add(key)
            incomplete_unique.append(item)

    test_scopes: list[dict[str, str]] = []
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
    for test in sorted(all_related_tests):
        test_scopes.append({
            "test": test,
            "reason": "related test preserved from local semantic-impact evidence",
        })

    version_mismatch_changes = sorted(
        c["change_id"]
        for c in normalized_changes
        if c["compatibility"] == "version-mismatch"
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "context": "C002",
        "workspace_id": workspace_id,
        "status": "partial-evidence" if incomplete_unique else "verified",
        "changes": sorted(normalized_changes, key=lambda x: x["change_id"]),
        "blast_radius": {
            "repositories": sorted(all_impacted_repos),
            "contracts": sorted(all_impacted_contracts),
            "flows": sorted(all_impacted_flows),
            "steps": sorted(all_impacted_steps),
            "related_tests": sorted(all_related_tests),
            "affected_files": sorted(all_affected_files),
        },
        "compatibility_findings": {
            "version_mismatch_changes": version_mismatch_changes,
        },
        "test_review_scope": test_scopes,
        "incomplete_evidence": incomplete_unique,
        "summary": {
            "changes": len(normalized_changes),
            "impacted_repositories": len(all_impacted_repos),
            "impacted_contracts": len(all_impacted_contracts),
            "impacted_flows": len(all_impacted_flows),
            "impacted_steps": len(all_impacted_steps),
            "related_tests": len(all_related_tests),
            "affected_files": len(all_affected_files),
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
        f"- Changes: {report['summary']['changes']}",
        f"- Impacted repositories: {report['summary']['impacted_repositories']}",
        f"- Impacted contracts: {report['summary']['impacted_contracts']}",
        f"- Impacted flows: {report['summary']['impacted_flows']}",
        f"- Related tests preserved: {report['summary']['related_tests']}",
        "",
    ]
    for change in report["changes"]:
        local = change["local_impact"]
        out.extend([
            f"## {change['change_id']} — {change['surface_kind']} / {change['change_type']}",
            "",
            f"- Repository: {change['repository_id']}",
            f"- Identifier: {change['identifier']}",
            f"- Mapping: {change['mapping_status']}",
            f"- Evidence confidence: {change['evidence_confidence']}",
            f"- Local risk: {local['risk_level']}",
            f"- Compatibility: {change['compatibility']}",
            f"- Review repositories: {', '.join(change['review_repositories']) or 'None'}",
            f"- Impacted flows: {', '.join(change['impacted_flows']) or 'None'}",
            f"- Related tests: {', '.join(local['related_tests']) or 'None'}",
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

    payloads = [
        json.loads(args.registry.read_text(encoding="utf-8")),
        json.loads(args.contracts.read_text(encoding="utf-8")),
        json.loads(args.flows.read_text(encoding="utf-8")),
        json.loads(args.changes.read_text(encoding="utf-8")),
    ]
    report = normalize(*payloads)

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown.write_text(render_markdown(report), encoding="utf-8")

    if args.require_complete and report["status"] != "verified":
        return 7
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
