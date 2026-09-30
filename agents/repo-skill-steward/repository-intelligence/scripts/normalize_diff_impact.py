#!/usr/bin/env python3
"""Normalize repository diffs and local semantic impacts into a cross-repository blast radius."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
CHANGE_TYPES = {"add", "modify", "delete", "rename"}
CLAIM_STATES = {"observed", "inferred"}
RISK_RANK = {"unknown": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


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


def _claim(item: dict[str, Any], where: str) -> tuple[str, list[str], str]:
    state = _text(item.get("state", "observed"), f"{where}.state")
    if state not in CLAIM_STATES:
        raise ValueError(f"{where}.state must be observed or inferred")
    evidence = _list(item.get("evidence"), f"{where}.evidence")
    if not evidence or not all(isinstance(x, str) and x.strip() for x in evidence):
        raise ValueError(f"{where}: evidence is required")
    rationale = str(item.get("rationale", "")).strip()
    if state == "inferred" and not rationale:
        raise ValueError(f"{where}: inferred claim requires rationale")
    return state, sorted(set(x.strip() for x in evidence)), rationale


def _risk(value: Any) -> str:
    risk = str(value or "unknown").strip().lower()
    return risk if risk in RISK_RANK else "unknown"


def _max_risk(*levels: str) -> str:
    return max(levels, key=lambda x: RISK_RANK.get(x, 0), default="unknown")


def _bump(level: str, minimum: str) -> str:
    return minimum if RISK_RANK[minimum] > RISK_RANK[level] else level


def _normalize_local_impact(raw: dict[str, Any], where: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{where}.impact must be an object")
    direct = _list(raw.get("impacted"), f"{where}.impact.impacted")
    indirect = _list(raw.get("indirect_impacted"), f"{where}.impact.indirect_impacted")

    impacts = []
    for bucket, values in [("direct", direct), ("indirect", indirect)]:
        for i, item in enumerate(values):
            if not isinstance(item, dict):
                raise ValueError(f"{where}.impact.{bucket}[{i}] must be an object")
            name = str(item.get("name", "")).strip()
            path = str(item.get("path", "")).strip()
            if not name and not path:
                raise ValueError(f"{where}.impact.{bucket}[{i}] requires name or path")
            impacts.append({
                "scope": bucket,
                "name": name or None,
                "path": path or None,
                "impact_type": str(item.get("impact_type", "")).strip() or None,
                "edge_type": str(item.get("edge_type_str", "")).strip() or None,
                "depth": int(item.get("depth", 1 if bucket == "direct" else 2)),
                "severity": str(item.get("severity", "")).strip() or None,
                "is_test": bool(item.get("is_test", False)),
            })

    impacts.sort(key=lambda x: (
        x["scope"],
        x["depth"],
        x["path"] or "",
        x["name"] or "",
        x["impact_type"] or "",
    ))
    return {
        "symbol_name": str(raw.get("symbol_name", "")).strip() or None,
        "change_type": str(raw.get("change_type", "")).strip() or None,
        "risk_level": _risk(raw.get("risk_level")),
        "files_affected": int(raw.get("files_affected", 0) or 0),
        "direct_impacted": int(raw.get("direct_impacted", len(direct)) or 0),
        "indirect_impacted_count": len(indirect),
        "breaking_changes": int(raw.get("breaking_changes", 0) or 0),
        "warnings": int(raw.get("warnings", 0) or 0),
        "impacts": impacts,
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

    repo_ids = {
        _text(r.get("repository_id"), "registry.repositories[].repository_id")
        for r in _list(registry.get("repositories"), "registry.repositories")
        if isinstance(r, dict)
    }
    contract_by_id = {
        _text(c.get("contract_id"), "contracts.contract_id"): c
        for c in _list(contracts.get("contracts"), "contracts.contracts")
        if isinstance(c, dict) and c.get("status") == "matched"
    }
    steps = {
        _text(s.get("step_id"), "flows.steps[].step_id"): s
        for s in _list(flows.get("steps"), "flows.steps")
        if isinstance(s, dict)
    }
    edges = {
        _text(e.get("edge_id"), "flows.edges[].edge_id"): e
        for e in _list(flows.get("edges"), "flows.edges")
        if isinstance(e, dict)
    }
    flow_records = [
        f for f in _list(flows.get("flows"), "flows.flows") if isinstance(f, dict)
    ]

    budgets = changes.get("budgets", {})
    if not isinstance(budgets, dict):
        raise ValueError("changes.budgets must be an object")
    max_symbol_impacts = int(budgets.get("max_symbol_impacts", 500))
    max_flow_impacts = int(budgets.get("max_flow_impacts", 100))
    if max_symbol_impacts < 1 or max_flow_impacts < 1:
        raise ValueError("impact budgets must be positive")

    local_by_change: dict[str, list[dict[str, Any]]] = {}
    for i, item in enumerate(_list(changes.get("local_impacts"), "changes.local_impacts")):
        if not isinstance(item, dict):
            raise ValueError(f"local_impacts[{i}] must be an object")
        change_id = _text(item.get("change_id"), f"local_impacts[{i}].change_id")
        state, evidence, rationale = _claim(item, f"local_impacts[{i}]")
        normalized = _normalize_local_impact(
            item.get("impact", {}),
            f"local_impacts[{i}]",
        )
        normalized.update({
            "provider": str(item.get("provider", "")).strip() or "unknown",
            "state": state,
            "evidence": evidence,
            "rationale": rationale,
        })
        local_by_change.setdefault(change_id, []).append(normalized)

    normalized_changes: list[dict[str, Any]] = []
    all_impacted_repos: set[str] = set()
    all_impacted_contracts: set[str] = set()
    all_impacted_flows: set[str] = set()
    overall_risk = "unknown"
    truncated = False

    raw_changes = _list(changes.get("changes"), "changes.changes")
    if not raw_changes:
        raise ValueError("changes.changes must not be empty")

    seen_change_ids: set[str] = set()
    for i, raw in enumerate(raw_changes):
        if not isinstance(raw, dict):
            raise ValueError(f"changes[{i}] must be an object")
        change_id = _text(raw.get("change_id"), f"changes[{i}].change_id")
        if change_id in seen_change_ids:
            raise ValueError(f"duplicate change_id: {change_id}")
        seen_change_ids.add(change_id)

        repository_id = _text(raw.get("repository_id"), f"changes[{i}].repository_id")
        if repository_id not in repo_ids:
            raise ValueError(f"{change_id}: unknown repository_id {repository_id}")
        change_type = _text(raw.get("change_type"), f"changes[{i}].change_type")
        if change_type not in CHANGE_TYPES:
            raise ValueError(f"{change_id}: invalid change_type")
        state, evidence, rationale = _claim(raw, f"changes[{i}]")

        path = _text(raw.get("path"), f"changes[{i}].path")
        symbol = str(raw.get("symbol", "")).strip() or None
        previous_path = str(raw.get("previous_path", "")).strip() or None
        previous_symbol = str(raw.get("previous_symbol", "")).strip() or None

        explicit_contracts = sorted(set(
            str(x).strip()
            for x in _list(raw.get("contract_refs"), f"changes[{i}].contract_refs")
            if str(x).strip()
        ))
        unknown_contracts = [cid for cid in explicit_contracts if cid not in contract_by_id]
        if unknown_contracts:
            raise ValueError(f"{change_id}: unknown contract_refs: {unknown_contracts}")

        local_impacts = local_by_change.get(change_id, [])
        impacted_names = {x for x in [symbol, previous_symbol] if x}
        local_risk = "unknown"
        breaking_changes = 0
        symbol_impacts: list[dict[str, Any]] = []

        for report in local_impacts:
            local_risk = _max_risk(local_risk, report["risk_level"])
            breaking_changes += report["breaking_changes"]
            if report["symbol_name"]:
                impacted_names.add(report["symbol_name"])
            for impact in report["impacts"]:
                if impact["name"]:
                    impacted_names.add(impact["name"])
                if len(symbol_impacts) < max_symbol_impacts:
                    symbol_impacts.append({
                        **impact,
                        "provider": report["provider"],
                        "state": report["state"],
                        "evidence": report["evidence"],
                    })
                else:
                    truncated = True

        directly_impacted_steps = sorted(
            sid
            for sid, step in steps.items()
            if step.get("repository_id") == repository_id
            and step.get("symbol")
            and step.get("symbol") in impacted_names
        )

        impacted_flow_records: list[dict[str, Any]] = []
        affected_repos: set[str] = {repository_id}
        propagated_contracts: set[str] = set()
        affected_steps: set[str] = set(directly_impacted_steps)

        for flow in flow_records:
            flow_id = _text(flow.get("flow_id"), "flow.flow_id")
            flow_steps = _list(flow.get("steps"), f"{flow_id}.steps")
            edge_ids = _list(flow.get("edge_ids"), f"{flow_id}.edge_ids")

            start_indexes = [flow_steps.index(sid) for sid in directly_impacted_steps if sid in flow_steps]
            explicit_edge_indexes = [
                idx
                for idx, eid in enumerate(edge_ids)
                if eid in edges and edges[eid].get("contract_id") in explicit_contracts
            ]

            if not start_indexes and not explicit_edge_indexes:
                continue

            start = min(
                start_indexes
                + [idx for idx in explicit_edge_indexes]
            )
            downstream_steps = flow_steps[start:]
            downstream_edges = edge_ids[start:] if start < len(edge_ids) else []
            downstream_repos = []
            for sid in downstream_steps:
                step = steps.get(sid)
                if not step:
                    continue
                affected_steps.add(sid)
                rid = step.get("repository_id")
                if rid:
                    affected_repos.add(rid)
                    if not downstream_repos or downstream_repos[-1] != rid:
                        downstream_repos.append(rid)

            crossed_contracts = []
            for eid in downstream_edges:
                edge = edges.get(eid)
                if not edge:
                    continue
                cid = edge.get("contract_id")
                if cid:
                    propagated_contracts.add(cid)
                    crossed_contracts.append(cid)

            if len(impacted_flow_records) < max_flow_impacts:
                impacted_flow_records.append({
                    "flow_id": flow_id,
                    "flow_state": flow.get("state", "unknown"),
                    "impact_start_step": flow_steps[start] if flow_steps else None,
                    "downstream_steps": downstream_steps,
                    "affected_repositories": downstream_repos,
                    "crossed_contracts": sorted(set(crossed_contracts)),
                    "evidence": list(flow.get("evidence", [])),
                })
            else:
                truncated = True

        for cid in explicit_contracts:
            contract = contract_by_id[cid]
            affected_repos.add(contract["provider"])
            affected_repos.add(contract["consumer"])

        changed_contract_records = [
            {
                "contract_id": cid,
                "provider": contract_by_id[cid]["provider"],
                "consumer": contract_by_id[cid]["consumer"],
                "key": contract_by_id[cid].get("key"),
                "kind": contract_by_id[cid].get("kind"),
                "impact_role": "changed-contract",
                "evidence": contract_by_id[cid].get("evidence", []),
            }
            for cid in explicit_contracts
        ]
        propagated_contract_records = [
            {
                "contract_id": cid,
                "provider": contract_by_id[cid]["provider"],
                "consumer": contract_by_id[cid]["consumer"],
                "key": contract_by_id[cid].get("key"),
                "kind": contract_by_id[cid].get("kind"),
                "impact_role": "downstream-flow-contract",
                "evidence": contract_by_id[cid].get("evidence", []),
            }
            for cid in sorted(propagated_contracts - set(explicit_contracts))
        ]

        change_risk = local_risk
        if len(affected_repos) > 1:
            change_risk = _bump(change_risk, "medium")
        if explicit_contracts:
            change_risk = _bump(change_risk, "high")
        if change_type in {"delete", "rename"} and (len(affected_repos) > 1 or symbol_impacts):
            change_risk = _bump(change_risk, "high")
        if breaking_changes > 0:
            change_risk = _bump(change_risk, "high")

        constraints = []
        if state == "inferred" or any(x["state"] == "inferred" for x in local_impacts):
            constraints.append("impact report contains inferred evidence")
        if any(f["flow_state"] == "inferred" for f in impacted_flow_records):
            constraints.append("one or more affected execution flows are inferred")
        if truncated:
            constraints.append("impact report truncated by configured budgets")

        change_record = {
            "change_id": change_id,
            "repository_id": repository_id,
            "change_type": change_type,
            "path": path,
            "previous_path": previous_path,
            "symbol": symbol,
            "previous_symbol": previous_symbol,
            "state": state,
            "risk_level": change_risk,
            "evidence": evidence,
            "rationale": rationale,
            "local_impact": {
                "reports": local_impacts,
                "symbols": symbol_impacts,
            },
            "changed_contracts": changed_contract_records,
            "downstream_contracts": propagated_contract_records,
            "directly_impacted_steps": directly_impacted_steps,
            "affected_steps": sorted(affected_steps),
            "affected_flows": sorted(impacted_flow_records, key=lambda x: x["flow_id"]),
            "affected_repositories": sorted(affected_repos),
            "constraints": sorted(set(constraints)),
        }
        normalized_changes.append(change_record)

        all_impacted_repos.update(affected_repos)
        all_impacted_contracts.update(explicit_contracts)
        all_impacted_contracts.update(propagated_contracts)
        all_impacted_flows.update(f["flow_id"] for f in impacted_flow_records)
        overall_risk = _max_risk(overall_risk, change_risk)

    missing_local = sorted(set(local_by_change) - seen_change_ids)
    if missing_local:
        raise ValueError(f"local impacts reference unknown change IDs: {missing_local}")

    normalized_changes.sort(key=lambda x: x["change_id"])
    return {
        "schema_version": SCHEMA_VERSION,
        "context": "C002",
        "workspace_id": workspace_id,
        "status": "verified",
        "risk_level": overall_risk,
        "changes": normalized_changes,
        "blast_radius": {
            "repositories": sorted(all_impacted_repos),
            "contracts": sorted(all_impacted_contracts),
            "flows": sorted(all_impacted_flows),
        },
        "summary": {
            "changes": len(normalized_changes),
            "affected_repositories": len(all_impacted_repos),
            "affected_contracts": len(all_impacted_contracts),
            "affected_flows": len(all_impacted_flows),
            "local_symbol_impacts": sum(
                len(c["local_impact"]["symbols"]) for c in normalized_changes
            ),
            "high_or_critical_changes": sum(
                1 for c in normalized_changes if RISK_RANK[c["risk_level"]] >= RISK_RANK["high"]
            ),
            "truncated": truncated,
            "max_symbol_impacts": max_symbol_impacts,
            "max_flow_impacts": max_flow_impacts,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    out = [
        "# Cross-Repository Diff Impact",
        "",
        f"- Workspace: {report['workspace_id']}",
        f"- Overall risk: {report['risk_level']}",
        f"- Changes: {report['summary']['changes']}",
        f"- Affected repositories: {report['summary']['affected_repositories']}",
        f"- Affected contracts: {report['summary']['affected_contracts']}",
        f"- Affected flows: {report['summary']['affected_flows']}",
        "",
    ]
    for change in report["changes"]:
        label = change["symbol"] or change["path"]
        out.extend([
            f"## {change['change_id']} — {change['change_type'].upper()} — {label}",
            "",
            f"- Repository: {change['repository_id']}",
            f"- Risk: {change['risk_level']}",
            f"- Affected repositories: {', '.join(change['affected_repositories'])}",
            f"- Affected flows: {', '.join(f['flow_id'] for f in change['affected_flows']) or 'None'}",
            f"- Changed contracts: {', '.join(c['contract_id'] for c in change['changed_contracts']) or 'None'}",
            f"- Downstream contracts: {', '.join(c['contract_id'] for c in change['downstream_contracts']) or 'None'}",
            f"- Local symbol impacts: {len(change['local_impact']['symbols'])}",
        ])
        if change["constraints"]:
            out.append(f"- Constraints: {'; '.join(change['constraints'])}")
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
    parser.add_argument("--max-risk", choices=list(RISK_RANK), default=None)
    args = parser.parse_args()

    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    contracts = json.loads(args.contracts.read_text(encoding="utf-8"))
    flows = json.loads(args.flows.read_text(encoding="utf-8"))
    changes = json.loads(args.changes.read_text(encoding="utf-8"))

    report = normalize(registry, contracts, flows, changes)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown.write_text(render_markdown(report), encoding="utf-8")

    if args.max_risk and RISK_RANK[report["risk_level"]] > RISK_RANK[args.max_risk]:
        return 7
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
