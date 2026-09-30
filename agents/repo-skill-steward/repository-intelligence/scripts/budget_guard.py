#!/usr/bin/env python3
"""Deterministic fail-closed budget enforcement for C002 Repository Intelligence."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


BUDGET_KEYS = {
    "context_tokens": "max_context_tokens",
    "graph_nodes": "max_graph_nodes",
    "output_bytes": "max_output_bytes",
    "elapsed_seconds": "stage_timeout_seconds",
}
INTEGER_METRICS = {"context_tokens", "graph_nodes", "output_bytes"}
TOKEN_METHODS = {
    "provider-reported",
    "exact-tokenizer",
    "utf8-byte-upper-bound",
}


def initial_usage() -> dict[str, Any]:
    return {
        "context_tokens": 0,
        "graph_nodes": 0,
        "output_bytes": 0,
        "stages_measured": 0,
        "last_stage_elapsed_seconds": None,
    }


def _number(value: Any, name: str, *, integer: bool) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a non-negative {'integer' if integer else 'number'}")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    if integer:
        if isinstance(value, float) and not value.is_integer():
            raise ValueError(f"{name} must be a non-negative integer")
        return int(value)
    return float(value)


def validate_budgets(budgets: dict[str, Any]) -> dict[str, int]:
    if not isinstance(budgets, dict):
        raise ValueError("budgets must be an object")
    required = set(BUDGET_KEYS.values())
    missing = sorted(required - set(budgets))
    if missing:
        raise ValueError(f"missing budgets: {', '.join(missing)}")
    out: dict[str, int] = {}
    for key in sorted(required):
        value = int(_number(budgets[key], f"budgets.{key}", integer=True))
        if value <= 0:
            raise ValueError(f"budgets.{key} must be positive")
        out[key] = value
    return out


def normalize_usage(usage: dict[str, Any] | None) -> dict[str, Any]:
    current = initial_usage()
    if usage is not None:
        if not isinstance(usage, dict):
            raise ValueError("usage must be an object")
        for key in current:
            if key in usage:
                current[key] = deepcopy(usage[key])

    current["context_tokens"] = int(_number(current["context_tokens"], "usage.context_tokens", integer=True))
    current["graph_nodes"] = int(_number(current["graph_nodes"], "usage.graph_nodes", integer=True))
    current["output_bytes"] = int(_number(current["output_bytes"], "usage.output_bytes", integer=True))
    current["stages_measured"] = int(_number(current["stages_measured"], "usage.stages_measured", integer=True))
    if current["last_stage_elapsed_seconds"] is not None:
        current["last_stage_elapsed_seconds"] = float(_number(
            current["last_stage_elapsed_seconds"],
            "usage.last_stage_elapsed_seconds",
            integer=False,
        ))
    return current


def normalize_metrics(metrics: dict[str, Any] | None) -> dict[str, Any]:
    if metrics is None:
        metrics = {}
    if not isinstance(metrics, dict):
        raise ValueError("metrics must be an object")

    measured: dict[str, Any] = {}
    for key in INTEGER_METRICS:
        if key in metrics:
            measured[key] = int(_number(metrics[key], f"metrics.{key}", integer=True))
    if "elapsed_seconds" in metrics:
        measured["elapsed_seconds"] = float(_number(metrics["elapsed_seconds"], "metrics.elapsed_seconds", integer=False))
    if "truncated" in metrics:
        if not isinstance(metrics["truncated"], bool):
            raise ValueError("metrics.truncated must be a boolean")
        measured["truncated"] = metrics["truncated"]

    if "context_tokens" in measured:
        method = str(metrics.get("context_token_method", "")).strip()
        if method not in TOKEN_METHODS:
            raise ValueError(
                "metrics.context_token_method must identify a supported counting method when context_tokens is reported"
            )
        measured["context_token_method"] = method

    return measured


def evaluate(
    budgets: dict[str, Any],
    usage: dict[str, Any] | None,
    stage_id: str,
    metrics: dict[str, Any] | None,
    *,
    required_metrics: list[str] | None = None,
    strict: bool = False,
    allow_truncation: bool = False,
) -> dict[str, Any]:
    """Evaluate stage-local measurements against cumulative/run limits.

    strict mode makes missing stage-required measurements incomplete and blocking.
    Legacy fixtures may use strict=False while provider adapters are upgraded.
    """
    limits = validate_budgets(budgets)
    if not isinstance(stage_id, str) or not stage_id.strip():
        raise ValueError("stage_id is required")
    stage_id = stage_id.strip()

    required = required_metrics or []
    if not isinstance(required, list) or any(x not in BUDGET_KEYS for x in required):
        raise ValueError("required_metrics contains an unsupported metric")

    current = normalize_usage(usage)
    measured = normalize_metrics(metrics)

    missing = sorted(set(required) - set(measured))
    violations: list[str] = []
    constraints: list[str] = []

    if strict and missing:
        violations.append(f"required budget measurements missing for {stage_id}: {', '.join(missing)}")

    if measured.get("truncated") is True:
        if allow_truncation:
            constraints.append("provider output was explicitly truncated")
        else:
            violations.append(
                f"provider output for {stage_id} was truncated; silent/incomplete output is not allowed"
            )

    next_usage = deepcopy(current)
    if "context_tokens" in measured:
        next_usage["context_tokens"] += measured["context_tokens"]
    if "output_bytes" in measured:
        next_usage["output_bytes"] += measured["output_bytes"]
    if "graph_nodes" in measured:
        next_usage["graph_nodes"] = max(next_usage["graph_nodes"], measured["graph_nodes"])
    if "elapsed_seconds" in measured:
        next_usage["last_stage_elapsed_seconds"] = measured["elapsed_seconds"]
    if any(key in measured for key in BUDGET_KEYS):
        next_usage["stages_measured"] += 1

    checks: dict[str, dict[str, Any]] = {}
    for metric, limit_key in BUDGET_KEYS.items():
        used = measured.get(metric) if metric == "elapsed_seconds" else next_usage[metric]
        limit = limits[limit_key]
        status = "unmeasured" if metric == "elapsed_seconds" and metric not in measured else "within-budget"
        if used is not None and used > limit:
            status = "over-budget"
            label = {
                "context_tokens": "context token",
                "graph_nodes": "graph node",
                "output_bytes": "output byte",
                "elapsed_seconds": "stage timeout",
            }[metric]
            violations.append(f"{label} budget exceeded for {stage_id}: {used:g} > {limit}")
        checks[metric] = {"used": used, "limit": limit, "status": status}

    if violations:
        decision = "block"
    elif constraints:
        decision = "allow-with-constraints"
    else:
        decision = "allow"

    remaining = {
        "context_tokens": max(0, limits["max_context_tokens"] - next_usage["context_tokens"]),
        "graph_nodes": max(0, limits["max_graph_nodes"] - next_usage["graph_nodes"]),
        "output_bytes": max(0, limits["max_output_bytes"] - next_usage["output_bytes"]),
    }

    return {
        "schema_version": 1,
        "stage": stage_id,
        "decision": decision,
        "strict": strict,
        "required_metrics": sorted(set(required)),
        "measured": measured,
        "missing_required": missing,
        "checks": checks,
        "usage": next_usage,
        "remaining": remaining,
        "violations": sorted(set(violations)),
        "constraints": sorted(set(constraints)),
    }


def exact_output_bytes(path: Path) -> int:
    return path.stat().st_size


def graph_node_count(path: Path) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        payload = payload["data"]
    if not isinstance(payload, dict) or not isinstance(payload.get("nodes"), list):
        raise ValueError("graph JSON must contain a nodes list")
    return len(payload["nodes"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--budgets", type=Path, required=True)
    parser.add_argument("--usage", type=Path)
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--required", action="append", default=[])
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--allow-truncation", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-allow", action="store_true")
    args = parser.parse_args()

    budgets = json.loads(args.budgets.read_text(encoding="utf-8"))
    usage = json.loads(args.usage.read_text(encoding="utf-8")) if args.usage else None
    metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
    result = evaluate(
        budgets, usage, args.stage, metrics,
        required_metrics=args.required,
        strict=args.strict,
        allow_truncation=args.allow_truncation,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.require_allow and result["decision"] == "block":
        return 8
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
