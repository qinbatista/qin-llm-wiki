import ast
import unittest
from pathlib import Path

from qin_llm_wiki.cli import PACKAGE_ROOT, TEMPLATE_ROOT


SUBPROCESS_LAUNCHES = {"run", "Popen", "call", "check_call", "check_output"}


class HiddenExecutionIntegrationTests(unittest.TestCase):
    def test_package_and_standalone_vault_helpers_match(self):
        package = (PACKAGE_ROOT / "hidden_process.py").read_bytes()
        template = (TEMPLATE_ROOT / "AI Memory" / "hidden_process.py").read_bytes()
        self.assertEqual(package, template)

    def test_runtime_and_test_launches_request_hidden_execution(self):
        violations = []
        launches = 0
        paths = [*PACKAGE_ROOT.rglob("*.py"), *(PACKAGE_ROOT.parent / "tests").rglob("*.py")]
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            modules, functions = set(), set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules.update(alias.asname or alias.name for alias in node.names if alias.name == "subprocess")
                elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
                    functions.update(alias.asname or alias.name for alias in node.names if alias.name in SUBPROCESS_LAUNCHES)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                function = node.func
                direct = isinstance(function, ast.Name) and function.id in functions
                qualified = isinstance(function, ast.Attribute) and isinstance(function.value, ast.Name) and function.value.id in modules and function.attr in SUBPROCESS_LAUNCHES
                if not (direct or qualified):
                    continue
                launches += 1
                guarded = any(
                    option.arg is None and isinstance(option.value, ast.Call)
                    and ((isinstance(option.value.func, ast.Name) and option.value.func.id == "hidden_process_options")
                         or (isinstance(option.value.func, ast.Attribute) and option.value.func.attr == "hidden_process_options"))
                    for option in node.keywords
                )
                if not guarded:
                    violations.append(f"{path.relative_to(PACKAGE_ROOT.parent)}:{node.lineno}")
        self.assertGreater(launches, 0)
        self.assertEqual(violations, [], "Unprotected subprocess launches")


if __name__ == "__main__":
    unittest.main()
