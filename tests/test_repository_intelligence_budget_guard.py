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
ENV = load("evidence_envelope", "evidence_envelope.py")
ORCH = load("orchestrator_budget", "orchestrate_repository_intelligence.py")


def budgets():
    return {
        "max_context_tokens": 100,
        "max_graph_nodes": 50,
        "max_output_bytes": 1000,
        "stage_timeout_seconds": 30,
    }


def manifest(strict=True, allow_truncation=False):
    return {
        "run_id": "budget-run",
        "purpose": "budget fixture",
        "mode": "analysis",
        "target": {
            "source": "fixture/repo",
            "revision": "abc123",
            "visibility": "local-fixture",
        },
        "budgets": budgets(),
        "budget_policy": {
            "strict": strict,
            "allow_truncation": allow_truncation,
        },
    }


class BudgetGuardTests(unittest.TestCase):
    def test_cumulative_context_and_output(self):
        one = BUDGET.evaluate(
            budgets(),
            None,
            "L1-context-packaging",
            {
                "context_tokens": 40,
                "context_token_method": "provider-reported",
                "output_bytes": 300,
                "elapsed_seconds": 2.0,
            },
        )
        self.assertEqual(one["decision"], "allow")
        self.assertEqual(one["usage"]["context_tokens"], 40)
        self.assertEqual(one["usage"]["output_bytes"], 300)

        two = BUDGET.evaluate(
            budgets(),
            one["usage"],
            "L4-wiki-qa",
            {
                "context_tokens": 50,
                "context_token_method": "exact-tokenizer",
                "output_bytes": 500,
                "elapsed_seconds": 3.0,
            },
        )
        self.assertEqual(two["decision"], "allow")
        self.assertEqual(two["usage"]["context_tokens"], 90)
        self.assertEqual(two["usage"]["output_bytes"], 800)
        self.assertEqual(two["remaining"]["context_tokens"], 10)
        self.assertEqual(two["remaining"]["output_bytes"], 200)

    def test_cumulative_context_overage_blocks(self):
        prior = BUDGET.initial_usage()
        prior["context_tokens"] = 80
        result = BUDGET.evaluate(
            budgets(),
            prior,
            "L4-wiki-qa",
            {
                "context_tokens": 30,
                "context_token_method": "provider-reported",
            },
        )
        self.assertEqual(result["decision"], "block")
        self.assertTrue(any("context token budget exceeded" in x for x in result["violations"]))

    def test_graph_nodes_use_max_not_sum(self):
        first = BUDGET.evaluate(budgets(), None, "L2-semantic-graph", {"graph_nodes": 30})
        second = BUDGET.evaluate(budgets(), first["usage"], "L3-architecture-presentation", {"graph_nodes": 40})
        self.assertEqual(second["usage"]["graph_nodes"], 40)
        self.assertEqual(second["decision"], "allow")

    def test_timeout_blocks(self):
        result = BUDGET.evaluate(
            budgets(), None, "L2-semantic-graph", {"elapsed_seconds": 30.1}
        )
        self.assertEqual(result["decision"], "block")
        self.assertTrue(any("stage timeout budget exceeded" in x for x in result["violations"]))

    def test_strict_missing_required_metric_blocks(self):
        result = BUDGET.evaluate(
            budgets(),
            None,
            "L1-context-packaging",
            {"output_bytes": 10, "elapsed_seconds": 1},
            required_metrics=["context_tokens", "output_bytes", "elapsed_seconds"],
            strict=True,
        )
        self.assertEqual(result["decision"], "block")
        self.assertEqual(result["missing_required"], ["context_tokens"])
        self.assertIn("context_tokens", result["unmeasured"])

    def test_truncation_blocks_by_default(self):
        result = BUDGET.evaluate(
            budgets(), None, "L1-context-packaging", {"truncated": True}
        )
        self.assertEqual(result["decision"], "block")

    def test_truncation_can_be_explicitly_constrained(self):
        result = BUDGET.evaluate(
            budgets(),
            None,
            "L1-context-packaging",
            {"truncated": True},
            allow_truncation=True,
        )
        self.assertEqual(result["decision"], "allow-with-constraints")
        self.assertIn("provider output was explicitly truncated", result["constraints"])

    def test_context_token_method_is_required(self):
        with self.assertRaisesRegex(ValueError, "context_token_method"):
            BUDGET.evaluate(budgets(), None, "L1-context-packaging", {"context_tokens": 3})

    def test_boolean_numeric_metric_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "non-negative integer"):
            BUDGET.evaluate(budgets(), None, "L2-semantic-graph", {"graph_nodes": True})

    def test_envelope_persists_budget_policy_and_usage(self):
        env = ENV.new_envelope(manifest(strict=True, allow_truncation=True))
        self.assertEqual(
            env["budget_policy"],
            {"strict": True, "allow_truncation": True},
        )
        self.assertEqual(env["budget_usage"], BUDGET.initial_usage())
        ENV.validate_envelope(env)

    def write_run(self, temp_dir, manifest_data, stage_results):
        root = pathlib.Path(temp_dir)
        manifest_path = root / "manifest.json"
        stage_dir = root / "stages"
        stage_dir.mkdir()
        manifest_path.write_text(json.dumps(manifest_data))
        for result in stage_results:
            (stage_dir / f"{result['stage']}.json").write_text(json.dumps(result))
        return manifest_path, stage_dir

    def test_orchestrator_blocks_over_budget(self):
        l0 = {
            "stage": "L0-intake",
            "status": "passed",
            "provider": "fixture",
            "evidence": ["e0"],
            "artifacts": [],
            "metrics": {"output_bytes": 100, "elapsed_seconds": 1},
            "constraints": [],
        }
        l1 = {
            "stage": "L1-context-packaging",
            "status": "passed",
            "provider": "fixture",
            "evidence": ["e1"],
            "artifacts": [],
            "metrics": {
                "context_tokens": 101,
                "context_token_method": "provider-reported",
                "output_bytes": 100,
                "elapsed_seconds": 1,
            },
            "constraints": [],
        }
        with tempfile.TemporaryDirectory() as td:
            mp, sd = self.write_run(td, manifest(), [l0, l1])
            _plan, env = ORCH.run(mp, sd)
            self.assertEqual(env["status"], "blocked")
            stage = next(s for s in env["stages"] if s["id"] == "L1-context-packaging")
            self.assertEqual(stage["status"], "blocked")
            self.assertEqual(stage["budget"]["decision"], "block")

    def test_provider_failure_remains_failed(self):
        failed = {
            "stage": "L0-intake",
            "status": "failed",
            "provider": "fixture",
            "evidence": [],
            "artifacts": [],
            "metrics": {},
            "constraints": [],
            "error": "provider failed",
        }
        with tempfile.TemporaryDirectory() as td:
            mp, sd = self.write_run(td, manifest(), [failed])
            _plan, env = ORCH.run(mp, sd)
            self.assertEqual(env["status"], "failed")
            stage = next(s for s in env["stages"] if s["id"] == "L0-intake")
            self.assertEqual(stage["status"], "failed")


if __name__ == "__main__":
    unittest.main()
