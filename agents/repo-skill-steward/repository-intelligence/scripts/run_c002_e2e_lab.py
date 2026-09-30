#!/usr/bin/env python3
"""Realistic C002 end-to-end Repository Intelligence integration lab."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


REG = _load_module("c002_e2e_registry", "multi_repo_registry.py")
FLOW = _load_module("c002_e2e_flow", "process_flow_synthesis.py")
IMPACT = _load_module("c002_e2e_impact", "diff_impact_normalize.py")
CACHE = _load_module("c002_e2e_cache", "incremental_cache.py")
ORCH = _load_module("c002_e2e_orchestrator", "orchestrate_repository_intelligence.py")


def _sha(payload: Any) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def workspace() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "workspace_id": "c002-e2e-commerce",
        "repositories": [
            {
                "repository_id": "web",
                "visibility": "local-fixture",
                "source": "fixture/web",
                "revision": "web-1",
                "requires": [
                    {
                        "key": "http.checkout.v1",
                        "kind": "http-api",
                        "version": "1.0.0",
                        "provider_hint": "api",
                        "state": "observed",
                        "evidence": ["web:http-client"],
                    }
                ],
            },
            {
                "repository_id": "api",
                "visibility": "local-fixture",
                "source": "fixture/api",
                "revision": "api-1",
                "provides": [
                    {
                        "key": "http.checkout.v1",
                        "kind": "http-api",
                        "version": "1.0.0",
                        "state": "observed",
                        "evidence": ["api:openapi"],
                    },
                    {
                        "key": "event.order.created",
                        "kind": "event",
                        "version": "1.0.0",
                        "state": "observed",
                        "evidence": ["api:event-publisher"],
                    },
                ],
                "requires": [
                    {
                        "key": "schema.checkout.v1",
                        "kind": "schema",
                        "version": "1.0.0",
                        "provider_hint": "contracts",
                        "state": "observed",
                        "evidence": ["api:schema-import"],
                    }
                ],
            },
            {
                "repository_id": "contracts",
                "visibility": "local-fixture",
                "source": "fixture/contracts",
                "revision": "contracts-1",
                "provides": [
                    {
                        "key": "schema.checkout.v1",
                        "kind": "schema",
                        "version": "1.0.0",
                        "state": "observed",
                        "evidence": ["contracts:checkout-schema"],
                    }
                ],
            },
            {
                "repository_id": "repo_worker_01",
                "visibility": "private",
                "source": "secret-owner/private-payments-worker",
                "revision": "worker-1",
                "requires": [
                    {
                        "key": "event.order.created",
                        "kind": "event",
                        "version": "1.0.0",
                        "provider_hint": "api",
                        "state": "observed",
                        "evidence": ["worker:event-consumer"],
                    }
                ],
            },
        ],
    }


def flow_observations(contracts: dict[str, Any]) -> dict[str, Any]:
    http_id = next(c["contract_id"] for c in contracts["contracts"] if c["kind"] == "http-api")
    event_id = next(c["contract_id"] for c in contracts["contracts"] if c["kind"] == "event")
    return {
        "schema_version": 1,
        "workspace_id": "c002-e2e-commerce",
        "budgets": {"max_hops": 16, "max_paths": 20},
        "steps": [
            {"step_id": "web.submit", "repository_id": "web", "label": "Submit checkout", "symbol": "submitCheckout", "kind": "entry", "entry": True, "state": "observed", "evidence": ["web:submit-handler"]},
            {"step_id": "web.http", "repository_id": "web", "label": "Checkout client", "symbol": "postCheckout", "kind": "http-client", "state": "observed", "evidence": ["web:http-client"]},
            {"step_id": "api.handle", "repository_id": "api", "label": "Checkout handler", "symbol": "handle_checkout", "kind": "http-handler", "state": "observed", "evidence": ["api:route"]},
            {"step_id": "api.publish", "repository_id": "api", "label": "Publish order event", "symbol": "publish_order_created", "kind": "event-publisher", "state": "observed", "evidence": ["api:publisher"]},
            {"step_id": "worker.consume", "repository_id": "repo_worker_01", "label": "Consume order event", "symbol": "consume_order_created", "kind": "event-consumer", "state": "observed", "evidence": ["worker:consumer"]},
            {"step_id": "worker.persist", "repository_id": "repo_worker_01", "label": "Persist payment", "symbol": "persist_payment", "kind": "storage-write", "terminal": True, "state": "observed", "evidence": ["worker:persist"]},
        ],
        "edges": [
            {"from": "web.submit", "to": "web.http", "relation": "calls", "state": "observed", "evidence": ["web:call-graph"]},
            {"from": "api.handle", "to": "api.publish", "relation": "publishes", "state": "observed", "evidence": ["api:call-graph"]},
            {"from": "worker.consume", "to": "worker.persist", "relation": "writes", "state": "observed", "evidence": ["worker:call-graph"]},
        ],
        "bindings": [
            {"contract_id": http_id, "provider_step": "api.handle", "consumer_step": "web.http", "flow_direction": "consumer-to-provider", "state": "observed", "evidence": ["binding:http"]},
            {"contract_id": event_id, "provider_step": "api.publish", "consumer_step": "worker.consume", "flow_direction": "provider-to-consumer", "state": "observed", "evidence": ["binding:event"]},
        ],
    }


def change_observations(contracts: dict[str, Any]) -> dict[str, Any]:
    event_id = next(c["contract_id"] for c in contracts["contracts"] if c["kind"] == "event")
    return {
        "schema_version": 1,
        "workspace_id": "c002-e2e-commerce",
        "changes": [
            {
                "change_id": "api-event-change",
                "repository_id": "api",
                "change_type": "modify",
                "surface_kind": "symbol",
                "identifier": "publish_order_created",
                "contract_ids": [event_id],
                "state": "observed",
                "evidence": ["git:diff:api"],
                "local_impact": {
                    "provider": "codegraph-0.20.1",
                    "symbols": ["publish_order_created"],
                    "files": ["api/orders.py"],
                    "tests": ["test_order_event"],
                    "evidence": ["codegraph:impact"],
                    "summary": {"filesAffected": 2, "breakingChanges": 0, "warnings": 1},
                },
            }
        ],
    }


def provider_health() -> dict[str, Any]:
    providers = [
        ("sazan-intake", "healthy"),
        ("repomix", "unhealthy"),
        ("gitingest", "healthy"),
        ("codegraph-0.20.1", "healthy"),
        ("sazan-mermaid-renderer", "healthy"),
        ("sazan-lightweight-wiki-qa", "healthy"),
        ("sazan-rebuild-spec", "healthy"),
        ("sazan-promotion-gate", "healthy"),
    ]
    return {
        "schema_version": 1,
        "providers": [
            {"provider": provider, "status": status, "evidence": [f"health:{provider}:{status}"]}
            for provider, status in providers
        ],
    }


def _stage(stage_id: str, provider: str, *, metrics: dict[str, Any], evidence: list[str], artifacts: list[str] | None = None, cross: dict[str, Any] | None = None) -> dict[str, Any]:
    out = {
        "stage": stage_id,
        "status": "passed",
        "provider": provider,
        "evidence": evidence,
        "artifacts": artifacts or [],
        "metrics": metrics,
        "constraints": [],
    }
    if cross:
        out["cross_cutting"] = cross
    return out


def cache_descriptor(revision: str, registry: dict[str, Any], contracts: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "repository_id": "api",
        "revision": revision,
        "stage": "L2-semantic-graph",
        "provider": "codegraph-0.20.1",
        "provider_version": "0.20.1",
        "provider_contract": "semantic-graph-v1",
        "stage_input_fingerprint": _sha({"registry": registry, "contracts": contracts}),
        "policy_fingerprint": _sha({"context": "C002", "privacy": "redact-private-source"}),
        "implementation_fingerprint": _sha({"provider": "codegraph-0.20.1", "normalizer": "c002"}),
        "dependencies": [
            {"name": "contracts", "fingerprint": _sha(contracts)},
            {"name": "provider-route", "fingerprint": _sha(provider_health())},
        ],
        "reuse_policy": "fingerprint-stable-cross-revision",
    }


def run_lab() -> dict[str, Any]:
    registry, contracts = REG.build(workspace())
    flows = FLOW.synthesize(registry, contracts, flow_observations(contracts))
    impact = IMPACT.normalize(registry, contracts, flows, change_observations(contracts))

    cache_before = cache_descriptor("api-1", registry, contracts)
    cache_entry = CACHE.create_entry(
        cache_before,
        _sha(impact),
        artifacts=[{"name": "impact-report", "fingerprint": _sha(impact)}],
        evidence=["c002-e2e:impact-normalized"],
    )
    cache_report = CACHE.evaluate(
        cache_entry,
        cache_descriptor("api-2", registry, contracts),
    )

    manifest = {
        "run_id": "c002-e2e-001",
        "purpose": "realistic c002 end-to-end repository intelligence lab",
        "mode": "analysis",
        "target": {
            "source": "fixture/api",
            "revision": "api-2",
            "visibility": "local-fixture",
        },
        "privacy": {"persist_private_identity": False},
        "budgets": {
            "max_context_tokens": 20000,
            "max_graph_nodes": 500,
            "max_output_bytes": 50000,
            "stage_timeout_seconds": 5,
        },
        "budget_policy": {"strict": True, "allow_truncation": False},
        "provider_policy": {"strict": True, "allow_degraded": False},
        "provider_health": provider_health(),
    }

    cross = {
        "license": {"status": "compatible", "evidence": ["fixture:license-compatible"]},
        "security": {"status": "passed", "evidence": ["fixture:security-passed"]},
        "capability_delta": {"status": "new", "evidence": ["fixture:capability-delta"]},
        "rollback": {"status": "verified", "evidence": ["fixture:rollback"]},
        "private_data": {"status": "compliant", "evidence": ["fixture:private-redaction"]},
        "verifier": {"status": "verified", "evidence": ["fixture:verifier"]},
    }
    stages = [
        _stage("L0-intake", "sazan-intake", metrics={"output_bytes": 900, "elapsed_seconds": 0.1}, evidence=["e2e:intake"], artifacts=["registry.json"], cross=cross),
        _stage("L1-context-packaging", "gitingest", metrics={"context_tokens": 1800, "context_token_method": "provider-reported", "output_bytes": 4000, "elapsed_seconds": 0.2}, evidence=["e2e:context"], artifacts=["context.txt"]),
        _stage("L2-semantic-graph", "codegraph-0.20.1", metrics={"graph_nodes": 80, "output_bytes": 5000, "elapsed_seconds": 0.3}, evidence=["e2e:semantic-graph"], artifacts=["semantic-graph.json"]),
        _stage("L3-architecture-presentation", "sazan-mermaid-renderer", metrics={"output_bytes": 2000, "elapsed_seconds": 0.1}, evidence=["e2e:architecture"], artifacts=["architecture.mmd"]),
        _stage("L4-wiki-qa", "sazan-lightweight-wiki-qa", metrics={"context_tokens": 1200, "context_token_method": "provider-reported", "output_bytes": 3000, "elapsed_seconds": 0.2}, evidence=["e2e:wiki-qa"], artifacts=["wiki-qa.json"]),
        _stage("L6-reverse-engineering", "sazan-rebuild-spec", metrics={"context_tokens": 900, "context_token_method": "provider-reported", "output_bytes": 2500, "elapsed_seconds": 0.2}, evidence=["e2e:reverse-engineering", "e2e:cross-repository-impact"], artifacts=["rebuild-spec.md", "impact-report.json"]),
    ]

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        manifest_path = root / "manifest.json"
        stage_dir = root / "stages"
        stage_dir.mkdir()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        for result in stages:
            (stage_dir / f"{result['stage']}.json").write_text(json.dumps(result), encoding="utf-8")
        plan, envelope = ORCH.run(manifest_path, stage_dir)

    l1 = next(stage for stage in envelope["stages"] if stage["id"] == "L1-context-packaging")
    persisted = json.dumps(
        {
            "registry": registry,
            "contracts": contracts,
            "flows": flows,
            "impact": impact,
            "cache": cache_report,
            "plan": plan,
            "envelope": envelope,
        },
        sort_keys=True,
    )
    privacy_safe = "secret-owner" not in persisted and "private-payments-worker" not in persisted

    checks = {
        "multi_repo_verified": contracts["status"] == "verified",
        "contracts_matched": contracts["summary"]["matched_contracts"] == 3,
        "flow_verified": flows["status"] == "verified" and flows["summary"]["flows"] == 1,
        "diff_impact_high": impact["impact_level"] == "high",
        "cache_cross_revision_hit": cache_report["decision"] == "hit" and cache_report["cross_revision_reuse"],
        "provider_fallback_exercised": bool(l1.get("provider_route", {}).get("fallback_used")) and l1["provider"] == "gitingest",
        "strict_budget_measured": envelope["budget_usage"]["stages_measured"] >= 6,
        "promotion_ready_for_parent_review": envelope["status"] == "ready-for-parent-review",
        "no_auto_promotion": envelope["promotion"] is not None and envelope["promotion"]["auto_promote"] is False,
        "private_identity_redacted": privacy_safe,
    }

    return {
        "schema_version": 1,
        "context": "C002",
        "lab": "realistic-end-to-end-integration",
        "status": "verified" if all(checks.values()) else "failed",
        "checks": checks,
        "summary": {
            "repositories": len(registry["repositories"]),
            "matched_contracts": contracts["summary"]["matched_contracts"],
            "flows": flows["summary"]["flows"],
            "impact_level": impact["impact_level"],
            "review_repositories": impact["blast_radius"]["repositories"],
            "provider_fallback": {
                "stage": "L1-context-packaging",
                "selected_provider": l1["provider"],
                "fallback_used": l1["provider_route"]["fallback_used"],
            },
            "cache": {
                "decision": cache_report["decision"],
                "cross_revision_reuse": cache_report["cross_revision_reuse"],
            },
            "orchestration": {
                "status": envelope["status"],
                "promotion_decision": envelope["promotion"]["decision"] if envelope["promotion"] else None,
                "budget_usage": envelope["budget_usage"],
            },
        },
        "fingerprints": {
            "registry": _sha(registry),
            "contracts": _sha(contracts),
            "flows": _sha(flows),
            "impact": _sha(impact),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-verified", action="store_true")
    args = parser.parse_args()

    report = run_lab()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.require_verified and report["status"] != "verified":
        return 12
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
