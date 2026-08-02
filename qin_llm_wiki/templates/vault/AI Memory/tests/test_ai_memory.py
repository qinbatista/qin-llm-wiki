import importlib.util
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "ai_memory.py"
SPECIFICATION = importlib.util.spec_from_file_location("ai_memory", SCRIPT_PATH)
MEMORY = importlib.util.module_from_spec(SPECIFICATION)
SPECIFICATION.loader.exec_module(MEMORY)


class AIMemoryTests(unittest.TestCase):
    def test_repeated_issue_updates_one_row(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = Path(temporary_directory) / "events.jsonl"
            first = MEMORY.record_event("GameOne", "combat.damage", "bug-fix", "Damage is wrong", "Multiplier ordering", "Monitoring", "partial", issue_id="combat-001", issue_status="MONITORING", files=["src/combat.py"], events_path=store)
            second = MEMORY.record_event("GameOne", "combat.damage", "bug-fix", "Damage fixed", "Multiplier reordered", "Focused tests pass", "passed", issue_id="combat-001", issue_status="RESOLVED", files=["src/combat.py"], events_path=store)
            events = MEMORY._read_events(store)
        self.assertEqual(first["status"], "written")
        self.assertEqual(second["status"], "updated")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["attempt_count"], 2)

    def test_compact_search_omits_long_evidence(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = Path(temporary_directory) / "events.jsonl"
            MEMORY.record_event("GameOne", "combat.damage", "bug-fix", "Fixed critical damage", "Rounding order", "Tests pass", "passed", files=["src/combat.py"], verification=["long evidence"], events_path=store)
            compact = MEMORY.search_events("GameOne", "combat.damage", "critical", compact=True, events_path=store)
        self.assertEqual(len(compact["matches"]), 1)
        self.assertNotIn("verification", compact["matches"][0])

    def test_files_must_be_project_relative(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = Path(temporary_directory) / "events.jsonl"
            with self.assertRaises(ValueError):
                MEMORY.record_event("GameOne", "combat.damage", "general", "Changed damage", "Update", "Done", "passed", files=["/private/source.py"], events_path=store)

    def test_render_creates_only_generated_root_views(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            store = root / "events.jsonl"
            recent = root / "Recent Work.md"
            dashboard = root / "Memory Dashboard.md"
            issues = root / "Issues.md"
            MEMORY.record_event("GameOne", "combat.damage", "feature", "Updated combat", "Improve gameplay", "Tests pass", "passed", recorded_at="2026-08-01T10:00:00Z", events_path=store)
            MEMORY.render_views(store, recent, dashboard, issues, now=datetime(2026, 8, 1, 18, 0, tzinfo=timezone.utc))
            recent_text = recent.read_text(encoding="utf-8")
            journal_exists = (root / "Journal").exists()
            archive_exists = (root / "Archive").exists()
        self.assertIn("1 outcomes", recent_text)
        self.assertFalse(journal_exists)
        self.assertFalse(archive_exists)


if __name__ == "__main__":
    unittest.main()
