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


ORCH = load("orchestrator_provider_routing", "orchestrate_repository_intelligence.py")


def provider_health(repomix="healthy", codegraph="healthy"):
    providers = [
        ("sazan-intake", "healthy"),
        ("repomix", repomix),
        ("gitingest", "healthy"),
        ("codegraph-0.20.1", codegraph),
        ("sazan-mermaid-renderer", "healthy"),
        ("sazan-lightweight-wiki-qa", "healthy"),
        ("sazan-rebuild-spec", "healthy"),
        ("sazan-promotion-gate", "healthy"),
    ]
    return {
        "schema_version": 1,
        "providers": [
            {
                "provider": provider,
                "status": status,
                "evidence": [f"health:{provider}:{status}"],
            }
            for provider, status in providers
        ],
    }


def manifest(health=None):
    out = {
        "run_id": "provider-routing-001",
        "purpose": "provider routing fixture",
        "mode": "analysis",
        "target": {
            "source": "fixture/repo",
            "revision": "abc123",
            "visibility": "local-fixture",
        },
        "privacy": {"persist_private_identity": False},
        "budgets": {
            "max_context_tokens": 10000,
            "max_graph_nodes": 100,
            "max_output_bytes": 100000,
            "stage_timeout_seconds": 60,
        },
        "provider_policy": {
            "strict": True,
            "allow_degraded": False,
        },
    }
    if health is not None:
        out["provider_health"] = health
    return out


def stage(stage_id, provider):
    return {
        "stage": stage_id,
        "status": "passed",
        "provider": provider,
        "evidence": [f"evidence:{stage_id}"],
        "artifacts": [],
        "metrics": {},
        "constraints": [],
    }


class ProviderRoutingIntegrationTests(unittest.TestCase):
    def write_run(self, tmp, manifest_data, results):
        root = pathlib.Path(tmp)
        manifest_path = root / "manifest.json"
        stage_dir = root / "stages"
        stage_dir.mkdir()
        manifest_path.write_text(json.dumps(manifest_data))
        for result in results:
            (stage_dir / f"{result['stage']}.json").write_text(json.dumps(result))
        return manifest_path, stage_dir

    def test_strict_routing_requires_health_payload(self):
        with tempfile.TemporaryDirectory() as td:
            mp, sd = self.write_run(td, manifest(None), [])
            with self.assertRaisesRegex(ValueError, "requires provider_health"):
                ORCH.run(mp, sd)

    def test_unhealthy_repomix_routes_l1_to_gitingest(self):
        results = [
            stage("L0-intake", "sazan-intake"),
            stage("L1-context-packaging", "gitingest"),
        ]
        with tempfile.TemporaryDirectory() as td:
            mp, sd = self.write_run(td, manifest(provider_health(repomix="unhealthy")), results)
            plan, env = ORCH.run(mp, sd)
            l1_plan = next(x for x in plan["stages"] if x["id"] == "L1-context-packaging")
            l1 = next(x for x in env["stages"] if x["id"] == "L1-context-packaging")
            self.assertEqual(l1_plan["provider"], "gitingest")
            self.assertEqual(l1["provider"], "gitingest")
            self.assertEqual(l1["status"], "passed-with-constraints")
            self.assertTrue(l1["provider_route"]["fallback_used"])

    def test_stage_result_from_unrouted_provider_is_blocked(self):
        results = [
            stage("L0-intake", "sazan-intake"),
            stage("L1-context-packaging", "repomix"),
        ]
        with tempfile.TemporaryDirectory() as td:
            mp, sd = self.write_run(td, manifest(provider_health(repomix="unhealthy")), results)
            _plan, env = ORCH.run(mp, sd)
            l1 = next(x for x in env["stages"] if x["id"] == "L1-context-packaging")
            self.assertEqual(env["status"], "blocked")
            self.assertEqual(l1["status"], "blocked")
            self.assertIn("does not match routed provider", l1["constraints"][0])

    def test_unhealthy_semantic_graph_blocks_before_stage_result(self):
        results = [
            stage("L0-intake", "sazan-intake"),
            stage("L1-context-packaging", "repomix"),
        ]
        with tempfile.TemporaryDirectory() as td:
            mp, sd = self.write_run(td, manifest(provider_health(codegraph="unhealthy")), results)
            plan, env = ORCH.run(mp, sd)
            l2_plan = next(x for x in plan["stages"] if x["id"] == "L2-semantic-graph")
            l2 = next(x for x in env["stages"] if x["id"] == "L2-semantic-graph")
            self.assertIsNone(l2_plan["provider_route"]["selected_provider"])
            self.assertEqual(l2_plan["provider_route"]["decision"], "blocked")
            self.assertEqual(l2["status"], "blocked")
            self.assertEqual(env["status"], "blocked")

    def test_healthy_primary_keeps_primary_provider(self):
        results = [
            stage("L0-intake", "sazan-intake"),
            stage("L1-context-packaging", "repomix"),
        ]
        with tempfile.TemporaryDirectory() as td:
            mp, sd = self.write_run(td, manifest(provider_health()), results)
            plan, env = ORCH.run(mp, sd)
            l1_plan = next(x for x in plan["stages"] if x["id"] == "L1-context-packaging")
            l1 = next(x for x in env["stages"] if x["id"] == "L1-context-packaging")
            self.assertEqual(l1_plan["provider"], "repomix")
            self.assertEqual(l1["provider"], "repomix")
            self.assertEqual(l1["status"], "passed")
            self.assertFalse(l1["provider_route"]["fallback_used"])

    def test_legacy_mode_preserves_static_provider_behavior(self):
        data = manifest(provider_health())
        data["provider_policy"]["strict"] = False
        results = [stage("L0-intake", "fixture-provider")]
        with tempfile.TemporaryDirectory() as td:
            mp, sd = self.write_run(td, data, results)
            plan, env = ORCH.run(mp, sd)
            self.assertIsNone(plan["provider_routing"])
            self.assertEqual(env["status"], "running")
            l0 = next(x for x in env["stages"] if x["id"] == "L0-intake")
            self.assertEqual(l0["provider"], "fixture-provider")
            self.assertIsNone(l0["provider_route"])


if __name__ == "__main__":
    unittest.main()
