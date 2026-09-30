#!/usr/bin/env python3
"""Normalize repository diffs into evidence-backed cross-repository blast radius."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
CLAIM_STATES = {"observed", "inferred"}
CHANGE_TYPES = {
    "body",
    "signature",
    "rename",
    "delete",
    "schema",
    "contract",
    "event",
    "file",
    "config",
}
CONTRACT_SIDES = {"provider", "consumer", "shared"}
RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


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
        raise ValueError(f"{where}: inferred impact observation requires rationale")
    return state, sorted(set(x.strip() for x in evidence)), rationale


def _impact_id(repo_id: str, change_id: str) -> str:
    raw = f"{repo_id}\0{change_id}".encode("utf-8")
    return "impact_" + hashlib.sha256(raw).hexdigest()[:16]


def _max_risk(*values: str) -> str:
    valid = [v for v in values if v in RISK_ORDER]
    if not valid:
        return "low"
    return max(valid, key=lambda v: RISK_ORDER[v])


def _escalate(risk: str, minimum: str) -> str:
    return _max_risk(risk, minimum)


def _flow_edges(flow_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _text(edge.get("edge_id"), "flow.edges[].edge_id"): edge
        for edge in _list(flow_report.get("edges"), "flow.edges")
        if isinstance(edge, dict)
    }


def normalize(
    registry: dict[str, Any],
    contracts: dict[str, Any],
    flow_report: dict[str, Any],
    changes: dict[str, Any],
) -> dict[str, Any]:
    for name, payload in [
        ("registry", registry),
        ("contracts", contracts),
        ("flow_report", flow_report),
        ("changes", changes),
    ]:
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"{name}.schema_version must be 1")

    workspace_id = _text(registry.get("workspace_id"), "registry.workspace_id")
    if (
        contracts.get("workspace_id") != workspace_id
        or flow_report.get("workspace_id") != workspace_id
        or changes.get("workspace_id") != workspace_id
    ):
        raise ValueError("workspace_id mismatch across impact inputs")

    repo_ids = {
        _text(repo.get("repository_id"), "registry.repositories[].repository_id")
        for repo in _list(registry.get("repositories"), "registry.repositories")
        if isinstance(repo, dict)
    }

    contract_by_id = {
        _text(c.get("contract_id"), "contracts.contracts[].contract_id"): c
        for c in _list(contracts.get("contracts"), "contracts.contracts")
        if isinstance(c, dict) and c.get("status") == "matched"
    }

    step_by_id = {
        _text(step.get("step_id"), "flow.steps[].step_id"): step
        for step in _list(flow_report.get("steps"), "flow.steps")
        if isinstance(step, dict)
    }
    edge_by_id = _flow_edges(flow_report)
    flows = [
        flow
        for flow in _list(flow_report.get("flows"), "flow.flows")
        if isinstance(flow, dict)
    ]

    raw_changes = _list(changes.get("changes"), "changes.changes")
    if not raw_changes:
        raise ValueError("changes.changes must not be empty")

    normalized_changes: list[dict[str, Any]] = []
    affected_contracts: dict[str, dict[str, Any]] = {}
    affected_flows: dict[str, dict[str, Any]] = {}
    affected_repos: dict[str, dict[str, Any]] = {}
    test_targets: set[str] = set()
    blockers: list[dict[str, Any]] = []
    global_constraints: set[str] = set()
    overall_risk = "low"

    def mark_repo(repo_id: str, *, reason: str, risk: str, evidence: list[str], state: str) -> None:
        record = affected_repos.setdefault(repo_id, {
            "repository_id": repo_id,
            "risk": "low",
            "state": "observed",
            "reasons": [],
            "evidence": [],
        })
        record["risk"] = _max_risk(record["risk"], risk)
        if state == "inferred":
            record["state"] = "inferred"
        record["reasons"] = sorted(set(record["reasons"] + [reason]))
        record["evidence"] = sorted(set(record["evidence"] + evidence))

    for index, raw in enumerate(raw_changes):
        if not isinstance(raw, dict):
            raise ValueError(f"changes[{index}] must be an object")
        change_id = _text(raw.get("change_id"), f"changes[{index}].change_id")
        repo_id = _text(raw.get("repository_id"), f"changes[{index}].repository_id")
        if repo_id not in repo_ids:
            raise ValueError(f"{change_id}: unknown repository_id {repo_id}")

        change_type = _text(raw.get("change_type"), f"changes[{index}].change_type")
        if change_type not in CHANGE_TYPES:
            raise ValueError(f"{change_id}: unsupported change_type {change_type}")

        state, evidence, rationale = _claim(raw, f"changes[{index}]")
        local = raw.get("local_impact", {})
        if not isinstance(local, dict):
            raise ValueError(f"{change_id}.local_impact must be an object")

        local_risk = str(local.get("risk", "low")).strip().lower()
        if local_risk not in RISK_ORDER:
            raise ValueError(f"{change_id}: local_impact.risk must be low/medium/high")

        local_symbols = sorted(set(
            str(x).strip() for x in _list(local.get("symbols"), f"{change_id}.local_impact.symbols")
            if str(x).strip()
        ))
        local_files = sorted(set(
            str(x).strip() for x in _list(local.get("files"), f"{change_id}.local_impact.files")
            if str(x).strip()
        ))
        related_tests = sorted(set(
            str(x).strip() for x in _list(local.get("tests"), f"{change_id}.local_impact.tests")
            if str(x).strip()
        ))
        test_targets.update(related_tests)

        touched_steps = sorted(set(
            str(x).strip() for x in _list(raw.get("touched_steps"), f"{change_id}.touched_steps")
            if str(x).strip()
        ))
        for sid in touched_steps:
            if sid not in step_by_id:
                raise ValueError(f"{change_id}: unknown touched_step {sid}")
            if step_by_id[sid].get("repository_id") != repo_id:
                raise ValueError(f"{change_id}: touched_step {sid} belongs to another repository")

        contract_touches = _list(raw.get("contract_touches"), f"{change_id}.contract_touches")
        normalized_touches = []
        for touch_index, touch in enumerate(contract_touches):
            if not isinstance(touch, dict):
                raise ValueError(f"{change_id}.contract_touches[{touch_index}] must be an object")
            cid = _text(touch.get("contract_id"), f"{change_id}.contract_touches[{touch_index}].contract_id")
            contract = contract_by_id.get(cid)
            if contract is None:
                raise ValueError(f"{change_id}: unknown or unmatched contract_id {cid}")
            side = _text(touch.get("side"), f"{change_id}.contract_touches[{touch_index}].side")
            if side not in CONTRACT_SIDES:
                raise ValueError(f"{change_id}: invalid contract side {side}")

            expected_repo = (
                contract["provider"] if side == "provider"
                else contract["consumer"] if side == "consumer"
                else None
            )
            if expected_repo is not None and expected_repo != repo_id:
                raise ValueError(f"{change_id}: contract side does not match changed repository")
            if side == "shared" and repo_id not in {contract["provider"], contract["consumer"]}:
                raise ValueError(f"{change_id}: shared contract touch repository is not a contract participant")

            touch_state, touch_evidence, touch_rationale = _claim(
                touch, f"{change_id}.contract_touches[{touch_index}]"
            )
            combined_state = (
                "observed"
                if state == touch_state == contract.get("claim_state") == "observed"
                else "inferred"
            )

            contract_risk = local_risk
            if change_type in {"signature", "delete", "schema", "contract", "event"}:
                contract_risk = _escalate(contract_risk, "high")
            elif change_type == "rename":
                contract_risk = _escalate(contract_risk, "medium")

            rec = affected_contracts.setdefault(cid, {
                "contract_id": cid,
                "key": contract.get("key"),
                "kind": contract.get("kind"),
                "provider": contract.get("provider"),
                "consumer": contract.get("consumer"),
                "risk": "low",
                "state": "observed",
                "changed_sides": [],
                "evidence": [],
                "constraints": [],
            })
            rec["risk"] = _max_risk(rec["risk"], contract_risk)
            if combined_state == "inferred":
                rec["state"] = "inferred"
                rec["constraints"] = sorted(set(
                    rec["constraints"] + ["contract impact contains inferred evidence"]
                ))
            rec["changed_sides"] = sorted(set(rec["changed_sides"] + [side]))
            rec["evidence"] = sorted(set(
                rec["evidence"] + evidence + touch_evidence + list(contract.get("evidence", []))
            ))

            if side == "provider":
                mark_repo(
                    contract["consumer"],
                    reason=f"consumes changed contract {cid}",
                    risk=contract_risk,
                    evidence=rec["evidence"],
                    state=combined_state,
                )
            elif side == "consumer":
                mark_repo(
                    contract["provider"],
                    reason=f"counterparty review for changed consumer contract {cid}",
                    risk=_escalate(local_risk, "medium"),
                    evidence=rec["evidence"],
                    state=combined_state,
                )
            else:
                for participant in {contract["provider"], contract["consumer"]}:
                    if participant != repo_id:
                        mark_repo(
                            participant,
                            reason=f"shares changed contract {cid}",
                            risk=contract_risk,
                            evidence=rec["evidence"],
                            state=combined_state,
                        )

            normalized_touches.append({
                "contract_id": cid,
                "side": side,
                "state": combined_state,
                "evidence": touch_evidence,
                "rationale": touch_rationale,
            })

        change_risk = local_risk
        if change_type in {"signature", "delete"}:
            change_risk = _escalate(change_risk, "high")
        elif change_type in {"schema", "contract", "event", "rename"}:
            change_risk = _escalate(change_risk, "medium")

        mark_repo(
            repo_id,
            reason=f"contains changed artifact {change_id}",
            risk=change_risk,
            evidence=evidence,
            state=state,
        )
        overall_risk = _max_risk(overall_risk, change_risk)

        touched_contract_ids = {x["contract_id"] for x in normalized_touches}
        impacted_flow_ids: list[str] = []

        for flow in flows:
            flow_id = _text(flow.get("flow_id"), "flow.flow_id")
            flow_steps = set(_list(flow.get("steps"), f"{flow_id}.steps"))
            flow_edge_ids = _list(flow.get("edge_ids"), f"{flow_id}.edge_ids")
            flow_contracts = {
                edge_by_id[eid].get("contract_id")
                for eid in flow_edge_ids
                if eid in edge_by_id and edge_by_id[eid].get("contract_id")
            }
            if not (set(touched_steps) & flow_steps or touched_contract_ids & flow_contracts):
                continue

            impacted_flow_ids.append(flow_id)
            flow_state = "observed"
            flow_evidence = set(evidence)
            flow_constraints = set(flow.get("constraints", []))
            downstream_repos: list[str] = []

            earliest = None
            if touched_steps:
                positions = [
                    flow["steps"].index(sid)
                    for sid in touched_steps
                    if sid in flow_steps
                ]
                if positions:
                    earliest = min(positions)

            if earliest is None and touched_contract_ids:
                for pos, eid in enumerate(flow_edge_ids):
                    edge = edge_by_id.get(eid, {})
                    if edge.get("contract_id") in touched_contract_ids:
                        earliest = pos + 1
                        break

            if earliest is not None:
                for sid in flow["steps"][earliest:]:
                    target_repo = step_by_id[sid]["repository_id"]
                    if target_repo not in downstream_repos:
                        downstream_repos.append(target_repo)
                    flow_evidence.update(step_by_id[sid].get("evidence", []))

            for eid in flow_edge_ids:
                edge = edge_by_id.get(eid, {})
                if edge.get("state") == "inferred":
                    flow_state = "inferred"
                flow_evidence.update(edge.get("evidence", []))

            if state == "inferred" or flow.get("state") == "inferred":
                flow_state = "inferred"
                flow_constraints.add("impact path contains inferred evidence")

            flow_risk = change_risk
            if len(flow.get("repositories", [])) > 1:
                flow_risk = _escalate(flow_risk, "medium")
            if touched_contract_ids and change_type in {"signature", "delete", "schema", "contract", "event"}:
                flow_risk = _escalate(flow_risk, "high")

            frec = affected_flows.setdefault(flow_id, {
                "flow_id": flow_id,
                "risk": "low",
                "state": "observed",
                "changed_repositories": [],
                "downstream_repositories": [],
                "evidence": [],
                "constraints": [],
            })
            frec["risk"] = _max_risk(frec["risk"], flow_risk)
            if flow_state == "inferred":
                frec["state"] = "inferred"
            frec["changed_repositories"] = sorted(set(frec["changed_repositories"] + [repo_id]))
            frec["downstream_repositories"] = list(dict.fromkeys(
                frec["downstream_repositories"] + downstream_repos
            ))
            frec["evidence"] = sorted(set(frec["evidence"]) | flow_evidence)
            frec["constraints"] = sorted(set(frec["constraints"]) | flow_constraints)

            for affected_repo in downstream_repos:
                if affected_repo != repo_id:
                    mark_repo(
                        affected_repo,
                        reason=f"downstream in affected flow {flow_id}",
                        risk=flow_risk,
                        evidence=frec["evidence"],
                        state=flow_state,
                    )

            overall_risk = _max_risk(overall_risk, flow_risk)

        normalized_changes.append({
            "impact_id": _impact_id(repo_id, change_id),
            "change_id": change_id,
            "repository_id": repo_id,
            "change_type": change_type,
            "path": str(raw.get("path", "")).strip() or None,
            "symbol": str(raw.get("symbol", "")).strip() or None,
            "state": state,
            "evidence": evidence,
            "rationale": rationale,
            "local_impact": {
                "risk": local_risk,
                "symbols": local_symbols,
                "files": local_files,
                "tests": related_tests,
            },
            "touched_steps": touched_steps,
            "contract_touches": normalized_touches,
            "affected_flows": sorted(set(impacted_flow_ids)),
            "normalized_risk": change_risk,
        })

    for record in affected_contracts.values():
        overall_risk = _max_risk(overall_risk, record["risk"])
    for record in affected_repos.values():
        overall_risk = _max_risk(overall_risk, record["risk"])

    if any(r["state"] == "inferred" for r in affected_repos.values()):
        global_constraints.add("blast radius includes inferred repository impact")
    if any(f["state"] == "inferred" for f in affected_flows.values()):
        global_constraints.add("blast radius includes inferred process-flow impact")

    if not affected_repos:
        blockers.append({"type": "no-affected-repositories"})

    return {
        "schema_version": SCHEMA_VERSION,
        "context": "C002",
        "workspace_id": workspace_id,
        "status": "blocked" if blockers else "verified",
        "risk_level": overall_risk,
        "changes": sorted(normalized_changes, key=lambda x: x["impact_id"]),
        "affected_repositories": sorted(affected_repos.values(), key=lambda x: x["repository_id"]),
        "affected_contracts": sorted(affected_contracts.values(), key=lambda x: x["contract_id"]),
        "affected_flows": sorted(affected_flows.values(), key=lambda x: x["flow_id"]),
        "test_targets": sorted(test_targets),
        "constraints": sorted(global_constraints),
        "blockers": blockers,
        "summary": {
            "changes": len(normalized_changes),
            "affected_repositories": len(affected_repos),
            "affected_contracts": len(affected_contracts),
            "affected_flows": len(affected_flows),
            "test_targets": len(test_targets),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    out = [
        "# Cross-Repository Diff Impact",
        "",
        f"- Workspace: {report['workspace_id']}",
        f"- Status: {report['status']}",
        f"- Risk: **{report['risk_level'].upper()}**",
        f"- Changes: {report['summary']['changes']}",
        f"- Affected repositories: {report['summary']['affected_repositories']}",
        f"- Affected contracts: {report['summary']['affected_contracts']}",
        f"- Affected flows: {report['summary']['affected_flows']}",
        "",
        "## Affected repositories",
        "",
    ]
    for repo in report["affected_repositories"]:
        out.append(
            f"- **{repo['repository_id']}** — {repo['risk'].upper()} / {repo['state'].upper()}: "
            + "; ".join(repo["reasons"])
        )
    out.extend(["", "## Affected contracts", ""])
    if report["affected_contracts"]:
        for contract in report["affected_contracts"]:
            out.append(
                f"- **{contract['contract_id']}** — {contract['kind']}:{contract['key']} — "
                f"{contract['risk'].upper()} / {contract['state'].upper()}"
            )
    else:
        out.append("- None.")
    out.extend(["", "## Affected flows", ""])
    if report["affected_flows"]:
        for flow in report["affected_flows"]:
            downstream = " → ".join(flow["downstream_repositories"]) or "none"
            out.append(
                f"- **{flow['flow_id']}** — {flow['risk'].upper()} / {flow['state'].upper()} — "
                f"downstream: {downstream}"
            )
    else:
        out.append("- None.")
    out.extend(["", "## Test targets", ""])
    if report["test_targets"]:
        out.extend(f"- {target}" for target in report["test_targets"])
    else:
        out.append("- None.")
    if report["constraints"]:
        out.extend(["", "## Constraints", ""])
        out.extend(f"- {c}" for c in report["constraints"])
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
    parser.add_argument("--require-impact", action="store_true")
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

    if args.require_impact and report["status"] != "verified":
        return 7
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
