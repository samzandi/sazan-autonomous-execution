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
IMPACT = load("diff_impact_normalize", "diff_impact_normalize.py")


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
            {"step_id": "web.submit", "repository_id": "web", "label": "Web submit", "symbol": "submitCheckout", "kind": "entry", "entry": True, "state": "observed", "evidence": ["web:submit"]},
            {"step_id": "web.http", "repository_id": "web", "label": "HTTP client", "symbol": "postCheckout", "kind": "http-client", "state": "observed", "evidence": ["web:http"]},
            {"step_id": "api.handle", "repository_id": "api", "label": "Checkout handler", "symbol": "handle_checkout", "kind": "http-handler", "state": "observed", "evidence": ["api:handler"]},
            {"step_id": "api.publish", "repository_id": "api", "label": "Publish event", "symbol": "publish_order_created", "kind": "event-publisher", "state": "observed", "evidence": ["api:publish"]},
            {"step_id": "worker.consume", "repository_id": "repo_worker_01", "label": "Consume event", "symbol": "consume_order_created", "kind": "event-consumer", "state": "observed", "evidence": ["worker:consume"]},
            {"step_id": "worker.store", "repository_id": "repo_worker_01", "label": "Store order", "symbol": "persist_order", "kind": "storage-write", "terminal": True, "state": "observed", "evidence": ["worker:store"]},
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


def symbol_change():
    return {
        "schema_version": 1,
        "workspace_id": "impact-fixture",
        "changes": [{
            "change_id": "api-handler-body",
            "repository_id": "api",
            "change_type": "modify",
            "surface_kind": "symbol",
            "identifier": "handle_checkout",
            "state": "observed",
            "evidence": ["git-diff:api/checkout.py"],
            "local_impact": {
                "symbols": ["handle_checkout"],
                "steps": ["api.handle"],
                "evidence": ["codegraph:impact:handle_checkout"],
            },
        }],
    }


class DiffImpactTests(unittest.TestCase):
    def test_symbol_change_propagates_downstream_not_upstream(self):
        registry, contracts, flows, _http_id, _event_id = fixture()
        report = IMPACT.normalize(registry, contracts, flows, symbol_change())
        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["blast_radius"]["repositories"], ["api", "repo_worker_01"])
        self.assertEqual(report["blast_radius"]["flows"], ["flow_001"])
        self.assertNotIn("web", report["blast_radius"]["repositories"])

    def test_http_contract_change_reaches_both_parties_and_downstream(self):
        registry, contracts, flows, http_id, _event_id = fixture()
        changes = {
            "schema_version": 1,
            "workspace_id": "impact-fixture",
            "changes": [{
                "change_id": "checkout-contract-change",
                "repository_id": "api",
                "change_type": "modify",
                "surface_kind": "http-api",
                "identifier": "http.checkout.v1",
                "contract_id": http_id,
                "state": "observed",
                "evidence": ["api:openapi-diff"],
            }],
        }
        report = IMPACT.normalize(registry, contracts, flows, changes)
        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["blast_radius"]["repositories"], ["api", "repo_worker_01", "web"])
        self.assertEqual(report["blast_radius"]["contracts"], [http_id])
        self.assertEqual(report["blast_radius"]["flows"], ["flow_001"])

    def test_contract_version_change_reports_mismatch(self):
        registry, contracts, flows, http_id, _event_id = fixture()
        changes = {
            "schema_version": 1,
            "workspace_id": "impact-fixture",
            "changes": [{
                "change_id": "checkout-v2",
                "repository_id": "api",
                "change_type": "version-change",
                "surface_kind": "http-api",
                "identifier": "http.checkout.v1",
                "contract_id": http_id,
                "new_version": "2.0.0",
                "state": "observed",
                "evidence": ["api:openapi-version-diff"],
            }],
        }
        report = IMPACT.normalize(registry, contracts, flows, changes)
        self.assertEqual(report["compatibility_findings"]["version_mismatch_changes"], ["checkout-v2"])
        self.assertEqual(report["summary"]["version_mismatches"], 1)

    def test_file_change_without_semantic_evidence_is_partial(self):
        registry, contracts, flows, _http_id, _event_id = fixture()
        changes = {
            "schema_version": 1,
            "workspace_id": "impact-fixture",
            "changes": [{
                "change_id": "file-only",
                "repository_id": "api",
                "change_type": "modify",
                "surface_kind": "file",
                "identifier": "api/checkout.py",
                "state": "observed",
                "evidence": ["git-diff:api/checkout.py"],
            }],
        }
        report = IMPACT.normalize(registry, contracts, flows, changes)
        self.assertEqual(report["status"], "partial-evidence")
        self.assertGreaterEqual(report["summary"]["incomplete_evidence"], 1)

    def test_unmapped_symbol_is_partial(self):
        registry, contracts, flows, _http_id, _event_id = fixture()
        changes = {
            "schema_version": 1,
            "workspace_id": "impact-fixture",
            "changes": [{
                "change_id": "unmapped-symbol",
                "repository_id": "api",
                "change_type": "modify",
                "surface_kind": "symbol",
                "identifier": "unknown_symbol",
                "state": "observed",
                "evidence": ["git-diff:unknown"],
                "local_impact": {"evidence": ["codegraph:no-match"]},
            }],
        }
        report = IMPACT.normalize(registry, contracts, flows, changes)
        self.assertEqual(report["status"], "partial-evidence")
        self.assertEqual(report["changes"][0]["mapping_status"], "unmapped")

    def test_inferred_change_propagates_constraint(self):
        registry, contracts, flows, _http_id, _event_id = fixture()
        data = symbol_change()
        data["changes"][0]["state"] = "inferred"
        data["changes"][0]["rationale"] = "Diff hunk overlaps the handler but exact semantic mapping is incomplete."
        report = IMPACT.normalize(registry, contracts, flows, data)
        self.assertIn("change observation is inferred", report["changes"][0]["constraints"])

    def test_contract_kind_mismatch_is_rejected(self):
        registry, contracts, flows, http_id, _event_id = fixture()
        changes = {
            "schema_version": 1,
            "workspace_id": "impact-fixture",
            "changes": [{
                "change_id": "bad-kind",
                "repository_id": "api",
                "change_type": "modify",
                "surface_kind": "event",
                "identifier": "wrong",
                "contract_id": http_id,
                "state": "observed",
                "evidence": ["diff"],
            }],
        }
        with self.assertRaisesRegex(ValueError, "does not match contract kind"):
            IMPACT.normalize(registry, contracts, flows, changes)

    def test_local_step_must_belong_to_changed_repository(self):
        registry, contracts, flows, _http_id, _event_id = fixture()
        data = symbol_change()
        data["changes"][0]["local_impact"]["steps"] = ["web.http"]
        with self.assertRaisesRegex(ValueError, "different repository"):
            IMPACT.normalize(registry, contracts, flows, data)

    def test_review_scope_contains_repository_flow_and_contract(self):
        registry, contracts, flows, http_id, _event_id = fixture()
        changes = {
            "schema_version": 1,
            "workspace_id": "impact-fixture",
            "changes": [{
                "change_id": "checkout-contract-change",
                "repository_id": "api",
                "change_type": "modify",
                "surface_kind": "http-api",
                "identifier": "http.checkout.v1",
                "contract_id": http_id,
                "state": "observed",
                "evidence": ["api:openapi-diff"],
            }],
        }
        report = IMPACT.normalize(registry, contracts, flows, changes)
        self.assertTrue(any(x.get("repository_id") == "web" for x in report["test_review_scope"]))
        self.assertTrue(any(x.get("contract_id") == http_id for x in report["test_review_scope"]))
        self.assertTrue(any(x.get("flow_id") == "flow_001" for x in report["test_review_scope"]))

    def test_private_source_is_not_present(self):
        registry, contracts, flows, _http_id, _event_id = fixture()
        report = IMPACT.normalize(registry, contracts, flows, symbol_change())
        self.assertNotIn("secret-owner", json.dumps(report, sort_keys=True))

    def test_output_is_deterministic(self):
        registry, contracts, flows, _http_id, _event_id = fixture()
        one = IMPACT.normalize(registry, contracts, flows, symbol_change())
        two = IMPACT.normalize(registry, contracts, flows, symbol_change())
        self.assertEqual(one, two)
        self.assertEqual(IMPACT.render_markdown(one), IMPACT.render_markdown(two))


if __name__ == "__main__":
    unittest.main()
