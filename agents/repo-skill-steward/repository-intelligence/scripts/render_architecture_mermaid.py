#!/usr/bin/env python3
"""Render a bounded, deterministic Mermaid architecture diagram from CodeGraph-style JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


UNSAFE = re.compile(r'["<>\\{}\[\]|]')
SPACE = re.compile(r"\s+")


def safe_text(value: Any, limit: int = 96) -> str:
    text = SPACE.sub(" ", str(value or "").strip())
    text = UNSAFE.sub("", text)
    text = text.replace(chr(96), "")
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text or "unnamed"


def mermaid_id(value: Any) -> str:
    raw = str(value)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"n_{digest}"


def normalize_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        payload = payload["data"]
    if not isinstance(payload, dict):
        raise ValueError("input must be a JSON object")
    nodes = payload.get("nodes", [])
    edges = payload.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("input must contain list fields: nodes and edges")
    return {"nodes": nodes, "edges": edges}


def render(
    payload: dict[str, Any],
    *,
    direction: str = "LR",
    include_external: bool = False,
    max_nodes: int = 120,
    max_edges: int = 240,
    title: str | None = None,
) -> str:
    if direction not in {"LR", "RL", "TB", "BT"}:
        raise ValueError("direction must be one of LR, RL, TB, BT")
    if max_nodes < 1 or max_edges < 1:
        raise ValueError("max_nodes and max_edges must be positive")

    raw_nodes = payload["nodes"]
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()

    for node in raw_nodes:
        if not isinstance(node, dict) or "id" not in node:
            continue
        if not include_external and bool(node.get("is_external")):
            continue
        node_key = str(node["id"])
        if node_key in seen:
            continue
        selected.append(node)
        seen.add(node_key)
        if len(selected) >= max_nodes:
            break

    allowed = {str(node["id"]) for node in selected}
    edges: list[dict[str, Any]] = []
    for edge in payload["edges"]:
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("from", ""))
        target = str(edge.get("to", ""))
        if source in allowed and target in allowed:
            edges.append(edge)
        if len(edges) >= max_edges:
            break

    lines = [f"flowchart {direction}"]
    if title:
        lines.append(f"  %% {safe_text(title, 140)}")

    for node in sorted(selected, key=lambda x: (safe_text(x.get("path")), safe_text(x.get("name")), str(x.get("id")))):
        node_id = mermaid_id(node["id"])
        name = safe_text(node.get("name"))
        node_type = safe_text(node.get("type"), 28)
        language = safe_text(node.get("language"), 24)
        path = safe_text(node.get("path"), 110)
        parts = [name]
        if node_type != "unnamed":
            parts.append(node_type)
        if language not in {"unnamed", "unknown"}:
            parts.append(language)
        label = " · ".join(parts)
        if path not in {"unnamed", name}:
            label += f"\\n{path}"
        lines.append(f'  {node_id}["{label}"]')

    def edge_sort_key(edge: dict[str, Any]) -> tuple[str, str, str]:
        return (
            str(edge.get("from", "")),
            str(edge.get("to", "")),
            safe_text(edge.get("type"), 32),
        )

    for edge in sorted(edges, key=edge_sort_key):
        source = mermaid_id(edge["from"])
        target = mermaid_id(edge["to"])
        relation = safe_text(edge.get("type"), 32)
        if relation == "unnamed":
            lines.append(f"  {source} --> {target}")
        else:
            lines.append(f'  {source} -->|{relation}| {target}')

    lines.append("")
    lines.append(f"  %% nodes={len(selected)} edges={len(edges)} external={'included' if include_external else 'excluded'}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render CodeGraph-style graph JSON as deterministic Mermaid.")
    parser.add_argument("input", type=Path, help="Input JSON file")
    parser.add_argument("-o", "--output", type=Path, help="Output Mermaid file; stdout when omitted")
    parser.add_argument("--direction", default="LR", choices=["LR", "RL", "TB", "BT"])
    parser.add_argument("--include-external", action="store_true")
    parser.add_argument("--max-nodes", type=int, default=120)
    parser.add_argument("--max-edges", type=int, default=240)
    parser.add_argument("--title")
    args = parser.parse_args()

    payload = normalize_payload(json.loads(args.input.read_text(encoding="utf-8")))
    content = render(
        payload,
        direction=args.direction,
        include_external=args.include_external,
        max_nodes=args.max_nodes,
        max_edges=args.max_edges,
        title=args.title,
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
