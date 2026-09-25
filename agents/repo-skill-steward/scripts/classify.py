#!/usr/bin/env python3
"""Classify repository inventory records into safe update strategies."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def classify_repository(record: dict[str, Any]) -> dict[str, Any]:
    strategies: list[str] = []
    gates: list[str] = []

    if record.get("archived"):
        return {
            "full_name": record.get("full_name"),
            "strategies": ["frozen"],
            "verification_profile": "none",
            "auto_propose": False,
            "auto_merge": False,
            "gates": ["archived-repository"],
        }

    if record.get("fork") and record.get("upstream"):
        strategies.append("upstream-sync")

    if record.get("dependency_markers") or record.get("has_dependencies"):
        strategies.append("dependency-update")

    if record.get("container_markers") or record.get("has_container_config"):
        strategies.append("container-image-update")

    if record.get("has_github_actions"):
        strategies.append("github-actions-update")

    skill_present = (
        bool(record.get("skill_surfaces"))
        or bool(record.get("has_skill_surface"))
        or "SKILL.md" in record.get("agent_markers", [])
        or bool(record.get("has_agent_markers") and record.get("visibility") == "private")
    )
    if skill_present:
        strategies.append("skill-agent-audit")

    has_tests = bool(record.get("has_tests"))
    has_ci = bool(record.get("has_github_actions"))

    if strategies:
        if has_tests and has_ci:
            verification_profile = "ci-and-tests"
        elif has_tests:
            verification_profile = "tests-plus-manual-review"
            gates.append("ci-missing")
        else:
            verification_profile = "manual-review-first"
            gates.append("tests-missing")
    else:
        verification_profile = "monitor-only"

    if not strategies:
        strategies.append("monitor-only")

    return {
        "full_name": record.get("full_name"),
        "strategies": strategies,
        "verification_profile": verification_profile,
        "auto_propose": bool(strategies != ["monitor-only"] and has_tests and has_ci),
        "auto_merge": False,
        "gates": gates,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify Sazan Repo & Skill Steward inventory JSON."
    )
    parser.add_argument(
        "inventory",
        nargs="?",
        default="-",
        help="Inventory JSON file path, or - for stdin.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.inventory == "-":
        payload = json.load(sys.stdin)
    else:
        with open(args.inventory, "r", encoding="utf-8") as handle:
            payload = json.load(handle)

    repositories = payload.get("repositories", [])
    result = [classify_repository(record) for record in repositories]
    print(json.dumps({"repositories": result}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
