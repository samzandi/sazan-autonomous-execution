#!/usr/bin/env python3
"""Evaluate Repository Intelligence promotion evidence deterministically."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


FINAL_ELIGIBLE = {"eligible-for-parent-promotion", "eligible-with-constraints"}
VERIFIER_STATES = {"verified", "verified-with-constraints", "pending-evidence", "rejected"}
INTEGRATION_MODES = {"embedded-core", "external-adapter", "reference-only", "internal-component"}


def _obj(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _list(value: Any, name: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list")
    return value


def _text(value: Any, name: str) -> str:
    out = str(value or "").strip()
    if not out:
        raise ValueError(f"{name} is required")
    return out


def _has_evidence(check: dict[str, Any]) -> bool:
    evidence = check.get("evidence", [])
    return isinstance(evidence, list) and any(str(x).strip() for x in evidence)


def evaluate(package: dict[str, Any]) -> dict[str, Any]:
    if package.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")

    candidate = _obj(package.get("candidate"), "candidate")
    name = _text(candidate.get("name"), "candidate.name")
    source = _text(candidate.get("source"), "candidate.source")
    revision = _text(candidate.get("revision"), "candidate.revision")
    mode = _text(candidate.get("integration_mode"), "candidate.integration_mode")
    if mode not in INTEGRATION_MODES:
        raise ValueError(f"unsupported integration_mode: {mode}")

    checks = _obj(package.get("checks"), "checks")
    required_names = [
        "provenance",
        "license",
        "security",
        "lab",
        "capability_delta",
        "rollback",
        "private_data",
        "verifier",
    ]
    missing = [name for name in required_names if name not in checks]
    if missing:
        raise ValueError(f"missing checks: {', '.join(missing)}")

    provenance = _obj(checks["provenance"], "checks.provenance")
    license_check = _obj(checks["license"], "checks.license")
    security = _obj(checks["security"], "checks.security")
    lab = _obj(checks["lab"], "checks.lab")
    delta = _obj(checks["capability_delta"], "checks.capability_delta")
    rollback = _obj(checks["rollback"], "checks.rollback")
    private_data = _obj(checks["private_data"], "checks.private_data")
    verifier = _obj(checks["verifier"], "checks.verifier")

    verifier_state = _text(verifier.get("status"), "checks.verifier.status")
    if verifier_state not in VERIFIER_STATES:
        raise ValueError(f"invalid verifier status: {verifier_state}")

    reasons: list[str] = []
    blockers: list[str] = []
    pending: list[str] = []
    constraints = [str(x).strip() for x in _list(package.get("constraints"), "constraints") if str(x).strip()]

    # Hard rejection rules.
    license_status = str(license_check.get("status", "")).strip()
    if license_status == "incompatible":
        blockers.append("license is incompatible")
    if license_status == "noncommercial" and mode != "reference-only":
        blockers.append("non-commercial license is restricted to reference-only use")
    if security.get("status") == "failed":
        blockers.append("security review failed")
    if lab.get("status") == "failed":
        blockers.append("lab validation failed")
    if private_data.get("status") == "violation":
        blockers.append("private-data policy violation")
    if verifier_state == "rejected":
        blockers.append("verifier rejected promotion")
    if delta.get("status") == "duplicate" and mode in {"embedded-core", "internal-component"}:
        blockers.append("no capability delta: duplicate core capability")
    if delta.get("status") == "incompatible":
        blockers.append("capability delta is incompatible with the target stack")

    # Required evidence/pending rules.
    if provenance.get("status") != "verified" or not _has_evidence(provenance):
        pending.append("canonical provenance is not fully verified")
    if not _has_evidence(license_check):
        pending.append("license evidence is incomplete")
    elif license_status in {"", "pending"}:
        pending.append("license evidence is incomplete")
    elif license_status == "unknown":
        if mode == "reference-only":
            constraints.append("license unknown: reference-only; no code copying, vendoring, or execution")
        else:
            pending.append("unknown license permits reference-only use until clarified")
    if security.get("status") not in {"passed", "passed-with-constraints"} or not _has_evidence(security):
        if security.get("status") != "failed":
            pending.append("security review evidence is incomplete")
    if lab.get("status") not in {"passed", "not-required"}:
        if lab.get("status") != "failed":
            pending.append("lab evidence is incomplete")
    if lab.get("status") == "passed" and not _has_evidence(lab):
        pending.append("passed lab has no evidence reference")
    if delta.get("status") not in {"new", "better", "replacement", "reference-value"} or not _has_evidence(delta):
        if delta.get("status") not in {"duplicate", "incompatible"}:
            pending.append("capability delta is not established")
    if rollback.get("status") != "verified":
        pending.append("rollback path is not verified")
    if private_data.get("status") != "compliant":
        if private_data.get("status") != "violation":
            pending.append("private-data handling is not verified")
    if verifier_state == "pending-evidence":
        pending.append("verifier requires more evidence")
    if verifier_state in {"verified", "verified-with-constraints"} and not _has_evidence(verifier):
        pending.append("verifier decision has no evidence reference")

    # Constraint accumulation.
    if security.get("status") == "passed-with-constraints":
        constraints.extend(
            str(x).strip()
            for x in _list(security.get("constraints"), "checks.security.constraints")
            if str(x).strip()
        )
    if verifier_state == "verified-with-constraints":
        constraints.extend(
            str(x).strip()
            for x in _list(verifier.get("constraints"), "checks.verifier.constraints")
            if str(x).strip()
        )
    constraints = sorted(set(constraints))

    if blockers:
        decision = "rejected"
        reasons.extend(blockers)
    elif pending:
        decision = "pending-evidence"
        reasons.extend(sorted(set(pending)))
    elif constraints:
        decision = "eligible-with-constraints"
        reasons.append("all mandatory gates passed with recorded constraints")
    else:
        decision = "eligible-for-parent-promotion"
        reasons.append("all mandatory gates passed")

    return {
        "schema_version": 1,
        "candidate": {
            "name": name,
            "source": source,
            "revision": revision,
            "integration_mode": mode,
        },
        "decision": decision,
        "auto_promote": False,
        "parent_approval_required": decision in FINAL_ELIGIBLE,
        "reasons": reasons,
        "constraints": constraints,
        "gate_checks": {
            "provenance": provenance.get("status"),
            "license": license_status,
            "security": security.get("status"),
            "lab": lab.get("status"),
            "capability_delta": delta.get("status"),
            "rollback": rollback.get("status"),
            "private_data": private_data.get("status"),
            "verifier": verifier_state,
        },
    }


def render_markdown(result: dict[str, Any]) -> str:
    c = result["candidate"]
    lines = [
        "# Promotion Gate Decision",
        "",
        f"- Candidate: {c['name']}",
        f"- Source: {c['source']}",
        f"- Revision: {c['revision']}",
        f"- Integration mode: {c['integration_mode']}",
        f"- Decision: **{result['decision']}**",
        f"- Auto-promote: **{str(result['auto_promote']).lower()}**",
        f"- Parent approval required: **{str(result['parent_approval_required']).lower()}**",
        "",
        "## Reasons",
        "",
    ]
    lines.extend(f"- {x}" for x in result["reasons"])
    lines.extend(["", "## Constraints", ""])
    if result["constraints"]:
        lines.extend(f"- {x}" for x in result["constraints"])
    else:
        lines.append("- None.")
    lines.extend(["", "## Gate checks", ""])
    for key, value in result["gate_checks"].items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--json", dest="json_out", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    parser.add_argument(
        "--require-eligible",
        action="store_true",
        help="exit non-zero unless decision is eligible-for-parent-promotion or eligible-with-constraints",
    )
    args = parser.parse_args()

    package = json.loads(args.input.read_text(encoding="utf-8"))
    result = evaluate(_obj(package, "input"))
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.markdown.write_text(render_markdown(result), encoding="utf-8")

    if args.require_eligible and result["decision"] not in FINAL_ELIGIBLE:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
