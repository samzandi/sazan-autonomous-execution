import importlib.util
import json
import pathlib
import unittest


BASE = pathlib.Path(__file__).parents[1] / "agents" / "repo-skill-steward" / "repository-intelligence"
SCRIPT = BASE / "scripts" / "release_readiness.py"
CURRENT = BASE / "release" / "c003_release_readiness_evidence.json"

SPEC = importlib.util.spec_from_file_location("c003_release_readiness", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def verified_gate(label):
    return {
        "status": "verified",
        "evidence": [f"evidence:{label}"],
    }


def ready_package():
    gates = {
        name: verified_gate(name)
        for name in MODULE.REQUIRED_GATES
    }
    return {
        "schema_version": 1,
        "context": "C003",
        "candidate": {
            "name": "fixture stable release",
            "channel": "stable",
        },
        "gates": gates,
        "open_blockers": [],
    }


class C003ReleaseReadinessTests(unittest.TestCase):
    def test_ready_fixture_requires_parent_review_and_never_auto_releases(self):
        result = MODULE.evaluate(ready_package())
        self.assertEqual(result["decision"], "eligible-for-parent-release-review")
        self.assertTrue(result["ready"])
        self.assertFalse(result["auto_release"])
        self.assertTrue(result["parent_release_approval_required"])
        self.assertEqual(result["blockers"], [])

    def test_current_c003_evidence_is_truthfully_blocked(self):
        package = json.loads(CURRENT.read_text(encoding="utf-8"))
        result = MODULE.evaluate(package)
        self.assertEqual(result["decision"], "blocked")
        self.assertFalse(result["ready"])
        self.assertFalse(result["auto_release"])
        self.assertFalse(result["parent_release_approval_required"])
        self.assertTrue(any("codex_runtime" in item for item in result["blockers"]))
        self.assertTrue(any("claude_runtime" in item for item in result["blockers"]))
        self.assertTrue(any("live_provider_parity" in item for item in result["blockers"]))

    def test_missing_gate_is_rejected(self):
        package = ready_package()
        del package["gates"]["privacy"]
        with self.assertRaisesRegex(ValueError, "missing gates"):
            MODULE.evaluate(package)

    def test_pending_gate_blocks(self):
        package = ready_package()
        package["gates"]["codex_runtime"] = {
            "status": "pending",
            "evidence": ["run:pending"],
            "blockers": ["runtime proof pending"],
        }
        result = MODULE.evaluate(package)
        self.assertEqual(result["decision"], "blocked")
        self.assertFalse(result["ready"])

    def test_nonverified_gate_requires_explanation(self):
        package = ready_package()
        package["gates"]["claude_runtime"] = {
            "status": "blocked",
            "evidence": ["run:blocked"],
        }
        result = MODULE.evaluate(package)
        self.assertTrue(any("must explain" in item for item in result["blockers"]))

    def test_verified_gate_cannot_hide_blocker(self):
        package = ready_package()
        package["gates"]["security"]["blockers"] = ["hidden blocker"]
        result = MODULE.evaluate(package)
        self.assertEqual(result["decision"], "blocked")
        self.assertTrue(any("verified gate cannot contain blockers" in item for item in result["blockers"]))

    def test_open_blocker_blocks_otherwise_ready_package(self):
        package = ready_package()
        package["open_blockers"] = ["external approval pending"]
        result = MODULE.evaluate(package)
        self.assertEqual(result["decision"], "blocked")
        self.assertFalse(result["ready"])

    def test_sensitive_marker_blocks(self):
        package = ready_package()
        package["gates"]["verifier"]["evidence"].append("sk-proj-example")
        result = MODULE.evaluate(package)
        self.assertEqual(result["decision"], "blocked")
        self.assertTrue(any("sensitive" in item for item in result["blockers"]))

    def test_deterministic_decision(self):
        one = MODULE.evaluate(ready_package())
        two = MODULE.evaluate(ready_package())
        self.assertEqual(json.dumps(one, sort_keys=True), json.dumps(two, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
