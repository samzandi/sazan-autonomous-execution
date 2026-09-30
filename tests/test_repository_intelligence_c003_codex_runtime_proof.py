import importlib.util
import pathlib
import unittest


SCRIPT = pathlib.Path(__file__).parents[1] / "agents" / "repo-skill-steward" / "repository-intelligence" / "scripts" / "validate_c003_codex_runtime_proof.py"
SPEC = importlib.util.spec_from_file_location("c003_codex_runtime_validator", SCRIPT)
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
        "summary": {
            "orchestration": {
                "status": "ready-for-parent-review",
            }
        },
    }


def metadata():
    return {
        "head_sha": "a" * 40,
        "model": "gpt-5.6-sol",
        "codex_cli_version": "codex-cli 0.159.2",
        "expected_codex_version": "0.159.2",
        "action_commit": "86365089eb2b84e0a8fb0717b304f8bdcb13b20e",
        "baseline_sha256": "fixture-sha",
    }


def codex_output():
    return {
        "schema_version": 1,
        "status": "verified",
        "runtime": {
            "name": "codex",
            "repository_head": "a" * 40,
            "model": "gpt-5.6-sol",
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


class C003CodexRuntimeProofValidatorTests(unittest.TestCase):
    def test_verified_fixture(self):
        report = MODULE.validate(codex_output(), baseline(), metadata())
        self.assertEqual(report["status"], "verified")
        self.assertTrue(all(report["checks"].values()))

    def test_wrong_head_blocks(self):
        output = codex_output()
        output["runtime"]["repository_head"] = "b" * 40
        report = MODULE.validate(output, baseline(), metadata())
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["checks"]["repository_head_matches"])

    def test_auto_promotion_claim_blocks(self):
        output = codex_output()
        output["checks"]["auto_promotion_disabled"] = False
        report = MODULE.validate(output, baseline(), metadata())
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["checks"]["parent_review_boundary"])

    def test_sensitive_marker_blocks(self):
        output = codex_output()
        output["evidence"].append("sk-proj-example")
        report = MODULE.validate(output, baseline(), metadata())
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["checks"]["no_sensitive_markers"])

    def test_cli_version_mismatch_blocks(self):
        meta = metadata()
        meta["codex_cli_version"] = "codex-cli 0.160.0"
        report = MODULE.validate(codex_output(), baseline(), meta)
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["checks"]["cli_version_matches"])


if __name__ == "__main__":
    unittest.main()
