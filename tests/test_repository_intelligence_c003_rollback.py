import importlib.util
import pathlib
import unittest


BASE = pathlib.Path(__file__).parents[1] / "agents" / "repo-skill-steward" / "repository-intelligence" / "scripts"


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, BASE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


ROLLBACK = load("c003_rollback_evidence", "rollback_evidence.py")
LAB = load("c003_rollback_lab", "run_c003_failure_rollback_lab.py")


def receipt():
    return {
        "schema_version": 1,
        "transaction_id": "tx-1",
        "repository_id": "repo_opaque_01",
        "isolation": {
            "mode": "git-worktree",
            "evidence": ["git:worktree"],
        },
        "rollback_point": {
            "revision": "a" * 40,
            "tree_hash": "b" * 40,
            "evidence": ["git:baseline"],
        },
        "mutation": {
            "revision": "c" * 40,
            "evidence": ["git:mutation"],
        },
        "failure": {
            "status": "observed",
            "command": "python3 failing assertion",
            "exit_code": 1,
            "evidence": ["runtime:failed"],
        },
        "rollback": {
            "method": "git-reset-hard-to-verified-revision",
            "target_revision": "a" * 40,
            "evidence": ["git:reset"],
        },
        "post_rollback": {
            "revision": "a" * 40,
            "tree_hash": "b" * 40,
            "clean_worktree": True,
            "parent_workspace_unchanged": True,
            "functional_validation": {
                "status": "passed",
                "evidence": ["runtime:passed"],
            },
        },
        "private_data": {
            "status": "compliant",
            "evidence": ["privacy:opaque-id"],
        },
    }


class C003RollbackEvidenceTests(unittest.TestCase):
    def test_verified_receipt(self):
        result = ROLLBACK.validate(receipt())
        self.assertEqual(result["status"], "verified")
        self.assertTrue(all(result["checks"].values()))

    def test_missing_failure_blocks(self):
        data = receipt()
        data["failure"]["exit_code"] = 0
        result = ROLLBACK.validate(data)
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["checks"]["failure_observed"])

    def test_wrong_target_blocks(self):
        data = receipt()
        data["rollback"]["target_revision"] = "d" * 40
        result = ROLLBACK.validate(data)
        self.assertFalse(result["checks"]["rollback_target_matches"])

    def test_tree_mismatch_blocks(self):
        data = receipt()
        data["post_rollback"]["tree_hash"] = "e" * 40
        result = ROLLBACK.validate(data)
        self.assertFalse(result["checks"]["tree_restored"])

    def test_dirty_worktree_blocks(self):
        data = receipt()
        data["post_rollback"]["clean_worktree"] = False
        result = ROLLBACK.validate(data)
        self.assertFalse(result["checks"]["worktree_clean"])

    def test_parent_workspace_change_blocks(self):
        data = receipt()
        data["post_rollback"]["parent_workspace_unchanged"] = False
        result = ROLLBACK.validate(data)
        self.assertFalse(result["checks"]["parent_workspace_unchanged"])

    def test_sensitive_marker_blocks(self):
        data = receipt()
        data["private_data"]["evidence"].append("sk-proj-example")
        result = ROLLBACK.validate(data)
        self.assertFalse(result["checks"]["no_sensitive_markers"])

    def test_absolute_path_blocks(self):
        data = receipt()
        data["failure"]["evidence"].append("/tmp/private/path")
        result = ROLLBACK.validate(data)
        self.assertFalse(result["checks"]["no_absolute_paths_persisted"])

    def test_real_git_worktree_failure_and_rollback(self):
        result = LAB.run_lab()
        self.assertEqual(result["status"], "verified")
        self.assertTrue(all(result["checks"].values()))
        self.assertNotEqual(result["rollback"]["mutation_revision"], result["rollback"]["rollback_revision"])
        self.assertEqual(result["rollback"]["rollback_revision"], result["rollback"]["final_revision"])
        self.assertEqual(result["rollback"]["rollback_tree"], result["rollback"]["final_tree"])
        self.assertTrue(result["execution"]["parent_workspace_unchanged"])


if __name__ == "__main__":
    unittest.main()
