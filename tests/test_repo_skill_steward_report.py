import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "agents" / "repo-skill-steward" / "scripts" / "report.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


report = load_module("steward_report", REPORT_PATH)


class ScheduledAuditReportTests(unittest.TestCase):
    def test_private_identity_is_not_rendered(self):
        inventory = {
            "repositories": [
                {
                    "full_name": "owner/public",
                    "visibility": "public",
                },
                {
                    "full_name": "<private-repository>",
                    "visibility": "private",
                    "has_dependencies": True,
                },
            ]
        }
        classification = {
            "repositories": [
                {
                    "full_name": "owner/public",
                    "strategies": ["monitor-only"],
                    "verification_profile": "monitor-only",
                    "auto_propose": False,
                    "auto_merge": False,
                    "gates": [],
                },
                {
                    "full_name": "<private-repository>",
                    "strategies": ["dependency-update"],
                    "verification_profile": "manual-review-first",
                    "auto_propose": False,
                    "auto_merge": False,
                    "gates": ["tests-missing"],
                },
            ]
        }

        summary = report.summarize(inventory, classification)
        rendered = report.render_markdown(summary)

        self.assertIn("owner/public", rendered)
        self.assertNotIn("<private-repository>", rendered)
        self.assertEqual(summary["private_repository_count"], 1)
        self.assertEqual(summary["strategy_counts"]["dependency-update"], 1)

    def test_mismatched_counts_fail_closed(self):
        with self.assertRaises(ValueError):
            report.summarize(
                {"repositories": [{"visibility": "public"}]},
                {"repositories": []},
            )


if __name__ == "__main__":
    unittest.main()
