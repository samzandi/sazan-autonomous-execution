#!/usr/bin/env python3
"""Fail-closed launcher for the SAZAN read-only GitHub MCP provider."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
OFFICIAL_REPOSITORY = "github/github-mcp-server"
OFFICIAL_IMAGE_PREFIX = "ghcr.io/github/github-mcp-server:"
APPROVED_TOOLSETS = {
    "context",
    "repos",
    "pull_requests",
    "issues",
    "actions",
    "code_security",
    "secret_protection",
}
FORBIDDEN_TOOLSETS = {"all", "git", "governance", "orgs", "projects"}
DEFAULT_PROFILE = Path(__file__).with_name("github-readonly-profile.json")


def _text(value: Any, name: str) -> str:
    out = str(value or "").strip()
    if not out:
        raise ValueError(f"{name} is required")
    return out


def load_profile(path: str | Path = DEFAULT_PROFILE) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("profile must be a JSON object")
    validate_profile(data)
    return data


def validate_profile(profile: dict[str, Any]) -> None:
    if profile.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("schema_version must be 1")

    source = profile.get("source")
    if not isinstance(source, dict):
        raise ValueError("source must be an object")
    if _text(source.get("repository"), "source.repository") != OFFICIAL_REPOSITORY:
        raise ValueError("GitHub MCP source must be the canonical official repository")
    if source.get("official") is not True:
        raise ValueError("GitHub MCP source must be marked official")

    release = _text(profile.get("release"), "release")
    if re.fullmatch(r"v\d+\.\d+\.\d+", release) is None:
        raise ValueError("release must be an immutable semantic version tag such as v1.14.0")

    expected_image = f"{OFFICIAL_IMAGE_PREFIX}{release}"
    if _text(profile.get("image"), "image") != expected_image:
        raise ValueError(f"image must be pinned to {expected_image}")

    if profile.get("access_mode") != "read_only":
        raise ValueError("GitHub MCP access_mode must remain read_only")
    if profile.get("lockdown") is not True:
        raise ValueError("GitHub MCP lockdown must remain enabled")
    if profile.get("write_authority") != "disabled":
        raise ValueError("write authority must remain disabled")
    if profile.get("destructive_authority") != "disabled":
        raise ValueError("destructive authority must remain disabled")

    toolsets = profile.get("toolsets")
    if not isinstance(toolsets, list) or not toolsets:
        raise ValueError("toolsets must be a non-empty list")
    if not all(isinstance(item, str) and item.strip() for item in toolsets):
        raise ValueError("toolsets must contain non-empty strings")

    normalized = [item.strip() for item in toolsets]
    if len(normalized) != len(set(normalized)):
        raise ValueError("toolsets must not contain duplicates")
    forbidden = sorted(set(normalized) & FORBIDDEN_TOOLSETS)
    if forbidden:
        raise ValueError(f"forbidden GitHub MCP toolsets: {', '.join(forbidden)}")
    unknown = sorted(set(normalized) - APPROVED_TOOLSETS)
    if unknown:
        raise ValueError(f"unapproved GitHub MCP toolsets: {', '.join(unknown)}")

    _text(profile.get("token_source_env"), "token_source_env")
    if profile.get("container_token_env") != "GITHUB_PERSONAL_ACCESS_TOKEN":
        raise ValueError("container_token_env must be GITHUB_PERSONAL_ACCESS_TOKEN")
    _text(profile.get("server_name"), "server_name")


def build_docker_command(profile: dict[str, Any]) -> list[str]:
    validate_profile(profile)
    toolsets = ",".join(profile["toolsets"])
    return [
        "docker",
        "run",
        "-i",
        "--rm",
        "--pull=missing",
        "--name",
        "sazan-github-mcp-readonly",
        "-e",
        profile["container_token_env"],
        "-e",
        "GITHUB_READ_ONLY=1",
        "-e",
        "GITHUB_LOCKDOWN_MODE=1",
        "-e",
        f"GITHUB_TOOLSETS={toolsets}",
        "-e",
        f"GITHUB_MCP_SERVER_NAME={profile['server_name']}",
        profile["image"],
    ]


def prepare_runtime_environment(
    profile: dict[str, Any],
    environ: dict[str, str] | None = None,
) -> dict[str, str]:
    validate_profile(profile)
    source = dict(os.environ if environ is None else environ)
    token_name = profile["token_source_env"]
    token = source.get(token_name, "").strip()
    if not token:
        raise RuntimeError(f"required token environment variable is missing: {token_name}")

    runtime = dict(source)
    runtime[profile["container_token_env"]] = token
    return runtime


def run(profile: dict[str, Any]) -> int:
    if shutil.which("docker") is None:
        raise RuntimeError("docker is required to run the GitHub MCP provider")
    command = build_docker_command(profile)
    runtime = prepare_runtime_environment(profile)
    completed = subprocess.run(command, env=runtime, check=False)
    return int(completed.returncode)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    profile = load_profile(args.profile)
    command = build_docker_command(profile)

    if args.dry_run:
        print(json.dumps({
            "status": "validated",
            "provider": profile["id"],
            "release": profile["release"],
            "access_mode": profile["access_mode"],
            "lockdown": profile["lockdown"],
            "toolsets": profile["toolsets"],
            "command": command,
            "secret_in_command": False,
        }, indent=2, sort_keys=True))
        return 0

    return run(profile)


if __name__ == "__main__":
    raise SystemExit(main())
