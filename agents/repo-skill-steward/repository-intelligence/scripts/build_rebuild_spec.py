#!/usr/bin/env python3
"""Build a deterministic evidence-backed clean-room rebuild specification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SECTION_ORDER = [
    ("objective", "Product objective"),
    ("behaviors", "Observed user behaviors"),
    ("architecture", "System architecture"),
    ("modules", "Module responsibilities"),
    ("interfaces", "Public interfaces and entry points"),
    ("data_contracts", "Data and state contracts"),
    ("flows", "Key execution flows"),
    ("dependencies", "Dependencies and external integrations"),
    ("build_run_test", "Build, run, and test requirements"),
    ("non_functional", "Non-functional constraints"),
    ("security_license", "Security and license constraints"),
    ("acceptance", "Acceptance criteria"),
    ("inferences", "Inferred implementation choices"),
    ("unknowns", "Unknowns and open questions"),
]


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("input must be a JSON object")
    return data


def _as_list(value: Any, field: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return value


def _validate_evidence(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    evidence = _as_list(data.get("evidence"), "evidence")
    by_id: dict[str, dict[str, Any]] = {}
    for item in evidence:
        if not isinstance(item, dict):
            raise ValueError("each evidence item must be an object")
        eid = str(item.get("id", "")).strip()
        if not eid:
            raise ValueError("evidence item missing id")
        if eid in by_id:
            raise ValueError(f"duplicate evidence id: {eid}")
        source = str(item.get("source", "")).strip()
        statement = str(item.get("statement", "")).strip()
        if not source or not statement:
            raise ValueError(f"evidence {eid} requires source and statement")
        by_id[eid] = item
    return by_id


def _validate_claim(
    claim: dict[str, Any],
    evidence_ids: set[str],
    section: str,
) -> dict[str, Any]:
    text = str(claim.get("text", "")).strip()
    if not text:
        raise ValueError(f"{section}: claim missing text")

    state = str(claim.get("state", "")).strip()
    if state not in {"observed", "inferred", "unknown"}:
        raise ValueError(f"{section}: invalid claim state {state!r}")

    refs = claim.get("evidence", [])
    if refs is None:
        refs = []
    if not isinstance(refs, list) or not all(isinstance(x, str) for x in refs):
        raise ValueError(f"{section}: evidence must be a list of IDs")
    missing = [x for x in refs if x not in evidence_ids]
    if missing:
        raise ValueError(f"{section}: unknown evidence IDs: {missing}")

    rationale = str(claim.get("rationale", "")).strip()

    if state == "observed" and not refs:
        raise ValueError(f"{section}: observed claim requires evidence")
    if state == "inferred":
        if not refs:
            raise ValueError(f"{section}: inferred claim requires evidence")
        if not rationale:
            raise ValueError(f"{section}: inferred claim requires rationale")
    if state == "unknown" and refs:
        raise ValueError(f"{section}: unknown claim must not cite evidence as proof")

    return {
        "text": text,
        "state": state,
        "evidence": refs,
        "rationale": rationale,
    }


def normalize(data: dict[str, Any]) -> dict[str, Any]:
    source = data.get("source")
    if not isinstance(source, dict):
        raise ValueError("source must be an object")
    repository = str(source.get("repository", "")).strip()
    revision = str(source.get("revision", "")).strip()
    if not repository or not revision:
        raise ValueError("source.repository and source.revision are required")

    evidence = _validate_evidence(data)
    evidence_ids = set(evidence)

    sections: dict[str, list[dict[str, Any]]] = {}
    raw_sections = data.get("sections", {})
    if not isinstance(raw_sections, dict):
        raise ValueError("sections must be an object")

    for key, _title in SECTION_ORDER:
        claims = _as_list(raw_sections.get(key), f"sections.{key}")
        normalized_claims = []
        for claim in claims:
            if not isinstance(claim, dict):
                raise ValueError(f"sections.{key}: each claim must be an object")
            normalized_claims.append(_validate_claim(claim, evidence_ids, key))
        sections[key] = normalized_claims

    if not sections["objective"]:
        raise ValueError("at least one product objective is required")
    if not sections["acceptance"]:
        raise ValueError("at least one acceptance criterion is required")

    return {
        "schema_version": 1,
        "source": {
            "repository": repository,
            "revision": revision,
            "visibility": str(source.get("visibility", "unknown")),
        },
        "sections": sections,
        "evidence": [evidence[eid] | {"id": eid} for eid in sorted(evidence)],
    }


def _claim_line(claim: dict[str, Any]) -> str:
    state = claim["state"].upper()
    refs = claim["evidence"]
    suffix = f" [evidence: {', '.join(refs)}]" if refs else ""
    line = f"- **{state}** — {claim['text']}{suffix}"
    if claim["state"] == "inferred":
        line += f"\n  - Rationale: {claim['rationale']}"
    return line


def render_markdown(spec: dict[str, Any]) -> str:
    src = spec["source"]
    out = [
        "# Clean-room Rebuild Specification",
        "",
        f"- Repository: {src['repository']}",
        f"- Revision: {src['revision']}",
        f"- Visibility: {src['visibility']}",
        f"- Schema version: {spec['schema_version']}",
        "",
        "## Claim semantics",
        "",
        "- OBSERVED: directly supported by cited evidence.",
        "- INFERRED: bounded design inference supported by evidence and rationale.",
        "- UNKNOWN: intentionally unresolved; requires validation.",
        "",
    ]

    for key, title in SECTION_ORDER:
        out.extend([f"## {title}", ""])
        claims = spec["sections"][key]
        if claims:
            out.extend(_claim_line(c) for c in claims)
        else:
            out.append("- No material claims recorded.")
        out.append("")

    out.extend(["## Evidence ledger", ""])
    for item in spec["evidence"]:
        out.append(
            f"- **{item['id']}** — {item['statement']} "
            f"(source: {item['source']})"
        )
    out.append("")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--markdown", type=Path, required=True)
    parser.add_argument("--json", dest="json_out", type=Path, required=True)
    args = parser.parse_args()

    spec = normalize(_load(args.input))
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text(render_markdown(spec), encoding="utf-8")
    args.json_out.write_text(
        json.dumps(spec, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
