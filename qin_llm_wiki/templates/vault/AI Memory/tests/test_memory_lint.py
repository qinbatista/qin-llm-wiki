import importlib.util
import json
import os
import shutil
import unittest
from pathlib import Path


MEMORY_ROOT = Path(__file__).parents[1]
LINT_SPECIFICATION = importlib.util.spec_from_file_location("memory_lint", MEMORY_ROOT / "memory_lint.py")
LINT = importlib.util.module_from_spec(LINT_SPECIFICATION)
LINT_SPECIFICATION.loader.exec_module(LINT)
GENERATED_VAULT_ROOT = MEMORY_ROOT.parent
TEST_CACHE_ROOT = Path(os.environ.get("QIN_LLM_WIKI_TEST_CACHE", GENERATED_VAULT_ROOT / "Cache" / "tests" / "memory-lint-runtime"))


class MemoryLintTests(unittest.TestCase):
    def setUp(self):
        TEST_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
        self.case_root = TEST_CACHE_ROOT / self._testMethodName
        if self.case_root.exists():
            shutil.rmtree(self.case_root)
        self._create_generic_vault()

    def tearDown(self):
        if self.case_root.exists():
            shutil.rmtree(self.case_root)

    def _write_fixture_file(self, relative_path, text):
        target_path = self.case_root / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(text, encoding="utf-8")

    def _create_generic_vault(self):
        self.case_root.mkdir(parents=True)
        self._write_fixture_file("AGENTS.md", "# Generic AI Contract\n\nThis disposable fixture keeps one event in `AI Memory/events.jsonl`, uses `AI Memory/ai_memory.py`, reads at most five events, and emits a Memory gate before project work. Reusable Lessons and Book References are current owners; `auto_classify.py` refreshes bounded candidates and `remove-invalid` rejects valid records.\n\n- [[Start Here]]\n")
        self._write_fixture_file("CLAUDE.md", "# Claude Entry\n\nAlways read `AGENTS.md`, use `AI Memory/ai_memory.py`, and emit the Memory gate with Reusable Lessons. Do not create duplicate chronology owners.\n\n- [[Start Here]]\n")
        self._write_fixture_file("instruction.md", "# AI Entry\n\n`AGENTS.md` controls this fixture. The Memory gate reads Reusable Lessons, while chronology remains in `AI Memory/events.jsonl`.\n\n- [[Start Here]]\n")
        self._write_fixture_file("Start Here.md", "# Generic Memory Fixture\n\nThis root makes every generic owner reachable without copying a real vault.\n\n- [[Projects/index|Projects]]\n- [[Knowledge/index|Knowledge]]\n- [[Preferences/index|Preferences]]\n- [[Skills/index|Skills]]\n- [[Recent Work]]\n- [[Issues]]\n- [[Memory Dashboard]]\n")
        self._write_fixture_file("Recent Work.md", "# Recent Work\n\nGenerated disposable chronology summary.\n\n<!-- BEGIN AI MEMORY DAILY SUMMARY -->\nNo recent outcome is recorded.\n<!-- END AI MEMORY DAILY SUMMARY -->\n\n- [[Start Here]]\n")
        self._write_fixture_file("Memory Dashboard.md", "# Project Memory Dashboard\n\nGenerated disposable project coverage is currently empty.\n\n- [[Start Here]]\n")
        self._write_fixture_file("Issues.md", "# Issues\n\nNo active issue lifecycle is recorded in this disposable fixture.\n\n- [[Start Here]]\n")
        self._write_fixture_file("Projects/index.md", "# Projects\n\nGeneric projects use one index and one current Knowledge owner; no real project is copied into this fixture.\n\n- [[Start Here]]\n")
        self._write_fixture_file("Knowledge/index.md", "# Knowledge\n\nThis generic index owns reusable current engineering knowledge.\n\n- [[Knowledge/Project Learning|Project Learning]]\n- [[Knowledge/Reusable Lessons/index|Reusable Lessons]]\n- [[Knowledge/Book References/index|Book References]]\n- [[Start Here]]\n")
        self._write_fixture_file("Knowledge/Project Learning.md", "# Project Learning\n\n## One outcome, one event\n\nBug states are ACTIVE, MONITORING, RESOLVED, or ARCHIVED. `Recent Work.md` remains generated from the one event store.\n\n- [[Knowledge/index|Knowledge]]\n")
        self._write_fixture_file("Knowledge/Reusable Lessons/index.md", "# Reusable Lessons\n\nVerified cross-project patterns are grouped by stable generic category.\n\n- [[Knowledge/Reusable Lessons/Candidates|Candidate Queue]]\n- [[Knowledge/Reusable Lessons/Memory and Process|Memory and Process]]\n- [[Knowledge/Reusable Lessons/Code Architecture|Code Architecture]]\n- [[Knowledge/Reusable Lessons/Game Architecture|Game Architecture]]\n- [[Knowledge/Reusable Lessons/UI and Interaction|UI and Interaction]]\n- [[Knowledge/Reusable Lessons/Technology Decisions|Technology Decisions]]\n- [[Knowledge/Reusable Lessons/Verification|Verification]]\n- [[Knowledge/index|Knowledge]]\n")
        self._write_fixture_file("Knowledge/Reusable Lessons/Candidates.md", "# Auto-Classified Lesson Queue\n\nThis disposable candidate queue retains only verified, privacy-safe evidence pending promotion.\n\n- [[Knowledge/Reusable Lessons/index|Reusable Lessons]]\n")
        lesson_pages = (("Memory and Process", "memory ownership and durable lifecycle recovery"), ("Code Architecture", "module ownership and source-of-truth boundaries"), ("Game Architecture", "runtime rules and presentation boundaries"), ("UI and Interaction", "readable state and interaction feedback"), ("Technology Decisions", "platform and compatibility decisions"), ("Verification", "runtime evidence and acceptance gates"))
        for title, subject in lesson_pages:
            self._write_fixture_file(f"Knowledge/Reusable Lessons/{title}.md", f"# {title}\n\nVerified reusable lessons about {subject} belong in this generic category.\n\n- [[Knowledge/Reusable Lessons/index|Reusable Lessons]]\n")
        self._write_fixture_file("Knowledge/Book References/index.md", "# Book References\n\nThis generic index stores topic triggers, bounded citation ranges, and freshness without local library paths.\n\n- [[Knowledge/Book References/Programming and Software Engineering|Programming and Software Engineering]]\n- [[Knowledge/Book References/Unity and Game Development|Unity and Game Development]]\n- [[Knowledge/Book References/Computer Graphics and Shaders|Computer Graphics and Shaders]]\n- [[Knowledge/index|Knowledge]]\n")
        book_pages = (("Programming and Software Engineering", "language, testing, architecture, and maintenance"), ("Unity and Game Development", "game systems, physics, scenes, and editor tooling"), ("Computer Graphics and Shaders", "rendering, lighting, textures, and graphics mathematics"))
        for title, subject in book_pages:
            self._write_fixture_file(f"Knowledge/Book References/{title}.md", f"# {title}\n\nBounded references about {subject} record a citation range and freshness label without a local path.\n\n- [[Knowledge/Book References/index|Book References]]\n")
        self._write_fixture_file("Preferences/index.md", "# Preferences\n\nStable generic working preferences have one current owner.\n\n- [[Preferences/AI Captured Preferences|AI Captured Preferences]]\n- [[Start Here]]\n")
        self._write_fixture_file("Preferences/AI Captured Preferences.md", "# AI Captured Preferences\n\nOnly bounded, verified preference candidates may update this generic owner.\n\n- [[Preferences/index|Preferences]]\n")
        self._write_fixture_file("Skills/index.md", "# Skills\n\nReusable capability contracts are indexed here without task chronology.\n\n- [[Start Here]]\n")
        runtime_files = ("ai_memory.py", "auto_classify.py", "memory_lint.py", "tests/test_ai_memory.py", "tests/test_auto_classify.py", "tests/test_memory_lint.py")
        for runtime_file in runtime_files:
            self._write_fixture_file(f"AI Memory/{runtime_file}", f"RUNTIME_FIXTURE = {runtime_file!r}\n")
        self._write_fixture_file("AI Memory/events.jsonl", "")

    def _valid_event(self, event_id="20260801T100000Z-abcdef123456"):
        return {"schema_version": 2, "event_id": event_id, "recorded_at": "2026-08-01T10:00:00Z", "last_seen": "2026-08-01T10:00:00Z", "project": "ProjectOne", "project_root": "", "working_line": "main", "record_kind": "event", "event_type": "verification", "summary": "Verified memory integrity", "reason": "Exercise the complete runtime", "result": "All focused checks pass", "verification_status": "passed", "module_changes": [{"module": "memory.integrity", "summary": "Verified memory integrity"}], "issue_id": "", "issue_status": "", "bug_class": "", "attempt_count": 1, "session_key": "", "task_scope_key": "", "task_group_key": "", "task_scope_mode": "unscoped", "files": ["src/memory.py"], "verification": ["Focused checks passed"], "decisions": [], "risks": [], "memory_candidates": [], "supersedes": "", "source": "ai-memory-v2", "fingerprint": "a" * 64}

    def _write_events(self, events):
        text = "".join(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n" for event in events)
        (self.case_root / "AI Memory" / "events.jsonl").write_text(text, encoding="utf-8")

    def test_empty_event_store_is_valid(self):
        (self.case_root / "AI Memory" / "events.jsonl").write_text("", encoding="utf-8")
        audit = LINT.inspect_vault(self.case_root)
        self.assertEqual(audit["status"], "pass", audit["errors"])
        self.assertEqual(audit["ai_memory"]["events"], 0)
        self.assertGreater(audit["reachable_pages"], 10)

    def test_malformed_cache_path_is_an_integrity_error(self):
        malformed_path = self.case_root / "Cache" / "tests" / "memory-only|Cache" / "evidence.json"
        malformed_path.parent.mkdir(parents=True)
        malformed_path.write_text("{}\n", encoding="utf-8")
        audit = LINT.inspect_vault(self.case_root)
        self.assertTrue(any("Malformed path component" in error for error in audit["errors"]))

    def test_ghost_artifact_is_an_integrity_error(self):
        ghost_path = self.case_root / "Knowledge" / ".DS_Store"
        ghost_path.write_bytes(b"ghost")
        audit = LINT.inspect_vault(self.case_root)
        self.assertTrue(any("Ghost artifact remains" in error for error in audit["errors"]))

    def test_local_markdown_image_uri_is_an_integrity_error(self):
        local_image_uri = "file://" + str(Path("/", "Users", "example", "diagram.png"))
        local_link_uri = "file://" + str(Path("/", "Users", "example", "evidence.txt"))
        page_path = self.case_root / "Knowledge" / "Local Image.md"
        page_path.write_text(f"# Local Image\n\nThis page embeds machine-local references.\n\n![diagram]({local_image_uri})\n\n[evidence]({local_link_uri})\n", encoding="utf-8")
        knowledge_index = self.case_root / "Knowledge" / "index.md"
        knowledge_index.write_text(knowledge_index.read_text(encoding="utf-8") + "\n- [[Knowledge/Local Image]]\n", encoding="utf-8")
        audit = LINT.inspect_vault(self.case_root)
        self.assertIn("Non-portable local image URI in Knowledge/Local Image.md: image[0]", audit["errors"])
        self.assertIn("Non-portable local URI in Knowledge/Local Image.md: link[0]", audit["errors"])
        self.assertNotIn(local_image_uri, "\n".join(audit["errors"]))
        self.assertNotIn(local_link_uri, "\n".join(audit["errors"]))

    def test_untitled_and_placeholder_only_markdown_are_integrity_errors(self):
        (self.case_root / "Knowledge" / "Untitled draft.md").write_text("# Draft\n\nThis page should have a stable owner name.\n", encoding="utf-8")
        (self.case_root / "Knowledge" / "Pending Rule.md").write_text("# Pending Rule\n\nTODO\n", encoding="utf-8")
        knowledge_index = self.case_root / "Knowledge" / "index.md"
        knowledge_index.write_text(knowledge_index.read_text(encoding="utf-8") + "\n- [[Knowledge/Untitled draft]]\n- [[Knowledge/Pending Rule]]\n", encoding="utf-8")
        audit = LINT.inspect_vault(self.case_root)
        self.assertTrue(any("Ghost Markdown remains: Knowledge/Untitled draft.md" in error for error in audit["errors"]))
        self.assertTrue(any("Placeholder-only memory page: Knowledge/Pending Rule.md" in error for error in audit["errors"]))

    def test_normalized_semantic_duplicate_markdown_is_an_integrity_error(self):
        target = "Knowledge/Project Learning#One outcome, one event"
        (self.case_root / "Knowledge" / "Rule A.md").write_text(f"# Rule A\n\n- [[{target}|First alias]] — Use one canonical owner for the verified state.\n", encoding="utf-8")
        (self.case_root / "Knowledge" / "Rule B.md").write_text(f"# Rule B\n\n[[{target}|Second alias]] USE one canonical owner for the verified state!\n", encoding="utf-8")
        knowledge_index = self.case_root / "Knowledge" / "index.md"
        knowledge_index.write_text(knowledge_index.read_text(encoding="utf-8") + "\n- [[Knowledge/Rule A]]\n- [[Knowledge/Rule B]]\n", encoding="utf-8")
        audit = LINT.inspect_vault(self.case_root)
        duplicate_errors = [error for error in audit["errors"] if "Semantic duplicate Markdown pages" in error]
        self.assertEqual(duplicate_errors, ["Semantic duplicate Markdown pages: Knowledge/Rule A.md, Knowledge/Rule B.md"])

    def test_same_index_body_with_different_owner_targets_is_not_duplicate(self):
        shared_tail = " — Current project truth.\n- [[AI Memory/events.jsonl|Events]] — Sole chronology.\n"
        self._write_fixture_file("Projects/Alpha/index.md", "# Alpha\n\n## Project knowledge\n\n- [[Projects/Alpha/Knowledge|Knowledge]]" + shared_tail)
        self._write_fixture_file("Projects/Beta/index.md", "# Beta\n\n## Project knowledge\n\n- [[Projects/Beta/Knowledge|Knowledge]]" + shared_tail)
        duplicate_errors = LINT.inspect_markdown_semantic_duplicates(self.case_root)
        self.assertEqual(duplicate_errors, [])

    def test_broken_wikilink_and_anchor_are_integrity_errors(self):
        page_path = self.case_root / "Knowledge" / "Broken Links.md"
        page_path.write_text("# Broken Links\n\nThis page contains invalid navigation.\n\n- [[Knowledge/Missing Page]]\n- [[Knowledge/Project Learning#Missing Heading]]\n", encoding="utf-8")
        knowledge_index = self.case_root / "Knowledge" / "index.md"
        knowledge_index.write_text(knowledge_index.read_text(encoding="utf-8") + "\n- [[Knowledge/Broken Links]]\n", encoding="utf-8")
        audit = LINT.inspect_vault(self.case_root)
        broken_errors = [error for error in audit["errors"] if "Broken or inaccessible wikilink" in error]
        self.assertEqual(len(broken_errors), 2)
        self.assertNotIn("Knowledge/Missing Page", "\n".join(broken_errors))

    def test_unreachable_semantic_page_is_an_integrity_error(self):
        (self.case_root / "Knowledge" / "Island.md").write_text("# Island\n\nThis semantic memory page has no root navigation path.\n", encoding="utf-8")
        audit = LINT.inspect_vault(self.case_root)
        self.assertIn("Unreachable memory page: Knowledge/Island.md", audit["errors"])

    def test_invalid_utf8_and_headings_only_pages_are_integrity_errors(self):
        (self.case_root / "Knowledge" / "Unreadable.md").write_bytes(b"\xff\xfe")
        (self.case_root / "Knowledge" / "Empty Meaning.md").write_text("# Empty Meaning\n\n## Nothing Else\n", encoding="utf-8")
        knowledge_index = self.case_root / "Knowledge" / "index.md"
        knowledge_index.write_text(knowledge_index.read_text(encoding="utf-8") + "\n- [[Knowledge/Unreadable]]\n- [[Knowledge/Empty Meaning]]\n", encoding="utf-8")
        audit = LINT.inspect_vault(self.case_root)
        self.assertTrue(any("Unreadable UTF-8 managed file Knowledge/Unreadable.md" in error for error in audit["errors"]))
        self.assertTrue(any("Headings-only or navigation-only memory page: Knowledge/Empty Meaning.md" in error for error in audit["errors"]))

    def test_placeholder_and_semantic_duplicate_events_are_integrity_errors(self):
        first = self._valid_event()
        duplicate = dict(first)
        duplicate.update({"event_id": "20260802T100000Z-fedcba654321", "recorded_at": "2026-08-02T10:00:00Z", "last_seen": "2026-08-02T10:00:00Z", "session_key": "2" * 24, "task_scope_key": "3" * 24, "task_group_key": "4" * 24, "task_scope_mode": "session+task+group"})
        placeholder = self._valid_event("20260803T100000Z-placeholder01")
        placeholder.update({"summary": "tmp", "reason": "tmp", "result": "tmp", "module_changes": [{"module": "memory.integrity", "summary": "tmp"}]})
        self._write_events([first, duplicate, placeholder])
        audit = LINT.inspect_vault(self.case_root)
        self.assertTrue(any("placeholder summary" in error for error in audit["errors"]))
        self.assertTrue(any("Semantic duplicate AI events" in error for error in audit["errors"]))

    def test_plaintext_task_and_group_fields_are_integrity_errors(self):
        event = self._valid_event()
        event.update({"task_name": "private-task-name", "task_group": "private-task-group"})
        self._write_events([event])
        audit = LINT.inspect_vault(self.case_root)
        self.assertTrue(any("forbidden private fields task_group, task_name" in error for error in audit["errors"]))

    def test_drive_relative_and_uri_event_files_are_integrity_errors(self):
        event = self._valid_event()
        private_path = str(Path("/", "Users", "example", "private-project", "source.py"))
        event["files"] = ["C:drive-relative.py", "obsidian:Projects/ProjectOne/Knowledge.md", private_path]
        self._write_events([event])
        _, errors = LINT.inspect_event_store(self.case_root / "AI Memory" / "events.jsonl")
        file_errors = [error for error in errors if "is not project-relative" in error]
        self.assertEqual(
            file_errors,
            [
                "AI event line 1: files[0] is not project-relative",
                "AI event line 1: files[1] is not project-relative",
                "AI event line 1: files[2] is not project-relative",
            ],
        )
        self.assertNotIn(private_path, "\n".join(errors))

    def test_windows_home_path_in_semantic_field_is_an_integrity_error(self):
        event = self._valid_event()
        event["verification"] = ["C:" + "\\Users\\example\\private-project\\evidence.txt"]
        self._write_events([event])
        _, errors = LINT.inspect_event_store(self.case_root / "AI Memory" / "events.jsonl")
        self.assertTrue(any("private or secret-like content is forbidden" in error for error in errors))

    def test_workspace_stale_paths_are_warnings_only(self):
        workspace_path = self.case_root / ".obsidian" / "workspace.json"
        workspace_path.parent.mkdir(parents=True)
        workspace_path.write_text('{"lastOpenFiles":["Journal/Old.md","Archive/Old.md"]}\n', encoding="utf-8")
        audit = LINT.inspect_vault(self.case_root)
        self.assertEqual(audit["status"], "pass", audit["errors"])
        self.assertEqual(len(audit["warnings"]), 2)


if __name__ == "__main__":
    unittest.main()
