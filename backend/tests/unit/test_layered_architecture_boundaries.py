import ast
import pathlib
import unittest


BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVICES_DIR = BACKEND_ROOT / "services"
CONTROLLERS_DIR = BACKEND_ROOT / "controllers"


class LayeredArchitectureBoundaryTests(unittest.TestCase):
    def _iter_python_files(self, root: pathlib.Path):
        for path in root.rglob("*.py"):
            if path.name == "__init__.py":
                continue
            yield path

    def _imports(self, path: pathlib.Path):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    yield "import", alias.name
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = [alias.name for alias in node.names]
                yield "from", module, names

    def test_services_do_not_import_flask_request_or_response(self):
        violating = []
        for path in self._iter_python_files(SERVICES_DIR):
            for entry in self._imports(path):
                if entry[0] != "from":
                    continue
                module, names = entry[1], entry[2]
                if module != "flask":
                    continue
                if any(name in {"request", "Response", "jsonify"} for name in names):
                    violating.append(str(path.relative_to(BACKEND_ROOT)))
        self.assertEqual(violating, [], f"Services importing Flask request/response APIs: {violating}")

    def test_controllers_do_not_import_config_collection_handles_or_pymongo(self):
        violating = []
        for path in self._iter_python_files(CONTROLLERS_DIR):
            for entry in self._imports(path):
                if entry[0] == "import":
                    module = entry[1]
                    if module.startswith("pymongo"):
                        violating.append(str(path.relative_to(BACKEND_ROOT)))
                    continue

                module, names = entry[1], entry[2]
                if module.startswith("pymongo"):
                    violating.append(str(path.relative_to(BACKEND_ROOT)))
                    continue
                if module == "config" and any(name.endswith("_collection") for name in names):
                    violating.append(str(path.relative_to(BACKEND_ROOT)))
        self.assertEqual(violating, [], f"Controller layer import boundary violations: {violating}")

    def test_non_repository_modules_do_not_import_config_collection_handles(self):
        violating = []
        for path in list(self._iter_python_files(SERVICES_DIR)) + list(self._iter_python_files(CONTROLLERS_DIR)):
            for entry in self._imports(path):
                if entry[0] != "from":
                    continue
                module, names = entry[1], entry[2]
                if module == "config" and any(name.endswith("_collection") for name in names):
                    violating.append(str(path.relative_to(BACKEND_ROOT)))
        self.assertEqual(violating, [], f"Non-repository modules importing collection handles: {violating}")


if __name__ == "__main__":
    unittest.main()
