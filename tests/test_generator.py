import importlib.util
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from qin_llm_wiki.cli import MANAGED_FILES, REQUIRED_ROOT_ENTRIES, _write_architecture, architecture_signature, compare_architecture, privacy_check, verify_vault


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_CACHE_ROOT = PROJECT_ROOT / "Cache" / "tests" / "llm-wiki-architecture"


class WikiGeneratorTests(unittest.TestCase):
    def setUp(self):
        TEST_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
        self.vault_path = TEST_CACHE_ROOT / self._testMethodName
        if self.vault_path.exists():
            shutil.rmtree(self.vault_path)

    def tearDown(self):
        if self.vault_path.exists():
            shutil.rmtree(self.vault_path)

    def test_init_generates_required_root_architecture(self):
        written = _write_architecture(self.vault_path, "Test Wiki", False)
        audit = verify_vault(self.vault_path)
        self.assertEqual(written["status"], "written")
        self.assertEqual(audit["status"], "pass")
        self.assertEqual(set(architecture_signature(self.vault_path)["root"]), set(REQUIRED_ROOT_ENTRIES))
        self.assertFalse((self.vault_path / "Archive").exists())
        self.assertFalse((self.vault_path / "Journal").exists())
        self.assertTrue((self.vault_path / "Preferences" / "AI Captured Preferences.md").is_file())

    def test_runtime_records_and_updates_one_issue(self):
        _write_architecture(self.vault_path, "Test Wiki", False)
        runtime_path = self.vault_path / "AI Memory" / "ai_memory.py"
        specification = importlib.util.spec_from_file_location("generated_ai_memory", runtime_path)
        runtime = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(runtime)
        runtime.add_project("GameOne", self.vault_path)
        first = runtime.record_event("GameOne", "combat.damage", "bug-fix", "Critical damage is wrong", "Rounding order", "Monitoring", "partial", issue_id="combat-critical-001", issue_status="MONITORING", files=["src/combat/damage.py"])
        second = runtime.record_event("GameOne", "combat.damage", "bug-fix", "Critical damage fixed", "Rounding order corrected", "Focused tests pass", "passed", issue_id="combat-critical-001", issue_status="RESOLVED", files=["src/combat/damage.py"])
        compact = runtime.search_events("GameOne", "combat.damage", "critical", compact=True)
        runtime.render_views()
        audit = verify_vault(self.vault_path)
        self.assertEqual(first["status"], "written")
        self.assertEqual(second["attempt_count"], 2)
        self.assertEqual(len(compact["matches"]), 1)
        self.assertEqual(compact["matches"][0]["attempt_count"], 2)
        self.assertEqual(audit["status"], "pass")

    def test_update_preserves_user_content_and_events(self):
        _write_architecture(self.vault_path, "Test Wiki", False)
        user_knowledge = self.vault_path / "Knowledge" / "User Notes.md"
        user_knowledge.write_text("# User Notes\n\nPrivate content remains local.\n", encoding="utf-8")
        events_path = self.vault_path / "AI Memory" / "events.jsonl"
        specification = importlib.util.spec_from_file_location("preservation_ai_memory", self.vault_path / "AI Memory" / "ai_memory.py")
        runtime = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(runtime)
        runtime.record_event("GameOne", "combat.damage", "feature", "Added damage", "Add combat", "Tests pass", "passed", files=["src/combat/damage.py"])
        original_events = events_path.read_text(encoding="utf-8")
        updated = _write_architecture(self.vault_path, "Test Wiki", False)
        self.assertEqual(updated["status"], "written")
        self.assertEqual(user_knowledge.read_text(encoding="utf-8"), "# User Notes\n\nPrivate content remains local.\n")
        self.assertEqual(events_path.read_text(encoding="utf-8"), original_events)

    def test_managed_drift_requires_explicit_force(self):
        _write_architecture(self.vault_path, "Test Wiki", False)
        managed_path = self.vault_path / MANAGED_FILES[0]
        managed_path.write_text("local managed edit\n", encoding="utf-8")
        blocked = _write_architecture(self.vault_path, "Test Wiki", False)
        forced = _write_architecture(self.vault_path, "Test Wiki", True)
        self.assertEqual(blocked["status"], "drift")
        self.assertEqual(forced["status"], "written")
        self.assertNotEqual(managed_path.read_text(encoding="utf-8"), "local managed edit\n")

    def test_privacy_gate_rejects_home_paths(self):
        _write_architecture(self.vault_path, "Test Wiki", False)
        private_note = self.vault_path / "Knowledge" / "Private.md"
        private_note.write_text("/" + "Users/example/private-project\n", encoding="utf-8")
        audit = privacy_check(self.vault_path)
        self.assertEqual(audit["status"], "fail")
        self.assertEqual(audit["findings"][0]["pattern"], "posix-home-path")

    def test_reference_comparison_when_configured(self):
        _write_architecture(self.vault_path, "Test Wiki", False)
        reference_value = os.getenv("QIN_LLM_WIKI_REFERENCE", "").strip()
        if not reference_value:
            self.skipTest("QIN_LLM_WIKI_REFERENCE is not configured")
        comparison = compare_architecture(Path(reference_value), self.vault_path)
        self.assertEqual(comparison["status"], "pass")
        self.assertTrue(comparison["same_architecture"])

    def test_generated_runtime_unit_tests_pass(self):
        _write_architecture(self.vault_path, "Test Wiki", False)
        test_directory = self.vault_path / "AI Memory" / "tests"
        completed = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(test_directory), "-v"], text=True, capture_output=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
