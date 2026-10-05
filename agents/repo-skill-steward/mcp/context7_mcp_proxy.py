#!/usr/bin/env python3
"""Fail-closed stdio guard for the SAZAN Context7 MCP provider."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
OFFICIAL_REPOSITORY = "upstash/context7"
PINNED_PACKAGE = "@upstash/context7-mcp@4.1.1"
DEFAULT_PROFILE = Path(__file__).with_name("context7-readonly-profile.json")
SAFE_TOOLS = {"resolve-library-id", "query-docs"}

SAFE_ENV_KEYS = {
    "PATH",
    "HOME",
    "USERPROFILE",
    "SYSTEMROOT",
    "SystemRoot",
    "COMSPEC",
    "ComSpec",
    "PATHEXT",
    "TMP",
    "TEMP",
    "TMPDIR",
    "HTTPS_PROXY",
    "https_proxy",
    "HTTP_PROXY",
    "http_proxy",
    "NO_PROXY",
    "no_proxy",
    "NODE_EXTRA_CA_CERTS",
    "SSL_CERT_FILE",
    "NPM_CONFIG_CACHE",
}

SECRET_PATTERNS = [
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bctx7sk[-_A-Za-z0-9]{10,}\b", re.IGNORECASE),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"Authorization\s*:\s*Bearer\s+\S+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]


def _text(value: Any, name: str) -> str:
    out = str(value or "").strip()
    if not out:
        raise ValueError(f"{name} is required")
    return out


def load_profile(path: str | Path = DEFAULT_PROFILE) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("profile must be a JSON object")
    validate_profile(raw)
    return raw


def validate_profile(profile: dict[str, Any]) -> None:
    if profile.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("schema_version must be 1")

    source = profile.get("source")
    if not isinstance(source, dict):
        raise ValueError("source must be an object")
    if source.get("repository") != OFFICIAL_REPOSITORY or source.get("official") is not True:
        raise ValueError("Context7 source must be the canonical official repository")

    if _text(profile.get("release"), "release") != PINNED_PACKAGE:
        raise ValueError(f"release must be pinned to {PINNED_PACKAGE}")
    if _text(profile.get("package"), "package") != PINNED_PACKAGE:
        raise ValueError(f"package must be pinned to {PINNED_PACKAGE}")
    if profile.get("transport") != "stdio":
        raise ValueError("Context7 production profile must use stdio transport")

    tools = profile.get("allowed_tools")
    if not isinstance(tools, list) or set(tools) != SAFE_TOOLS or len(tools) != len(SAFE_TOOLS):
        raise ValueError("Context7 tool surface must contain exactly the two approved read tools")

    max_query_chars = profile.get("max_query_chars")
    if not isinstance(max_query_chars, int) or not 256 <= max_query_chars <= 4000:
        raise ValueError("max_query_chars must be between 256 and 4000")

    if profile.get("action_authority") != "disabled":
        raise ValueError("action authority must remain disabled")
    if profile.get("destructive_authority") != "disabled":
        raise ValueError("destructive authority must remain disabled")
    if profile.get("container_token_env") != "CONTEXT7_API_KEY":
        raise ValueError("container_token_env must be CONTEXT7_API_KEY")
    _text(profile.get("token_source_env"), "token_source_env")


def build_upstream_command(profile: dict[str, Any]) -> list[str]:
    validate_profile(profile)
    return [
        "npx",
        "--yes",
        profile["package"],
        "--transport",
        "stdio",
    ]


def prepare_runtime_environment(
    profile: dict[str, Any],
    environ: dict[str, str] | None = None,
) -> dict[str, str]:
    validate_profile(profile)
    source = dict(os.environ if environ is None else environ)
    runtime = {key: value for key, value in source.items() if key in SAFE_ENV_KEYS and value}

    token = source.get(profile["token_source_env"], "").strip()
    if token:
        runtime[profile["container_token_env"]] = token

    runtime["OTEL_SDK_DISABLED"] = "true"
    return runtime


def contains_sensitive_material(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_PATTERNS)


def _validate_query(profile: dict[str, Any], value: Any, field: str) -> str:
    text = _text(value, field)
    if len(text) > profile["max_query_chars"]:
        raise ValueError(f"{field} exceeds the Context7 query length limit")
    if contains_sensitive_material(text):
        raise PermissionError(f"{field} appears to contain a credential or private key")
    return text


def validate_tool_call(
    profile: dict[str, Any],
    tool_name: str,
    arguments: dict[str, Any],
) -> None:
    validate_profile(profile)
    if tool_name not in SAFE_TOOLS:
        raise PermissionError(f"Context7 tool is not allowed: {tool_name}")

    _validate_query(profile, arguments.get("query"), "query")

    if tool_name == "resolve-library-id":
        library_name = _text(arguments.get("libraryName"), "libraryName")
        if len(library_name) > 200:
            raise ValueError("libraryName is too long")
        if contains_sensitive_material(library_name):
            raise PermissionError("libraryName appears to contain a credential")
        return

    library_id = _text(arguments.get("libraryId"), "libraryId")
    if len(library_id) > 300:
        raise ValueError("libraryId is too long")
    if re.fullmatch(r"/[A-Za-z0-9_.@-]+/[A-Za-z0-9_.@-]+(?:/[A-Za-z0-9_.@+-]+)?", library_id) is None:
        raise ValueError("libraryId must use the Context7 /org/project[/version] form")


def filter_tools_response(profile: dict[str, Any], message: dict[str, Any]) -> dict[str, Any]:
    result = message.get("result")
    if not isinstance(result, dict):
        return message
    tools = result.get("tools")
    if not isinstance(tools, list):
        return message

    allowed = set(profile["allowed_tools"])
    filtered: list[dict[str, Any]] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        if str(tool.get("name", "")) not in allowed:
            continue
        annotations = tool.get("annotations")
        if isinstance(annotations, dict) and annotations.get("readOnlyHint") is False:
            continue
        filtered.append(tool)
    result["tools"] = filtered
    return message


def _write_message(stream: Any, message: dict[str, Any]) -> None:
    stream.write(json.dumps(message, separators=(",", ":")) + "\n")
    stream.flush()


class Context7Proxy:
    def __init__(self, profile: dict[str, Any], command: list[str]) -> None:
        self.profile = profile
        self.command = command
        self.pending: dict[Any, str] = {}
        self.lock = threading.Lock()

    def _stderr_pump(self, child: subprocess.Popen[str]) -> None:
        assert child.stderr is not None
        for line in child.stderr:
            sys.stderr.write(line)
            sys.stderr.flush()

    def _stdout_pump(self, child: subprocess.Popen[str]) -> None:
        assert child.stdout is not None
        for line in child.stdout:
            raw = line.strip()
            if not raw:
                continue
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(message, dict):
                continue

            response_id = message.get("id")
            method = None
            if response_id is not None:
                with self.lock:
                    method = self.pending.pop(response_id, None)
            if method == "tools/list":
                message = filter_tools_response(self.profile, message)
            _write_message(sys.stdout, message)

    def run(self) -> int:
        child = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=prepare_runtime_environment(self.profile),
        )
        assert child.stdin is not None

        threading.Thread(target=self._stderr_pump, args=(child,), daemon=True).start()
        threading.Thread(target=self._stdout_pump, args=(child,), daemon=True).start()

        try:
            for line in sys.stdin:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(message, dict):
                    continue

                method = message.get("method")
                request_id = message.get("id")
                if request_id is not None and isinstance(method, str):
                    with self.lock:
                        self.pending[request_id] = method

                if method == "tools/call":
                    params = message.get("params")
                    if not isinstance(params, dict):
                        params = {}
                    tool_name = str(params.get("name", ""))
                    arguments = params.get("arguments")
                    if not isinstance(arguments, dict):
                        arguments = {}
                    try:
                        validate_tool_call(self.profile, tool_name, arguments)
                    except (PermissionError, ValueError) as exc:
                        if request_id is not None:
                            with self.lock:
                                self.pending.pop(request_id, None)
                            _write_message(
                                sys.stdout,
                                {
                                    "jsonrpc": "2.0",
                                    "id": request_id,
                                    "error": {"code": -32001, "message": str(exc)},
                                },
                            )
                        continue

                child.stdin.write(raw + "\n")
                child.stdin.flush()
        finally:
            try:
                child.stdin.close()
            except BrokenPipeError:
                pass
            try:
                return child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.terminate()
                try:
                    return child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    return child.wait()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    profile = load_profile(args.profile)
    command = build_upstream_command(profile)
    runtime = prepare_runtime_environment(profile)

    if args.dry_run:
        print(
            json.dumps(
                {
                    "status": "validated",
                    "provider": profile["id"],
                    "release": profile["release"],
                    "transport": profile["transport"],
                    "allowed_tools": profile["allowed_tools"],
                    "api_key_configured": profile["container_token_env"] in runtime,
                    "sanitized_environment": True,
                    "telemetry_disabled": runtime.get("OTEL_SDK_DISABLED") == "true",
                    "command": command,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if shutil.which("npx") is None:
        raise RuntimeError("npx is required to run the Context7 MCP provider")
    return Context7Proxy(profile, command).run()


if __name__ == "__main__":
    raise SystemExit(main())
