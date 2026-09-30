import importlib.util
import pathlib
import unittest


SCRIPT = pathlib.Path(__file__).parents[1] / "agents" / "repo-skill-steward" / "repository-intelligence" / "scripts" / "validate_c003_claude_runtime_proof.py"
SPEC = importlib.util.spec_from_file_location("c003_claude_runtime_validator", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def baseline():
    return {
        "status": "verified",
        "checks": {
            "multi_repo_verified": True,
            "contracts_matched": True,
            "flow_verified": True,
            "diff_impact_high": True,
            "cache_cross_revision_hit": True,
            "provider_fallback_exercised": True,
            "strict_budget_measured": True,
            "promotion_ready_for_parent_review": True,
            "no_auto_promotion": True,
            "private_identity_redacted": True,
        },
        "summary": {"orchestration": {"status": "ready-for-parent-review"}},
    }


def metadata():
    return {
        "head_sha": "a" * 40,
        "model": "claude-opus-5",
        "expected_claude_code_version": "2.1.286",
        "action_commit": "12dd8d74c712f5f3669365b2369b558c495b1104",
        "baseline_sha256": "fixture-sha",
    }


def claude_output():
    return {
        "schema_version": 1,
        "status": "verified",
        "runtime": {
            "name": "claude-code",
            "repository_head": "a" * 40,
            "model": "claude-opus-5",
            "cli_version": "2.1.286",
        },
        "checks": {
            "repository_head_matches": True,
            "c002_end_to_end_passed": True,
            "c002_orchestration_passed": True,
            "parent_review_gate_observed": True,
            "auto_promotion_disabled": True,
            "private_identity_redaction_observed": True,
            "workspace_unchanged": True,
        },
        "evidence": ["git-head", "tests", "baseline", "gate"],
        "blockers": [],
    }


class C003ClaudeRuntimeProofValidatorTests(unittest.TestCase):
    def test_verified_fixture(self):
        report = MODULE.validate(claude_output(), baseline(), metadata())
        self.assertEqual(report["status"], "verified")
        self.assertTrue(all(report["checks"].values()))

    def test_wrong_head_blocks(self):
        output = claude_output()
        output["runtime"]["repository_head"] = "b" * 40
        report = MODULE.validate(output, baseline(), metadata())
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["checks"]["repository_head_matches"])

    def test_wrong_cli_version_blocks(self):
        output = claude_output()
        output["runtime"]["cli_version"] = "2.1.200"
        report = MODULE.validate(output, baseline(), metadata())
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["checks"]["cli_version_matches"])

    def test_sensitive_marker_blocks(self):
        output = claude_output()
        output["evidence"].append("sk-ant-example")
        report = MODULE.validate(output, baseline(), metadata())
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["checks"]["no_sensitive_markers"])


if __name__ == "__main__":
    unittest.main()
