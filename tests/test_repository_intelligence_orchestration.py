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


ENV = load("evidence_envelope", "evidence_envelope.py")
ORCH = load("orchestrator", "orchestrate_repository_intelligence.py")


def manifest(visibility="local-fixture", mode="analysis"):
    return {
        "run_id": "run-001",
        "purpose": "fixture capability",
        "mode": mode,
        "target": {
            "source": "fixture/repo",
            "revision": "abc123",
            "visibility": visibility,
        },
        "privacy": {"persist_private_identity": False},
        "budgets": {
            "max_context_tokens": 10000,
            "max_graph_nodes": 100,
            "max_output_bytes": 100000,
            "stage_timeout_seconds": 60,
        },
    }


def stage(stage_id, cross=None, constraints=None):
    return {
        "stage": stage_id,
        "status": "passed-with-constraints" if constraints else "passed",
        "provider": "fixture-provider",
        "evidence": [f"evidence:{stage_id}"],
        "artifacts": [f"artifact:{stage_id}"],
        "metrics": {"fixture": 1},
        "constraints": constraints or [],
        "cross_cutting": cross or {},
    }


class EvidenceEnvelopeTests(unittest.TestCase):
    def test_analysis_skips_semantic_editing(self):
        env = ENV.new_envelope(manifest())
        l5 = next(s for s in env["stages"] if s["id"] == "L5-semantic-editing")
        self.assertEqual(l5["status"], "skipped")

    def test_edit_mode_requires_semantic_editing(self):
        env = ENV.new_envelope(manifest(mode="analysis-and-edit"))
        l5 = next(s for s in env["stages"] if s["id"] == "L5-semantic-editing")
        self.assertEqual(l5["status"], "pending")

    def test_private_repository_identity_is_not_persisted(self):
        data = manifest(visibility="private")
        data["target"]["source"] = "private-owner/private-repo"
        env = ENV.new_envelope(data)
        self.assertNotEqual(env["target"]["repository_id"], "private-owner/private-repo")
        self.assertTrue(env["target"]["repository_id"].startswith("repo_"))
        self.assertFalse(env["target"]["identity_persisted"])
        self.assertNotIn("private-owner", ENV.canonical_json(env))

    def test_private_identity_persistence_is_rejected(self):
        data = manifest(visibility="private")
        data["privacy"]["persist_private_identity"] = True
        with self.assertRaisesRegex(ValueError, "forbidden"):
            ENV.new_envelope(data)

    def test_stage_order_is_enforced(self):
        env = ENV.new_envelope(manifest())
        with self.assertRaisesRegex(ValueError, "prior stages"):
            ENV.apply_stage_result(env, stage("L2-semantic-graph"))

    def test_pass_requires_evidence(self):
        env = ENV.new_envelope(manifest())
        result = stage("L0-intake")
        result["evidence"] = []
        with self.assertRaisesRegex(ValueError, "requires evidence"):
            ENV.apply_stage_result(env, result)


class OrchestratorTests(unittest.TestCase):
    def write_run(self, tmp, manifest_data, results):
        tmp = pathlib.Path(tmp)
        manifest_path = tmp / "manifest.json"
        stage_dir = tmp / "stages"
        stage_dir.mkdir()
        manifest_path.write_text(json.dumps(manifest_data))
        for result in results:
            (stage_dir / f"{result['stage']}.json").write_text(json.dumps(result))
        return manifest_path, stage_dir

    def test_partial_run_stays_running(self):
        with tempfile.TemporaryDirectory() as td:
            mp, sd = self.write_run(td, manifest(), [stage("L0-intake")])
            plan, env = ORCH.run(mp, sd)
            self.assertEqual(env["status"], "running")
            self.assertFalse(plan["rules"]["auto_promote"])

    def test_full_analysis_run_reaches_parent_review(self):
        cross = {
            "license": {"status": "compatible", "evidence": ["MIT"]},
            "security": {"status": "passed", "evidence": ["security-lab"]},
            "capability_delta": {"status": "new", "evidence": ["delta-review"]},
            "rollback": {"status": "verified", "evidence": ["git-revert"]},
            "private_data": {"status": "compliant", "evidence": ["privacy-review"]},
            "verifier": {"status": "verified", "evidence": ["verifier-report"]},
        }
        results = [
            stage("L0-intake", cross=cross),
            stage("L1-context-packaging"),
            stage("L2-semantic-graph"),
            stage("L3-architecture-presentation"),
            stage("L4-wiki-qa"),
            stage("L6-reverse-engineering"),
        ]
        with tempfile.TemporaryDirectory() as td:
            mp, sd = self.write_run(td, manifest(), results)
            _plan, env = ORCH.run(mp, sd)
            self.assertEqual(env["status"], "ready-for-parent-review")
            self.assertEqual(env["promotion"]["decision"], "eligible-for-parent-promotion")
            self.assertFalse(env["promotion"]["auto_promote"])

    def test_unknown_license_blocks_full_run(self):
        cross = {
            "license": {"status": "unknown", "evidence": ["no-license"]},
            "security": {"status": "passed", "evidence": ["security-lab"]},
            "capability_delta": {"status": "new", "evidence": ["delta-review"]},
            "rollback": {"status": "verified", "evidence": ["git-revert"]},
            "private_data": {"status": "compliant", "evidence": ["privacy-review"]},
            "verifier": {"status": "verified", "evidence": ["verifier-report"]},
        }
        results = [
            stage("L0-intake", cross=cross),
            stage("L1-context-packaging"),
            stage("L2-semantic-graph"),
            stage("L3-architecture-presentation"),
            stage("L4-wiki-qa"),
            stage("L6-reverse-engineering"),
        ]
        with tempfile.TemporaryDirectory() as td:
            mp, sd = self.write_run(td, manifest(), results)
            _plan, env = ORCH.run(mp, sd)
            self.assertEqual(env["status"], "blocked")
            self.assertEqual(env["promotion"]["decision"], "pending-evidence")


if __name__ == "__main__":
    unittest.main()
