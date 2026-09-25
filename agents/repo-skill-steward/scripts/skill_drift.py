#!/usr/bin/env python3
"""Compare a canonical SKILL.md with an installed/local copy without overwriting it."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_frontmatter(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return {}

    data: dict[str, Any] = {}
    for line in lines[1:end]:
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip().strip("\"'")
        if value:
            data[key] = value
    return data


def compare(canonical_text: str, installed_text: str) -> dict[str, Any]:
    canonical_meta = parse_frontmatter(canonical_text)
    installed_meta = parse_frontmatter(installed_text)
    canonical_name = canonical_meta.get("name")
    installed_name = installed_meta.get("name")

    result: dict[str, Any] = {
        "canonical_sha256": sha256_text(canonical_text),
        "installed_sha256": sha256_text(installed_text),
        "canonical_name": canonical_name,
        "installed_name": installed_name,
        "same_content": canonical_text == installed_text,
        "auto_replace": False,
    }

    if canonical_text == installed_text:
        result.update(
            {
                "status": "exact-copy",
                "sync_mode": "verified-refresh-eligible",
                "manual_review_required": False,
            }
        )
        return result

    if canonical_name and installed_name and canonical_name != installed_name:
        result.update(
            {
                "status": "different-skill",
                "sync_mode": "do-not-sync",
                "manual_review_required": True,
            }
        )
        return result

    if canonical_name and installed_name and canonical_name == installed_name:
        result.update(
            {
                "status": "same-name-local-drift",
                "sync_mode": "preserve-local-review-upstream",
                "manual_review_required": True,
            }
        )
        return result

    result.update(
        {
            "status": "unverified-drift",
            "sync_mode": "do-not-sync",
            "manual_review_required": True,
        }
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", required=True, help="Canonical SKILL.md path")
    parser.add_argument("--installed", required=True, help="Installed/local SKILL.md path")
    args = parser.parse_args()

    canonical = Path(args.canonical).read_text(encoding="utf-8")
    installed = Path(args.installed).read_text(encoding="utf-8")
    print(json.dumps(compare(canonical, installed), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
