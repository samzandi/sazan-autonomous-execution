import importlib.util
import json
import pathlib
import unittest


SCRIPT = pathlib.Path(__file__).parents[1] / "agents" / "repo-skill-steward" / "repository-intelligence" / "scripts" / "run_c002_e2e_lab.py"
SPEC = importlib.util.spec_from_file_location("c002_e2e_lab", SCRIPT)
LAB = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(LAB)


class C002EndToEndLabTests(unittest.TestCase):
    def test_realistic_pipeline_is_verified(self):
        report = LAB.run_lab()
        self.assertEqual(report["status"], "verified")
        self.assertTrue(all(report["checks"].values()))
        self.assertEqual(report["summary"]["matched_contracts"], 3)
        self.assertEqual(report["summary"]["flows"], 1)
        self.assertEqual(report["summary"]["impact_level"], "high")
        self.assertEqual(report["summary"]["orchestration"]["status"], "ready-for-parent-review")

    def test_fallback_cache_and_privacy_are_exercised(self):
        report = LAB.run_lab()
        self.assertEqual(report["summary"]["provider_fallback"]["selected_provider"], "gitingest")
        self.assertTrue(report["summary"]["provider_fallback"]["fallback_used"])
        self.assertEqual(report["summary"]["cache"]["decision"], "hit")
        self.assertTrue(report["summary"]["cache"]["cross_revision_reuse"])
        text = json.dumps(report, sort_keys=True)
        self.assertNotIn("secret-owner", text)
        self.assertNotIn("private-payments-worker", text)

    def test_report_is_deterministic(self):
        self.assertEqual(LAB.run_lab(), LAB.run_lab())


if __name__ == "__main__":
    unittest.main()
