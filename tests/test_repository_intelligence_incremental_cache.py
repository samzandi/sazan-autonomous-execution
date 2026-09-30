import importlib.util
import json
import pathlib
import tempfile
import unittest


BASE = pathlib.Path(__file__).parents[1] / "agents" / "repo-skill-steward" / "repository-intelligence" / "scripts"


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, BASE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


CACHE = load("incremental_cache", "incremental_cache.py")


def descriptor(revision="r1", **overrides):
    data = {
        "schema_version": 1,
        "repository_id": "repo_public_fixture",
        "revision": revision,
        "stage": "L2-semantic-graph",
        "provider": "codegraph-0.20.1",
        "provider_version": "0.20.1",
        "provider_contract": "semantic-graph-v1",
        "stage_input_fingerprint": "input-a",
        "policy_fingerprint": "policy-a",
        "implementation_fingerprint": "impl-a",
        "dependencies": [
            {"name": "context", "fingerprint": "ctx-a"},
            {"name": "provider-route", "fingerprint": "route-a"},
        ],
        "reuse_policy": "fingerprint-stable-cross-revision",
    }
    data.update(overrides)
    return data


class IncrementalCacheTests(unittest.TestCase):
    def test_same_descriptor_hits(self):
        entry = CACHE.create_entry(descriptor(), "result-a")
        report = CACHE.evaluate(entry, descriptor())
        self.assertEqual(report["decision"], "hit")
        self.assertFalse(report["cross_revision_reuse"])

    def test_cross_revision_hit_requires_stable_fingerprints(self):
        entry = CACHE.create_entry(descriptor("r1"), "result-a")
        report = CACHE.evaluate(entry, descriptor("r2"))
        self.assertEqual(report["decision"], "hit")
        self.assertTrue(report["cross_revision_reuse"])

    def test_same_revision_policy_invalidates_revision_change(self):
        entry = CACHE.create_entry(
            descriptor("r1", reuse_policy="same-revision-only"),
            "result-a",
        )
        report = CACHE.evaluate(
            entry,
            descriptor("r2", reuse_policy="same-revision-only"),
        )
        self.assertEqual(report["decision"], "miss")
        self.assertIn("revision-changed-under-same-revision-policy", report["reasons"])

    def test_stage_input_change_invalidates(self):
        entry = CACHE.create_entry(descriptor(), "result-a")
        report = CACHE.evaluate(
            entry,
            descriptor(stage_input_fingerprint="input-b"),
        )
        self.assertEqual(report["decision"], "miss")
        self.assertIn("stage_input_fingerprint-changed", report["reasons"])

    def test_provider_version_change_invalidates(self):
        entry = CACHE.create_entry(descriptor(), "result-a")
        report = CACHE.evaluate(
            entry,
            descriptor(provider_version="0.21.0"),
        )
        self.assertIn("provider_version-changed", report["reasons"])

    def test_contract_change_invalidates(self):
        entry = CACHE.create_entry(descriptor(), "result-a")
        report = CACHE.evaluate(
            entry,
            descriptor(provider_contract="semantic-graph-v2"),
        )
        self.assertIn("provider_contract-changed", report["reasons"])

    def test_policy_change_invalidates(self):
        entry = CACHE.create_entry(descriptor(), "result-a")
        report = CACHE.evaluate(
            entry,
            descriptor(policy_fingerprint="policy-b"),
        )
        self.assertIn("policy_fingerprint-changed", report["reasons"])

    def test_implementation_change_invalidates(self):
        entry = CACHE.create_entry(descriptor(), "result-a")
        report = CACHE.evaluate(
            entry,
            descriptor(implementation_fingerprint="impl-b"),
        )
        self.assertIn("implementation_fingerprint-changed", report["reasons"])

    def test_dependency_change_invalidates(self):
        entry = CACHE.create_entry(descriptor(), "result-a")
        changed = descriptor()
        changed["dependencies"][0]["fingerprint"] = "ctx-b"
        report = CACHE.evaluate(entry, changed)
        self.assertIn("dependencies-changed", report["reasons"])

    def test_repository_change_invalidates(self):
        entry = CACHE.create_entry(descriptor(), "result-a")
        report = CACHE.evaluate(
            entry,
            descriptor(repository_id="other-repo"),
        )
        self.assertIn("repository_id-changed", report["reasons"])

    def test_corrupt_cache_key_invalidates(self):
        entry = CACHE.create_entry(descriptor(), "result-a")
        entry["cache_key"] = "cache_corrupt"
        report = CACHE.evaluate(entry, descriptor())
        self.assertIn("stored-cache-key-integrity-failed", report["reasons"])

    def test_missing_result_fingerprint_invalidates(self):
        entry = CACHE.create_entry(descriptor(), "result-a")
        entry["result_fingerprint"] = ""
        report = CACHE.evaluate(entry, descriptor())
        self.assertIn("missing-result-fingerprint", report["reasons"])

    def test_dependency_order_does_not_change_key(self):
        one = descriptor()
        two = descriptor()
        two["dependencies"] = list(reversed(two["dependencies"]))
        self.assertEqual(CACHE.cache_key(one), CACHE.cache_key(two))

    def test_revision_not_in_cross_revision_semantic_key(self):
        self.assertEqual(CACHE.cache_key(descriptor("r1")), CACHE.cache_key(descriptor("r2")))

    def test_dependency_fingerprint_is_deterministic(self):
        one = [
            {"name": "b", "fingerprint": "2"},
            {"name": "a", "fingerprint": "1"},
        ]
        two = list(reversed(one))
        self.assertEqual(CACHE.dependency_fingerprint(one), CACHE.dependency_fingerprint(two))

    def test_duplicate_dependency_names_rejected(self):
        bad = descriptor()
        bad["dependencies"] = [
            {"name": "same", "fingerprint": "a"},
            {"name": "same", "fingerprint": "b"},
        ]
        with self.assertRaisesRegex(ValueError, "duplicate dependency"):
            CACHE.cache_key(bad)

    def test_file_fingerprint(self):
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "artifact.bin"
            path.write_bytes(b"abc")
            one = CACHE.fingerprint_file(path)
            path.write_bytes(b"abd")
            two = CACHE.fingerprint_file(path)
            self.assertNotEqual(one, two)

    def test_private_source_not_required(self):
        d = descriptor(repository_id="repo_opaque_01")
        entry = CACHE.create_entry(d, "result-a", evidence=["cache:test"])
        text = json.dumps(entry, sort_keys=True)
        self.assertNotIn("github.com/", text)
        self.assertNotIn("secret-owner", text)

    def test_result_is_deterministic(self):
        entry1 = CACHE.create_entry(
            descriptor(),
            "result-a",
            artifacts=[
                {"name": "b", "fingerprint": "2"},
                {"name": "a", "fingerprint": "1"},
            ],
            evidence=["e2", "e1"],
        )
        entry2 = CACHE.create_entry(
            descriptor(),
            "result-a",
            artifacts=[
                {"name": "a", "fingerprint": "1"},
                {"name": "b", "fingerprint": "2"},
            ],
            evidence=["e1", "e2"],
        )
        self.assertEqual(entry1, entry2)


if __name__ == "__main__":
    unittest.main()
