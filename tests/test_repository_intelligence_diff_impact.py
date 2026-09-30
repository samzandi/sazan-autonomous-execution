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
                "revision": "api-1",
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


def flow_inputs():
    registry, contracts = REG.build(workspace())
    http_id = next(c["contract_id"] for c in contracts["contracts"] if c["kind"] == "http-api")
    event_id = next(c["contract_id"] for c in contracts["contracts"] if c["kind"] == "event")
    obs = {
        "schema_version": 1,
        "workspace_id": "impact-fixture",
        "steps": [
            {"step_id":"web.submit","repository_id":"web","label":"Submit","symbol":"submitCheckout","kind":"entry","entry":True,"state":"observed","evidence":["web:submit"]},
            {"step_id":"web.http","repository_id":"web","label":"HTTP client","symbol":"postCheckout","kind":"http-client","state":"observed","evidence":["web:http"]},
            {"step_id":"api.handle","repository_id":"api","label":"Checkout handler","symbol":"handle_checkout","kind":"handler","state":"observed","evidence":["api:handler"]},
            {"step_id":"api.publish","repository_id":"api","label":"Publish event","symbol":"publish_order_created","kind":"event-publisher","state":"observed","evidence":["api:publisher"]},
            {"step_id":"worker.consume","repository_id":"repo_worker_01","label":"Consume event","symbol":"consume_order_created","kind":"event-consumer","state":"observed","evidence":["worker:consumer"]},
            {"step_id":"worker.persist","repository_id":"repo_worker_01","label":"Persist","symbol":"persist_order","kind":"storage-write","terminal":True,"state":"observed","evidence":["worker:persist"]},
        ],
        "edges": [
            {"from":"web.submit","to":"web.http","relation":"calls","state":"observed","evidence":["web:call"]},
            {"from":"api.handle","to":"api.publish","relation":"calls","state":"observed","evidence":["api:call"]},
            {"from":"worker.consume","to":"worker.persist","relation":"calls","state":"observed","evidence":["worker:call"]},
        ],
        "bindings": [
            {"contract_id":http_id,"provider_step":"api.handle","consumer_step":"web.http","flow_direction":"consumer-to-provider","state":"observed","evidence":["binding:http"]},
            {"contract_id":event_id,"provider_step":"api.publish","consumer_step":"worker.consume","flow_direction":"provider-to-consumer","state":"observed","evidence":["binding:event"]},
        ],
    }
    flows = FLOW.synthesize(registry, contracts, obs)
    return registry, contracts, flows, http_id, event_id


class DiffImpactTests(unittest.TestCase):
    def test_symbol_contract_change_propagates_downstream(self):
        registry, contracts, flows, _http, event = flow_inputs()
        changes = {
            "schema_version": 1,
            "workspace_id": "impact-fixture",
            "changes": [{
                "change_id": "c1",
                "repository_id": "api",
                "change_type": "modify",
                "surface_kind": "symbol",
                "identifier": "publish_order_created",
                "contract_ids": [event],
                "state": "observed",
                "evidence": ["git:diff"],
                "local_impact": {
                    "provider": "codegraph",
                    "symbols": ["publish_order_created"],
                    "tests": ["test_order_event"],
                    "evidence": ["codegraph:impact"],
                    "summary": {"filesAffected": 2, "breakingChanges": 0, "warnings": 1},
                },
            }],
        }
        report = IMPACT.normalize(registry, contracts, flows, changes)
        c1 = report["changes"][0]
        self.assertEqual(c1["impact_level"], "high")
        self.assertEqual(c1["review_repositories"], ["api", "repo_worker_01"])
        self.assertEqual(c1["impacted_flows"], ["flow_001"])
        self.assertIn(event, report["blast_radius"]["contracts"])
        self.assertIn("api:test_order_event", report["blast_radius"]["tests"])

    def test_local_helper_change_does_not_expand_cross_repo_without_evidence(self):
        registry, contracts, flows, _http, _event = flow_inputs()
        changes = {
            "schema_version": 1,
            "workspace_id": "impact-fixture",
            "changes": [{
                "change_id": "c2",
                "repository_id": "api",
                "change_type": "modify",
                "surface_kind": "symbol",
                "identifier": "internal_helper",
                "state": "observed",
                "evidence": ["git:diff"],
                "local_impact": {
                    "provider": "codegraph",
                    "symbols": ["internal_helper"],
                    "files": ["service/internal.py"],
                    "tests": ["test_internal_helper"],
                    "evidence": ["codegraph:impact"],
                    "summary": {"filesAffected": 1, "breakingChanges": 0, "warnings": 0},
                },
            }],
        }
        report = IMPACT.normalize(registry, contracts, flows, changes)
        c2 = report["changes"][0]
        self.assertEqual(c2["review_repositories"], ["api"])
        self.assertEqual(c2["impacted_contracts"], [])
        self.assertEqual(c2["impacted_flows"], [])
        self.assertEqual(c2["impact_level"], "low")

    def test_contract_version_mismatch_is_critical(self):
        registry, contracts, flows, _http, event = flow_inputs()
        changes = {
            "schema_version": 1,
            "workspace_id": "impact-fixture",
            "changes": [{
                "change_id": "c3",
                "repository_id": "api",
                "change_type": "version-change",
                "surface_kind": "event",
                "identifier": "event.order.created",
                "contract_id": event,
                "new_version": "2.0.0",
                "state": "observed",
                "evidence": ["schema:diff"],
                "local_impact": {"evidence": ["schema:validation"]},
            }],
        }
        report = IMPACT.normalize(registry, contracts, flows, changes)
        self.assertEqual(report["impact_level"], "critical")
        self.assertEqual(report["summary"]["version_mismatches"], 1)
        self.assertIn("c3", report["compatibility_findings"]["version_mismatch_changes"])

    def test_codegraph_shape_is_normalized(self):
        registry, contracts, flows, _http, _event = flow_inputs()
        changes = {
            "schema_version": 1,
            "workspace_id": "impact-fixture",
            "changes": [{
                "change_id": "c4",
                "repository_id": "api",
                "change_type": "modify",
                "surface_kind": "file",
                "identifier": "service/orders.py",
                "state": "observed",
                "evidence": ["git:diff"],
                "local_impact": {
                    "provider": "codegraph-0.20.1",
                    "repository_root": "/workspace/api",
                    "evidence": ["codegraph:run"],
                    "directImpact": [{
                        "uri": "file:///workspace/api/api/checkout.py",
                        "severity": "warning",
                        "type": "caller",
                    }],
                    "indirectImpact": [{
                        "uri": "file:///workspace/api/tests/test_checkout.py",
                        "severity": "info",
                        "path": ["calculate_total", "handle_checkout"],
                    }],
                    "affectedTests": [{
                        "uri": "file:///workspace/api/tests/test_checkout.py",
                        "testName": "test_checkout_total",
                    }],
                    "summary": {"filesAffected": 2, "breakingChanges": 0, "warnings": 1},
                },
            }],
        }
        report = IMPACT.normalize(registry, contracts, flows, changes)
        local = report["changes"][0]["local_impact"]
        self.assertEqual(local["files"], ["api/checkout.py", "tests/test_checkout.py"])
        self.assertEqual(local["tests"], ["test_checkout_total"])
        self.assertEqual(report["changes"][0]["impact_level"], "medium")

    def test_private_absolute_path_is_redacted(self):
        registry, contracts, flows, _http, _event = flow_inputs()
        changes = {
            "schema_version": 1,
            "workspace_id": "impact-fixture",
            "changes": [{
                "change_id": "c5",
                "repository_id": "repo_worker_01",
                "change_type": "modify",
                "surface_kind": "file",
                "identifier": "worker.py",
                "state": "observed",
                "evidence": ["git:diff"],
                "local_impact": {
                    "provider": "codegraph",
                    "evidence": ["codegraph:run"],
                    "directImpact": [{
                        "uri": "file:///home/runner/secret-owner/private-worker/worker.py",
                        "severity": "info",
                        "type": "reference",
                    }],
                },
            }],
        }
        report = IMPACT.normalize(registry, contracts, flows, changes)
        payload = json.dumps(report)
        self.assertNotIn("secret-owner", payload)
        self.assertIn("private-path-", payload)

    def test_inferred_change_preserves_constraint(self):
        registry, contracts, flows, _http, _event = flow_inputs()
        changes = {
            "schema_version": 1,
            "workspace_id": "impact-fixture",
            "changes": [{
                "change_id": "c6",
                "repository_id": "api",
                "change_type": "modify",
                "surface_kind": "symbol",
                "identifier": "handle_checkout",
                "state": "inferred",
                "rationale": "Diff hunk maps to the handler through symbol context.",
                "evidence": ["diff:context"],
                "local_impact": {"symbols":["handle_checkout"],"evidence":["codegraph:impact"]},
            }],
        }
        report = IMPACT.normalize(registry, contracts, flows, changes)
        self.assertIn("change observation is inferred", report["changes"][0]["constraints"])

    def test_file_without_semantic_evidence_is_partial(self):
        registry, contracts, flows, _http, _event = flow_inputs()
        changes = {
            "schema_version": 1,
            "workspace_id": "impact-fixture",
            "changes": [{
                "change_id": "c7",
                "repository_id": "api",
                "change_type": "modify",
                "surface_kind": "file",
                "identifier": "unknown.py",
                "state": "observed",
                "evidence": ["git:diff"],
                "local_impact": {},
            }],
        }
        report = IMPACT.normalize(registry, contracts, flows, changes)
        self.assertEqual(report["status"], "partial-evidence")
        self.assertEqual(report["changes"][0]["impact_level"], "unknown")

    def test_duplicate_change_id_is_rejected(self):
        registry, contracts, flows, _http, _event = flow_inputs()
        item = {
            "change_id": "dup",
            "repository_id": "api",
            "change_type": "modify",
            "surface_kind": "symbol",
            "identifier": "handle_checkout",
            "state": "observed",
            "evidence": ["git:diff"],
            "local_impact": {"symbols":["handle_checkout"],"evidence":["codegraph:impact"]},
        }
        changes = {"schema_version":1,"workspace_id":"impact-fixture","changes":[item,dict(item)]}
        with self.assertRaisesRegex(ValueError, "duplicate change_id"):
            IMPACT.normalize(registry, contracts, flows, changes)

    def test_contract_surface_requires_contract_id(self):
        registry, contracts, flows, _http, _event = flow_inputs()
        changes = {
            "schema_version":1,
            "workspace_id":"impact-fixture",
            "changes":[{
                "change_id":"bad",
                "repository_id":"api",
                "change_type":"modify",
                "surface_kind":"event",
                "identifier":"event.order.created",
                "state":"observed",
                "evidence":["diff"],
                "local_impact":{"evidence":["impact"]},
            }],
        }
        with self.assertRaisesRegex(ValueError, "requires contract_id"):
            IMPACT.normalize(registry, contracts, flows, changes)

    def test_workspace_mismatch_is_rejected(self):
        registry, contracts, flows, _http, _event = flow_inputs()
        changes = {"schema_version":1,"workspace_id":"other","changes":[{"x":1}]}
        with self.assertRaisesRegex(ValueError, "workspace_id mismatch"):
            IMPACT.normalize(registry, contracts, flows, changes)

    def test_deterministic_output(self):
        registry, contracts, flows, _http, _event = flow_inputs()
        changes = {
            "schema_version": 1,
            "workspace_id": "impact-fixture",
            "changes": [{
                "change_id": "c8",
                "repository_id": "api",
                "change_type": "modify",
                "surface_kind": "symbol",
                "identifier": "handle_checkout",
                "state": "observed",
                "evidence": ["git:diff"],
                "local_impact": {"symbols":["handle_checkout"],"evidence":["codegraph:impact"]},
            }],
        }
        one = IMPACT.normalize(registry, contracts, flows, changes)
        two = IMPACT.normalize(registry, contracts, flows, changes)
        self.assertEqual(one, two)
        self.assertEqual(IMPACT.render_markdown(one), IMPACT.render_markdown(two))


if __name__ == "__main__":
    unittest.main()
