import importlib.util
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
MCP_DIR = ROOT / "agents" / "repo-skill-steward" / "mcp"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "github_mcp_live_smoke",
        MCP_DIR / "github_mcp_live_smoke.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


SMOKE = load_module()


class GitHubMcpLiveSmokeTests(unittest.TestCase):
    def test_parse_jsonrpc_lines_ignores_non_json_noise(self):
        output = (
            "log line\n"
            '{"jsonrpc":"2.0","id":1,"result":{"ok":true}}\n'
            "not-json\n"
        )
        responses = SMOKE.parse_jsonrpc_lines(output)
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0]["id"], 1)

    def test_inventory_requires_read_tool_and_rejects_known_write_tool(self):
        good = {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "tools": [
                    {
                        "name": "get_file_contents",
                        "annotations": {"readOnlyHint": True},
                    }
                ]
            },
        }
        self.assertEqual(SMOKE.verify_tool_inventory(good), ["get_file_contents"])

        bad = json.loads(json.dumps(good))
        bad["result"]["tools"].append(
            {"name": "create_issue", "annotations": {"readOnlyHint": False}}
        )
        with self.assertRaisesRegex(RuntimeError, "non-read-only|write-capable"):
            SMOKE.verify_tool_inventory(bad)

    def test_read_call_rejects_tool_error(self):
        with self.assertRaisesRegex(RuntimeError, "tool error"):
            SMOKE.verify_read_call(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "result": {"isError": True, "content": [{"type": "text", "text": "x"}]},
                }
            )

    def test_payload_contains_initialize_list_and_read_call(self):
        payload = SMOKE.build_messages(
            "samzandi",
            "sazan-autonomous-execution",
            "main",
            ".sazan/guardian.yml",
        )
        messages = [json.loads(line) for line in payload.splitlines()]
        self.assertEqual(messages[0]["method"], "initialize")
        self.assertEqual(messages[2]["method"], "tools/list")
        self.assertEqual(messages[3]["method"], "tools/call")
        self.assertEqual(messages[3]["params"]["name"], "get_file_contents")

    def test_redaction_removes_secret(self):
        token = "temporary-secret"
        self.assertNotIn(token, SMOKE.redact(f"error {token}", token))


if __name__ == "__main__":
    unittest.main()
