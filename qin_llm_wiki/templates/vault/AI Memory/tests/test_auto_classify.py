import importlib.util
import os
import shutil
import unittest
from pathlib import Path


MEMORY_ROOT = Path(__file__).parents[1]
CLASSIFIER_SPECIFICATION = importlib.util.spec_from_file_location("auto_classify", MEMORY_ROOT / "auto_classify.py")
CLASSIFIER = importlib.util.module_from_spec(CLASSIFIER_SPECIFICATION)
CLASSIFIER_SPECIFICATION.loader.exec_module(CLASSIFIER)
MEMORY_SPECIFICATION = importlib.util.spec_from_file_location("ai_memory_for_classifier", MEMORY_ROOT / "ai_memory.py")
MEMORY = importlib.util.module_from_spec(MEMORY_SPECIFICATION)
MEMORY_SPECIFICATION.loader.exec_module(MEMORY)
VAULT_ROOT = MEMORY_ROOT.parent
TEST_CACHE_ROOT = Path(os.environ.get("QIN_LLM_WIKI_TEST_CACHE", VAULT_ROOT / "Cache" / "tmp-auto-classify-runtime")).expanduser().resolve()


class AutoClassifyTests(unittest.TestCase):
    def setUp(self):
        TEST_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
        self.case_root = TEST_CACHE_ROOT / self._testMethodName
        if self.case_root.exists():
            shutil.rmtree(self.case_root)
        self.case_root.mkdir(parents=True)
        self.store = self.case_root / "AI Memory" / "events.jsonl"

    def tearDown(self):
        if self.case_root.exists():
            shutil.rmtree(self.case_root)

    def _record_architecture_event(self, project, recorded_at):
        return MEMORY.record_event(project, "architecture.ownership", "architecture", "Verified architecture schema ownership boundary", "The module contract has one source of truth", "The verified ownership boundary removes duplicate state", "passed", verification=["Focused architecture checks passed"], decisions=["Keep one canonical module owner"], files=["src/architecture.py"], recorded_at=recorded_at, events_path=self.store)

    def test_empty_store_writes_semantic_candidate_queue_and_categories(self):
        output = CLASSIFIER.sync_catalog(self.case_root, self.store, apply=True)
        candidate_path = self.case_root / "Knowledge" / "Reusable Lessons" / "Candidates.md"
        self.assertEqual(output["status"], "written")
        self.assertEqual(output["events"], 0)
        self.assertIn("Generated from verified events", candidate_path.read_text(encoding="utf-8"))
        for relative_path in CLASSIFIER.TAXONOMY_PATHS.values():
            self.assertTrue((self.case_root / relative_path).is_file())

    def test_repeated_projects_do_not_implicitly_create_global_rules(self):
        self._record_architecture_event("ProjectOne", "2026-08-01T10:00:00Z")
        self._record_architecture_event("ProjectTwo", "2026-08-02T10:00:00Z")
        output = CLASSIFIER.sync_catalog(self.case_root, self.store, apply=True)
        category_text = (self.case_root / CLASSIFIER.TAXONOMY_PATHS["code-architecture"]).read_text(encoding="utf-8")
        self.assertEqual(output["auto_promoted"], 0)
        self.assertNotIn("AUTO-LESSON:RL-AUTO-", category_text)

    def test_one_project_remains_candidate(self):
        self._record_architecture_event("ProjectOne", "2026-08-01T10:00:00Z")
        output = CLASSIFIER.sync_catalog(self.case_root, self.store, apply=True)
        candidate_text = (self.case_root / CLASSIFIER.CANDIDATE_PATH).read_text(encoding="utf-8")
        self.assertEqual(output["auto_promoted"], 0)
        self.assertIn("Decision: CANDIDATE", candidate_text)

    def test_unrelated_rules_in_the_same_taxonomy_cluster_do_not_merge(self):
        first = MEMORY.record_event("ProjectOne", "architecture.ownership", "architecture", "Verified account data ownership boundary", "The account contract has one source of truth", "The account owner preserves data consistency", "passed", verification=["Account ownership checks passed"], decisions=["Keep the account data owner"], files=["src/account.py"], recorded_at="2026-08-01T10:00:00Z", events_path=self.store)
        second = MEMORY.record_event("ProjectTwo", "architecture.ownership", "architecture", "Verified inventory state ownership boundary", "The inventory contract has one source of truth", "The inventory owner preserves state consistency", "passed", verification=["Inventory ownership checks passed"], decisions=["Keep the inventory state owner"], files=["src/inventory.py"], recorded_at="2026-08-02T10:00:00Z", events_path=self.store)
        output = CLASSIFIER.sync_catalog(self.case_root, self.store, apply=True)
        self.assertEqual(first["status"], "written")
        self.assertEqual(second["status"], "written")
        self.assertEqual(output["auto_promoted"], 0)
        self.assertEqual(output["candidate_groups"], 1)

    def test_private_and_placeholder_events_never_enter_candidates(self):
        valid = self._record_architecture_event("ProjectOne", "2026-08-01T10:00:00Z")
        event = MEMORY._read_events(self.store)[0]
        private_event = dict(event)
        private_event.update({"event_id": "20260802T100000Z-private000001", "project": "ProjectTwo", "summary": f"Read {Path('/', 'Users', 'example', 'private-project')}"})
        placeholder_event = dict(event)
        placeholder_event.update({"event_id": "20260803T100000Z-placehold001", "project": "ProjectThree", "summary": "tmp"})
        MEMORY._write_events([event, private_event, placeholder_event], self.store)
        output = CLASSIFIER.sync_catalog(self.case_root, self.store, apply=True)
        candidate_text = (self.case_root / CLASSIFIER.CANDIDATE_PATH).read_text(encoding="utf-8")
        self.assertEqual(valid["status"], "written")
        self.assertEqual(output["privacy_blocked_events"], 1)
        self.assertEqual(output["invalid_placeholder_events"], 1)
        self.assertNotIn("private-project", candidate_text)
        self.assertNotIn(" — tmp", candidate_text)

    def test_recall_returns_bounded_category_match(self):
        self._record_architecture_event("ProjectOne", "2026-08-01T10:00:00Z")
        output = CLASSIFIER.recall(self.case_root, self.store, query="ownership boundary", limit=1, project="ProjectOne")
        self.assertEqual(output["status"], "ok")
        self.assertEqual(len(output["matches"]), 1)
        self.assertEqual(output["matches"][0]["category"], "code-architecture")

    def test_stale_auto_promotions_are_removed_after_evidence_changes(self):
        MEMORY.record_event("Global Preferences", "ui.layout", "preference", "Prefer readable UI layout", "Explicit global user preference", "Use readable spacing and truthful button feedback", "passed", events_path=self.store)
        promoted = CLASSIFIER.sync_catalog(self.case_root, self.store, apply=True)
        self.assertEqual(promoted["auto_promoted"], 1)
        events = MEMORY._read_events(self.store)
        events[0]["verification_status"] = "partial"
        MEMORY._write_events(events, self.store)
        CLASSIFIER.sync_catalog(self.case_root, self.store, apply=True)
        category_text = (self.case_root / CLASSIFIER.TAXONOMY_PATHS["ui-interaction"]).read_text(encoding="utf-8")
        self.assertNotIn("AUTO-LESSON:RL-AUTO-", category_text)

    def test_project_preference_is_not_global_and_recall_does_not_mix_projects(self):
        for project in ("ProjectOne", "ProjectTwo"):
            MEMORY.record_event(project, "ui.layout", "preference", "Prefer readable UI layout", "Local project design decision", "Use readable spacing and truthful button feedback", "passed", events_path=self.store)
        result = CLASSIFIER.sync_catalog(self.case_root, self.store, apply=True)
        self.assertEqual(result["auto_promoted"], 0)
        self.assertEqual(CLASSIFIER.recall(self.case_root, self.store)["matches"], [])
        matches = CLASSIFIER.recall(self.case_root, self.store, project="ProjectOne")["matches"]
        self.assertTrue(matches)
        self.assertTrue(all(row["source_projects"] == ["ProjectOne"] for row in matches))


if __name__ == "__main__":
    unittest.main()
