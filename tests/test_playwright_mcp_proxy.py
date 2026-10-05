import importlib.util
import json
import pathlib
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).parents[1]
MCP_DIR = ROOT / "agents" / "repo-skill-steward" / "mcp"
PROFILE = MCP_DIR / "playwright-observe-profile.json"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "playwright_mcp_proxy",
        MCP_DIR / "playwright_mcp_proxy.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


MCP = load_module()


class PlaywrightMcpProxyTests(unittest.TestCase):
    def test_profile_is_official_pinned_and_observe_only(self):
        profile = MCP.load_profile(PROFILE)
        self.assertEqual(profile["release"], "v0.0.83")
        self.assertEqual(profile["package"], "@playwright/mcp@0.0.83")
        self.assertEqual(profile["mode"], "observe")
        self.assertFalse(profile["allow_local_network"])
        self.assertEqual(profile["additional_caps"], [])

    def test_command_uses_isolation_sandbox_and_no_webmcp(self):
        profile = MCP.load_profile(PROFILE)
        command = MCP.build_upstream_command(profile, "/tmp/sazan-playwright-test")
        joined = " ".join(command)
        self.assertIn("@playwright/mcp@0.0.83", joined)
        self.assertIn("--isolated", command)
        self.assertIn("--sandbox", command)
        self.assertIn("--no-webmcp", command)
        self.assertNotIn("--no-sandbox", command)
        self.assertNotIn("--caps", command)
        self.assertNotIn("@latest", joined)

    def test_side_effect_tool_is_denied(self):
        profile = MCP.load_profile(PROFILE)
        with self.assertRaisesRegex(PermissionError, "not allowed"):
            MCP.validate_tool_call(
                profile,
                "browser_click",
                {"target": "button"},
            )

    def test_explicit_screenshot_filename_is_denied(self):
        profile = MCP.load_profile(PROFILE)
        with self.assertRaisesRegex(PermissionError, "file output"):
            MCP.validate_tool_call(
                profile,
                "browser_take_screenshot",
                {"filename": "proof.png"},
            )

    def test_private_network_navigation_is_denied(self):
        profile = MCP.load_profile(PROFILE)
        with self.assertRaisesRegex(ValueError, "local/private"):
            MCP.validate_tool_call(
                profile,
                "browser_navigate",
                {"url": "http://127.0.0.1:8000/"},
            )

    def test_local_network_can_be_enabled_only_by_runtime_override(self):
        profile = MCP.load_profile(PROFILE)
        MCP.validate_tool_call(
            profile,
            "browser_navigate",
            {"url": "http://127.0.0.1:8000/"},
            allow_local_network_override=True,
        )

    @mock.patch.object(MCP, "_resolved_addresses")
    def test_public_https_navigation_is_allowed(self, resolve):
        resolve.return_value = {MCP.ipaddress.ip_address("93.184.216.34")}
        profile = MCP.load_profile(PROFILE)
        MCP.validate_tool_call(
            profile,
            "browser_navigate",
            {"url": "https://example.com/"},
        )

    def test_tool_inventory_is_filtered(self):
        profile = MCP.load_profile(PROFILE)
        response = {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "tools": [
                    {"name": "browser_snapshot"},
                    {"name": "browser_click"},
                    {"name": "browser_type"},
                ]
            },
        }
        filtered = MCP.filter_tools_response(profile, response)
        self.assertEqual(
            [tool["name"] for tool in filtered["result"]["tools"]],
            ["browser_snapshot"],
        )

    def test_unpinned_package_is_rejected(self):
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        profile["package"] = "@playwright/mcp@latest"
        with self.assertRaisesRegex(ValueError, "pinned"):
            MCP.validate_profile(profile)


if __name__ == "__main__":
    unittest.main()
