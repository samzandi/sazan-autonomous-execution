#!/usr/bin/env python3
"""Live documentation proof for the governed Context7 MCP provider."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any


MCP_DIR = Path(__file__).resolve().parent
PROXY = MCP_DIR / "context7_mcp_proxy.py"
PROTOCOL_VERSION = "2025-06-18"


def send(process: subprocess.Popen[str], message: dict[str, Any]) -> None:
    assert process.stdin is not None
    process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
    process.stdin.flush()


def wait_for_id(
    messages: "queue.Queue[dict[str, Any]]",
    response_id: int,
    timeout: float = 120.0,
) -> dict[str, Any]:
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


def result_text(message: dict[str, Any]) -> str:
    if "error" in message:
        raise RuntimeError(f"MCP call failed: {message['error']}")
    result = message.get("result")
    if not isinstance(result, dict) or result.get("isError") is True:
        raise RuntimeError("MCP tool returned an error")
    content = result.get("content")
    if not isinstance(content, list):
        raise RuntimeError("MCP tool returned no content")
    texts = [
        str(item.get("text", ""))
        for item in content
        if isinstance(item, dict) and item.get("type") == "text"
    ]
    out = "\n".join(texts).strip()
    if not out:
        raise RuntimeError("MCP tool returned empty text")
    return out


def run() -> dict[str, Any]:
    env = dict(os.environ)
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
    threading.Thread(target=reader, args=(process, messages), daemon=True).start()

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
                    "clientInfo": {"name": "sazan-context7-smoke", "version": "1.0.0"},
                },
            },
        )
        initialized = wait_for_id(messages, 1)
        if "error" in initialized:
            raise RuntimeError(f"Context7 initialize failed: {initialized['error']}")

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
        names = {
            str(tool.get("name"))
            for tool in tools
            if isinstance(tool, dict) and tool.get("name")
        }
        if names != {"resolve-library-id", "query-docs"}:
            raise RuntimeError(f"unexpected Context7 tool surface: {sorted(names)}")

        send(
            process,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "resolve-library-id",
                    "arguments": {
                        "libraryName": "Next.js",
                        "query": "Find the official Next.js documentation for middleware redirects.",
                    },
                },
            },
        )
        resolved = result_text(wait_for_id(messages, 3))
        if "next" not in resolved.lower():
            raise RuntimeError("Context7 library resolution did not return a Next.js match")

        send(
            process,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "query-docs",
                    "arguments": {
                        "libraryId": "/vercel/next.js",
                        "query": "How do middleware redirects work?",
                    },
                },
            },
        )
        docs = result_text(wait_for_id(messages, 4))
        if len(docs) < 80:
            raise RuntimeError("Context7 documentation response was unexpectedly short")

        send(
            process,
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "query-docs",
                    "arguments": {
                        "libraryId": "/vercel/next.js",
                        "query": "inspect sk-proj-1234567890abcdefghijk",
                    },
                },
            },
        )
        denied = wait_for_id(messages, 5)
        error = denied.get("error")
        if not isinstance(error, dict) or "credential" not in str(error.get("message", "")):
            raise RuntimeError("Context7 guard did not block a credential-like query")

        return {
            "status": "passed",
            "provider": "context7-readonly",
            "release": "@upstash/context7-mcp@4.1.1",
            "tool_count": len(names),
            "resolve_library": "passed",
            "query_docs": "passed",
            "credential_guard": "passed",
            "api_key_configured": bool(os.environ.get("SAZAN_CONTEXT7_API_KEY", "").strip()),
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
        if process.stderr is not None and process.returncode not in {0, -15, 143}:
            sys.stderr.write(process.stderr.read()[-4000:])


def main() -> int:
    print(json.dumps(run(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
