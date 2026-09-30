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


REG = load("multi_repo_registry", "multi_repo_registry.py")
FLOW = load("process_flow_synthesis", "process_flow_synthesis.py")
IMPACT = load("diff_impact_normalizer", "diff_impact_normalizer.py")


def workspace():
    return {
        "schema_version": 1,
        "workspace_id": "impact-fixture",
        "repositories": [
            {
                "repository_id": "web",
                "visibility": "local-fixture",
                "source": "fixture/web",
                "revision": "web-1",
                "requires": [{
                    "key": "http.checkout.v1",
                    "kind": "http-api",
                    "version": "1.0.0",
                    "provider_hint": "api",
                    "state": "observed",
                    "evidence": ["web:http-client"],
                }],
            },
            {
                "repository_id": "api",
                "visibility": "local-fixture",
                "source": "fixture/api",
                "revision": "api-2",
                "provides": [
                    {
                        "key": "http.checkout.v1",
                        "kind": "http-api",
                        "version": "1.0.0",
                        "state": "observed",
                        "evidence": ["api:http-route"],
                    },
                    {
                        "key": "event.order.created",
                        "kind": "event",
                        "version": "1.0.0",
                        "state": "observed",
                        "evidence": ["api:event-publisher"],
                    },
                ],
            },
            {
                "repository_id": "repo_worker_01",
                "visibility": "private",
                "source": "secret-owner/private-worker",
                "revision": "worker-1",
                "requires": [{
                    "key": "event.order.created",
                    "kind": "event",
                    "version": "1.0.0",
                    "provider_hint": "api",
                    "state": "observed",
                    "evidence": ["worker:event-consumer"],
                }],
            },
        ],
    }


def fixture():
    registry, contracts = REG.build(workspace())
    http_id = next(c["contract_id"] for c in contracts["contracts"] if c["kind"] == "http-api")
    event_id = next(c["contract_id"] for c in contracts["contracts"] if c["kind"] == "event")
    observations = {
        "schema_version": 1,
        "workspace_id": "impact-fixture",
        "steps": [
            {"step_id": "web.submit", "repository_id": "web", "label": "Web submit", "kind": "entry", "entry": True, "state": "observed", "evidence": ["web:submit"]},
            {"step_id": "web.http", "repository_id": "web", "label": "HTTP client", "kind": "http-client", "state": "observed", "evidence": ["web:http"]},
            {"step_id": "api.handle", "repository_id": "api", "label": "Checkout handler", "kind": "http-handler", "state": "observed", "evidence": ["api:handler"]},
            {"step_id": "api.publish", "repository_id": "api", "label": "Publish event", "kind": "event-publisher", "state": "observed", "evidence": ["api:publish"]},
            {"step_id": "worker.consume", "repository_id": "repo_worker_01", "label": "Consume event", "kind": "event-consumer", "state": "observed", "evidence": ["worker:consume"]},
            {"step_id": "worker.store", "repository_id": "repo_worker_01", "label": "Store order", "kind": "storage-write", "terminal": True, "state": "observed", "evidence": ["worker:store"]},
        ],
        "edges": [
            {"from": "web.submit", "to": "web.http", "relation": "calls", "state": "observed", "evidence": ["web:call"]},
            {"from": "api.handle", "to": "api.publish", "relation": "publishes", "state": "observed", "evidence": ["api:call"]},
            {"from": "worker.consume", "to": "worker.store", "relation": "writes", "state": "observed", "evidence": ["worker:call"]},
        ],
        "bindings": [
            {"contract_id": http_id, "provider_step": "api.handle", "consumer_step": "web.http", "flow_direction": "consumer-to-provider", "state": "observed", "evidence": ["binding:http"]},
            {"contract_id": event_id, "provider_step": "api.publish", "consumer_step": "worker.consume", "flow_direction": "provider-to-consumer", "state": "observed", "evidence": ["binding:event"]},
        ],
    }
    flows = FLOW.synthesize(registry, contracts, observations)
    return registry, contracts, flows, http_id, event_id


def signature_change(http_id):
    return {
        "schema_version": 1,
        "workspace_id": "impact-fixture",
        "changes": [{
            "change_id": "api-calculate-total-signature",
            "repository_id": "api",
            "change_type": "signature",
            "path": "service/orders.py",
            "symbol": "calculate_total",
            "state": "observed",
            "evidence": ["codegraph:pr-context"],
            "local_impact": {
                "risk": "medium",
                "symbols": ["calculate_total", "handle_checkout"],
                "files": ["service/orders.py", "api/checkout.py"],
                "tests": ["tests/test_checkout.py"],
            },
            "touched_steps": ["api.handle"],
            "contract_touches": [{
                "contract_id": http_id,
                "side": "provider",
                "state": "observed",
                "evidence": ["api:route-contract"],
            }],
        }],
    }


class DiffImpactTests(unittest.TestCase):
    def test_provider_signature_change_propagates_cross_repo(self):
        registry, contracts, flows, http_id, _event_id = fixture()
        report = IMPACT.normalize(registry, contracts, flows, signature_change(http_id))
        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["risk_level"], "high")
        repos = {x["repository_id"] for x in report["affected_repositories"]}
        self.assertEqual(repos, {"web", "api", "repo_worker_01"})
        self.assertEqual(report["summary"]["affected_contracts"], 1)
        self.assertEqual(report["summary"]["affected_flows"], 1)
        self.assertIn("tests/test_checkout.py", report["test_targets"])

    def test_body_only_step_change_does_not_mark_upsteam_consumer(self):
        registry, contracts, flows, _http_id, _event_id = fixture()
        changes = {
            "schema_version": 1,
            "workspace_id": "impact-fixture",
            "changes": [{
                "change_id": "api-handler-body",
                "repository_id": "api",
                "change_type": "body",
                "state": "observed",
                "evidence": ["codegraph:pr-context"],
                "local_impact": {"risk": "low", "symbols": ["handle_checkout"], "files": ["api/checkout.py"], "tests": []},
                "touched_steps": ["api.handle"],
                "contract_touches": [],
            }],
        }
        report = IMPACT.normalize(registry, contracts, flows, changes)
        repos = {x["repository_id"] for x in report["affected_repositories"]}
        self.assertEqual(repos, {"api", "repo_worker_01"})
        self.assertNotIn("web", repos)
        self.assertEqual(report["risk_level"], "medium")

    def test_event_contract_change_is_high_and_reaches_worker(self):
        registry, contracts, flows, _http_id, event_id = fixture()
        changes = {
            "schema_version": 1,
            "workspace_id": "impact-fixture",
            "changes": [{
                "change_id": "event-shape",
                "repository_id": "api",
                "change_type": "event",
                "state": "observed",
                "evidence": ["api:event-diff"],
                "local_impact": {"risk": "medium", "symbols": ["publish_order_created"], "files": ["events.py"], "tests": ["tests/test_events.py"]},
                "touched_steps": ["api.publish"],
                "contract_touches": [{
                    "contract_id": event_id,
                    "side": "provider",
                    "state": "observed",
                    "evidence": ["api:event-contract"],
                }],
            }],
        }
        report = IMPACT.normalize(registry, contracts, flows, changes)
        worker = next(r for r in report["affected_repositories"] if r["repository_id"] == "repo_worker_01")
        self.assertEqual(worker["risk"], "high")
        self.assertEqual(report["risk_level"], "high")

    def test_consumer_contract_change_marks_provider_for_review(self):
        registry, contracts, flows, http_id, _event_id = fixture()
        changes = {
            "schema_version": 1,
            "workspace_id": "impact-fixture",
            "changes": [{
                "change_id": "web-client-contract",
                "repository_id": "web",
                "change_type": "contract",
                "state": "observed",
                "evidence": ["web:client-diff"],
                "local_impact": {"risk": "medium", "symbols": ["postCheckout"], "files": ["checkout.ts"], "tests": []},
                "touched_steps": ["web.http"],
                "contract_touches": [{
                    "contract_id": http_id,
                    "side": "consumer",
                    "state": "observed",
                    "evidence": ["web:http-contract"],
                }],
            }],
        }
        report = IMPACT.normalize(registry, contracts, flows, changes)
        api = next(r for r in report["affected_repositories"] if r["repository_id"] == "api")
        self.assertTrue(any("counterparty review" in x for x in api["reasons"]))

    def test_inferred_mapping_propagates_constraint(self):
        registry, contracts, flows, http_id, _event_id = fixture()
        data = signature_change(http_id)
        data["changes"][0]["state"] = "inferred"
        data["changes"][0]["rationale"] = "Diff hunk overlaps the route symbol but exact AST mapping is unavailable."
        report = IMPACT.normalize(registry, contracts, flows, data)
        self.assertTrue(report["constraints"])
        self.assertTrue(any(r["state"] == "inferred" for r in report["affected_repositories"]))

    def test_unknown_contract_is_rejected(self):
        registry, contracts, flows, http_id, _event_id = fixture()
        data = signature_change(http_id)
        data["changes"][0]["contract_touches"][0]["contract_id"] = "missing"
        with self.assertRaisesRegex(ValueError, "unknown or unmatched contract_id"):
            IMPACT.normalize(registry, contracts, flows, data)

    def test_step_must_belong_to_changed_repo(self):
        registry, contracts, flows, http_id, _event_id = fixture()
        data = signature_change(http_id)
        data["changes"][0]["touched_steps"] = ["web.http"]
        with self.assertRaisesRegex(ValueError, "belongs to another repository"):
            IMPACT.normalize(registry, contracts, flows, data)

    def test_workspace_mismatch_is_rejected(self):
        registry, contracts, flows, http_id, _event_id = fixture()
        data = signature_change(http_id)
        data["workspace_id"] = "other"
        with self.assertRaisesRegex(ValueError, "workspace_id mismatch"):
            IMPACT.normalize(registry, contracts, flows, data)

    def test_private_source_is_not_present(self):
        registry, contracts, flows, http_id, _event_id = fixture()
        report = IMPACT.normalize(registry, contracts, flows, signature_change(http_id))
        self.assertNotIn("secret-owner", json.dumps(report, sort_keys=True))

    def test_output_is_deterministic(self):
        registry, contracts, flows, http_id, _event_id = fixture()
        one = IMPACT.normalize(registry, contracts, flows, signature_change(http_id))
        two = IMPACT.normalize(registry, contracts, flows, signature_change(http_id))
        self.assertEqual(one, two)
        self.assertEqual(IMPACT.render_markdown(one), IMPACT.render_markdown(two))


if __name__ == "__main__":
    unittest.main()
