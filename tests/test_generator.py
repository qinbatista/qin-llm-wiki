import importlib.util
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from qin_llm_wiki.cli import MANAGED_FILES, REQUIRED_ROOT_ENTRIES, REQUIRED_RUNTIME_FILES, _write_architecture, architecture_signature, compare_architecture, privacy_check, verify_vault
from qin_llm_wiki.hidden_process import hidden_process_options


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_CACHE_ROOT = PROJECT_ROOT / "Cache" / "tmp-llm-wiki-architecture"


class WikiGeneratorTests(unittest.TestCase):
    def setUp(self):
        TEST_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
        self.vault_path = TEST_CACHE_ROOT / self._testMethodName
        self.external_root = TEST_CACHE_ROOT / f"{self._testMethodName}-external"
        for path in (self.vault_path, self.external_root):
            if path.is_symlink() or path.is_file():
                path.unlink()
            elif path.exists():
                shutil.rmtree(path)

    def tearDown(self):
        for path in (self.vault_path, self.external_root):
            if path.is_symlink() or path.is_file():
                path.unlink()
            elif path.exists():
                shutil.rmtree(path)

    def _make_symlink(self, link_path, target_path):
        link_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            link_path.symlink_to(target_path, target_is_directory=target_path.is_dir())
        except (NotImplementedError, OSError) as error:
            self.skipTest(f"Symlink creation is unavailable on this host: {error}")

    def _tree_snapshot(self, snapshot_root):
        snapshot_root = Path(snapshot_root)
        snapshot = {".": ("directory", snapshot_root.lstat().st_mode, snapshot_root.lstat().st_mtime_ns)}
        for root, directory_names, file_names in os.walk(snapshot_root, followlinks=False):
            root_path = Path(root)
            for name in sorted((*directory_names, *file_names)):
                path = root_path / name
                relative_path = path.relative_to(snapshot_root).as_posix()
                path_stat = path.lstat()
                if path.is_symlink():
                    snapshot[relative_path] = ("symlink", os.readlink(path), path_stat.st_mode, path_stat.st_mtime_ns)
                elif path.is_file():
                    snapshot[relative_path] = ("file", path.read_bytes(), path_stat.st_mode, path_stat.st_mtime_ns)
                else:
                    snapshot[relative_path] = ("directory", path_stat.st_mode, path_stat.st_mtime_ns)
        return snapshot

    def test_init_generates_required_root_and_memory_architecture(self):
        written = _write_architecture(self.vault_path, "Example Wiki", False)
        audit = verify_vault(self.vault_path, run_runtime=False)
        signature = architecture_signature(self.vault_path)
        self.assertEqual(written["status"], "written")
        self.assertEqual(audit["status"], "pass", audit["errors"])
        self.assertEqual(set(signature["root"]), set(REQUIRED_ROOT_ENTRIES))
        self.assertTrue(all(signature["runtime"].values()))
        self.assertTrue(all(signature["capabilities"].values()))
        self.assertFalse((self.vault_path / "Archive").exists())
        self.assertTrue((self.vault_path / "Knowledge" / "Reusable Lessons" / "index.md").is_file())
        self.assertTrue((self.vault_path / "Knowledge" / "Book References" / "index.md").is_file())

    def test_deep_verify_runs_lint_runtime_tests_and_disposable_replay(self):
        _write_architecture(self.vault_path, "Example Wiki", False)
        audit = verify_vault(self.vault_path, run_runtime=True)
        check_statuses = {check["check_id"]: check["status"] for check in audit["check_runs"]}
        self.assertEqual(audit["status"], "pass", audit["errors"])
        self.assertEqual(check_statuses, {"architecture-structure": "pass", "vault-integrity": "pass", "runtime-unit-tests": "pass", "record-search-render-replay": "pass"})
        self.assertFalse((self.vault_path / "Cache" / "tmp-llm-wiki-architecture" / "runtime-replay").exists())

    def test_runtime_records_and_updates_one_issue(self):
        _write_architecture(self.vault_path, "Example Wiki", False)
        runtime_path = self.vault_path / "AI Memory" / "ai_memory.py"
        specification = importlib.util.spec_from_file_location("generated_ai_memory", runtime_path)
        runtime = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(runtime)
        runtime.add_project("GameOne", self.vault_path)
        first = runtime.record_event("GameOne", "combat.damage", "bug-fix", "Critical damage is wrong", "Rounding order", "Monitoring remains active", "partial", issue_id="combat-critical-001", issue_status="MONITORING", files=["src/combat/damage.py"])
        second = runtime.record_event("GameOne", "combat.damage", "bug-fix", "Critical damage fixed", "Rounding order corrected", "Focused checks pass", "passed", issue_id="combat-critical-001", issue_status="RESOLVED", files=["src/combat/damage.py"])
        compact = runtime.search_events("GameOne", "combat.damage", "critical", compact=True)
        runtime.render_views()
        audit = verify_vault(self.vault_path, run_runtime=False)
        self.assertEqual(first["status"], "written")
        self.assertEqual(second["attempt_count"], 2)
        self.assertEqual(len(compact["matches"]), 1)
        self.assertEqual(compact["matches"][0]["attempt_count"], 2)
        self.assertEqual(audit["status"], "pass", audit["errors"])

    def test_update_preserves_user_content_events_and_classified_lessons(self):
        _write_architecture(self.vault_path, "Example Wiki", False)
        user_knowledge = self.vault_path / "Knowledge" / "User Notes.md"
        user_knowledge.write_text("# User Notes\n\nPrivate content remains local.\n", encoding="utf-8")
        category_path = self.vault_path / "Knowledge" / "Reusable Lessons" / "Code Architecture.md"
        category_path.write_text(category_path.read_text(encoding="utf-8") + "\nA user-curated lesson remains local.\n", encoding="utf-8")
        events_path = self.vault_path / "AI Memory" / "events.jsonl"
        specification = importlib.util.spec_from_file_location("preservation_ai_memory", self.vault_path / "AI Memory" / "ai_memory.py")
        runtime = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(runtime)
        runtime.record_event("GameOne", "combat.damage", "feature", "Added damage calculation", "Add combat behavior", "Focused checks pass", "passed", files=["src/combat/damage.py"])
        original_events = events_path.read_text(encoding="utf-8")
        updated = _write_architecture(self.vault_path, "Example Wiki", False)
        self.assertEqual(updated["status"], "written")
        self.assertEqual(user_knowledge.read_text(encoding="utf-8"), "# User Notes\n\nPrivate content remains local.\n")
        self.assertIn("A user-curated lesson remains local.", category_path.read_text(encoding="utf-8"))
        self.assertEqual(events_path.read_text(encoding="utf-8"), original_events)

    def test_update_from_v1_0_seed_owners_is_idempotent_and_deep_verifiable(self):
        _write_architecture(self.vault_path, "Example Wiki", False)
        legacy_seed_content = {
            "Knowledge/index.md": "# Knowledge\n\nUser-curated index note remains.\n\n- [[Knowledge/Project Learning|Project Learning]]\n- [[Knowledge/Privacy and Safety|Privacy and Safety]]\n- [[Start Here]]\n",
            "Knowledge/Project Learning.md": "# Project Learning\n\nUser-curated learning note remains.\n\n## One outcome, one event\n\nRecord one durable result in `AI Memory/events.jsonl`.\n\n## Repeated Bugs\n\nUse one stable issue ID. Lifecycle status is `ACTIVE`, `MONITORING`, or `RESOLVED`.\n\nGenerated `Recent Work.md` remains current.\n",
            "Knowledge/Privacy and Safety.md": "# Privacy and Safety\n\nUser-curated privacy note remains.\n\n- Store no credentials, secrets, raw prompts, or private reasoning.\n- Keep public architecture separate from private vaults.\n",
        }
        for relative_path, content in legacy_seed_content.items():
            (self.vault_path / relative_path).write_text(content, encoding="utf-8")
        shutil.rmtree(self.vault_path / "Knowledge" / "Reusable Lessons")
        shutil.rmtree(self.vault_path / "Knowledge" / "Book References")
        for relative_path in ("AI Memory/auto_classify.py", "AI Memory/tests/test_auto_classify.py", "AI Memory/tests/test_memory_lint.py"):
            (self.vault_path / relative_path).unlink()
        updated = _write_architecture(self.vault_path, "Example Wiki", False)
        first_owner_bytes = {relative_path: (self.vault_path / relative_path).read_bytes() for relative_path in legacy_seed_content}
        audit = verify_vault(self.vault_path, run_runtime=True)
        self.assertEqual(updated["status"], "written")
        self.assertEqual(set(updated["migrated_seed_fragments"]), set(legacy_seed_content))
        self.assertTrue(all(check["status"] == "pass" for check in audit["check_runs"]), audit)
        self.assertEqual(audit["status"], "pass", audit["errors"])
        for relative_path, original_content in legacy_seed_content.items():
            self.assertIn("User-curated", (self.vault_path / relative_path).read_text(encoding="utf-8"))
            self.assertTrue(first_owner_bytes[relative_path].startswith(original_content.encode("utf-8")))
        second_update = _write_architecture(self.vault_path, "Example Wiki", False)
        self.assertEqual(second_update["migrated_seed_fragments"], {})
        self.assertEqual({relative_path: (self.vault_path / relative_path).read_bytes() for relative_path in legacy_seed_content}, first_owner_bytes)

    def test_managed_drift_requires_explicit_force_and_reports_digests(self):
        _write_architecture(self.vault_path, "Example Wiki", False)
        managed_path = self.vault_path / MANAGED_FILES[0]
        managed_path.write_text("local managed edit\n", encoding="utf-8")
        blocked = _write_architecture(self.vault_path, "Example Wiki", False)
        forced = _write_architecture(self.vault_path, "Example Wiki", True)
        self.assertEqual(blocked["status"], "drift")
        self.assertEqual(blocked["managed_files"][0]["file"], MANAGED_FILES[0])
        self.assertEqual(len(blocked["managed_files"][0]["current_sha256"]), 64)
        self.assertEqual(len(blocked["managed_files"][0]["template_sha256"]), 64)
        self.assertEqual(forced["status"], "written")
        self.assertNotEqual(managed_path.read_text(encoding="utf-8"), "local managed edit\n")

    def test_force_managed_repairs_unreadable_utf8_managed_file(self):
        _write_architecture(self.vault_path, "Example Wiki", False)
        managed_path = self.vault_path / "AGENTS.md"
        managed_path.write_bytes(b"\xff\xfe")
        blocked = _write_architecture(self.vault_path, "Example Wiki", False)
        repaired = _write_architecture(self.vault_path, "Example Wiki", True)
        self.assertEqual(blocked["status"], "drift")
        self.assertEqual(repaired["status"], "written")
        self.assertIn("Example Wiki memory contract", managed_path.read_text(encoding="utf-8"))

    def test_update_rejects_escaping_managed_target_before_any_write(self):
        _write_architecture(self.vault_path, "Example Wiki", False)
        self.external_root.mkdir(parents=True)
        external_file = self.external_root / "user-content.md"
        external_file.write_text("External user content remains unchanged.\n", encoding="utf-8")
        managed_path = self.vault_path / "AGENTS.md"
        managed_path.unlink()
        self._make_symlink(managed_path, external_file)
        original_external = external_file.read_bytes()
        original_vault = self._tree_snapshot(self.vault_path)
        original_external_tree = self._tree_snapshot(self.external_root)
        output = _write_architecture(self.vault_path, "Example Wiki", True)
        self.assertEqual(output["status"], "error")
        self.assertEqual(output["written"], [])
        self.assertTrue(any("symlink" in error for error in output["errors"]))
        self.assertEqual(self._tree_snapshot(self.vault_path), original_vault)
        self.assertEqual(self._tree_snapshot(self.external_root), original_external_tree)
        self.assertEqual(external_file.read_bytes(), original_external)
        self.assertTrue(managed_path.is_symlink())

    def test_update_rejects_escaping_parent_before_creating_any_file(self):
        self.vault_path.mkdir(parents=True)
        external_knowledge = self.external_root / "knowledge"
        external_knowledge.mkdir(parents=True)
        marker_path = external_knowledge / "user-content.md"
        marker_path.write_text("External knowledge remains unchanged.\n", encoding="utf-8")
        self._make_symlink(self.vault_path / "Knowledge", external_knowledge)
        original_external = marker_path.read_bytes()
        original_vault = self._tree_snapshot(self.vault_path)
        original_external_tree = self._tree_snapshot(self.external_root)
        output = _write_architecture(self.vault_path, "Example Wiki", False)
        self.assertEqual(output["status"], "error")
        self.assertEqual(output["written"], [])
        self.assertTrue(any("symlink" in error or "escapes" in error for error in output["errors"]))
        self.assertEqual(self._tree_snapshot(self.vault_path), original_vault)
        self.assertEqual(self._tree_snapshot(self.external_root), original_external_tree)
        self.assertFalse((self.vault_path / "AGENTS.md").exists())
        self.assertFalse((self.vault_path / "AI Memory" / "events.jsonl").exists())
        self.assertEqual(marker_path.read_bytes(), original_external)

    def test_update_rejects_generated_output_symlink_before_other_writes(self):
        _write_architecture(self.vault_path, "Example Wiki", False)
        self.external_root.mkdir(parents=True)
        external_file = self.external_root / "generated-view-target.md"
        external_file.write_text("External generated-view target remains unchanged.\n", encoding="utf-8")
        generated_path = self.vault_path / "Recent Work.md"
        generated_path.unlink()
        self._make_symlink(generated_path, external_file)
        managed_path = self.vault_path / "CLAUDE.md"
        managed_path.write_text("local managed drift\n", encoding="utf-8")
        seed_path = self.vault_path / "Skills" / "index.md"
        seed_path.unlink()
        original_external = external_file.read_bytes()
        original_vault = self._tree_snapshot(self.vault_path)
        original_external_tree = self._tree_snapshot(self.external_root)
        output = _write_architecture(self.vault_path, "Example Wiki", True)
        self.assertEqual(output["status"], "error")
        self.assertEqual(output["written"], [])
        self.assertTrue(any("symlink" in error for error in output["errors"]))
        self.assertEqual(self._tree_snapshot(self.vault_path), original_vault)
        self.assertEqual(self._tree_snapshot(self.external_root), original_external_tree)
        self.assertEqual(managed_path.read_text(encoding="utf-8"), "local managed drift\n")
        self.assertFalse(seed_path.exists())
        self.assertEqual(external_file.read_bytes(), original_external)

    def test_strict_lint_rejects_malformed_cache_path_even_though_cache_content_is_disposable(self):
        _write_architecture(self.vault_path, "Example Wiki", False)
        malformed_path = self.vault_path / "Cache" / "tests" / "memory-only|Cache" / "evidence.json"
        malformed_path.parent.mkdir(parents=True)
        malformed_path.write_text("{}\n", encoding="utf-8")
        audit = verify_vault(self.vault_path, run_runtime=False)
        self.assertEqual(audit["status"], "fail")
        self.assertTrue(any("Malformed path component" in error for error in audit["errors"]))

    def test_privacy_gate_rejects_home_paths(self):
        _write_architecture(self.vault_path, "Example Wiki", False)
        private_note = self.vault_path / "Knowledge" / "Private.md"
        private_note.write_text("/" + "Users/example/private-project\n", encoding="utf-8")
        audit = privacy_check(self.vault_path)
        self.assertEqual(audit["status"], "fail")
        self.assertEqual(audit["findings"][0]["pattern"], "posix-home-path")

    def test_two_fresh_generated_vaults_have_the_same_architecture(self):
        reference_path = self.vault_path / "reference"
        candidate_path = self.vault_path / "candidate"
        _write_architecture(reference_path, "Reference Wiki", False)
        _write_architecture(candidate_path, "Candidate Wiki", False)
        comparison = compare_architecture(reference_path, candidate_path, run_runtime=False)
        self.assertEqual(comparison["status"], "pass")
        self.assertTrue(comparison["same_architecture"])

    def test_reference_comparison_when_configured(self):
        _write_architecture(self.vault_path, "Example Wiki", False)
        reference_value = os.getenv("QIN_LLM_WIKI_REFERENCE", "").strip()
        if not reference_value:
            self.skipTest("QIN_LLM_WIKI_REFERENCE is not configured")
        comparison = compare_architecture(Path(reference_value), self.vault_path, run_runtime=False)
        self.assertEqual(comparison["status"], "pass", comparison)
        self.assertTrue(comparison["same_architecture"])

    def test_generated_runtime_unit_tests_pass_with_bytecode_disabled(self):
        _write_architecture(self.vault_path, "Example Wiki", False)
        test_directory = self.vault_path / "AI Memory" / "tests"
        environment = os.environ.copy()
        environment["QIN_LLM_WIKI_TEST_CACHE"] = str(Path("Cache") / "tmp-direct-runtime")
        completed = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", str(test_directory), "-p", "test_*.py", "-v"], cwd=self.vault_path, env=environment, text=True, capture_output=True, check=False, **hidden_process_options())
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_required_runtime_catalog_includes_classifier_and_lint_tests(self):
        self.assertIn("AI Memory/auto_classify.py", MANAGED_FILES)
        self.assertIn("AI Memory/tests/test_auto_classify.py", REQUIRED_RUNTIME_FILES)
        self.assertIn("AI Memory/tests/test_memory_lint.py", REQUIRED_RUNTIME_FILES)
        self.assertIn("AI Memory/hidden_process.py", MANAGED_FILES)
        self.assertIn("AI Memory/tests/test_hidden_process.py", REQUIRED_RUNTIME_FILES)


if __name__ == "__main__":
    unittest.main()
