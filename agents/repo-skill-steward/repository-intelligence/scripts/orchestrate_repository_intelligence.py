#!/usr/bin/env python3
"""C002 Repository Intelligence orchestration state machine."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


ENV = _load_module("evidence_envelope", HERE / "evidence_envelope.py")
BUDGET = _load_module("budget_guard", HERE / "budget_guard.py")
PROVIDER = _load_module("provider_health", HERE / "provider_health.py")
PROMOTION = _load_module("evaluate_promotion", HERE / "evaluate_promotion.py")


PROVIDERS = {
    "L0-intake": "sazan-intake",
    "L1-context-packaging": "repomix",
    "L2-semantic-graph": "codegraph-0.20.1",
    "L3-architecture-presentation": "sazan-mermaid-renderer",
    "L4-wiki-qa": "sazan-lightweight-wiki-qa",
    "L5-semantic-editing": "serena-1.7.0-isolated",
    "L6-reverse-engineering": "sazan-rebuild-spec",
    "L7-promotion": "sazan-promotion-gate",
}

STRICT_BUDGET_METRICS = {
    "L0-intake": ["output_bytes", "elapsed_seconds"],
    "L1-context-packaging": ["context_tokens", "output_bytes", "elapsed_seconds"],
    "L2-semantic-graph": ["graph_nodes", "output_bytes", "elapsed_seconds"],
    "L3-architecture-presentation": ["output_bytes", "elapsed_seconds"],
    "L4-wiki-qa": ["context_tokens", "output_bytes", "elapsed_seconds"],
    "L5-semantic-editing": ["output_bytes", "elapsed_seconds"],
    "L6-reverse-engineering": ["context_tokens", "output_bytes", "elapsed_seconds"],
    "L7-promotion": [],
}


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected JSON object")
    return data


def _provider_routing(
    manifest_data: dict[str, Any],
    envelope: dict[str, Any],
) -> dict[str, Any] | None:
    policy = envelope["provider_policy"]
    if not policy["strict"]:
        return None
    health = manifest_data.get("provider_health")
    if not isinstance(health, dict):
        raise ValueError("strict provider routing requires provider_health observations")
    stages = [
        stage["id"]
        for stage in envelope["stages"]
        if stage["status"] != "skipped"
    ]
    return PROVIDER.route_pipeline(
        health,
        visibility=envelope["target"]["visibility"],
        stages=stages,
        allow_degraded=policy["allow_degraded"],
    )


def _route_map(routing: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if routing is None:
        return {}
    return {item["stage"]: item for item in routing["stages"]}


def plan(
    envelope: dict[str, Any],
    routing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    routes = _route_map(routing)
    stages = []
    for stage in envelope["stages"]:
        route = routes.get(stage["id"])
        provider = (
            route["selected_provider"]
            if route is not None and route["selected_provider"] is not None
            else PROVIDERS[stage["id"]]
        )
        stages.append({
            "id": stage["id"],
            "provider": provider,
            "provider_route": route,
            "required": stage["status"] != "skipped",
            "status": stage["status"],
        })
    return {
        "schema_version": 1,
        "context": "C002",
        "run_id": envelope["run_id"],
        "target": envelope["target"],
        "budgets": envelope["budgets"],
        "budget_policy": envelope["budget_policy"],
        "provider_policy": envelope["provider_policy"],
        "provider_routing": routing,
        "stages": stages,
        "rules": {
            "stop_on_failed": True,
            "stop_on_blocked": True,
            "auto_promote": False,
            "parent_approval_required": True,
            "private_identity_persistence": False,
            "budget_enforcement": True,
            "budget_violation_blocks_stage": True,
            "provider_health_enforcement": envelope["provider_policy"]["strict"],
            "silent_provider_fallback": False,
        },
    }


def _apply_with_budget(
    envelope: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    stage_id = str(result.get("stage", "")).strip()
    original_status = str(result.get("status", "")).strip()

    # Preserve an upstream provider/policy failure as the primary cause. A failed
    # provider is not required to manufacture usage telemetry after failure.
    if original_status in {"failed", "blocked"}:
        guarded = dict(result)
        guarded["budget"] = {
            "schema_version": 1,
            "stage": stage_id,
            "decision": "not-evaluated",
            "reason": f"stage already {original_status} before budget evaluation",
            "usage": dict(envelope.get("budget_usage", BUDGET.initial_usage())),
            "violations": [],
            "constraints": [],
        }
        return ENV.apply_stage_result(envelope, guarded)

    policy = envelope["budget_policy"]
    decision = BUDGET.evaluate(
        envelope["budgets"],
        envelope.get("budget_usage"),
        stage_id,
        result.get("metrics", {}),
        required_metrics=STRICT_BUDGET_METRICS.get(stage_id, []),
        strict=policy["strict"],
        allow_truncation=policy["allow_truncation"],
    )

    guarded = dict(result)
    guarded["budget"] = decision
    guarded["constraints"] = sorted(set(
        list(result.get("constraints", [])) + decision["constraints"]
    ))

    if decision["decision"] == "block":
        guarded["status"] = "blocked"
        guarded["error"] = "; ".join(decision["violations"])
        guarded["constraints"] = sorted(set(
            guarded["constraints"] + decision["violations"]
        ))
    elif decision["decision"] == "allow-with-constraints":
        if guarded.get("status") == "passed":
            guarded["status"] = "passed-with-constraints"

    updated = ENV.apply_stage_result(envelope, guarded)
    updated["budget_usage"] = decision["usage"]
    return updated


def promotion_package(envelope: dict[str, Any]) -> dict[str, Any]:
    cross = envelope["cross_cutting"]
    target = envelope["target"]
    l0 = next(s for s in envelope["stages"] if s["id"] == "L0-intake")
    l6 = next(s for s in envelope["stages"] if s["id"] == "L6-reverse-engineering")

    provenance_evidence = l0["evidence"]
    lab_evidence = [
        evidence
        for stage in envelope["stages"]
        if stage["status"] in {"passed", "passed-with-constraints"}
        for evidence in stage["evidence"]
    ]

    return {
        "schema_version": 1,
        "candidate": {
            "name": envelope["request"]["purpose"],
            "source": target["repository_id"],
            "revision": target["revision"],
            "integration_mode": "internal-component",
        },
        "checks": {
            "provenance": {
                "status": "verified" if provenance_evidence else "pending",
                "evidence": provenance_evidence,
            },
            "license": cross["license"],
            "security": cross["security"],
            "lab": {
                "status": "passed" if l6["status"] in {"passed", "passed-with-constraints"} else "pending",
                "evidence": lab_evidence,
            },
            "capability_delta": cross["capability_delta"],
            "rollback": cross["rollback"],
            "private_data": cross["private_data"],
            "verifier": cross["verifier"],
        },
        "constraints": sorted({
            constraint
            for stage in envelope["stages"]
            for constraint in stage.get("constraints", [])
        }),
    }


def run(manifest: Path, stage_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_data = _load(manifest)
    envelope = ENV.new_envelope(manifest_data)
    routing = _provider_routing(manifest_data, envelope)
    routes = _route_map(routing)
    run_plan = plan(envelope, routing)

    for stage in envelope["stages"]:
        if stage["status"] == "skipped":
            continue

        route = routes.get(stage["id"])
        if route is not None and route["decision"] == "blocked":
            blocked = {
                "stage": stage["id"],
                "status": "blocked",
                "provider": None,
                "provider_route": route,
                "evidence": route["evidence"],
                "artifacts": [],
                "metrics": {},
                "constraints": route["blockers"],
                "error": "; ".join(route["blockers"]),
            }
            envelope = _apply_with_budget(envelope, blocked)
            break

        result_path = stage_dir / f"{stage['id']}.json"
        if not result_path.exists():
            break
        result = _load(result_path)
        if result.get("stage") != stage["id"]:
            raise ValueError(f"{result_path}: stage ID mismatch")

        if route is not None:
            selected = route["selected_provider"]
            actual = str(result.get("provider", "")).strip()
            if actual != selected:
                mismatch = {
                    "stage": stage["id"],
                    "status": "blocked",
                    "provider": actual or None,
                    "provider_route": route,
                    "evidence": list(route["evidence"]),
                    "artifacts": [],
                    "metrics": {},
                    "constraints": [
                        f"stage provider does not match routed provider: {actual or '<missing>'} != {selected}"
                    ],
                    "error": "provider routing mismatch",
                }
                envelope = _apply_with_budget(envelope, mismatch)
                break
            result = dict(result)
            result["provider_route"] = route
            result["evidence"] = sorted(set(
                list(result.get("evidence", [])) + list(route["evidence"])
            ))
            result["constraints"] = sorted(set(
                list(result.get("constraints", [])) + list(route["constraints"])
            ))
            if route["fallback_used"] and result.get("status") == "passed":
                result["status"] = "passed-with-constraints"

        envelope = _apply_with_budget(envelope, result)
        if envelope["status"] in {"failed", "blocked"}:
            break

    l7 = next(s for s in envelope["stages"] if s["id"] == "L7-promotion")
    pre_l7 = [
        s for s in envelope["stages"]
        if s["id"] != "L7-promotion" and s["status"] != "skipped"
    ]
    if all(s["status"] in {"passed", "passed-with-constraints"} for s in pre_l7):
        l7_route = routes.get("L7-promotion")
        if l7_route is not None and l7_route["decision"] == "blocked":
            envelope = _apply_with_budget(envelope, {
                "stage": "L7-promotion",
                "status": "blocked",
                "provider": None,
                "provider_route": l7_route,
                "evidence": l7_route["evidence"],
                "artifacts": [],
                "metrics": {},
                "constraints": l7_route["blockers"],
                "error": "; ".join(l7_route["blockers"]),
            })
        else:
            package = promotion_package(envelope)
            decision = PROMOTION.evaluate(package)
            selected_provider = (
                l7_route["selected_provider"]
                if l7_route is not None
                else PROVIDERS["L7-promotion"]
            )
            route_evidence = list(l7_route["evidence"]) if l7_route is not None else []
            route_constraints = list(l7_route["constraints"]) if l7_route is not None else []
            l7_result = {
                "stage": "L7-promotion",
                "status": (
                    "passed-with-constraints"
                    if decision["decision"] == "eligible-with-constraints" or route_constraints
                    else "passed"
                    if decision["decision"] == "eligible-for-parent-promotion"
                    else "blocked"
                ),
                "provider": selected_provider,
                "provider_route": l7_route,
                "evidence": sorted(set([
                    f"promotion-decision:{decision['decision']}",
                    "machine-gate:auto-promote=false",
                ] + route_evidence)),
                "artifacts": [],
                "metrics": {},
                "constraints": sorted(set(decision["constraints"] + route_constraints)),
                "error": None if decision["decision"] in PROMOTION.FINAL_ELIGIBLE else "; ".join(decision["reasons"]),
            }
            envelope = _apply_with_budget(envelope, l7_result)
            envelope["promotion"] = decision

    ENV.validate_envelope(envelope)
    return run_plan, envelope


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--stage-dir", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--envelope", type=Path, required=True)
    parser.add_argument("--require-parent-review", action="store_true")
    args = parser.parse_args()

    run_plan, envelope = run(args.manifest, args.stage_dir)
    args.plan.parent.mkdir(parents=True, exist_ok=True)
    args.envelope.parent.mkdir(parents=True, exist_ok=True)
    args.plan.write_text(json.dumps(run_plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.envelope.write_text(ENV.canonical_json(envelope), encoding="utf-8")

    if args.require_parent_review and envelope["status"] != "ready-for-parent-review":
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
