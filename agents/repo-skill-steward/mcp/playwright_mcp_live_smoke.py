#!/usr/bin/env python3
"""Live browser proof for the governed Playwright MCP observe proxy."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


MCP_DIR = Path(__file__).resolve().parent
PROXY = MCP_DIR / "playwright_mcp_proxy.py"
PROTOCOL_VERSION = "2024-11-05"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = b"""<!doctype html><html><head><title>SAZAN MCP Smoke</title></head>
<body><main><h1>SAZAN Playwright MCP</h1><p id="status">observe-only smoke passed</p>
<button id="danger">Do not click</button></main></body></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def start_server() -> tuple[ThreadingHTTPServer, int]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, int(server.server_address[1])


def send(process: subprocess.Popen[str], message: dict[str, Any]) -> None:
    assert process.stdin is not None
    process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
    process.stdin.flush()


def wait_for_id(messages: "queue.Queue[dict[str, Any]]", response_id: int, timeout: float = 90.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        remaining = max(0.1, deadline - time.monotonic())
        try:
            message = messages.get(timeout=remaining)
        except queue.Empty as exc:
            raise RuntimeError(f"timed out waiting for MCP response id={response_id}") from exc
        if message.get("id") == response_id:
            return message
    raise RuntimeError(f"timed out waiting for MCP response id={response_id}")


def reader(process: subprocess.Popen[str], messages: "queue.Queue[dict[str, Any]]") -> None:
    assert process.stdout is not None
    for line in process.stdout:
        raw = line.strip()
        if not raw:
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            messages.put(value)


def run() -> dict[str, Any]:
    server, port = start_server()
    env = dict(os.environ)
    env["SAZAN_PLAYWRIGHT_ALLOW_LOCAL_NETWORK"] = "1"

    process = subprocess.Popen(
        [sys.executable, str(PROXY)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        bufsize=1,
    )
    messages: "queue.Queue[dict[str, Any]]" = queue.Queue()
    reader_thread = threading.Thread(target=reader, args=(process, messages), daemon=True)
    reader_thread.start()

    try:
        send(
            process,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "sazan-playwright-smoke", "version": "1.0.0"},
                },
            },
        )
        initialize = wait_for_id(messages, 1)
        if "error" in initialize:
            raise RuntimeError(f"MCP initialize failed: {initialize['error']}")

        send(
            process,
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            },
        )

        send(process, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        listed = wait_for_id(messages, 2)
        tools = listed.get("result", {}).get("tools", [])
        tool_names = {
            str(tool.get("name"))
            for tool in tools
            if isinstance(tool, dict) and tool.get("name")
        }
        required = {"browser_navigate", "browser_snapshot"}
        if not required.issubset(tool_names):
            raise RuntimeError(f"required observe tools missing: {sorted(required - tool_names)}")
        forbidden = {"browser_click", "browser_type", "browser_fill_form", "browser_evaluate"}
        leaked = sorted(tool_names & forbidden)
        if leaked:
            raise RuntimeError(f"side-effect tools leaked through proxy: {leaked}")

        url = f"http://127.0.0.1:{port}/"
        send(
            process,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "browser_navigate",
                    "arguments": {"url": url},
                },
            },
        )
        navigate = wait_for_id(messages, 3)
        if "error" in navigate or navigate.get("result", {}).get("isError") is True:
            raise RuntimeError("browser_navigate failed in live smoke")

        send(
            process,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "browser_snapshot",
                    "arguments": {},
                },
            },
        )
        snapshot = wait_for_id(messages, 4)
        if "error" in snapshot or snapshot.get("result", {}).get("isError") is True:
            raise RuntimeError("browser_snapshot failed in live smoke")
        snapshot_text = json.dumps(snapshot, sort_keys=True)
        if "SAZAN Playwright MCP" not in snapshot_text:
            raise RuntimeError("snapshot did not contain the expected page content")

        send(
            process,
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "browser_click",
                    "arguments": {"target": "#danger"},
                },
            },
        )
        denied = wait_for_id(messages, 5)
        error = denied.get("error")
        if not isinstance(error, dict) or "not allowed" not in str(error.get("message", "")):
            raise RuntimeError("proxy did not block browser_click")

        return {
            "status": "passed",
            "provider": "playwright-observe",
            "release": "v0.0.83",
            "tool_count": len(tool_names),
            "navigate": "passed",
            "snapshot": "passed",
            "side_effect_block": "passed",
            "persistent_profile": False,
            "local_network_override": "smoke-only",
        }
    finally:
        try:
            if process.stdin is not None:
                process.stdin.close()
        except BrokenPipeError:
            pass
        try:
            process.terminate()
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        stderr = ""
        if process.stderr is not None:
            stderr = process.stderr.read()
        if process.returncode not in {0, -15, 143} and stderr:
            sys.stderr.write(stderr[-4000:])
        server.shutdown()
        server.server_close()


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
