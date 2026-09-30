import importlib.util
import json
import pathlib
import unittest


SCRIPT = pathlib.Path(__file__).parents[1] / "agents" / "repo-skill-steward" / "repository-intelligence" / "scripts" / "runtime_contract_parity.py"
SPEC = importlib.util.spec_from_file_location("c003_runtime_parity", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


COMMON = {
    "repository_head_matches": True,
    "model_matches": True,
    "cli_version_matches": True,
    "baseline_verified": True,
    "parent_review_boundary": True,
    "focused_tests_reported": True,
    "private_identity_redaction": True,
    "workspace_unchanged": True,
    "evidence_present": True,
    "no_sensitive_markers": True,
}


def report(name, model, cli, head="a" * 40, baseline_sha="b" * 64):
    runtime = {
        "name": name,
        "repository_head": head,
        "model": model,
        "action_commit": "c" * 40,
    }
    if name == "codex":
        runtime["codex_cli_version"] = cli
    else:
        runtime["cli_version"] = cli
    return {
        "schema_version": 1,
        "context": "C003",
        "milestone": f"{name}-runtime-proof",
        "status": "verified",
        "checks": dict(COMMON),
        "runtime": runtime,
        "baseline": {
            "status": "verified",
            "sha256": baseline_sha,
            "orchestration_status": "ready-for-parent-review",
        },
        "blockers": [],
    }


def fixtures():
    return (
        report("codex", "gpt-5.6-sol", "0.159.2"),
        report("claude-code", "claude-opus-5", "2.1.286"),
    )


class RuntimeContractParityTests(unittest.TestCase):
    def test_verified_parity(self):
        codex, claude = fixtures()
        result = MODULE.compare(codex, claude, expected_head="a" * 40)
        self.assertEqual(result["status"], "verified")
        self.assertTrue(all(result["parity_checks"].values()))
        self.assertEqual(result["blockers"], [])

    def test_head_mismatch_blocks(self):
        codex, claude = fixtures()
        claude["runtime"]["repository_head"] = "d" * 40
        result = MODULE.compare(codex, claude)
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["parity_checks"]["same_repository_head"])

    def test_baseline_mismatch_blocks(self):
        codex, claude = fixtures()
        claude["baseline"]["sha256"] = "e" * 64
        result = MODULE.compare(codex, claude)
        self.assertFalse(result["parity_checks"]["same_baseline"])
        self.assertEqual(result["status"], "blocked")

    def test_failed_provider_invariant_blocks(self):
        codex, claude = fixtures()
        codex["checks"]["workspace_unchanged"] = False
        result = MODULE.compare(codex, claude)
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("workspace_unchanged" in item for item in result["blockers"]))

    def test_provider_blocker_blocks(self):
        codex, claude = fixtures()
        claude["blockers"] = ["external quota"]
        result = MODULE.compare(codex, claude)
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("contains blockers" in item for item in result["blockers"]))

    def test_sensitive_marker_blocks(self):
        codex, claude = fixtures()
        codex["note"] = "sk-proj-example"
        result = MODULE.compare(codex, claude)
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("sensitive marker" in item for item in result["blockers"]))

    def test_expected_head_mismatch_blocks(self):
        codex, claude = fixtures()
        result = MODULE.compare(codex, claude, expected_head="f" * 40)
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["parity_checks"]["expected_head_matches"])

    def test_output_is_deterministic(self):
        one = MODULE.compare(*fixtures(), expected_head="a" * 40)
        two = MODULE.compare(*fixtures(), expected_head="a" * 40)
        self.assertEqual(
            json.dumps(one, sort_keys=True),
            json.dumps(two, sort_keys=True),
        )


if __name__ == "__main__":
    unittest.main()
