import importlib.util
import json
import pathlib
import unittest


BASE = pathlib.Path(__file__).parents[1] / "agents" / "repo-skill-steward" / "repository-intelligence"
SCRIPTS = BASE / "scripts"
SPEC_PATH = BASE / "reproducibility" / "c003_reproducibility_spec.json"
REPO_ROOT = pathlib.Path(__file__).parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


BUILD = load("c003_repro_build", "build_reproducibility_pack.py")
VALIDATE = load("c003_repro_validate", "validate_reproducibility_pack.py")


class C003ReproducibilityPackTests(unittest.TestCase):
    def test_current_repository_pack_verifies(self):
        pack = BUILD.build(REPO_ROOT, SPEC_PATH)
        report = VALIDATE.validate(pack, REPO_ROOT, SPEC_PATH)
        self.assertEqual(report["status"], "verified")
        self.assertTrue(all(report["checks"].values()))

    def test_pack_is_deterministic_for_same_revision(self):
        one = BUILD.build(REPO_ROOT, SPEC_PATH)
        two = BUILD.build(REPO_ROOT, SPEC_PATH)
        self.assertEqual(
            json.dumps(one, sort_keys=True),
            json.dumps(two, sort_keys=True),
        )

    def test_file_manifest_tamper_blocks(self):
        pack = BUILD.build(REPO_ROOT, SPEC_PATH)
        pack["files"][0]["sha256"] = "0" * 64
        report = VALIDATE.validate(pack, REPO_ROOT, SPEC_PATH)
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["checks"]["file_manifest"])

    def test_revision_tamper_blocks(self):
        pack = BUILD.build(REPO_ROOT, SPEC_PATH)
        pack["source"]["revision"] = "0" * 40
        report = VALIDATE.validate(pack, REPO_ROOT, SPEC_PATH)
        self.assertFalse(report["checks"]["source_revision"])

    def test_fingerprint_tamper_blocks(self):
        pack = BUILD.build(REPO_ROOT, SPEC_PATH)
        pack["pack_fingerprint"] = "0" * 64
        report = VALIDATE.validate(pack, REPO_ROOT, SPEC_PATH)
        self.assertFalse(report["checks"]["pack_fingerprint"])

    def test_sensitive_marker_blocks(self):
        pack = BUILD.build(REPO_ROOT, SPEC_PATH)
        pack["runtime_proofs"][0]["blocker"] = "sk-proj-example"
        pack["pack_fingerprint"] = VALIDATE._fingerprint_without_field(pack)
        report = VALIDATE.validate(pack, REPO_ROOT, SPEC_PATH)
        self.assertFalse(report["checks"]["no_sensitive_markers"])


if __name__ == "__main__":
    unittest.main()
