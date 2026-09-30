import importlib.util
import pathlib
import unittest


SCRIPT = pathlib.Path(__file__).parents[1] / "agents" / "repo-skill-steward" / "repository-intelligence" / "scripts" / "evaluate_promotion.py"
SPEC = importlib.util.spec_from_file_location("evaluate_promotion", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def package():
    return {
        "schema_version": 1,
        "candidate": {
            "name": "example-capability",
            "source": "example/repo",
            "revision": "abc123",
            "integration_mode": "embedded-core",
        },
        "checks": {
            "provenance": {
                "status": "verified",
                "evidence": ["canonical repo + immutable revision"],
            },
            "license": {
                "status": "compatible",
                "spdx": "MIT",
                "evidence": ["canonical LICENSE"],
            },
            "security": {
                "status": "passed",
                "evidence": ["security review S1"],
            },
            "lab": {
                "status": "passed",
                "evidence": ["CI run 123"],
            },
            "capability_delta": {
                "status": "new",
                "evidence": ["delta review D1"],
            },
            "rollback": {
                "status": "verified",
                "evidence": ["revert commit / disable adapter"],
            },
            "private_data": {
                "status": "compliant",
                "evidence": ["no private data persisted"],
            },
            "verifier": {
                "status": "verified",
                "evidence": ["verifier report V1"],
            },
        },
        "constraints": [],
    }


class PromotionGateTests(unittest.TestCase):
    def test_clean_candidate_is_eligible_but_never_auto_promoted(self):
        result = MODULE.evaluate(package())
        self.assertEqual(result["decision"], "eligible-for-parent-promotion")
        self.assertFalse(result["auto_promote"])
        self.assertTrue(result["parent_approval_required"])

    def test_unknown_license_blocks_embedded_promotion(self):
        data = package()
        data["checks"]["license"] = {
            "status": "unknown",
            "evidence": ["no canonical license detected"],
        }
        result = MODULE.evaluate(data)
        self.assertEqual(result["decision"], "pending-evidence")

    def test_unknown_license_can_only_be_reference_only_with_constraint(self):
        data = package()
        data["candidate"]["integration_mode"] = "reference-only"
        data["checks"]["license"] = {
            "status": "unknown",
            "evidence": ["no canonical license detected"],
        }
        data["checks"]["capability_delta"]["status"] = "reference-value"
        result = MODULE.evaluate(data)
        self.assertEqual(result["decision"], "eligible-with-constraints")
        self.assertTrue(any("license unknown" in x for x in result["constraints"]))

    def test_noncommercial_core_is_rejected(self):
        data = package()
        data["checks"]["license"] = {
            "status": "noncommercial",
            "evidence": ["PolyForm Noncommercial license"],
        }
        result = MODULE.evaluate(data)
        self.assertEqual(result["decision"], "rejected")

    def test_noncommercial_reference_only_is_allowed(self):
        data = package()
        data["candidate"]["integration_mode"] = "reference-only"
        data["checks"]["license"] = {
            "status": "noncommercial",
            "evidence": ["PolyForm Noncommercial license"],
        }
        data["checks"]["capability_delta"]["status"] = "reference-value"
        result = MODULE.evaluate(data)
        self.assertEqual(result["decision"], "eligible-for-parent-promotion")

    def test_failed_security_is_rejected(self):
        data = package()
        data["checks"]["security"]["status"] = "failed"
        result = MODULE.evaluate(data)
        self.assertEqual(result["decision"], "rejected")

    def test_failed_lab_is_rejected(self):
        data = package()
        data["checks"]["lab"]["status"] = "failed"
        result = MODULE.evaluate(data)
        self.assertEqual(result["decision"], "rejected")

    def test_missing_rollback_is_pending(self):
        data = package()
        data["checks"]["rollback"]["status"] = "missing"
        result = MODULE.evaluate(data)
        self.assertEqual(result["decision"], "pending-evidence")

    def test_verified_rollback_without_evidence_is_pending(self):
        data = package()
        data["checks"]["rollback"]["evidence"] = []
        result = MODULE.evaluate(data)
        self.assertEqual(result["decision"], "pending-evidence")
        self.assertTrue(any("rollback" in reason for reason in result["reasons"]))

    def test_duplicate_core_capability_is_rejected(self):
        data = package()
        data["checks"]["capability_delta"]["status"] = "duplicate"
        result = MODULE.evaluate(data)
        self.assertEqual(result["decision"], "rejected")

    def test_verifier_constraints_propagate(self):
        data = package()
        data["checks"]["verifier"] = {
            "status": "verified-with-constraints",
            "evidence": ["verifier report V2"],
            "constraints": ["operate only in isolated subprocess"],
        }
        result = MODULE.evaluate(data)
        self.assertEqual(result["decision"], "eligible-with-constraints")
        self.assertIn("operate only in isolated subprocess", result["constraints"])

    def test_private_data_violation_is_rejected(self):
        data = package()
        data["checks"]["private_data"]["status"] = "violation"
        result = MODULE.evaluate(data)
        self.assertEqual(result["decision"], "rejected")

    def test_missing_evidence_for_passed_gate_is_pending(self):
        data = package()
        data["checks"]["provenance"]["evidence"] = []
        result = MODULE.evaluate(data)
        self.assertEqual(result["decision"], "pending-evidence")


if __name__ == "__main__":
    unittest.main()
