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


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected JSON object")
    return data


def plan(envelope: dict[str, Any]) -> dict[str, Any]:
    stages = []
    for stage in envelope["stages"]:
        stages.append({
            "id": stage["id"],
            "provider": PROVIDERS[stage["id"]],
            "required": stage["status"] != "skipped",
            "status": stage["status"],
        })
    return {
        "schema_version": 1,
        "context": "C002",
        "run_id": envelope["run_id"],
        "target": envelope["target"],
        "budgets": envelope["budgets"],
        "stages": stages,
        "rules": {
            "stop_on_failed": True,
            "stop_on_blocked": True,
            "auto_promote": False,
            "parent_approval_required": True,
            "private_identity_persistence": False,
        },
    }


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
    envelope = ENV.new_envelope(_load(manifest))
    run_plan = plan(envelope)

    for stage in envelope["stages"]:
        if stage["status"] == "skipped":
            continue
        result_path = stage_dir / f"{stage['id']}.json"
        if not result_path.exists():
            break
        result = _load(result_path)
        if result.get("stage") != stage["id"]:
            raise ValueError(f"{result_path}: stage ID mismatch")
        envelope = ENV.apply_stage_result(envelope, result)
        if envelope["status"] in {"failed", "blocked"}:
            break

    l7 = next(s for s in envelope["stages"] if s["id"] == "L7-promotion")
    pre_l7 = [
        s for s in envelope["stages"]
        if s["id"] != "L7-promotion" and s["status"] != "skipped"
    ]
    if all(s["status"] in {"passed", "passed-with-constraints"} for s in pre_l7):
        package = promotion_package(envelope)
        decision = PROMOTION.evaluate(package)
        l7_result = {
            "stage": "L7-promotion",
            "status": (
                "passed-with-constraints"
                if decision["decision"] == "eligible-with-constraints"
                else "passed"
                if decision["decision"] == "eligible-for-parent-promotion"
                else "blocked"
            ),
            "provider": PROVIDERS["L7-promotion"],
            "evidence": [
                f"promotion-decision:{decision['decision']}",
                "machine-gate:auto-promote=false",
            ],
            "artifacts": [],
            "metrics": {},
            "constraints": decision["constraints"],
            "error": None if decision["decision"] in PROMOTION.FINAL_ELIGIBLE else "; ".join(decision["reasons"]),
        }
        envelope = ENV.apply_stage_result(envelope, l7_result)
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
