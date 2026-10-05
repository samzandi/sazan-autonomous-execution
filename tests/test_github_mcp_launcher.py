import importlib.util
import json
import os
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[1]
MCP_DIR = ROOT / "agents" / "repo-skill-steward" / "mcp"
PROFILE = MCP_DIR / "github-readonly-profile.json"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "github_mcp_launcher",
        MCP_DIR / "github_mcp_launcher.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


MCP = load_module()


class GitHubMcpLauncherTests(unittest.TestCase):
    def test_canonical_profile_is_valid_and_pinned(self):
        profile = MCP.load_profile(PROFILE)
        self.assertEqual(profile["release"], "v1.14.0")
        self.assertEqual(
            profile["image"],
            "ghcr.io/github/github-mcp-server:v1.14.0",
        )
        self.assertEqual(profile["access_mode"], "read_only")
        self.assertTrue(profile["lockdown"])

    def test_command_enforces_read_only_lockdown_and_approved_toolsets(self):
        profile = MCP.load_profile(PROFILE)
        command = MCP.build_docker_command(profile)
        joined = " ".join(command)

        self.assertIn("GITHUB_READ_ONLY=1", joined)
        self.assertIn("GITHUB_LOCKDOWN_MODE=1", joined)
        self.assertIn(
            "GITHUB_TOOLSETS=context,repos,pull_requests,issues,actions,code_security,secret_protection",
            joined,
        )
        self.assertNotIn("SAZAN_GITHUB_TOKEN", joined)
        self.assertNotIn("all", profile["toolsets"])

    def test_runtime_token_is_in_environment_not_command(self):
        profile = MCP.load_profile(PROFILE)
        token = "test-token-never-log"
        runtime = MCP.prepare_runtime_environment(
            profile,
            {"SAZAN_GITHUB_TOKEN": token},
        )
        command = MCP.build_docker_command(profile)

        self.assertEqual(runtime["GITHUB_PERSONAL_ACCESS_TOKEN"], token)
        self.assertNotIn(token, " ".join(command))

    def test_missing_token_fails_closed(self):
        profile = MCP.load_profile(PROFILE)
        with self.assertRaisesRegex(RuntimeError, "required token"):
            MCP.prepare_runtime_environment(profile, {})

    def test_all_toolset_is_rejected(self):
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        profile["toolsets"] = ["all"]
        with self.assertRaisesRegex(ValueError, "forbidden"):
            MCP.validate_profile(profile)

    def test_write_mode_is_rejected(self):
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        profile["access_mode"] = "read_write"
        with self.assertRaisesRegex(ValueError, "read_only"):
            MCP.validate_profile(profile)

    def test_unpinned_image_is_rejected(self):
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        profile["image"] = "ghcr.io/github/github-mcp-server:latest"
        with self.assertRaisesRegex(ValueError, "pinned"):
            MCP.validate_profile(profile)

    def test_profile_file_validation_uses_no_external_dependency(self):
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "profile.json"
            path.write_text(json.dumps(profile), encoding="utf-8")
            loaded = MCP.load_profile(path)
        self.assertEqual(loaded["id"], "github-readonly")


if __name__ == "__main__":
    unittest.main()
