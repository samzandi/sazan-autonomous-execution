#!/usr/bin/env python3
"""Common evidence-envelope primitives for Sazan Repository Intelligence C002."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any


SCHEMA_VERSION = 1
STAGE_ORDER = [
    "L0-intake",
    "L1-context-packaging",
    "L2-semantic-graph",
    "L3-architecture-presentation",
    "L4-wiki-qa",
    "L5-semantic-editing",
    "L6-reverse-engineering",
    "L7-promotion",
]
STAGE_STATES = {"pending", "running", "passed", "passed-with-constraints", "skipped", "blocked", "failed"}
RUN_STATES = {"planned", "running", "blocked", "failed", "ready-for-parent-review", "complete"}


def _text(value: Any, name: str) -> str:
    out = str(value or "").strip()
    if not out:
        raise ValueError(f"{name} is required")
    return out


def private_safe_repository_id(source: str, revision: str) -> str:
    material = f"{source}\0{revision}".encode("utf-8")
    return "repo_" + hashlib.sha256(material).hexdigest()[:16]


def new_envelope(manifest: dict[str, Any]) -> dict[str, Any]:
    target = manifest.get("target")
    if not isinstance(target, dict):
        raise ValueError("target must be an object")

    revision = _text(target.get("revision"), "target.revision")
    visibility = _text(target.get("visibility"), "target.visibility")
    source = _text(target.get("source"), "target.source")
    if visibility not in {"public", "private", "internal", "local-fixture"}:
        raise ValueError("unsupported target.visibility")

    persist_private_identity = bool(
        manifest.get("privacy", {}).get("persist_private_identity", False)
        if isinstance(manifest.get("privacy"), dict)
        else False
    )
    if visibility in {"private", "internal"} and persist_private_identity:
        raise ValueError("private/internal repository identity persistence is forbidden")

    repository_id = (
        source
        if visibility in {"public", "local-fixture"}
        else private_safe_repository_id(source, revision)
    )

    mode = _text(manifest.get("mode", "analysis"), "mode")
    if mode not in {"analysis", "analysis-and-edit"}:
        raise ValueError("mode must be analysis or analysis-and-edit")

    budgets = manifest.get("budgets", {})
    if not isinstance(budgets, dict):
        raise ValueError("budgets must be an object")
    normalized_budgets = {
        "max_context_tokens": int(budgets.get("max_context_tokens", 120000)),
        "max_graph_nodes": int(budgets.get("max_graph_nodes", 5000)),
        "max_output_bytes": int(budgets.get("max_output_bytes", 5_000_000)),
        "stage_timeout_seconds": int(budgets.get("stage_timeout_seconds", 900)),
    }
    if any(v <= 0 for v in normalized_budgets.values()):
        raise ValueError("all budgets must be positive")

    stages = []
    for stage_id in STAGE_ORDER:
        optional = stage_id == "L5-semantic-editing" and mode == "analysis"
        stages.append({
            "id": stage_id,
            "status": "skipped" if optional else "pending",
            "provider": None,
            "evidence": [],
            "artifacts": [],
            "metrics": {},
            "constraints": [],
            "error": None,
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "context": "C002",
        "run_id": _text(manifest.get("run_id"), "run_id"),
        "status": "planned",
        "target": {
            "repository_id": repository_id,
            "revision": revision,
            "visibility": visibility,
            "identity_persisted": visibility in {"public", "local-fixture"},
        },
        "request": {
            "purpose": _text(manifest.get("purpose"), "purpose"),
            "mode": mode,
        },
        "privacy": {
            "persist_private_identity": False,
        },
        "budgets": normalized_budgets,
        "budget_usage": {
            "context_tokens": 0,
            "graph_nodes": 0,
            "output_bytes": 0,
            "stages_measured": 0,
            "last_stage_elapsed_seconds": None,
        },
        "stages": stages,
        "cross_cutting": {
            "license": {"status": "pending", "evidence": []},
            "security": {"status": "pending", "evidence": []},
            "capability_delta": {"status": "pending", "evidence": []},
            "rollback": {"status": "pending", "evidence": []},
            "private_data": {"status": "pending", "evidence": []},
            "verifier": {"status": "pending-evidence", "evidence": []},
        },
        "promotion": None,
    }


def apply_stage_result(envelope: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(envelope)
    stage_id = _text(result.get("stage"), "stage")
    stage = next((s for s in out["stages"] if s["id"] == stage_id), None)
    if stage is None:
        raise ValueError(f"unknown stage: {stage_id}")

    status = _text(result.get("status"), "status")
    if status not in STAGE_STATES - {"pending", "running"}:
        raise ValueError(f"invalid terminal stage status: {status}")

    prior = out["stages"][: out["stages"].index(stage)]
    incomplete = [
        x["id"]
        for x in prior
        if x["status"] not in {"passed", "passed-with-constraints", "skipped"}
    ]
    if incomplete:
        raise ValueError(f"cannot complete {stage_id} before prior stages: {', '.join(incomplete)}")

    evidence = result.get("evidence", [])
    artifacts = result.get("artifacts", [])
    metrics = result.get("metrics", {})
    constraints = result.get("constraints", [])
    if not isinstance(evidence, list) or not isinstance(artifacts, list) or not isinstance(constraints, list):
        raise ValueError("evidence, artifacts, and constraints must be lists")
    if not isinstance(metrics, dict):
        raise ValueError("metrics must be an object")

    if status in {"passed", "passed-with-constraints"} and not evidence:
        raise ValueError(f"{stage_id}: passed stage requires evidence")
    if status == "passed-with-constraints" and not constraints:
        raise ValueError(f"{stage_id}: constrained pass requires constraints")

    stage.update({
        "status": status,
        "provider": result.get("provider"),
        "evidence": evidence,
        "artifacts": artifacts,
        "metrics": metrics,
        "constraints": constraints,
        "error": result.get("error"),
    })

    cross = result.get("cross_cutting")
    if cross is not None:
        if not isinstance(cross, dict):
            raise ValueError("cross_cutting must be an object")
        for key, value in cross.items():
            if key not in out["cross_cutting"]:
                raise ValueError(f"unknown cross-cutting gate: {key}")
            if not isinstance(value, dict):
                raise ValueError(f"cross_cutting.{key} must be an object")
            out["cross_cutting"][key] = value

    terminal = [s["status"] for s in out["stages"]]
    if "failed" in terminal:
        out["status"] = "failed"
    elif "blocked" in terminal:
        out["status"] = "blocked"
    elif all(s in {"passed", "passed-with-constraints", "skipped"} for s in terminal):
        out["status"] = "ready-for-parent-review"
    else:
        out["status"] = "running"
    return out


def validate_envelope(envelope: dict[str, Any]) -> None:
    if envelope.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported evidence envelope schema version")
    if envelope.get("status") not in RUN_STATES:
        raise ValueError("invalid run status")
    usage = envelope.get("budget_usage")
    if not isinstance(usage, dict):
        raise ValueError("budget_usage must be an object")
    required_usage = {
        "context_tokens",
        "graph_nodes",
        "output_bytes",
        "stages_measured",
        "last_stage_elapsed_seconds",
    }
    if set(usage) != required_usage:
        raise ValueError("budget_usage does not match C002 contract")
    stages = envelope.get("stages")
    if not isinstance(stages, list):
        raise ValueError("stages must be a list")
    if [s.get("id") for s in stages] != STAGE_ORDER:
        raise ValueError("stage order does not match C002 contract")
    if envelope.get("target", {}).get("visibility") in {"private", "internal"}:
        if envelope.get("target", {}).get("identity_persisted"):
            raise ValueError("private/internal identity must not be persisted")


def canonical_json(envelope: dict[str, Any]) -> str:
    validate_envelope(envelope)
    return json.dumps(envelope, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
