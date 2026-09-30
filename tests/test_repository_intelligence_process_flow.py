import importlib.util
import pathlib
import unittest


BASE = pathlib.Path(__file__).parents[1] / "agents" / "repo-skill-steward" / "repository-intelligence" / "scripts"


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, BASE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


REG = load("multi_repo_registry", "multi_repo_registry.py")
FLOW = load("process_flow_synthesis", "process_flow_synthesis.py")


def workspace():
    return {
        "schema_version": 1,
        "workspace_id": "flow-fixture",
        "repositories": [
            {
                "repository_id": "web",
                "visibility": "local-fixture",
                "source": "fixture/web",
                "revision": "web-1",
                "requires": [
                    {
                        "key": "http.checkout.v1",
                        "kind": "http-api",
                        "version": "1.0.0",
                        "provider_hint": "api",
                        "state": "observed",
                        "evidence": ["web:http-client"],
                    }
                ],
            },
            {
                "repository_id": "api",
                "visibility": "local-fixture",
                "source": "fixture/api",
                "revision": "api-1",
                "provides": [
                    {
                        "key": "http.checkout.v1",
                        "kind": "http-api",
                        "version": "1.0.0",
                        "state": "observed",
                        "evidence": ["api:route"],
                    },
                    {
                        "key": "event.order.created",
                        "kind": "event",
                        "version": "1.0.0",
                        "state": "observed",
                        "evidence": ["api:publisher"],
                    },
                ],
            },
            {
                "repository_id": "repo_worker_01",
                "visibility": "private",
                "source": "secret-owner/private-worker",
                "revision": "worker-1",
                "requires": [
                    {
                        "key": "event.order.created",
                        "kind": "event",
                        "version": "1.0.0",
                        "provider_hint": "api",
                        "state": "observed",
                        "evidence": ["worker:consumer"],
                    }
                ],
            },
        ],
    }


def observations(contracts):
    http_id = next(c["contract_id"] for c in contracts["contracts"] if c["kind"] == "http-api")
    event_id = next(c["contract_id"] for c in contracts["contracts"] if c["kind"] == "event")
    return {
        "schema_version": 1,
        "workspace_id": "flow-fixture",
        "budgets": {"max_hops": 16, "max_paths": 20},
        "steps": [
            {
                "step_id": "web.submit",
                "repository_id": "web",
                "label": "Web submit checkout",
                "symbol": "submitCheckout",
                "kind": "entry",
                "entry": True,
                "state": "observed",
                "evidence": ["web:submit-handler"],
            },
            {
                "step_id": "web.http",
                "repository_id": "web",
                "label": "Web checkout HTTP client",
                "symbol": "postCheckout",
                "kind": "http-client",
                "state": "observed",
                "evidence": ["web:http-client"],
            },
            {
                "step_id": "api.handle",
                "repository_id": "api",
                "label": "API checkout handler",
                "symbol": "handle_checkout",
                "kind": "http-handler",
                "state": "observed",
                "evidence": ["api:route"],
            },
            {
                "step_id": "api.publish",
                "repository_id": "api",
                "label": "Publish order.created event",
                "symbol": "publish_order_created",
                "kind": "event-publisher",
                "state": "observed",
                "evidence": ["api:publisher"],
            },
            {
                "step_id": "worker.consume",
                "repository_id": "repo_worker_01",
                "label": "Worker consumes order.created",
                "symbol": "consume_order_created",
                "kind": "event-consumer",
                "state": "observed",
                "evidence": ["worker:consumer"],
            },
            {
                "step_id": "worker.persist",
                "repository_id": "repo_worker_01",
                "label": "Storage write",
                "symbol": "persist_order",
                "kind": "storage-write",
                "terminal": True,
                "state": "observed",
                "evidence": ["worker:storage-call"],
            },
        ],
        "edges": [
            {
                "from": "web.submit",
                "to": "web.http",
                "relation": "calls",
                "state": "observed",
                "evidence": ["web:call-graph"],
            },
            {
                "from": "api.handle",
                "to": "api.publish",
                "relation": "publishes",
                "state": "observed",
                "evidence": ["api:call-graph"],
            },
            {
                "from": "worker.consume",
                "to": "worker.persist",
                "relation": "writes",
                "state": "observed",
                "evidence": ["worker:call-graph"],
            },
        ],
        "bindings": [
            {
                "contract_id": http_id,
                "provider_step": "api.handle",
                "consumer_step": "web.http",
                "flow_direction": "consumer-to-provider",
                "state": "observed",
                "evidence": ["binding:http"],
            },
            {
                "contract_id": event_id,
                "provider_step": "api.publish",
                "consumer_step": "worker.consume",
                "flow_direction": "provider-to-consumer",
                "state": "observed",
                "evidence": ["binding:event"],
            },
        ],
    }


def fixture():
    registry, contracts = REG.build(workspace())
    return registry, contracts, observations(contracts)


class ProcessFlowTests(unittest.TestCase):
    def test_observed_end_to_end_flow(self):
        registry, contracts, obs = fixture()
        report = FLOW.synthesize(registry, contracts, obs)
        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["summary"]["flows"], 1)
        self.assertEqual(report["summary"]["observed_flows"], 1)
        flow = report["flows"][0]
        self.assertEqual(flow["repositories"], ["web", "api", "repo_worker_01"])
        self.assertEqual(flow["entry_step"], "web.submit")
        self.assertEqual(flow["terminal_step"], "worker.persist")

    def test_private_repository_source_never_needed(self):
        registry, contracts, obs = fixture()
        report = FLOW.synthesize(registry, contracts, obs)
        text = str(report)
        self.assertNotIn("secret-owner", text)

    def test_cross_repo_local_edge_is_rejected(self):
        registry, contracts, obs = fixture()
        obs["edges"].append({
            "from": "web.http",
            "to": "api.handle",
            "relation": "invalid-direct-hop",
            "state": "observed",
            "evidence": ["bad"],
        })
        with self.assertRaisesRegex(ValueError, "contract bindings"):
            FLOW.synthesize(registry, contracts, obs)

    def test_binding_repository_must_match_contract(self):
        registry, contracts, obs = fixture()
        obs["bindings"][0]["provider_step"] = "api.publish"
        # Same repository still valid; force a real mismatch.
        obs["bindings"][0]["provider_step"] = "worker.consume"
        with self.assertRaisesRegex(ValueError, "provider_step repository"):
            FLOW.synthesize(registry, contracts, obs)

    def test_duplicate_binding_is_rejected(self):
        registry, contracts, obs = fixture()
        obs["bindings"].append(dict(obs["bindings"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate contract binding"):
            FLOW.synthesize(registry, contracts, obs)

    def test_inferred_binding_downgrades_flow(self):
        registry, contracts, obs = fixture()
        obs["bindings"][1]["state"] = "inferred"
        obs["bindings"][1]["rationale"] = "Publisher/consumer names imply the event hop."
        report = FLOW.synthesize(registry, contracts, obs)
        self.assertEqual(report["summary"]["inferred_flows"], 1)
        self.assertEqual(report["flows"][0]["state"], "inferred")
        self.assertTrue(report["flows"][0]["constraints"])

    def test_no_terminal_path_blocks(self):
        registry, contracts, obs = fixture()
        for step in obs["steps"]:
            step["terminal"] = False
        with self.assertRaisesRegex(ValueError, "terminal step"):
            FLOW.synthesize(registry, contracts, obs)

    def test_unreachable_step_is_reported(self):
        registry, contracts, obs = fixture()
        obs["steps"].append({
            "step_id": "api.dead",
            "repository_id": "api",
            "label": "Unreachable diagnostic step",
            "kind": "operation",
            "state": "observed",
            "evidence": ["api:dead"],
        })
        report = FLOW.synthesize(registry, contracts, obs)
        self.assertIn("api.dead", report["unreachable_steps"])

    def test_cycle_is_reported_without_forcing_failure(self):
        registry, contracts, obs = fixture()
        obs["steps"].append({
            "step_id": "api.retry",
            "repository_id": "api",
            "label": "Retry loop",
            "kind": "retry",
            "state": "observed",
            "evidence": ["api:retry"],
        })
        obs["edges"].extend([
            {
                "from": "api.handle",
                "to": "api.retry",
                "relation": "retry",
                "state": "observed",
                "evidence": ["api:retry-edge"],
            },
            {
                "from": "api.retry",
                "to": "api.handle",
                "relation": "retry-return",
                "state": "observed",
                "evidence": ["api:retry-edge"],
            },
        ])
        report = FLOW.synthesize(registry, contracts, obs)
        self.assertEqual(report["status"], "verified")
        self.assertGreaterEqual(report["summary"]["cycles"], 1)

    def test_workspace_mismatch_is_rejected(self):
        registry, contracts, obs = fixture()
        obs["workspace_id"] = "other"
        with self.assertRaisesRegex(ValueError, "workspace_id mismatch"):
            FLOW.synthesize(registry, contracts, obs)

    def test_output_is_deterministic(self):
        registry, contracts, obs = fixture()
        one = FLOW.synthesize(registry, contracts, obs)
        two = FLOW.synthesize(registry, contracts, obs)
        self.assertEqual(one, two)
        self.assertEqual(FLOW.render_markdown(one), FLOW.render_markdown(two))


if __name__ == "__main__":
    unittest.main()
