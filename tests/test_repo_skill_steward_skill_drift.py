import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "agents" / "repo-skill-steward" / "scripts" / "skill_drift.py"


def load_module():
    spec = importlib.util.spec_from_file_location("skill_drift", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


skill_drift = load_module()


class SkillDriftTests(unittest.TestCase):
    def test_exact_copy_is_refresh_eligible_but_not_auto_replace(self):
        text = "---\nname: demo\ndescription: Demo\n---\n# Demo\n"
        result = skill_drift.compare(text, text)
        self.assertEqual(result["status"], "exact-copy")
        self.assertFalse(result["manual_review_required"])
        self.assertFalse(result["auto_replace"])

    def test_same_name_modified_copy_requires_manual_review(self):
        canonical = "---\nname: demo\ndescription: Canonical\n---\n# Demo\n"
        installed = "---\nname: demo\ndescription: Project adapted\n---\n# Demo\nProject rule.\n"
        result = skill_drift.compare(canonical, installed)
        self.assertEqual(result["status"], "same-name-local-drift")
        self.assertEqual(result["sync_mode"], "preserve-local-review-upstream")
        self.assertTrue(result["manual_review_required"])
        self.assertFalse(result["auto_replace"])

    def test_different_skill_names_never_sync(self):
        canonical = "---\nname: one\ndescription: One\n---\n"
        installed = "---\nname: two\ndescription: Two\n---\n"
        result = skill_drift.compare(canonical, installed)
        self.assertEqual(result["status"], "different-skill")
        self.assertTrue(result["manual_review_required"])
        self.assertFalse(result["auto_replace"])


if __name__ == "__main__":
    unittest.main()
