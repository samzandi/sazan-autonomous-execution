import importlib.util
import json
import pathlib
import tempfile
import unittest


SCRIPT = pathlib.Path(__file__).parents[1] / "agents" / "repo-skill-steward" / "repository-intelligence" / "scripts" / "build_rebuild_spec.py"
SPEC = importlib.util.spec_from_file_location("build_rebuild_spec", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def base_input():
    return {
        "source": {
            "repository": "example/repo",
            "revision": "abc123",
            "visibility": "public",
        },
        "evidence": [
            {
                "id": "E1",
                "source": "tests/test_checkout.py",
                "statement": "Checkout returns a normalized total.",
            },
            {
                "id": "E2",
                "source": "CodeGraph dependency graph",
                "statement": "handle_checkout calls calculate_total.",
            },
        ],
        "sections": {
            "objective": [
                {
                    "state": "observed",
                    "text": "Provide a checkout total.",
                    "evidence": ["E1"],
                }
            ],
            "flows": [
                {
                    "state": "observed",
                    "text": "Checkout delegates total calculation to the service layer.",
                    "evidence": ["E2"],
                }
            ],
            "acceptance": [
                {
                    "state": "observed",
                    "text": "Given valid line items, checkout returns the normalized total.",
                    "evidence": ["E1"],
                }
            ],
            "inferences": [
                {
                    "state": "inferred",
                    "text": "Keep the API and calculation concerns in separate modules.",
                    "evidence": ["E2"],
                    "rationale": "The observed call crosses the API and service module boundary.",
                }
            ],
            "unknowns": [
                {
                    "state": "unknown",
                    "text": "Production persistence requirements are not established.",
                    "evidence": [],
                }
            ],
        },
    }


class RebuildSpecTests(unittest.TestCase):
    def test_normalization_is_deterministic(self):
        one = MODULE.normalize(base_input())
        two = MODULE.normalize(base_input())
        self.assertEqual(one, two)
        self.assertEqual(MODULE.render_markdown(one), MODULE.render_markdown(two))

    def test_observed_claim_requires_evidence(self):
        data = base_input()
        data["sections"]["objective"][0]["evidence"] = []
        with self.assertRaisesRegex(ValueError, "observed claim requires evidence"):
            MODULE.normalize(data)

    def test_inferred_claim_requires_rationale(self):
        data = base_input()
        data["sections"]["inferences"][0]["rationale"] = ""
        with self.assertRaisesRegex(ValueError, "inferred claim requires rationale"):
            MODULE.normalize(data)

    def test_unknown_claim_cannot_present_evidence_as_proof(self):
        data = base_input()
        data["sections"]["unknowns"][0]["evidence"] = ["E1"]
        with self.assertRaisesRegex(ValueError, "unknown claim must not cite evidence as proof"):
            MODULE.normalize(data)

    def test_unknown_evidence_id_is_rejected(self):
        data = base_input()
        data["sections"]["flows"][0]["evidence"] = ["MISSING"]
        with self.assertRaisesRegex(ValueError, "unknown evidence IDs"):
            MODULE.normalize(data)

    def test_required_sections(self):
        data = base_input()
        data["sections"]["acceptance"] = []
        with self.assertRaisesRegex(ValueError, "acceptance criterion"):
            MODULE.normalize(data)

    def test_cli_artifacts_have_expected_markers(self):
        spec = MODULE.normalize(base_input())
        rendered = MODULE.render_markdown(spec)
        self.assertIn("# Clean-room Rebuild Specification", rendered)
        self.assertIn("**OBSERVED**", rendered)
        self.assertIn("**INFERRED**", rendered)
        self.assertIn("**UNKNOWN**", rendered)
        self.assertIn("## Evidence ledger", rendered)


if __name__ == "__main__":
    unittest.main()
