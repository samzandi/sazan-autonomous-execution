import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "agents" / "repo-skill-steward" / "scripts" / "inventory.py"
CLASSIFY_PATH = ROOT / "agents" / "repo-skill-steward" / "scripts" / "classify.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


inventory = load_module("steward_inventory", INVENTORY_PATH)
classify = load_module("steward_classify", CLASSIFY_PATH)


class EmptyRepositoryTests(unittest.TestCase):
    def test_empty_repository_root_is_not_an_inspection_error(self):
        client = inventory.GitHubClient("dummy")

        def fake_get_json(path):
            raise RuntimeError(
                'GitHub API error 404: {"message":"This repository is empty."}'
            )

        client.get_json = fake_get_json
        self.assertEqual(client.list_contents("owner/empty"), [])

    def test_missing_subpath_still_fails_closed(self):
        client = inventory.GitHubClient("dummy")

        def fake_get_json(path):
            raise RuntimeError(
                'GitHub API error 404: {"message":"This repository is empty."}'
            )

        client.get_json = fake_get_json
        with self.assertRaises(RuntimeError):
            client.list_contents("owner/empty", ".github")


class PrivacyTests(unittest.TestCase):
    def test_private_record_redacts_identity_and_workflow_names(self):
        record = {
            "full_name": "owner/private-app",
            "visibility": "private",
            "archived": False,
            "fork": False,
            "default_branch": "secret-branch",
            "dependency_markers": ["package.json"],
            "container_markers": [],
            "agent_markers": ["AGENTS.md"],
            "skill_surfaces": [],
            "has_tests": True,
            "has_github_actions": True,
            "workflows": ["internal-release.yml"],
            "root_entry_count": 42,
        }
        safe = inventory.public_safe(record)
        self.assertEqual(safe["full_name"], "<private-repository>")
        self.assertNotIn("default_branch", safe)
        self.assertNotIn("workflows", safe)
        self.assertNotIn("dependency_markers", safe)
        self.assertTrue(safe["has_dependencies"])
        self.assertEqual(safe["workflow_count"], 1)


class ClassificationTests(unittest.TestCase):
    def test_fork_with_dependencies_ci_and_tests(self):
        record = {
            "full_name": "owner/fork",
            "archived": False,
            "fork": True,
            "upstream": "upstream/repo",
            "dependency_markers": ["package.json"],
            "container_markers": [],
            "agent_markers": ["AGENTS.md"],
            "skill_surfaces": ["skills"],
            "has_tests": True,
            "has_github_actions": True,
        }
        result = classify.classify_repository(record)
        self.assertIn("upstream-sync", result["strategies"])
        self.assertIn("dependency-update", result["strategies"])
        self.assertIn("github-actions-update", result["strategies"])
        self.assertIn("skill-agent-audit", result["strategies"])
        self.assertEqual(result["verification_profile"], "ci-and-tests")
        self.assertTrue(result["auto_propose"])
        self.assertFalse(result["auto_merge"])

    def test_update_surface_without_tests_requires_manual_gate(self):
        record = {
            "full_name": "owner/app",
            "archived": False,
            "fork": False,
            "upstream": None,
            "dependency_markers": [],
            "container_markers": ["compose.yaml"],
            "agent_markers": [],
            "skill_surfaces": [],
            "has_tests": False,
            "has_github_actions": False,
        }
        result = classify.classify_repository(record)
        self.assertEqual(result["verification_profile"], "manual-review-first")
        self.assertIn("tests-missing", result["gates"])
        self.assertFalse(result["auto_propose"])
        self.assertFalse(result["auto_merge"])


if __name__ == "__main__":
    unittest.main()
