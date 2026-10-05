import importlib.util
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
MCP_DIR = ROOT / "agents" / "repo-skill-steward" / "mcp"
PROFILE = MCP_DIR / "context7-readonly-profile.json"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "context7_mcp_proxy",
        MCP_DIR / "context7_mcp_proxy.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


MCP = load_module()


class Context7McpProxyTests(unittest.TestCase):
    def test_profile_is_official_pinned_and_read_only(self):
        profile = MCP.load_profile(PROFILE)
        self.assertEqual(profile["package"], "@upstash/context7-mcp@4.1.1")
        self.assertEqual(
            set(profile["allowed_tools"]),
            {"resolve-library-id", "query-docs"},
        )
        self.assertEqual(profile["action_authority"], "disabled")
        self.assertEqual(profile["destructive_authority"], "disabled")

    def test_command_is_pinned_and_uses_stdio(self):
        profile = MCP.load_profile(PROFILE)
        command = MCP.build_upstream_command(profile)
        joined = " ".join(command)
        self.assertIn("@upstash/context7-mcp@4.1.1", joined)
        self.assertIn("--transport stdio", joined)
        self.assertNotIn("@latest", joined)
        self.assertNotIn("--api-key", joined)

    def test_runtime_environment_does_not_forward_unrelated_secrets(self):
        profile = MCP.load_profile(PROFILE)
        runtime = MCP.prepare_runtime_environment(
            profile,
            {
                "PATH": "/bin",
                "HOME": "/tmp/home",
                "SAZAN_CONTEXT7_API_KEY": "ctx7-test-only",
                "GITHUB_TOKEN": "do-not-forward",
                "VERCEL_TOKEN": "do-not-forward",
            },
        )
        self.assertEqual(runtime["CONTEXT7_API_KEY"], "ctx7-test-only")
        self.assertNotIn("SAZAN_CONTEXT7_API_KEY", runtime)
        self.assertNotIn("GITHUB_TOKEN", runtime)
        self.assertNotIn("VERCEL_TOKEN", runtime)
        self.assertEqual(runtime["OTEL_SDK_DISABLED"], "true")

    def test_secret_like_query_is_blocked(self):
        profile = MCP.load_profile(PROFILE)
        with self.assertRaisesRegex(PermissionError, "credential"):
            MCP.validate_tool_call(
                profile,
                "query-docs",
                {
                    "libraryId": "/vercel/next.js",
                    "query": "debug this token sk-proj-1234567890abcdefghijk",
                },
            )

    def test_unapproved_tool_is_blocked(self):
        profile = MCP.load_profile(PROFILE)
        with self.assertRaisesRegex(PermissionError, "not allowed"):
            MCP.validate_tool_call(profile, "write-docs", {"query": "x"})

    def test_library_id_must_be_context7_shape(self):
        profile = MCP.load_profile(PROFILE)
        with self.assertRaisesRegex(ValueError, "libraryId"):
            MCP.validate_tool_call(
                profile,
                "query-docs",
                {"libraryId": "nextjs", "query": "middleware redirects"},
            )

    def test_tool_inventory_is_filtered_and_read_only(self):
        profile = MCP.load_profile(PROFILE)
        response = {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "tools": [
                    {
                        "name": "resolve-library-id",
                        "annotations": {"readOnlyHint": True},
                    },
                    {
                        "name": "query-docs",
                        "annotations": {"readOnlyHint": True},
                    },
                    {
                        "name": "unexpected-write",
                        "annotations": {"readOnlyHint": False},
                    },
                ]
            },
        }
        filtered = MCP.filter_tools_response(profile, response)
        self.assertEqual(
            [tool["name"] for tool in filtered["result"]["tools"]],
            ["resolve-library-id", "query-docs"],
        )

    def test_unpinned_package_is_rejected(self):
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        profile["package"] = "@upstash/context7-mcp@latest"
        with self.assertRaisesRegex(ValueError, "pinned"):
            MCP.validate_profile(profile)


if __name__ == "__main__":
    unittest.main()
