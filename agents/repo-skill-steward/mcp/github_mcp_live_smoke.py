#!/usr/bin/env python3
"""Credentialed runtime smoke test for the guarded GitHub MCP provider."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import github_mcp_launcher as launcher  # noqa: E402


PROTOCOL_VERSION = "2024-11-05"
KNOWN_WRITE_TOOLS = {
    "add_issue_comment",
    "add_pull_request_review_comment",
    "create_branch",
    "create_issue",
    "create_or_update_file",
    "create_pull_request",
    "create_repository",
    "delete_file",
    "fork_repository",
    "merge_pull_request",
    "push_files",
    "rerun_failed_jobs",
    "run_workflow",
    "update_issue",
    "update_pull_request",
}


def _response_by_id(responses: list[dict[str, Any]], response_id: int) -> dict[str, Any]:
    for response in responses:
        if response.get("id") == response_id:
            return response
    raise RuntimeError(f"missing MCP response id={response_id}")


def parse_jsonrpc_lines(output: str) -> list[dict[str, Any]]:
    responses: list[dict[str, Any]] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and value.get("jsonrpc") == "2.0":
            responses.append(value)
    return responses


def verify_tool_inventory(response: dict[str, Any]) -> list[str]:
    if "error" in response:
        raise RuntimeError(f"tools/list failed: {response['error']}")

    result = response.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("tools/list response has no result object")
    tools = result.get("tools")
    if not isinstance(tools, list) or not tools:
        raise RuntimeError("tools/list returned no tools")

    names: list[str] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        name = str(tool.get("name", "")).strip()
        if name:
            names.append(name)
        annotations = tool.get("annotations")
        if isinstance(annotations, dict) and annotations.get("readOnlyHint") is False:
            raise RuntimeError(f"non-read-only MCP tool exposed: {name or '<unnamed>'}")

    leaked = sorted(set(names) & KNOWN_WRITE_TOOLS)
    if leaked:
        raise RuntimeError(f"write-capable MCP tools exposed: {', '.join(leaked)}")
    if "get_file_contents" not in names:
        raise RuntimeError("required read tool get_file_contents is not exposed")
    return names


def verify_read_call(response: dict[str, Any]) -> None:
    if "error" in response:
        raise RuntimeError(f"tools/call failed: {response['error']}")
    result = response.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("tools/call response has no result object")
    if result.get("isError") is True:
        raise RuntimeError("get_file_contents returned an MCP tool error")
    content = result.get("content")
    if not isinstance(content, list) or not content:
        raise RuntimeError("get_file_contents returned no content")


def verify_token_access(token: str, repository: str) -> None:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "sazan-github-mcp-live-smoke",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"GitHub credential check returned HTTP {response.status}")


def build_messages(owner: str, repo: str, ref: str, path: str) -> str:
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "sazan-mcp-live-smoke", "version": "1.0.0"},
            },
        },
        {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        },
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        },
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_file_contents",
                "arguments": {
                    "owner": owner,
                    "repo": repo,
                    "path": path,
                    "ref": ref,
                },
            },
        },
    ]
    return "\n".join(json.dumps(message, separators=(",", ":")) for message in messages) + "\n"


def redact(text: str, token: str) -> str:
    return text.replace(token, "[REDACTED]") if token else text


def run_live_smoke(
    repository: str,
    ref: str,
    path: str,
    profile_path: Path = launcher.DEFAULT_PROFILE,
) -> dict[str, Any]:
    if "/" not in repository:
        raise ValueError("repository must be owner/name")
    owner, repo = repository.split("/", 1)

    profile = launcher.load_profile(profile_path)
    token_name = profile["token_source_env"]
    token = os.environ.get(token_name, "").strip()
    if not token:
        raise RuntimeError(f"required token environment variable is missing: {token_name}")

    verify_token_access(token, repository)

    command = launcher.build_docker_command(profile)
    runtime = launcher.prepare_runtime_environment(profile)
    payload = build_messages(owner, repo, ref, path)

    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=runtime,
    )
    assert process.stdin is not None
    process.stdin.write(payload)
    process.stdin.flush()

    # Match the upstream conformance harness: keep stdin open briefly so the
    # stdio server can emit responses before EOF triggers graceful shutdown.
    time.sleep(1.0)
    process.stdin.close()
    process.stdin = None

    try:
        stdout, stderr = process.communicate(timeout=120)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.communicate()
        raise RuntimeError("GitHub MCP live smoke timed out") from exc

    if process.returncode != 0:
        safe_stderr = redact(stderr[-4000:], token)
        raise RuntimeError(
            f"GitHub MCP container exited with {process.returncode}: {safe_stderr}"
        )

    responses = parse_jsonrpc_lines(stdout)
    if not responses:
        safe_stdout = redact(stdout[-4000:], token)
        safe_stderr = redact(stderr[-4000:], token)
        raise RuntimeError(
            "GitHub MCP emitted no JSON-RPC responses; "
            f"stdout={safe_stdout!r} stderr={safe_stderr!r}"
        )
    initialize = _response_by_id(responses, 1)
    if "error" in initialize or not isinstance(initialize.get("result"), dict):
        raise RuntimeError("MCP initialize failed")

    tool_names = verify_tool_inventory(_response_by_id(responses, 2))
    verify_read_call(_response_by_id(responses, 3))

    return {
        "status": "passed",
        "provider": profile["id"],
        "release": profile["release"],
        "access_mode": profile["access_mode"],
        "lockdown": profile["lockdown"],
        "tool_count": len(tool_names),
        "read_tool_call": "get_file_contents",
        "repository": repository,
        "ref": ref,
        "path": path,
        "credential_source": token_name,
        "secret_logged": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repository",
        default=os.environ.get("SAZAN_MCP_SMOKE_REPOSITORY", ""),
    )
    parser.add_argument(
        "--ref",
        default=os.environ.get("SAZAN_MCP_SMOKE_REF", "main"),
    )
    parser.add_argument(
        "--path",
        default=os.environ.get("SAZAN_MCP_SMOKE_PATH", ".sazan/guardian.yml"),
    )
    parser.add_argument("--profile", type=Path, default=launcher.DEFAULT_PROFILE)
    args = parser.parse_args()

    result = run_live_smoke(args.repository, args.ref, args.path, args.profile)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
