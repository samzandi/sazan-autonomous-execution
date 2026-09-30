#!/usr/bin/env python3
"""Deterministic budget enforcement for C002 Repository Intelligence runs."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


NUMERIC_METRICS = {
    "context_tokens",
    "graph_nodes",
    "output_bytes",
    "elapsed_seconds",
}


def initial_usage() -> dict[str, Any]:
    return {
        "context_tokens": 0,
        "graph_nodes": 0,
        "output_bytes": 0,
        "stages_measured": 0,
        "last_stage_elapsed_seconds": None,
    }


def _nonnegative_number(value: Any, name: str, *, integer: bool) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a non-negative {'integer' if integer else 'number'}")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    if integer:
        if isinstance(value, float) and not value.is_integer():
            raise ValueError(f"{name} must be a non-negative integer")
        return int(value)
    return float(value)


def _validate_budgets(budgets: dict[str, Any]) -> dict[str, int]:
    if not isinstance(budgets, dict):
        raise ValueError("budgets must be an object")
    required = {
        "max_context_tokens",
        "max_graph_nodes",
        "max_output_bytes",
        "stage_timeout_seconds",
    }
    missing = sorted(required - set(budgets))
    if missing:
        raise ValueError(f"missing budgets: {', '.join(missing)}")
    out = {}
    for key in sorted(required):
        value = _nonnegative_number(budgets[key], f"budgets.{key}", integer=True)
        if value <= 0:
            raise ValueError(f"budgets.{key} must be positive")
        out[key] = int(value)
    return out


def evaluate(
    budgets: dict[str, Any],
    usage: dict[str, Any] | None,
    stage_id: str,
    metrics: dict[str, Any] | None,
) -> dict[str, Any]:
    """Evaluate a stage's reported metrics against the run budget.

    Metric semantics:
    - context_tokens: stage-local context tokens; accumulated across stages.
    - output_bytes: stage-local persisted output bytes; accumulated across stages.
    - graph_nodes: stage-local graph node count; run usage stores the maximum.
    - elapsed_seconds: stage wall-clock duration; checked against per-stage timeout.
    - truncated: boolean; does not block by itself but records a constraint.

    Unknown metrics are deliberately ignored by the guard and remain available to
    the evidence envelope.
    """

    limits = _validate_budgets(budgets)
    if not isinstance(stage_id, str) or not stage_id.strip():
        raise ValueError("stage_id is required")
    stage_id = stage_id.strip()

    if metrics is None:
        metrics = {}
    if not isinstance(metrics, dict):
        raise ValueError("metrics must be an object")

    current = initial_usage()
    if usage is not None:
        if not isinstance(usage, dict):
            raise ValueError("usage must be an object")
        for key in current:
            if key in usage:
                current[key] = deepcopy(usage[key])

    # Validate prior usage so corrupted envelopes cannot bypass limits.
    current["context_tokens"] = int(_nonnegative_number(
        current["context_tokens"], "usage.context_tokens", integer=True
    ))
    current["graph_nodes"] = int(_nonnegative_number(
        current["graph_nodes"], "usage.graph_nodes", integer=True
    ))
    current["output_bytes"] = int(_nonnegative_number(
        current["output_bytes"], "usage.output_bytes", integer=True
    ))
    current["stages_measured"] = int(_nonnegative_number(
        current["stages_measured"], "usage.stages_measured", integer=True
    ))
    if current["last_stage_elapsed_seconds"] is not None:
        current["last_stage_elapsed_seconds"] = _nonnegative_number(
            current["last_stage_elapsed_seconds"],
            "usage.last_stage_elapsed_seconds",
            integer=False,
        )

    measured: dict[str, int | float | bool] = {}
    if "context_tokens" in metrics:
        measured["context_tokens"] = int(_nonnegative_number(
            metrics["context_tokens"], "metrics.context_tokens", integer=True
        ))
    if "graph_nodes" in metrics:
        measured["graph_nodes"] = int(_nonnegative_number(
            metrics["graph_nodes"], "metrics.graph_nodes", integer=True
        ))
    if "output_bytes" in metrics:
        measured["output_bytes"] = int(_nonnegative_number(
            metrics["output_bytes"], "metrics.output_bytes", integer=True
        ))
    if "elapsed_seconds" in metrics:
        measured["elapsed_seconds"] = _nonnegative_number(
            metrics["elapsed_seconds"], "metrics.elapsed_seconds", integer=False
        )
    if "truncated" in metrics:
        if not isinstance(metrics["truncated"], bool):
            raise ValueError("metrics.truncated must be a boolean")
        measured["truncated"] = metrics["truncated"]

    next_usage = deepcopy(current)
    if "context_tokens" in measured:
        next_usage["context_tokens"] += int(measured["context_tokens"])
    if "output_bytes" in measured:
        next_usage["output_bytes"] += int(measured["output_bytes"])
    if "graph_nodes" in measured:
        next_usage["graph_nodes"] = max(
            next_usage["graph_nodes"], int(measured["graph_nodes"])
        )
    if "elapsed_seconds" in measured:
        next_usage["last_stage_elapsed_seconds"] = measured["elapsed_seconds"]
    if any(key in measured for key in NUMERIC_METRICS):
        next_usage["stages_measured"] += 1

    violations: list[str] = []
    if next_usage["context_tokens"] > limits["max_context_tokens"]:
        violations.append(
            f"context token budget exceeded: {next_usage['context_tokens']} > "
            f"{limits['max_context_tokens']}"
        )
    if next_usage["graph_nodes"] > limits["max_graph_nodes"]:
        violations.append(
            f"graph node budget exceeded: {next_usage['graph_nodes']} > "
            f"{limits['max_graph_nodes']}"
        )
    if next_usage["output_bytes"] > limits["max_output_bytes"]:
        violations.append(
            f"output byte budget exceeded: {next_usage['output_bytes']} > "
            f"{limits['max_output_bytes']}"
        )
    elapsed = measured.get("elapsed_seconds")
    if elapsed is not None and elapsed > limits["stage_timeout_seconds"]:
        violations.append(
            f"stage timeout budget exceeded for {stage_id}: {elapsed:g}s > "
            f"{limits['stage_timeout_seconds']}s"
        )

    constraints: list[str] = []
    if measured.get("truncated") is True:
        constraints.append("provider output was truncated to stay within configured budget")

    if violations:
        decision = "block"
    elif constraints:
        decision = "allow-with-constraints"
    else:
        decision = "allow"

    remaining = {
        "context_tokens": max(
            0, limits["max_context_tokens"] - next_usage["context_tokens"]
        ),
        "graph_nodes": max(
            0, limits["max_graph_nodes"] - next_usage["graph_nodes"]
        ),
        "output_bytes": max(
            0, limits["max_output_bytes"] - next_usage["output_bytes"]
        ),
    }

    return {
        "schema_version": 1,
        "stage": stage_id,
        "decision": decision,
        "measured": measured,
        "usage": next_usage,
        "remaining": remaining,
        "violations": violations,
        "constraints": constraints,
        "unmeasured": sorted(NUMERIC_METRICS - set(measured)),
    }
