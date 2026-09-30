#!/usr/bin/env python3
"""Synthesize evidence-backed execution flows across repository boundaries."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
CLAIM_STATES = {"observed", "inferred"}
FLOW_DIRECTIONS = {"consumer-to-provider", "provider-to-consumer"}


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


def _normalize_claim(item: dict[str, Any], where: str) -> tuple[str, list[str], str]:
    state = _text(item.get("state", "observed"), f"{where}.state")
    if state not in CLAIM_STATES:
        raise ValueError(f"{where}.state must be observed or inferred")
    evidence = _list(item.get("evidence"), f"{where}.evidence")
    if not evidence or not all(isinstance(x, str) and x.strip() for x in evidence):
        raise ValueError(f"{where}: evidence is required")
    rationale = str(item.get("rationale", "")).strip()
    if state == "inferred" and not rationale:
        raise ValueError(f"{where}: inferred relationship requires rationale")
    return state, sorted(set(x.strip() for x in evidence)), rationale


def _edge_id(prefix: str, source: str, target: str, discriminator: str) -> str:
    material = f"{prefix}\0{source}\0{target}\0{discriminator}".encode("utf-8")
    return prefix + "_" + hashlib.sha256(material).hexdigest()[:16]


def _find_cycles(adjacency: dict[str, list[str]]) -> list[list[str]]:
    cycles: set[tuple[str, ...]] = set()
    visiting: list[str] = []
    active: set[str] = set()
    done: set[str] = set()

    def canonical_cycle(nodes: list[str]) -> tuple[str, ...]:
        core = nodes[:-1]
        rotations = [tuple(core[i:] + core[:i]) for i in range(len(core))]
        best = min(rotations)
        return best + (best[0],)

    def visit(node: str) -> None:
        if node in done:
            return
        if node in active:
            idx = visiting.index(node)
            cycles.add(canonical_cycle(visiting[idx:] + [node]))
            return
        active.add(node)
        visiting.append(node)
        for nxt in adjacency.get(node, []):
            visit(nxt)
        visiting.pop()
        active.remove(node)
        done.add(node)

    for node in sorted(adjacency):
        visit(node)
    return [list(c) for c in sorted(cycles)]


def synthesize(
    registry: dict[str, Any],
    contracts: dict[str, Any],
    observations: dict[str, Any],
) -> dict[str, Any]:
    for name, payload in [
        ("registry", registry),
        ("contracts", contracts),
        ("observations", observations),
    ]:
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"{name}.schema_version must be 1")

    workspace_id = _text(registry.get("workspace_id"), "registry.workspace_id")
    if contracts.get("workspace_id") != workspace_id or observations.get("workspace_id") != workspace_id:
        raise ValueError("workspace_id mismatch across registry/contracts/observations")

    repo_ids = {
        _text(r.get("repository_id"), "registry.repositories[].repository_id")
        for r in _list(registry.get("repositories"), "registry.repositories")
        if isinstance(r, dict)
    }
    if len(repo_ids) < 2:
        raise ValueError("process synthesis requires a multi-repository registry")

    contract_by_id: dict[str, dict[str, Any]] = {}
    for raw in _list(contracts.get("contracts"), "contracts.contracts"):
        if not isinstance(raw, dict):
            raise ValueError("contracts.contracts entries must be objects")
        cid = _text(raw.get("contract_id"), "contract.contract_id")
        if cid in contract_by_id:
            raise ValueError(f"duplicate contract_id: {cid}")
        if raw.get("status") != "matched":
            continue
        contract_by_id[cid] = raw

    raw_steps = _list(observations.get("steps"), "observations.steps")
    if not raw_steps:
        raise ValueError("observations.steps must not be empty")

    steps: dict[str, dict[str, Any]] = {}
    for i, raw in enumerate(raw_steps):
        if not isinstance(raw, dict):
            raise ValueError(f"steps[{i}] must be an object")
        sid = _text(raw.get("step_id"), f"steps[{i}].step_id")
        if sid in steps:
            raise ValueError(f"duplicate step_id: {sid}")
        repository_id = _text(raw.get("repository_id"), f"steps[{i}].repository_id")
        if repository_id not in repo_ids:
            raise ValueError(f"{sid}: unknown repository_id {repository_id}")
        state, evidence, rationale = _normalize_claim(raw, f"steps[{i}]")
        steps[sid] = {
            "step_id": sid,
            "repository_id": repository_id,
            "label": _text(raw.get("label"), f"steps[{i}].label"),
            "symbol": str(raw.get("symbol", "")).strip() or None,
            "kind": _text(raw.get("kind", "operation"), f"steps[{i}].kind"),
            "entry": bool(raw.get("entry", False)),
            "terminal": bool(raw.get("terminal", False)),
            "state": state,
            "evidence": evidence,
            "rationale": rationale,
        }

    entries = sorted(sid for sid, s in steps.items() if s["entry"])
    terminals = sorted(sid for sid, s in steps.items() if s["terminal"])
    if not entries:
        raise ValueError("at least one entry step is required")
    if not terminals:
        raise ValueError("at least one terminal step is required")

    edges: list[dict[str, Any]] = []

    for i, raw in enumerate(_list(observations.get("edges"), "observations.edges")):
        if not isinstance(raw, dict):
            raise ValueError(f"edges[{i}] must be an object")
        source = _text(raw.get("from"), f"edges[{i}].from")
        target = _text(raw.get("to"), f"edges[{i}].to")
        if source not in steps or target not in steps:
            raise ValueError(f"edges[{i}]: unknown step")
        if steps[source]["repository_id"] != steps[target]["repository_id"]:
            raise ValueError("cross-repository edges must use contract bindings")
        state, evidence, rationale = _normalize_claim(raw, f"edges[{i}]")
        relation = _text(raw.get("relation", "calls"), f"edges[{i}].relation")
        edges.append({
            "edge_id": _edge_id("local", source, target, relation),
            "from": source,
            "to": target,
            "scope": "intra-repository",
            "relation": relation,
            "contract_id": None,
            "state": state,
            "evidence": evidence,
            "rationale": rationale,
            "constraints": [],
        })

    used_bindings: set[str] = set()
    for i, raw in enumerate(_list(observations.get("bindings"), "observations.bindings")):
        if not isinstance(raw, dict):
            raise ValueError(f"bindings[{i}] must be an object")
        cid = _text(raw.get("contract_id"), f"bindings[{i}].contract_id")
        if cid in used_bindings:
            raise ValueError(f"duplicate contract binding: {cid}")
        used_bindings.add(cid)
        contract = contract_by_id.get(cid)
        if contract is None:
            raise ValueError(f"bindings[{i}]: unknown or unmatched contract_id {cid}")

        provider_step = _text(raw.get("provider_step"), f"bindings[{i}].provider_step")
        consumer_step = _text(raw.get("consumer_step"), f"bindings[{i}].consumer_step")
        if provider_step not in steps or consumer_step not in steps:
            raise ValueError(f"bindings[{i}]: unknown provider/consumer step")
        if steps[provider_step]["repository_id"] != contract["provider"]:
            raise ValueError(f"{cid}: provider_step repository does not match contract provider")
        if steps[consumer_step]["repository_id"] != contract["consumer"]:
            raise ValueError(f"{cid}: consumer_step repository does not match contract consumer")

        direction = _text(raw.get("flow_direction"), f"bindings[{i}].flow_direction")
        if direction not in FLOW_DIRECTIONS:
            raise ValueError(f"bindings[{i}]: invalid flow_direction")
        state, evidence, rationale = _normalize_claim(raw, f"bindings[{i}]")
        if direction == "consumer-to-provider":
            source, target = consumer_step, provider_step
        else:
            source, target = provider_step, consumer_step

        combined_state = (
            "observed"
            if state == "observed" and contract.get("claim_state") == "observed"
            else "inferred"
        )
        constraints = list(contract.get("constraints", []))
        if combined_state == "inferred":
            constraints.append("cross-repository flow hop contains inferred evidence")

        edges.append({
            "edge_id": _edge_id("cross", source, target, cid),
            "from": source,
            "to": target,
            "scope": "cross-repository",
            "relation": f"{contract.get('kind')}:{contract.get('key')}",
            "contract_id": cid,
            "state": combined_state,
            "evidence": sorted(set(evidence + list(contract.get("evidence", [])))),
            "rationale": rationale,
            "constraints": sorted(set(constraints)),
        })

    adjacency: dict[str, list[str]] = {sid: [] for sid in steps}
    edge_lookup: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for edge in edges:
        adjacency[edge["from"]].append(edge["to"])
        edge_lookup.setdefault((edge["from"], edge["to"]), []).append(edge)
    for values in adjacency.values():
        values.sort()
    for values in edge_lookup.values():
        values.sort(key=lambda e: e["edge_id"])

    budgets = observations.get("budgets", {})
    if not isinstance(budgets, dict):
        raise ValueError("observations.budgets must be an object")
    max_hops = int(budgets.get("max_hops", 32))
    max_paths = int(budgets.get("max_paths", 100))
    if max_hops < 1 or max_paths < 1:
        raise ValueError("max_hops and max_paths must be positive")

    paths: list[list[str]] = []
    truncated = False

    def walk(node: str, current: list[str]) -> None:
        nonlocal truncated
        if len(paths) >= max_paths:
            truncated = True
            return
        if len(current) - 1 > max_hops:
            truncated = True
            return
        if node in terminals:
            paths.append(list(current))
            return
        for nxt in adjacency.get(node, []):
            if nxt in current:
                continue
            walk(nxt, current + [nxt])
            if len(paths) >= max_paths:
                return

    for entry in entries:
        walk(entry, [entry])
        if len(paths) >= max_paths:
            break

    flow_records: list[dict[str, Any]] = []
    for index, path in enumerate(sorted(paths)):
        path_edges: list[dict[str, Any]] = []
        for source, target in zip(path, path[1:]):
            candidates = edge_lookup[(source, target)]
            path_edges.append(candidates[0])
        observed = all(steps[s]["state"] == "observed" for s in path) and all(
            e["state"] == "observed" for e in path_edges
        )
        evidence = sorted({
            ev
            for sid in path
            for ev in steps[sid]["evidence"]
        } | {
            ev
            for edge in path_edges
            for ev in edge["evidence"]
        })
        constraints = sorted({
            c
            for edge in path_edges
            for c in edge["constraints"]
        })
        if not observed:
            constraints.append("end-to-end flow contains inferred evidence")
            constraints = sorted(set(constraints))

        repos = []
        for sid in path:
            rid = steps[sid]["repository_id"]
            if not repos or repos[-1] != rid:
                repos.append(rid)

        flow_records.append({
            "flow_id": f"flow_{index + 1:03d}",
            "state": "observed" if observed else "inferred",
            "entry_step": path[0],
            "terminal_step": path[-1],
            "steps": path,
            "repositories": repos,
            "edge_ids": [e["edge_id"] for e in path_edges],
            "evidence": evidence,
            "constraints": constraints,
        })

    cycles = _find_cycles(adjacency)
    reachable = {sid for path in paths for sid in path}
    unreachable_steps = sorted(set(steps) - reachable)

    blockers: list[dict[str, Any]] = []
    if not flow_records:
        blockers.append({"type": "no-complete-entry-to-terminal-flow"})
    if any(entry in unreachable_steps for entry in entries):
        blockers.append({"type": "entry-without-complete-terminal-path"})

    return {
        "schema_version": SCHEMA_VERSION,
        "context": "C002",
        "workspace_id": workspace_id,
        "status": "blocked" if blockers else "verified",
        "steps": [steps[sid] for sid in sorted(steps)],
        "edges": sorted(edges, key=lambda e: e["edge_id"]),
        "flows": flow_records,
        "cycles": cycles,
        "unreachable_steps": unreachable_steps,
        "blockers": blockers,
        "summary": {
            "steps": len(steps),
            "edges": len(edges),
            "flows": len(flow_records),
            "observed_flows": sum(1 for f in flow_records if f["state"] == "observed"),
            "inferred_flows": sum(1 for f in flow_records if f["state"] == "inferred"),
            "cross_repository_edges": sum(1 for e in edges if e["scope"] == "cross-repository"),
            "cycles": len(cycles),
            "unreachable_steps": len(unreachable_steps),
            "truncated": truncated,
            "max_hops": max_hops,
            "max_paths": max_paths,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    step_by_id = {s["step_id"]: s for s in report["steps"]}
    out = [
        "# Cross-Repository Process Flows",
        "",
        f"- Workspace: {report['workspace_id']}",
        f"- Status: {report['status']}",
        f"- Complete flows: {report['summary']['flows']}",
        f"- Cross-repository hops: {report['summary']['cross_repository_edges']}",
        "",
    ]
    for flow in report["flows"]:
        labels = [step_by_id[s]["label"] for s in flow["steps"]]
        out.extend([
            f"## {flow['flow_id']} — {flow['state'].upper()}",
            "",
            " → ".join(labels),
            "",
            f"- Repositories: {' → '.join(flow['repositories'])}",
            f"- Evidence items: {len(flow['evidence'])}",
        ])
        if flow["constraints"]:
            out.append(f"- Constraints: {'; '.join(flow['constraints'])}")
        out.append("")
    if report["cycles"]:
        out.extend(["## Cycles", ""])
        out.extend(f"- {' → '.join(cycle)}" for cycle in report["cycles"])
        out.append("")
    if report["unreachable_steps"]:
        out.extend(["## Unreachable steps", ""])
        out.extend(f"- {step}" for step in report["unreachable_steps"])
        out.append("")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("registry", type=Path)
    parser.add_argument("contracts", type=Path)
    parser.add_argument("observations", type=Path)
    parser.add_argument("--json", dest="json_out", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    parser.add_argument("--require-flow", action="store_true")
    args = parser.parse_args()

    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    contracts = json.loads(args.contracts.read_text(encoding="utf-8"))
    observations = json.loads(args.observations.read_text(encoding="utf-8"))
    report = synthesize(registry, contracts, observations)

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown.write_text(render_markdown(report), encoding="utf-8")

    if args.require_flow and report["status"] != "verified":
        return 6
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
