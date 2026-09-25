#!/usr/bin/env python3
"""Render an aggregate, public-safe repository audit report."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def summarize(
    inventory_payload: dict[str, Any],
    classification_payload: dict[str, Any],
) -> dict[str, Any]:
    inventory = inventory_payload.get("repositories", [])
    classifications = classification_payload.get("repositories", [])

    if not isinstance(inventory, list) or not isinstance(classifications, list):
        raise ValueError("repositories must be arrays")
    if len(inventory) != len(classifications):
        raise ValueError("inventory/classification repository counts differ")

    strategy_counts: Counter[str] = Counter()
    verification_counts: Counter[str] = Counter()
    public_rows: list[dict[str, Any]] = []
    private_count = 0
    error_count = 0
    auto_propose_count = 0

    for inv, cls in zip(inventory, classifications):
        if not isinstance(inv, dict) or not isinstance(cls, dict):
            raise ValueError("repository records must be objects")

        visibility = inv.get("visibility")
        if visibility == "private":
            private_count += 1

        if "error" in inv:
            error_count += 1

        strategies = cls.get("strategies", [])
        if isinstance(strategies, list):
            strategy_counts.update(str(item) for item in strategies)

        profile = cls.get("verification_profile")
        if profile:
            verification_counts[str(profile)] += 1

        if cls.get("auto_propose"):
            auto_propose_count += 1

        full_name = str(inv.get("full_name", ""))
        if visibility != "private" and full_name and full_name != "<private-repository>":
            public_rows.append(
                {
                    "full_name": full_name,
                    "strategies": [str(item) for item in strategies],
                    "verification_profile": profile,
                    "auto_propose": bool(cls.get("auto_propose", False)),
                }
            )

    return {
        "repository_count": len(inventory),
        "private_repository_count": private_count,
        "public_repository_count": len(inventory) - private_count,
        "inspection_error_count": error_count,
        "auto_propose_count": auto_propose_count,
        "strategy_counts": dict(sorted(strategy_counts.items())),
        "verification_counts": dict(sorted(verification_counts.items())),
        "public_repositories": sorted(public_rows, key=lambda item: item["full_name"].casefold()),
    }


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Sazan Repo & Skill Steward — scheduled audit",
        "",
        "This report is intentionally public-safe. Private repository identities and detailed metadata are not included.",
        "",
        "## Aggregate",
        "",
        f"- Repositories scanned: {summary['repository_count']}",
        f"- Public repositories: {summary['public_repository_count']}",
        f"- Private repositories: {summary['private_repository_count']}",
        f"- Inspection errors: {summary['inspection_error_count']}",
        f"- Repositories eligible for automatic update proposals: {summary['auto_propose_count']}",
        "",
        "## Update strategies",
        "",
    ]

    strategy_counts = summary.get("strategy_counts", {})
    if strategy_counts:
        for name, count in strategy_counts.items():
            lines.append(f"- {name}: {count}")
    else:
        lines.append("- none")

    lines.extend(["", "## Verification profiles", ""])
    verification_counts = summary.get("verification_counts", {})
    if verification_counts:
        for name, count in verification_counts.items():
            lines.append(f"- {name}: {count}")
    else:
        lines.append("- none")

    public_repositories = summary.get("public_repositories", [])
    if public_repositories:
        lines.extend(
            [
                "",
                "## Public repository matrix",
                "",
                "| Repository | Strategies | Verification | Auto-propose |",
                "| --- | --- | --- | --- |",
            ]
        )
        for row in public_repositories:
            strategies = ", ".join(row["strategies"]) or "none"
            auto = "yes" if row["auto_propose"] else "no"
            lines.append(
                f"| {row['full_name']} | {strategies} | {row['verification_profile']} | {auto} |"
            )

    lines.extend(
        [
            "",
            "## Safety",
            "",
            "- This scheduled audit is read-only.",
            "- It does not merge, push, install, publish, deploy, delete, or rotate credentials.",
            "- Private repository details remain runtime-only.",
        ]
    )

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--classification", required=True)
    parser.add_argument("--output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = summarize(load_json(args.inventory), load_json(args.classification))
    rendered = render_markdown(summary)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
