#!/usr/bin/env python3
"""Build a deterministic C003 Repository Intelligence reproducibility pack."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected JSON object")
    return data


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return proc.stdout.strip()


def _relative_path(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    path = Path(text)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{name} must be a safe repository-relative path")
    return path.as_posix()


def _normalize_spec(spec: dict[str, Any]) -> dict[str, Any]:
    if spec.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("spec.schema_version must be 1")
    if spec.get("context") != "C003":
        raise ValueError("spec.context must be C003")

    required_files_raw = spec.get("required_files")
    if not isinstance(required_files_raw, list) or not required_files_raw:
        raise ValueError("spec.required_files must be a non-empty list")
    required_files = sorted({
        _relative_path(item, "spec.required_files[]") for item in required_files_raw
    })

    external_tools = spec.get("external_tools")
    if not isinstance(external_tools, list) or not external_tools:
        raise ValueError("spec.external_tools must be a non-empty list")
    normalized_tools = []
    names = set()
    for index, raw in enumerate(external_tools):
        if not isinstance(raw, dict):
            raise ValueError(f"spec.external_tools[{index}] must be an object")
        name = str(raw.get("name", "")).strip()
        version = str(raw.get("version", "")).strip()
        source = str(raw.get("source", "")).strip()
        immutable_ref = str(raw.get("immutable_ref", "")).strip()
        integrity = str(raw.get("integrity", "")).strip()
        if not all([name, version, source, immutable_ref, integrity]):
            raise ValueError(f"spec.external_tools[{index}] is incomplete")
        if name in names:
            raise ValueError(f"duplicate external tool: {name}")
        names.add(name)
        item = {
            "name": name,
            "version": version,
            "source": source,
            "immutable_ref": immutable_ref,
            "integrity": integrity,
        }
        if "sha256" in raw:
            sha = str(raw["sha256"]).strip().lower()
            if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
                raise ValueError(f"spec.external_tools[{index}].sha256 is invalid")
            item["sha256"] = sha
        normalized_tools.append(item)
    normalized_tools.sort(key=lambda item: item["name"])

    verified_runs = spec.get("verified_runs")
    if not isinstance(verified_runs, list) or not verified_runs:
        raise ValueError("spec.verified_runs must be a non-empty list")
    normalized_runs = []
    run_ids = set()
    for index, raw in enumerate(verified_runs):
        if not isinstance(raw, dict):
            raise ValueError(f"spec.verified_runs[{index}] must be an object")
        milestone = str(raw.get("milestone", "")).strip()
        run_id = raw.get("run_id")
        status = str(raw.get("status", "")).strip()
        if not milestone or not isinstance(run_id, int) or run_id <= 0:
            raise ValueError(f"spec.verified_runs[{index}] is invalid")
        if status != "verified":
            raise ValueError(f"spec.verified_runs[{index}] must be verified")
        if run_id in run_ids:
            raise ValueError(f"duplicate verified run id: {run_id}")
        run_ids.add(run_id)
        normalized_runs.append({"milestone": milestone, "run_id": run_id, "status": status})
    normalized_runs.sort(key=lambda item: item["milestone"])

    runtime_proofs = spec.get("runtime_proofs", [])
    if not isinstance(runtime_proofs, list):
        raise ValueError("spec.runtime_proofs must be a list")
    normalized_proofs = []
    runtime_names = set()
    for index, raw in enumerate(runtime_proofs):
        if not isinstance(raw, dict):
            raise ValueError(f"spec.runtime_proofs[{index}] must be an object")
        runtime = str(raw.get("runtime", "")).strip()
        status = str(raw.get("status", "")).strip()
        run_id = raw.get("run_id")
        blocker = str(raw.get("blocker", "")).strip()
        if not runtime or runtime in runtime_names:
            raise ValueError(f"spec.runtime_proofs[{index}].runtime is invalid")
        if status not in {"verified", "blocked"}:
            raise ValueError(f"spec.runtime_proofs[{index}].status is invalid")
        if not isinstance(run_id, int) or run_id <= 0:
            raise ValueError(f"spec.runtime_proofs[{index}].run_id is invalid")
        if status == "blocked" and not blocker:
            raise ValueError(f"spec.runtime_proofs[{index}] blocked proof requires blocker")
        runtime_names.add(runtime)
        normalized_proofs.append({
            "runtime": runtime,
            "status": status,
            "run_id": run_id,
            "blocker": blocker if status == "blocked" else "",
        })
    normalized_proofs.sort(key=lambda item: item["runtime"])

    commands = spec.get("reproduction_commands")
    if not isinstance(commands, list) or not commands:
        raise ValueError("spec.reproduction_commands must be a non-empty list")
    normalized_commands = []
    for index, command in enumerate(commands):
        command = str(command or "").strip()
        if not command:
            raise ValueError(f"spec.reproduction_commands[{index}] is empty")
        normalized_commands.append(command)

    return {
        "schema_version": SCHEMA_VERSION,
        "context": "C003",
        "scope": str(spec.get("scope", "")).strip(),
        "required_files": required_files,
        "external_tools": normalized_tools,
        "verified_runs": normalized_runs,
        "runtime_proofs": normalized_proofs,
        "reproduction_commands": normalized_commands,
    }


def build(repo_root: Path, spec_path: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    spec_path = spec_path.resolve()
    spec = _normalize_spec(_load(spec_path))

    revision = _git(repo_root, "rev-parse", "HEAD")
    tree_hash = _git(repo_root, "rev-parse", "HEAD^{tree}")
    status = _git(repo_root, "status", "--porcelain")

    files = []
    for relative in spec["required_files"]:
        path = repo_root / relative
        if not path.is_file():
            raise ValueError(f"required file missing: {relative}")
        files.append({
            "path": relative,
            "sha256": _sha256_file(path),
            "bytes": path.stat().st_size,
        })

    spec_bytes = spec_path.read_bytes()
    pack = {
        "schema_version": SCHEMA_VERSION,
        "context": "C003",
        "scope": spec["scope"],
        "source": {
            "revision": revision,
            "tree_hash": tree_hash,
            "clean": status == "",
        },
        "spec": {
            "path": spec_path.relative_to(repo_root).as_posix(),
            "sha256": _sha256_bytes(spec_bytes),
        },
        "files": files,
        "external_tools": spec["external_tools"],
        "verified_runs": spec["verified_runs"],
        "runtime_proofs": spec["runtime_proofs"],
        "reproduction_commands": spec["reproduction_commands"],
    }
    canonical = json.dumps(pack, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    pack["pack_fingerprint"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return pack


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    pack = build(args.repo_root, args.spec)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(pack, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
