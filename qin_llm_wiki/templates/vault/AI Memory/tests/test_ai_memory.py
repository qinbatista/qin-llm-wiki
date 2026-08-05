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
                MEMORY.record_event("GameOne", "combat.damage", "general", "Changed damage", "Update", "Done", "passed", files=[str(Path("/", "private", "source.py"))], events_path=store)

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

    def test_memory_candidates_are_a_noop_when_none_are_relevant(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            result = MEMORY.record_memory_candidates([], events_path=root / "events.jsonl", preferences_root=root)
        self.assertEqual(result, {"status": "no-candidates", "written": False, "candidates": 0})
        self.assertFalse((root / "events.jsonl").exists())
        self.assertFalse((root / "Preferences").exists())

    def test_memory_candidates_write_one_event_and_owner_pages(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            ui_page = root / "Preferences" / "UI Style Preferences.md"
            ui_page.parent.mkdir(parents=True)
            ui_page.write_text("# UI Style Preferences\n\nExisting user-owned content.\n", encoding="utf-8")
            candidates = [{
                "kind": "preference",
                "area": "ui",
                "statement": "Prefer compact parallel status rows with visible progress bars.",
                "evidence": "User explicitly requested a clearer compact monitoring layout.",
                "basis": "explicit_user_request",
                "confidence": "high",
                "source": "ending",
            }, {
                "kind": "technical-trait",
                "area": "technical",
                "statement": "Values evidence-backed lifecycle state over status prose.",
                "evidence": "User repeatedly asked for observable status and restart guidance.",
                "basis": "repeated_user_correction",
                "confidence": "high",
                "source": "ending",
            }]
            result = MEMORY.record_memory_candidates(candidates, project="Global Preferences", events_path=root / "events.jsonl", preferences_root=root, recorded_at="2026-08-05T12:00:00Z")
            events = MEMORY._read_events(root / "events.jsonl")
            duplicate = MEMORY.record_memory_candidates(candidates, project="Global Preferences", events_path=root / "events.jsonl", preferences_root=root, recorded_at="2026-08-05T12:00:00Z")
            ui_text = ui_page.read_text(encoding="utf-8")
            captured_text = (root / "Preferences" / "AI Captured Preferences.md").read_text(encoding="utf-8")
        self.assertEqual(result["status"], "written")
        self.assertEqual(result["candidates"], 2)
        self.assertEqual(duplicate["status"], "duplicate")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["record_kind"], "memory")
        self.assertEqual(len(events[0]["memory_candidates"]), 2)
        self.assertIn("Prefer compact parallel status rows", ui_text)
        self.assertIn("Values evidence-backed lifecycle state", captured_text)
        self.assertIn("Existing user-owned content.", ui_text)

    def test_memory_candidates_reject_private_content(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaises(ValueError):
                MEMORY.record_memory_candidates([{
                    "kind": "preference",
                    "area": "general",
                    "statement": f"Use {Path('/', 'Users', 'example', 'private-project')} as the source.",
                    "evidence": "Explicit request.",
                    "basis": "explicit_user_request",
                    "confidence": "high",
                    "source": "ending",
                }], events_path=Path(temporary_directory) / "events.jsonl", preferences_root=Path(temporary_directory))


if __name__ == "__main__":
    unittest.main()
