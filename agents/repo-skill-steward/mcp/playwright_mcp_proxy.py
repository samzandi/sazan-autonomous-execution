#!/usr/bin/env python3
"""Governed stdio proxy for the SAZAN Playwright MCP observe profile."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SCHEMA_VERSION = 1
OFFICIAL_REPOSITORY = "microsoft/playwright-mcp"
PACKAGE_PREFIX = "@playwright/mcp@"
DEFAULT_PROFILE = Path(__file__).with_name("playwright-observe-profile.json")

SAFE_TOOLS = {
    "browser_console_messages",
    "browser_find",
    "browser_navigate",
    "browser_network_request",
    "browser_network_requests",
    "browser_snapshot",
    "browser_take_screenshot",
    "browser_get_config",
    "browser_cookie_get",
    "browser_cookie_list",
    "browser_localstorage_get",
    "browser_localstorage_list",
    "browser_sessionstorage_get",
    "browser_sessionstorage_list",
}

URL_TOOLS = {"browser_navigate", "browser_network_request"}
FILE_WRITING_ARGUMENTS = {"filename", "path"}
FORBIDDEN_CAPS = {"vision", "pdf", "devtools", "testing"}


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
        raise ValueError("Playwright MCP source must be the official Microsoft repository")

    release = _text(profile.get("release"), "release")
    if re.fullmatch(r"v\d+\.\d+\.\d+", release) is None:
        raise ValueError("release must be an immutable semantic version tag")

    package = _text(profile.get("package"), "package")
    expected_package = f"{PACKAGE_PREFIX}{release.removeprefix('v')}"
    if package != expected_package:
        raise ValueError(f"package must be pinned to {expected_package}")

    if profile.get("mode") != "observe":
        raise ValueError("default Playwright MCP mode must remain observe")
    if profile.get("runtime") != "npx":
        raise ValueError("runtime must be npx")
    if profile.get("headless") is not True:
        raise ValueError("headless must remain enabled")
    if profile.get("isolated") is not True:
        raise ValueError("isolated browser state must remain enabled")
    if profile.get("sandbox") is not True:
        raise ValueError("browser sandbox must remain enabled")
    if profile.get("webmcp") is not False:
        raise ValueError("WebMCP must remain disabled")
    if profile.get("image_responses") != "omit":
        raise ValueError("image responses must remain omitted in observe mode")
    if profile.get("codegen") != "none":
        raise ValueError("codegen must remain disabled in observe mode")
    if profile.get("allow_local_network") is not False:
        raise ValueError("local/private network access must remain disabled by default")
    if profile.get("action_authority") != "disabled":
        raise ValueError("action authority must remain disabled")
    if profile.get("destructive_authority") != "disabled":
        raise ValueError("destructive authority must remain disabled")

    caps = profile.get("additional_caps")
    if not isinstance(caps, list):
        raise ValueError("additional_caps must be a list")
    if set(caps) & FORBIDDEN_CAPS:
        raise ValueError("optional Playwright capabilities are forbidden in observe mode")
    if caps:
        raise ValueError("observe mode does not enable additional capabilities")

    tools = profile.get("allowed_tools")
    if not isinstance(tools, list) or not tools:
        raise ValueError("allowed_tools must be a non-empty list")
    if len(tools) != len(set(tools)):
        raise ValueError("allowed_tools must not contain duplicates")
    unknown = sorted(set(tools) - SAFE_TOOLS)
    if unknown:
        raise ValueError(f"unapproved Playwright tools: {', '.join(unknown)}")


def build_upstream_command(profile: dict[str, Any], output_dir: str) -> list[str]:
    validate_profile(profile)
    command = [
        "npx",
        "--yes",
        profile["package"],
        "--headless",
        "--browser",
        profile["browser"],
        "--isolated",
        "--sandbox",
        "--no-webmcp",
        "--image-responses",
        profile["image_responses"],
        "--codegen",
        profile["codegen"],
        "--block-service-workers",
        "--output-dir",
        output_dir,
        "--output-max-size",
        "10485760",
        "--timeout-action",
        "5000",
        "--timeout-navigation",
        "30000",
        "--idle-timeout",
        "300000",
    ]
    return command


def _resolved_addresses(hostname: str) -> set[ipaddress._BaseAddress]:
    addresses: set[ipaddress._BaseAddress] = set()
    for item in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM):
        raw = item[4][0]
        try:
            addresses.add(ipaddress.ip_address(raw))
        except ValueError:
            continue
    return addresses


def validate_navigation_url(url: str, *, allow_local_network: bool = False) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("observe mode permits only http/https navigation")
    if not parsed.hostname:
        raise ValueError("navigation URL must contain a hostname")

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost":
        if allow_local_network:
            return
        raise ValueError("localhost access is disabled in observe mode")

    try:
        literal = ipaddress.ip_address(hostname)
        addresses = {literal}
    except ValueError:
        addresses = _resolved_addresses(hostname)
        if not addresses:
            raise ValueError("navigation hostname could not be resolved")

    for address in addresses:
        private = (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        )
        if private and not allow_local_network:
            raise ValueError("local/private network targets are disabled in observe mode")


def validate_tool_call(
    profile: dict[str, Any],
    tool_name: str,
    arguments: dict[str, Any],
    *,
    allow_local_network_override: bool = False,
) -> None:
    validate_profile(profile)
    if tool_name not in profile["allowed_tools"]:
        raise PermissionError(f"Playwright MCP tool is not allowed in observe mode: {tool_name}")

    if tool_name in {"browser_take_screenshot"}:
        if any(key in arguments for key in FILE_WRITING_ARGUMENTS):
            raise PermissionError("explicit file output is disabled in observe mode")

    if tool_name in URL_TOOLS:
        url = str(arguments.get("url", "")).strip()
        if not url:
            raise ValueError(f"{tool_name} requires a URL")
        validate_navigation_url(
            url,
            allow_local_network=(
                allow_local_network_override or bool(profile.get("allow_local_network"))
            ),
        )


def filter_tools_response(profile: dict[str, Any], message: dict[str, Any]) -> dict[str, Any]:
    result = message.get("result")
    if not isinstance(result, dict):
        return message
    tools = result.get("tools")
    if not isinstance(tools, list):
        return message
    allowed = set(profile["allowed_tools"])
    result["tools"] = [
        tool for tool in tools
        if isinstance(tool, dict) and str(tool.get("name", "")) in allowed
    ]
    return message


def _write_message(stream: Any, message: dict[str, Any]) -> None:
    stream.write(json.dumps(message, separators=(",", ":")) + "\n")
    stream.flush()


class ObserveProxy:
    def __init__(self, profile: dict[str, Any], command: list[str]) -> None:
        self.profile = profile
        self.command = command
        self.pending: dict[Any, str] = {}
        self.lock = threading.Lock()
        self.local_override = os.environ.get("SAZAN_PLAYWRIGHT_ALLOW_LOCAL_NETWORK") == "1"

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
        )
        assert child.stdin is not None

        stderr_thread = threading.Thread(target=self._stderr_pump, args=(child,), daemon=True)
        stdout_thread = threading.Thread(target=self._stdout_pump, args=(child,), daemon=True)
        stderr_thread.start()
        stdout_thread.start()

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
                        validate_tool_call(
                            self.profile,
                            tool_name,
                            arguments,
                            allow_local_network_override=self.local_override,
                        )
                    except (PermissionError, ValueError) as exc:
                        if request_id is not None:
                            with self.lock:
                                self.pending.pop(request_id, None)
                            _write_message(
                                sys.stdout,
                                {
                                    "jsonrpc": "2.0",
                                    "id": request_id,
                                    "error": {
                                        "code": -32001,
                                        "message": str(exc),
                                    },
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

    with tempfile.TemporaryDirectory(prefix="sazan-playwright-mcp-") as output_dir:
        command = build_upstream_command(profile, output_dir)
        if args.dry_run:
            print(
                json.dumps(
                    {
                        "status": "validated",
                        "provider": profile["id"],
                        "release": profile["release"],
                        "package": profile["package"],
                        "mode": profile["mode"],
                        "allowed_tools": profile["allowed_tools"],
                        "local_network": profile["allow_local_network"],
                        "persistent_profile": False,
                        "webmcp": False,
                        "additional_caps": [],
                        "command": command,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0

        if shutil.which("npx") is None:
            raise RuntimeError("npx is required to run the Playwright MCP provider")
        return ObserveProxy(profile, command).run()


if __name__ == "__main__":
    raise SystemExit(main())
