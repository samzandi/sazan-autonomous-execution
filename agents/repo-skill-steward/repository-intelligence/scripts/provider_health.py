#!/usr/bin/env python3
"""Evidence-backed provider health and fallback routing for C002."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
HEALTH_STATES = {"healthy", "degraded", "unhealthy", "unknown"}

DEFAULT_ROUTES = {
    "L0-intake": [
        {"provider": "sazan-intake", "contract": "intake-v1", "private_safe": True},
    ],
    "L1-context-packaging": [
        {"provider": "repomix", "contract": "context-packaging-v1", "private_safe": True},
        {"provider": "gitingest", "contract": "context-packaging-v1", "private_safe": True},
    ],
    "L2-semantic-graph": [
        {"provider": "codegraph-0.20.1", "contract": "semantic-graph-v1", "private_safe": True},
    ],
    "L3-architecture-presentation": [
        {"provider": "sazan-mermaid-renderer", "contract": "architecture-presentation-v1", "private_safe": True},
    ],
    "L4-wiki-qa": [
        {"provider": "sazan-lightweight-wiki-qa", "contract": "wiki-qa-v1", "private_safe": True},
    ],
    "L5-semantic-editing": [
        {"provider": "serena-1.7.0-isolated", "contract": "semantic-editing-v1", "private_safe": True},
    ],
    "L6-reverse-engineering": [
        {"provider": "sazan-rebuild-spec", "contract": "reverse-engineering-v1", "private_safe": True},
    ],
    "L7-promotion": [
        {"provider": "sazan-promotion-gate", "contract": "promotion-gate-v1", "private_safe": True},
    ],
}


def _text(value: Any, name: str) -> str:
    out = str(value or "").strip()
    if not out:
        raise ValueError(f"{name} is required")
    return out


def normalize_health(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("provider_health must be an object")
    if payload.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
        raise ValueError("provider_health.schema_version must be 1")
    raw = payload.get("providers")
    if not isinstance(raw, list):
        raise ValueError("provider_health.providers must be a list")

    providers: dict[str, dict[str, Any]] = {}
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"providers[{i}] must be an object")
        provider_id = _text(item.get("provider"), f"providers[{i}].provider")
        if provider_id in providers:
            raise ValueError(f"duplicate provider observation: {provider_id}")
        status = _text(item.get("status"), f"providers[{i}].status")
        if status not in HEALTH_STATES:
            raise ValueError(f"{provider_id}: unsupported health status {status}")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence or not all(
            isinstance(x, str) and x.strip() for x in evidence
        ):
            raise ValueError(f"{provider_id}: health evidence is required")
        providers[provider_id] = {
            "provider": provider_id,
            "status": status,
            "evidence": sorted(set(x.strip() for x in evidence)),
            "reason": str(item.get("reason", "")).strip() or None,
        }
    return providers


def _candidate_reason(
    candidate: dict[str, Any],
    observations: dict[str, dict[str, Any]],
    *,
    required_contract: str,
    private_target: bool,
    allow_degraded: bool,
) -> tuple[bool, str, list[str]]:
    provider = _text(candidate.get("provider"), "candidate.provider")
    contract = _text(candidate.get("contract"), f"{provider}.contract")
    if contract != required_contract:
        return False, f"contract mismatch: {contract} != {required_contract}", []
    if private_target and not bool(candidate.get("private_safe", False)):
        return False, "provider is not approved for private/internal targets", []

    obs = observations.get(provider)
    if obs is None:
        return False, "no health observation", []
    status = obs["status"]
    if status == "healthy":
        return True, "healthy", obs["evidence"]
    if status == "degraded" and allow_degraded:
        return True, "degraded health explicitly allowed", obs["evidence"]
    return False, f"health status is {status}", obs["evidence"]


def route_stage(
    stage_id: str,
    health_payload: dict[str, Any],
    *,
    visibility: str = "public",
    routes: dict[str, list[dict[str, Any]]] | None = None,
    allow_degraded: bool = False,
) -> dict[str, Any]:
    stage_id = _text(stage_id, "stage_id")
    routing = routes or DEFAULT_ROUTES
    candidates = routing.get(stage_id)
    if not candidates:
        raise ValueError(f"no provider route configured for {stage_id}")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError(f"{stage_id}: provider route must contain candidates")

    observations = normalize_health(health_payload)
    primary_contract = _text(candidates[0].get("contract"), f"{stage_id}.primary.contract")
    private_target = visibility in {"private", "internal"}

    attempts = []
    selected = None
    selected_index = None
    selected_evidence: list[str] = []

    for index, candidate in enumerate(candidates):
        provider = _text(candidate.get("provider"), f"{stage_id}.candidate.provider")
        eligible, reason, evidence = _candidate_reason(
            candidate,
            observations,
            required_contract=primary_contract,
            private_target=private_target,
            allow_degraded=allow_degraded,
        )
        attempts.append({
            "provider": provider,
            "eligible": eligible,
            "reason": reason,
            "evidence": evidence,
        })
        if eligible and selected is None:
            selected = provider
            selected_index = index
            selected_evidence = evidence

    if selected is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "stage": stage_id,
            "decision": "blocked",
            "selected_provider": None,
            "primary_provider": _text(candidates[0].get("provider"), "primary.provider"),
            "fallback_used": False,
            "contract": primary_contract,
            "attempts": attempts,
            "evidence": sorted({e for a in attempts for e in a["evidence"]}),
            "constraints": [],
            "blockers": ["no eligible healthy provider for stage contract"],
        }

    fallback_used = bool(selected_index)
    constraints = []
    if fallback_used:
        constraints.append(
            f"provider fallback used: {_text(candidates[0].get('provider'), 'primary.provider')} -> {selected}"
        )
    if observations[selected]["status"] == "degraded":
        constraints.append(f"selected provider health is degraded: {selected}")

    return {
        "schema_version": SCHEMA_VERSION,
        "stage": stage_id,
        "decision": "fallback" if fallback_used else "primary",
        "selected_provider": selected,
        "primary_provider": _text(candidates[0].get("provider"), "primary.provider"),
        "fallback_used": fallback_used,
        "contract": primary_contract,
        "attempts": attempts,
        "evidence": sorted(set(selected_evidence)),
        "constraints": constraints,
        "blockers": [],
    }


def route_pipeline(
    health_payload: dict[str, Any],
    *,
    visibility: str = "public",
    stages: list[str] | None = None,
    routes: dict[str, list[dict[str, Any]]] | None = None,
    allow_degraded: bool = False,
) -> dict[str, Any]:
    routing = routes or DEFAULT_ROUTES
    stage_ids = stages or list(routing)
    decisions = [
        route_stage(
            stage_id,
            health_payload,
            visibility=visibility,
            routes=routing,
            allow_degraded=allow_degraded,
        )
        for stage_id in stage_ids
    ]
    blocked = [d["stage"] for d in decisions if d["decision"] == "blocked"]
    fallbacks = [d["stage"] for d in decisions if d["fallback_used"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "blocked" if blocked else "routable",
        "visibility": visibility,
        "stages": decisions,
        "summary": {
            "stages": len(decisions),
            "blocked": len(blocked),
            "fallbacks": len(fallbacks),
        },
        "blocked_stages": blocked,
        "fallback_stages": fallbacks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("health", type=Path)
    parser.add_argument("--visibility", default="public")
    parser.add_argument("--stage", action="append", default=[])
    parser.add_argument("--allow-degraded", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-routable", action="store_true")
    args = parser.parse_args()

    health = json.loads(args.health.read_text(encoding="utf-8"))
    report = route_pipeline(
        health,
        visibility=args.visibility,
        stages=args.stage or None,
        allow_degraded=args.allow_degraded,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.require_routable and report["status"] != "routable":
        return 9
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
