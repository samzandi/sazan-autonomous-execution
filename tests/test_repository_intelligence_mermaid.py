import importlib.util
import pathlib
import unittest


SCRIPT = pathlib.Path(__file__).parents[1] / "agents" / "repo-skill-steward" / "repository-intelligence" / "scripts" / "render_architecture_mermaid.py"
SPEC = importlib.util.spec_from_file_location("render_architecture_mermaid", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class MermaidRendererTests(unittest.TestCase):
    def fixture(self):
        return {
            "nodes": [
                {"id": "1", "name": "checkout", "path": "api/checkout.py", "type": "codefile", "language": "python", "is_external": False},
                {"id": "2", "name": "orders", "path": "service/orders.py", "type": "codefile", "language": "python", "is_external": False},
                {"id": "3", "name": "money", "path": "core/money.py", "type": "codefile", "language": "python", "is_external": False},
                {"id": "ext", "name": "requests", "path": "", "type": "module", "language": "unknown", "is_external": True},
            ],
            "edges": [
                {"from": "1", "to": "2", "type": "import"},
                {"from": "2", "to": "3", "type": "import"},
                {"from": "2", "to": "ext", "type": "import"},
            ],
        }

    def test_deterministic(self):
        one = MODULE.render(self.fixture(), title="Fixture")
        two = MODULE.render(self.fixture(), title="Fixture")
        self.assertEqual(one, two)

    def test_external_excluded_by_default(self):
        rendered = MODULE.render(self.fixture())
        self.assertNotIn("requests", rendered)
        self.assertIn("nodes=3 edges=2 external=excluded", rendered)

    def test_external_can_be_included(self):
        rendered = MODULE.render(self.fixture(), include_external=True)
        self.assertIn("requests", rendered)
        self.assertIn("nodes=4 edges=3 external=included", rendered)

    def test_unsafe_label_characters_removed(self):
        fixture = self.fixture()
        fixture["nodes"][0]["name"] = 'bad["<tag>|' + chr(96) + "name"
        rendered = MODULE.render(fixture)
        self.assertNotIn("<tag>", rendered)
        self.assertNotIn(chr(96), rendered)

    def test_bounds_are_enforced(self):
        rendered = MODULE.render(self.fixture(), max_nodes=2, max_edges=1)
        self.assertIn("nodes=2", rendered)
        self.assertLessEqual(rendered.count("-->"), 1)


if __name__ == "__main__":
    unittest.main()
