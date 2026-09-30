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


BUDGET = load("budget_guard", "budget_guard.py")
ORCH = load("orchestrator_budget", "orchestrate_repository_intelligence.py")


def budgets():
    return {
        "max_context_tokens": 1000,
        "max_graph_nodes": 100,
        "max_output_bytes": 10000,
        "stage_timeout_seconds": 30,
    }


class BudgetGuardTests(unittest.TestCase):
    def test_within_budget_allows(self):
        result = BUDGET.evaluate(
            budgets(),
            None,
            "L1-context-packaging",
            {
                "context_tokens": 100,
                "context_token_method": "provider-reported",
                "output_bytes": 500,
                "elapsed_seconds": 2.5,
            },
            required_metrics=["context_tokens", "output_bytes", "elapsed_seconds"],
            strict=True,
        )
        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["usage"]["context_tokens"], 100)
        self.assertEqual(result["usage"]["output_bytes"], 500)

    def test_context_and_output_are_cumulative(self):
        first = BUDGET.evaluate(
            budgets(),
            None,
            "L1-context-packaging",
            {
                "context_tokens": 600,
                "context_token_method": "provider-reported",
                "output_bytes": 7000,
                "elapsed_seconds": 1,
            },
        )
        second = BUDGET.evaluate(
            budgets(),
            first["usage"],
            "L4-wiki-qa",
            {
                "context_tokens": 500,
                "context_token_method": "exact-tokenizer",
                "output_bytes": 3500,
                "elapsed_seconds": 1,
            },
        )
        self.assertEqual(second["decision"], "block")
        self.assertEqual(second["usage"]["context_tokens"], 1100)
        self.assertEqual(second["usage"]["output_bytes"], 10500)

    def test_graph_nodes_use_max_not_sum(self):
        first = BUDGET.evaluate(budgets(), None, "L2-semantic-graph", {"graph_nodes": 70})
        second = BUDGET.evaluate(budgets(), first["usage"], "L3-architecture-presentation", {"graph_nodes": 80})
        self.assertEqual(second["usage"]["graph_nodes"], 80)
        self.assertEqual(second["decision"], "allow")

    def test_missing_required_metric_blocks_in_strict_mode(self):
        result = BUDGET.evaluate(
            budgets(),
            None,
            "L2-semantic-graph",
            {"graph_nodes": 10, "output_bytes": 50},
            required_metrics=["graph_nodes", "output_bytes", "elapsed_seconds"],
            strict=True,
        )
        self.assertEqual(result["decision"], "block")
        self.assertEqual(result["missing_required"], ["elapsed_seconds"])

    def test_missing_metric_is_legacy_compatible_when_not_strict(self):
        result = BUDGET.evaluate(
            budgets(),
            None,
            "L2-semantic-graph",
            {},
            required_metrics=["graph_nodes"],
            strict=False,
        )
        self.assertEqual(result["decision"], "allow")

    def test_context_method_is_required(self):
        with self.assertRaisesRegex(ValueError, "context_token_method"):
            BUDGET.evaluate(
                budgets(),
                None,
                "L1-context-packaging",
                {"context_tokens": 10},
            )

    def test_timeout_blocks(self):
        result = BUDGET.evaluate(
            budgets(),
            None,
            "L1-context-packaging",
            {"elapsed_seconds": 31},
        )
        self.assertEqual(result["decision"], "block")
        self.assertTrue(any("stage timeout" in x for x in result["violations"]))

    def test_truncation_blocks_by_default(self):
        result = BUDGET.evaluate(
            budgets(),
            None,
            "L1-context-packaging",
            {"truncated": True},
        )
        self.assertEqual(result["decision"], "block")

    def test_explicit_truncation_override_is_constrained(self):
        result = BUDGET.evaluate(
            budgets(),
            None,
            "L1-context-packaging",
            {"truncated": True},
            allow_truncation=True,
        )
        self.assertEqual(result["decision"], "allow-with-constraints")
        self.assertTrue(result["constraints"])

    def test_output_bytes_over_limit_blocks(self):
        result = BUDGET.evaluate(
            budgets(),
            None,
            "L3-architecture-presentation",
            {"output_bytes": 10001},
        )
        self.assertEqual(result["decision"], "block")

    def test_exact_output_bytes_helper(self):
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "artifact.bin"
            path.write_bytes(b"abcdef")
            self.assertEqual(BUDGET.exact_output_bytes(path), 6)

    def test_graph_node_count_helper(self):
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "graph.json"
            path.write_text(json.dumps({"nodes": [{"id": 1}, {"id": 2}], "edges": []}))
            self.assertEqual(BUDGET.graph_node_count(path), 2)

    def test_result_is_deterministic(self):
        metrics = {
            "context_tokens": 20,
            "context_token_method": "utf8-byte-upper-bound",
            "output_bytes": 30,
            "elapsed_seconds": 1.25,
        }
        one = BUDGET.evaluate(budgets(), None, "L1-context-packaging", metrics)
        two = BUDGET.evaluate(budgets(), None, "L1-context-packaging", metrics)
        self.assertEqual(one, two)


def strict_manifest():
    return {
        "run_id": "budget-strict-run",
        "purpose": "strict budget fixture",
        "mode": "analysis",
        "target": {
            "source": "fixture/repo",
            "revision": "abc123",
            "visibility": "local-fixture",
        },
        "privacy": {"persist_private_identity": False},
        "budgets": {
            "max_context_tokens": 5000,
            "max_graph_nodes": 500,
            "max_output_bytes": 50000,
            "stage_timeout_seconds": 60,
        },
        "budget_policy": {
            "strict": True,
            "allow_truncation": False,
        },
    }


def stage_result(stage_id, metrics, cross=None):
    return {
        "stage": stage_id,
        "status": "passed",
        "provider": "budget-fixture",
        "evidence": [f"evidence:{stage_id}"],
        "artifacts": [f"artifact:{stage_id}"],
        "metrics": metrics,
        "constraints": [],
        "cross_cutting": cross or {},
    }


def strict_stage_results():
    cross = {
        "license": {"status": "compatible", "evidence": ["MIT"]},
        "security": {"status": "passed", "evidence": ["security"]},
        "capability_delta": {"status": "new", "evidence": ["delta"]},
        "rollback": {"status": "verified", "evidence": ["rollback"]},
        "private_data": {"status": "compliant", "evidence": ["privacy"]},
        "verifier": {"status": "verified", "evidence": ["verifier"]},
    }
    return [
        stage_result("L0-intake", {"output_bytes": 100, "elapsed_seconds": 1}, cross=cross),
        stage_result("L1-context-packaging", {
            "context_tokens": 1000,
            "context_token_method": "provider-reported",
            "output_bytes": 1000,
            "elapsed_seconds": 2,
        }),
        stage_result("L2-semantic-graph", {
            "graph_nodes": 100,
            "output_bytes": 1000,
            "elapsed_seconds": 2,
        }),
        stage_result("L3-architecture-presentation", {
            "output_bytes": 1000,
            "elapsed_seconds": 1,
        }),
        stage_result("L4-wiki-qa", {
            "context_tokens": 500,
            "context_token_method": "exact-tokenizer",
            "output_bytes": 1000,
            "elapsed_seconds": 2,
        }),
        stage_result("L6-reverse-engineering", {
            "context_tokens": 500,
            "context_token_method": "provider-reported",
            "output_bytes": 1000,
            "elapsed_seconds": 2,
        }),
    ]


class OrchestratorBudgetTests(unittest.TestCase):
    def write_run(self, tmp, manifest, results):
        root = pathlib.Path(tmp)
        manifest_path = root / "manifest.json"
        stage_dir = root / "stages"
        stage_dir.mkdir()
        manifest_path.write_text(json.dumps(manifest))
        for result in results:
            (stage_dir / f"{result['stage']}.json").write_text(json.dumps(result))
        return manifest_path, stage_dir

    def test_strict_complete_run_reaches_parent_review(self):
        with tempfile.TemporaryDirectory() as td:
            manifest_path, stage_dir = self.write_run(td, strict_manifest(), strict_stage_results())
            plan, envelope = ORCH.run(manifest_path, stage_dir)
            self.assertTrue(plan["budget_policy"]["strict"])
            self.assertEqual(envelope["status"], "ready-for-parent-review")
            self.assertGreater(envelope["budget_usage"]["stages_measured"], 0)
            l2 = next(x for x in envelope["stages"] if x["id"] == "L2-semantic-graph")
            self.assertEqual(l2["budget"]["decision"], "allow")

    def test_strict_missing_metric_blocks_stage(self):
        results = strict_stage_results()
        results[1]["metrics"].pop("elapsed_seconds")
        with tempfile.TemporaryDirectory() as td:
            manifest_path, stage_dir = self.write_run(td, strict_manifest(), results)
            _plan, envelope = ORCH.run(manifest_path, stage_dir)
            self.assertEqual(envelope["status"], "blocked")
            l1 = next(x for x in envelope["stages"] if x["id"] == "L1-context-packaging")
            self.assertEqual(l1["budget"]["decision"], "block")
            self.assertIn("elapsed_seconds", l1["budget"]["missing_required"])

    def test_strict_truncated_provider_blocks(self):
        results = strict_stage_results()
        results[1]["metrics"]["truncated"] = True
        with tempfile.TemporaryDirectory() as td:
            manifest_path, stage_dir = self.write_run(td, strict_manifest(), results)
            _plan, envelope = ORCH.run(manifest_path, stage_dir)
            self.assertEqual(envelope["status"], "blocked")

    def test_legacy_manifest_remains_non_strict(self):
        manifest = strict_manifest()
        manifest.pop("budget_policy")
        results = strict_stage_results()
        for result in results:
            result["metrics"] = {"fixture": 1}
        with tempfile.TemporaryDirectory() as td:
            manifest_path, stage_dir = self.write_run(td, manifest, results)
            _plan, envelope = ORCH.run(manifest_path, stage_dir)
            self.assertEqual(envelope["status"], "ready-for-parent-review")
            self.assertFalse(envelope["budget_policy"]["strict"])

    def test_provider_failure_remains_primary_failure(self):
        failed = {
            "stage": "L0-intake",
            "status": "failed",
            "provider": "fixture-provider",
            "evidence": [],
            "artifacts": [],
            "metrics": {},
            "constraints": [],
            "error": "provider failed before producing metrics",
            "cross_cutting": {},
        }
        with tempfile.TemporaryDirectory() as td:
            manifest_path, stage_dir = self.write_run(td, strict_manifest(), [failed])
            _plan, envelope = ORCH.run(manifest_path, stage_dir)
            self.assertEqual(envelope["status"], "failed")
            l0 = next(x for x in envelope["stages"] if x["id"] == "L0-intake")
            self.assertEqual(l0["status"], "failed")
            self.assertEqual(l0["budget"]["decision"], "not-evaluated")


if __name__ == "__main__":
    unittest.main()
