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

def fixture():
    workspace = {
        "schema_version": 1,
        "workspace_id": "impact-fixture",
        "repositories": [
            {"repository_id":"web","visibility":"local-fixture","source":"fixture/web","revision":"web-1","requires":[{"key":"http.checkout.v1","kind":"http-api","version":"1.0.0","provider_hint":"api","state":"observed","evidence":["web:http"]}]},
            {"repository_id":"api","visibility":"local-fixture","source":"fixture/api","revision":"api-2","provides":[{"key":"http.checkout.v1","kind":"http-api","version":"1.0.0","state":"observed","evidence":["api:http"]},{"key":"event.order.created","kind":"event","version":"1.0.0","state":"observed","evidence":["api:event"]}]},
            {"repository_id":"repo_worker_01","visibility":"private","source":"secret-owner/private-worker","revision":"worker-1","requires":[{"key":"event.order.created","kind":"event","version":"1.0.0","provider_hint":"api","state":"observed","evidence":["worker:event"]}]}
        ]
    }
    registry, contracts = REG.build(workspace)
    http_id = next(c["contract_id"] for c in contracts["contracts"] if c["kind"] == "http-api")
    event_id = next(c["contract_id"] for c in contracts["contracts"] if c["kind"] == "event")
    obs = {
        "schema_version":1,"workspace_id":"impact-fixture",
        "steps":[
            {"step_id":"web.submit","repository_id":"web","label":"Web submit","symbol":"submitCheckout","kind":"entry","entry":True,"state":"observed","evidence":["web:submit"]},
            {"step_id":"web.http","repository_id":"web","label":"HTTP client","symbol":"postCheckout","kind":"http-client","state":"observed","evidence":["web:http"]},
            {"step_id":"api.handle","repository_id":"api","label":"Checkout handler","symbol":"handle_checkout","kind":"http-handler","state":"observed","evidence":["api:handler"]},
            {"step_id":"api.publish","repository_id":"api","label":"Publish event","symbol":"publish_order_created","kind":"event-publisher","state":"observed","evidence":["api:publish"]},
            {"step_id":"worker.consume","repository_id":"repo_worker_01","label":"Consume event","symbol":"consume_order_created","kind":"event-consumer","state":"observed","evidence":["worker:consume"]},
            {"step_id":"worker.store","repository_id":"repo_worker_01","label":"Store order","symbol":"persist_order","kind":"storage-write","terminal":True,"state":"observed","evidence":["worker:store"]}
        ],
        "edges":[
            {"from":"web.submit","to":"web.http","relation":"calls","state":"observed","evidence":["web:call"]},
            {"from":"api.handle","to":"api.publish","relation":"publishes","state":"observed","evidence":["api:call"]},
            {"from":"worker.consume","to":"worker.store","relation":"writes","state":"observed","evidence":["worker:call"]}
        ],
        "bindings":[
            {"contract_id":http_id,"provider_step":"api.handle","consumer_step":"web.http","flow_direction":"consumer-to-provider","state":"observed","evidence":["binding:http"]},
            {"contract_id":event_id,"provider_step":"api.publish","consumer_step":"worker.consume","flow_direction":"provider-to-consumer","state":"observed","evidence":["binding:event"]}
        ]
    }
    flows = FLOW.synthesize(registry, contracts, obs)
    return registry, contracts, flows, http_id

def change():
    return {
        "schema_version":1,"workspace_id":"impact-fixture",
        "changes":[{
            "change_id":"api-handler","repository_id":"api","change_type":"modify","surface_kind":"symbol","identifier":"handle_checkout","path":"api/checkout.py","symbol":"handle_checkout","state":"observed","evidence":["git-diff"],
            "local_impact":{"risk_level":"low","symbols":["handle_checkout"],"files":["api/checkout.py"],"tests":["tests/test_checkout.py"],"direct_callers":["test_checkout_total"],"steps":["api.handle"],"evidence":["codegraph:pr_context"]}
        }]
    }

class DiffImpactTests(unittest.TestCase):
    def test_symbol_change_propagates_downstream_only(self):
        r,c,f,_ = fixture()
        out = IMPACT.normalize(r,c,f,change())
        self.assertEqual(out["blast_radius"]["repositories"], ["api","repo_worker_01"])
        self.assertNotIn("web", out["blast_radius"]["repositories"])

    def test_contract_touch_adds_counterparty(self):
        r,c,f,http_id = fixture()
        data = change()
        data["changes"][0]["contract_touches"]=[{"contract_id":http_id,"side":"provider","state":"observed","evidence":["api:http-contract"]}]
        out=IMPACT.normalize(r,c,f,data)
        self.assertEqual(out["blast_radius"]["repositories"], ["api","repo_worker_01","web"])
        self.assertEqual(out["blast_radius"]["contracts"], [http_id])

    def test_local_risk_is_preserved_not_recomputed(self):
        r,c,f,_=fixture()
        data=change(); data["changes"][0]["local_impact"]["risk_level"]="medium"
        out=IMPACT.normalize(r,c,f,data)
        self.assertEqual(out["changes"][0]["local_impact"]["risk_level"],"medium")
        self.assertNotIn("risk_level",out)

    def test_related_tests_preserved(self):
        r,c,f,_=fixture()
        out=IMPACT.normalize(r,c,f,change())
        self.assertEqual(out["blast_radius"]["related_tests"],["tests/test_checkout.py"])

    def test_file_without_semantic_evidence_is_partial(self):
        r,c,f,_=fixture()
        data={"schema_version":1,"workspace_id":"impact-fixture","changes":[{"change_id":"file","repository_id":"api","change_type":"modify","surface_kind":"file","identifier":"api/checkout.py","state":"observed","evidence":["git-diff"]}]}
        out=IMPACT.normalize(r,c,f,data)
        self.assertEqual(out["status"],"partial-evidence")

    def test_inferred_contract_touch_downgrades_confidence(self):
        r,c,f,http_id=fixture()
        data=change()
        data["changes"][0]["contract_touches"]=[{"contract_id":http_id,"side":"provider","state":"inferred","evidence":["route-overlap"],"rationale":"Handler is inferred to implement the HTTP surface."}]
        out=IMPACT.normalize(r,c,f,data)
        self.assertEqual(out["changes"][0]["evidence_confidence"],"inferred")
        self.assertIn("contract-touch mapping contains inferred evidence",out["changes"][0]["constraints"])

    def test_wrong_contract_side_is_rejected(self):
        r,c,f,http_id=fixture()
        data=change()
        data["changes"][0]["contract_touches"]=[{"contract_id":http_id,"side":"consumer","state":"observed","evidence":["bad"]}]
        with self.assertRaisesRegex(ValueError,"consumer-side touch"):
            IMPACT.normalize(r,c,f,data)

    def test_provider_version_change_compares_consumer_requirement(self):
        r,c,f,http_id=fixture()
        data={"schema_version":1,"workspace_id":"impact-fixture","changes":[{"change_id":"v2","repository_id":"api","change_type":"version-change","surface_kind":"http-api","identifier":"http.checkout.v1","contract_id":http_id,"new_version":"2.0.0","state":"observed","evidence":["openapi-diff"]}]}
        out=IMPACT.normalize(r,c,f,data)
        self.assertEqual(out["summary"]["version_mismatches"],1)

    def test_private_source_not_present(self):
        r,c,f,_=fixture()
        out=IMPACT.normalize(r,c,f,change())
        self.assertNotIn("secret-owner",json.dumps(out,sort_keys=True))

    def test_deterministic(self):
        r,c,f,_=fixture()
        a=IMPACT.normalize(r,c,f,change()); b=IMPACT.normalize(r,c,f,change())
        self.assertEqual(a,b)
        self.assertEqual(IMPACT.render_markdown(a),IMPACT.render_markdown(b))


    def test_duplicate_change_id_is_rejected(self):
        r,c,f,_=fixture()
        item=change()["changes"][0]
        data={"schema_version":1,"workspace_id":"impact-fixture","changes":[item,dict(item)]}
        with self.assertRaisesRegex(ValueError,"duplicate change_id"):
            IMPACT.normalize(r,c,f,data)

    def test_private_absolute_path_is_redacted(self):
        r,c,f,_=fixture()
        data={
            "schema_version":1,
            "workspace_id":"impact-fixture",
            "changes":[{
                "change_id":"private-file",
                "repository_id":"repo_worker_01",
                "change_type":"modify",
                "surface_kind":"file",
                "identifier":"worker.py",
                "state":"observed",
                "evidence":["git-diff"],
                "local_impact":{
                    "files":["/home/runner/secret-owner/private-worker/worker.py"],
                    "evidence":["codegraph:impact"]
                }
            }]
        }
        out=IMPACT.normalize(r,c,f,data)
        payload=json.dumps(out,sort_keys=True)
        self.assertNotIn("secret-owner",payload)
        self.assertIn("private-path-",payload)

if __name__ == "__main__":
    unittest.main()
