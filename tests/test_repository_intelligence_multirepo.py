import importlib.util
import json
import pathlib
import unittest


SCRIPT = pathlib.Path(__file__).parents[1] / "agents" / "repo-skill-steward" / "repository-intelligence" / "scripts" / "multi_repo_registry.py"
SPEC = importlib.util.spec_from_file_location("multi_repo_registry", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def workspace():
    return {
        "schema_version": 1,
        "workspace_id": "fixture-workspace",
        "repositories": [
            {
                "repository_id": "web",
                "visibility": "public",
                "source": "sazan-lab/web",
                "revision": "web-1",
                "requires": [
                    {
                        "key": "http.checkout.v1",
                        "kind": "http-api",
                        "version": "1.0.0",
                        "provider_hint": "api",
                        "state": "observed",
                        "evidence": ["web:client-code"],
                    },
                    {
                        "key": "external.stripe.v1",
                        "kind": "http-api",
                        "version": "2026-09",
                        "scope": "external",
                        "state": "observed",
                        "evidence": ["web:stripe-client"],
                    },
                ],
            },
            {
                "repository_id": "api",
                "visibility": "public",
                "source": "sazan-lab/api",
                "revision": "api-1",
                "provides": [
                    {
                        "key": "http.checkout.v1",
                        "kind": "http-api",
                        "version": "1.0.0",
                        "surface": "POST /checkout",
                        "state": "observed",
                        "evidence": ["api:openapi"],
                    },
                    {
                        "key": "event.order.created",
                        "kind": "event",
                        "version": "1.0.0",
                        "state": "observed",
                        "evidence": ["api:event-publisher"],
                    },
                ],
                "requires": [
                    {
                        "key": "schema.checkout.v1",
                        "kind": "schema",
                        "version": "1.0.0",
                        "provider_hint": "contracts",
                        "state": "observed",
                        "evidence": ["api:schema-import"],
                    }
                ],
            },
            {
                "repository_id": "contracts",
                "visibility": "public",
                "source": "sazan-lab/contracts",
                "revision": "contracts-1",
                "provides": [
                    {
                        "key": "schema.checkout.v1",
                        "kind": "schema",
                        "version": "1.0.0",
                        "state": "observed",
                        "evidence": ["contracts:schema"],
                    }
                ],
            },
            {
                "repository_id": "repo_worker_01",
                "visibility": "private",
                "source": "secret-owner/payments-worker",
                "revision": "worker-7",
                "requires": [
                    {
                        "key": "event.order.created",
                        "kind": "event",
                        "version": "1.0.0",
                        "provider_hint": "api",
                        "state": "observed",
                        "evidence": ["worker:event-consumer"],
                    }
                ],
            },
        ],
    }


class MultiRepoRegistryTests(unittest.TestCase):
    def test_matches_cross_repo_contracts(self):
        registry, report = MODULE.build(workspace())
        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["summary"]["matched_contracts"], 3)
        self.assertEqual(report["summary"]["external_requirements"], 1)
        self.assertEqual(report["summary"]["blockers"], 0)
        self.assertIn("api", registry["relationships"]["web"]["upstream"])
        self.assertIn("web", registry["relationships"]["api"]["downstream"])

    def test_private_source_is_not_persisted(self):
        registry, report = MODULE.build(workspace())
        payload = json.dumps({"registry": registry, "report": report}, sort_keys=True)
        self.assertNotIn("secret-owner", payload)
        private = next(r for r in registry["repositories"] if r["repository_id"] == "repo_worker_01")
        self.assertIsNone(private["source"])

    def test_private_repo_requires_opaque_id(self):
        data = workspace()
        data["repositories"][-1].pop("repository_id")
        with self.assertRaisesRegex(ValueError, "stable opaque repository_id"):
            MODULE.build(data)

    def test_version_mismatch_blocks(self):
        data = workspace()
        data["repositories"][0]["requires"][0]["version"] = "2.0.0"
        _registry, report = MODULE.build(data)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["summary"]["version_mismatches"], 1)
        self.assertTrue(any(x["type"] == "version-mismatch" for x in report["blockers"]))

    def test_missing_internal_provider_blocks(self):
        data = workspace()
        data["repositories"][0]["requires"][0]["key"] = "http.missing.v1"
        _registry, report = MODULE.build(data)
        self.assertEqual(report["status"], "blocked")
        self.assertTrue(any(x["type"] == "unresolved-contract" for x in report["blockers"]))

    def test_external_requirement_does_not_block(self):
        data = workspace()
        data["repositories"][0]["requires"] = [
            {
                "key": "external.only",
                "kind": "http-api",
                "version": "1",
                "scope": "external",
                "state": "observed",
                "evidence": ["client-code"],
            }
        ]
        _registry, report = MODULE.build(data)
        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["summary"]["external_requirements"], 1)

    def test_ambiguous_provider_blocks_without_hint(self):
        data = workspace()
        data["repositories"][0]["requires"][0].pop("provider_hint")
        data["repositories"][2]["provides"].append({
            "key": "http.checkout.v1",
            "kind": "http-api",
            "version": "1.0.0",
            "state": "observed",
            "evidence": ["contracts:proxy"],
        })
        _registry, report = MODULE.build(data)
        self.assertTrue(any(x["type"] == "ambiguous-provider" for x in report["blockers"]))

    def test_provider_hint_resolves_ambiguity(self):
        data = workspace()
        data["repositories"][2]["provides"].append({
            "key": "http.checkout.v1",
            "kind": "http-api",
            "version": "1.0.0",
            "state": "observed",
            "evidence": ["contracts:proxy"],
        })
        _registry, report = MODULE.build(data)
        self.assertFalse(any(
            x["type"] == "ambiguous-provider" and x.get("consumer") == "web"
            for x in report["blockers"]
        ))

    def test_inferred_contract_requires_rationale(self):
        data = workspace()
        data["repositories"][0]["requires"][0]["state"] = "inferred"
        with self.assertRaisesRegex(ValueError, "requires rationale"):
            MODULE.build(data)

    def test_inferred_relationship_propagates_constraint(self):
        data = workspace()
        req = data["repositories"][0]["requires"][0]
        req["state"] = "inferred"
        req["rationale"] = "Client symbol name and route usage imply the dependency."
        _registry, report = MODULE.build(data)
        checkout = next(c for c in report["contracts"] if c["consumer"] == "web")
        self.assertEqual(checkout["claim_state"], "inferred")
        self.assertTrue(checkout["constraints"])

    def test_output_is_deterministic(self):
        one = MODULE.build(workspace())
        two = MODULE.build(workspace())
        self.assertEqual(
            json.dumps(one, sort_keys=True),
            json.dumps(two, sort_keys=True),
        )


if __name__ == "__main__":
    unittest.main()
