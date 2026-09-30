import importlib.util
import json
import pathlib
import unittest


BASE = pathlib.Path(__file__).parents[1] / "agents" / "repo-skill-steward" / "repository-intelligence" / "scripts"


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, BASE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


ROUTER = load("provider_health", "provider_health.py")


def health(*items):
    return {
        "schema_version": 1,
        "providers": list(items),
    }


def obs(provider, status="healthy", evidence=None, reason=None):
    out = {
        "provider": provider,
        "status": status,
        "evidence": evidence or [f"health:{provider}:{status}"],
    }
    if reason:
        out["reason"] = reason
    return out


class ProviderHealthTests(unittest.TestCase):
    def test_primary_healthy_is_selected(self):
        report = ROUTER.route_stage(
            "L1-context-packaging",
            health(obs("repomix"), obs("gitingest")),
        )
        self.assertEqual(report["decision"], "primary")
        self.assertEqual(report["selected_provider"], "repomix")
        self.assertFalse(report["fallback_used"])

    def test_unhealthy_primary_uses_explicit_fallback(self):
        report = ROUTER.route_stage(
            "L1-context-packaging",
            health(obs("repomix", "unhealthy"), obs("gitingest", "healthy")),
        )
        self.assertEqual(report["decision"], "fallback")
        self.assertEqual(report["selected_provider"], "gitingest")
        self.assertTrue(report["fallback_used"])
        self.assertTrue(any("repomix -> gitingest" in x for x in report["constraints"]))

    def test_degraded_primary_is_not_used_by_default(self):
        report = ROUTER.route_stage(
            "L1-context-packaging",
            health(obs("repomix", "degraded"), obs("gitingest", "healthy")),
        )
        self.assertEqual(report["selected_provider"], "gitingest")

    def test_degraded_can_be_explicitly_allowed(self):
        report = ROUTER.route_stage(
            "L1-context-packaging",
            health(obs("repomix", "degraded"), obs("gitingest", "healthy")),
            allow_degraded=True,
        )
        self.assertEqual(report["selected_provider"], "repomix")
        self.assertTrue(any("degraded" in x for x in report["constraints"]))

    def test_no_healthy_candidate_blocks(self):
        report = ROUTER.route_stage(
            "L1-context-packaging",
            health(obs("repomix", "unhealthy"), obs("gitingest", "unknown")),
        )
        self.assertEqual(report["decision"], "blocked")
        self.assertIsNone(report["selected_provider"])

    def test_missing_health_observation_is_not_assumed_healthy(self):
        report = ROUTER.route_stage(
            "L1-context-packaging",
            health(obs("gitingest", "healthy")),
        )
        self.assertEqual(report["selected_provider"], "gitingest")
        primary = report["attempts"][0]
        self.assertEqual(primary["reason"], "no health observation")

    def test_contract_mismatch_fallback_is_rejected(self):
        routes = {
            "L1-context-packaging": [
                {"provider": "primary", "contract": "context-v1", "private_safe": True},
                {"provider": "wrong-fallback", "contract": "semantic-graph-v1", "private_safe": True},
            ]
        }
        report = ROUTER.route_stage(
            "L1-context-packaging",
            health(obs("primary", "unhealthy"), obs("wrong-fallback", "healthy")),
            routes=routes,
        )
        self.assertEqual(report["decision"], "blocked")
        self.assertIn("contract mismatch", report["attempts"][1]["reason"])

    def test_private_target_rejects_non_private_safe_provider(self):
        routes = {
            "L4-wiki-qa": [
                {"provider": "hosted-wiki", "contract": "wiki-qa-v1", "private_safe": False},
            ]
        }
        report = ROUTER.route_stage(
            "L4-wiki-qa",
            health(obs("hosted-wiki", "healthy")),
            visibility="private",
            routes=routes,
        )
        self.assertEqual(report["decision"], "blocked")
        self.assertIn("not approved", report["attempts"][0]["reason"])

    def test_no_equivalent_fallback_for_semantic_graph(self):
        report = ROUTER.route_stage(
            "L2-semantic-graph",
            health(obs("codegraph-0.20.1", "unhealthy")),
        )
        self.assertEqual(report["decision"], "blocked")
        self.assertEqual(report["primary_provider"], "codegraph-0.20.1")

    def test_health_evidence_is_required(self):
        with self.assertRaisesRegex(ValueError, "health evidence is required"):
            ROUTER.route_stage(
                "L1-context-packaging",
                {"schema_version": 1, "providers": [{"provider": "repomix", "status": "healthy", "evidence": []}]},
            )

    def test_pipeline_reports_fallback_and_blocked_stages(self):
        payload = health(
            obs("sazan-intake"),
            obs("repomix", "unhealthy"),
            obs("gitingest"),
            obs("codegraph-0.20.1", "unhealthy"),
        )
        report = ROUTER.route_pipeline(
            payload,
            stages=["L0-intake", "L1-context-packaging", "L2-semantic-graph"],
        )
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["fallback_stages"], ["L1-context-packaging"])
        self.assertEqual(report["blocked_stages"], ["L2-semantic-graph"])

    def test_output_is_deterministic(self):
        payload = health(obs("repomix"), obs("gitingest"))
        one = ROUTER.route_stage("L1-context-packaging", payload)
        two = ROUTER.route_stage("L1-context-packaging", payload)
        self.assertEqual(one, two)
        self.assertEqual(json.dumps(one, sort_keys=True), json.dumps(two, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
