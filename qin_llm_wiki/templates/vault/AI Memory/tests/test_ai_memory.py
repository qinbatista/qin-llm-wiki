import importlib.util
import json
import os
import shutil
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).parents[1] / "ai_memory.py"
SPECIFICATION = importlib.util.spec_from_file_location("ai_memory", SCRIPT_PATH)
MEMORY = importlib.util.module_from_spec(SPECIFICATION)
SPECIFICATION.loader.exec_module(MEMORY)
VAULT_ROOT = SCRIPT_PATH.parents[1]
TEST_CACHE_ROOT = Path(os.environ.get("QIN_LLM_WIKI_TEST_CACHE", VAULT_ROOT / "Cache" / "tests" / "ai-memory-runtime"))


class AIMemoryTests(unittest.TestCase):
    def setUp(self):
        TEST_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
        self.case_root = TEST_CACHE_ROOT / self._testMethodName
        if self.case_root.exists():
            shutil.rmtree(self.case_root)
        self.case_root.mkdir(parents=True)
        self.store = self.case_root / "events.jsonl"

    def tearDown(self):
        if self.case_root.exists():
            shutil.rmtree(self.case_root)

    def _symlink_or_skip(self, target_path, link_path):
        link_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            link_path.symlink_to(target_path.resolve())
        except (NotImplementedError, OSError) as error:
            self.skipTest(f"symlink creation is unavailable: {error}")

    def test_repeated_issue_updates_one_row(self):
        first = MEMORY.record_event("GameOne", "combat.damage", "bug-fix", "Damage is wrong", "Multiplier ordering", "Monitoring remains active", "partial", issue_id="combat-001", issue_status="MONITORING", files=["src/combat.py"], events_path=self.store)
        second = MEMORY.record_event("GameOne", "combat.damage", "bug-fix", "Damage calculation fixed", "Multiplier reordered", "Focused checks pass", "passed", issue_id="combat-001", issue_status="RESOLVED", files=["src/combat.py"], events_path=self.store)
        events = MEMORY._read_events(self.store)
        self.assertEqual(first["status"], "written")
        self.assertEqual(second["status"], "updated")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["attempt_count"], 2)

    def test_issue_update_is_resorted_before_bounded_search(self):
        MEMORY.record_event("GameOne", "combat.damage", "bug-fix", "Initial damage issue", "Rounding order", "Monitoring remains active", "partial", issue_id="combat-001", files=["src/combat.py"], recorded_at="2026-08-01T10:00:00Z", events_path=self.store)
        MEMORY.record_event("GameOne", "combat.damage", "verification", "Intermediate damage check", "Exercise retrieval ordering", "Intermediate checks pass", "passed", files=["src/combat.py"], recorded_at="2026-08-02T10:00:00Z", events_path=self.store)
        MEMORY.record_event("GameOne", "combat.damage", "bug-fix", "Latest damage repair", "Corrected rounding order", "Latest checks pass", "passed", issue_id="combat-001", files=["src/combat.py"], recorded_at="2026-08-03T10:00:00Z", events_path=self.store)
        match = MEMORY.search_events("GameOne", "combat.damage", limit=1, compact=True, events_path=self.store)["matches"][0]
        self.assertEqual(match["summary"], "Latest damage repair")
        self.assertEqual(match["last_seen"], "2026-08-03T10:00:00Z")

    def test_bug_fix_requires_stable_issue_id(self):
        with self.assertRaises(ValueError):
            MEMORY.record_event("GameOne", "combat.damage", "bug-fix", "Damage calculation fixed", "Multiplier reordered", "Focused checks pass", "passed", files=["src/combat.py"], events_path=self.store)

    def test_compact_search_crosses_session_provenance_without_exposing_evidence(self):
        MEMORY.record_event("GameOne", "combat.damage", "verification", "Verified critical damage", "Rounding order changed", "Focused checks pass", "passed", files=["src/combat.py"], verification=["long evidence"], recorded_at="2026-08-01T10:00:00Z", events_path=self.store, task_name="critical damage", session_id="11111111-1111-4111-8111-111111111111")
        compact = MEMORY.search_events("GameOne", "combat.damage", "critical", compact=True, events_path=self.store, task_name="another task", session_id="22222222-2222-4222-8222-222222222222")
        self.assertEqual(len(compact["matches"]), 1)
        self.assertNotIn("verification", compact["matches"][0])
        self.assertEqual(compact["matches"][0]["scope_relation"], "project_result_provenance")
        self.assertEqual(compact["matches"][0]["provenance_relation"], "unrelated_session")

    def test_semantic_duplicate_ignores_session_and_task_provenance(self):
        first = MEMORY.record_event("GameOne", "combat.damage", "verification", "Verified damage contract", "The runtime path was exercised", "Focused checks pass", "passed", files=["src/combat.py"], recorded_at="2026-08-01T10:00:00Z", events_path=self.store, task_name="first task", session_id="11111111-1111-4111-8111-111111111111")
        second = MEMORY.record_event("GameOne", "combat.damage", "verification", "Verified damage contract", "The runtime path was exercised", "Focused checks pass", "passed", files=["src/combat.py"], recorded_at="2026-08-02T10:00:00Z", events_path=self.store, task_name="second task", session_id="22222222-2222-4222-8222-222222222222")
        self.assertEqual(first["status"], "written")
        self.assertEqual(second["status"], "duplicate")
        self.assertEqual(first["event_id"], second["event_id"])
        self.assertEqual(len(MEMORY._read_events(self.store)), 1)

    def test_semantic_duplicate_uses_casefolded_project_identity(self):
        first = MEMORY.record_event("GameOne", "combat.damage", "verification", "Verified damage contract", "Exercise canonical identity", "Focused checks pass", "passed", files=["src/combat.py"], recorded_at="2026-08-01T10:00:00Z", events_path=self.store)
        second = MEMORY.record_event("gameone", "combat.damage", "verification", "Verified damage contract", "Exercise canonical identity", "Focused checks pass", "passed", files=["src/combat.py"], recorded_at="2026-08-02T10:00:00Z", events_path=self.store)
        self.assertEqual(second["status"], "duplicate")
        self.assertEqual(second["event_id"], first["event_id"])
        self.assertEqual(len(MEMORY._read_events(self.store)), 1)

    def test_recorded_at_requires_iso_utc_and_normalizes_zero_offset(self):
        MEMORY.record_event("GameOne", "combat.damage", "verification", "Verified timestamp contract", "Exercise UTC normalization", "Focused checks pass", "passed", files=["src/combat.py"], recorded_at="2026-08-01T10:00:00+00:00", events_path=self.store)
        event = MEMORY._read_events(self.store)[0]
        self.assertEqual(event["recorded_at"], "2026-08-01T10:00:00Z")
        original_store = self.store.read_bytes()
        for invalid_value in ("not-a-time", "2026-08-01T10:00:00", "2026-08-01T10:00:00-07:00"):
            with self.subTest(recorded_at=invalid_value), self.assertRaises(ValueError):
                MEMORY.record_event("GameOne", "combat.damage", "verification", "Different timestamp outcome", "Exercise invalid UTC input", "Focused checks pass", "passed", files=["src/combat.py"], recorded_at=invalid_value, events_path=self.store)
            self.assertEqual(self.store.read_bytes(), original_store)

    def test_secret_guard_covers_every_persisted_user_field_before_write(self):
        synthetic_secret = "sk-" + "a" * 20
        cases = [("project", {"project": synthetic_secret}), ("module", {"module": f"architecture.{synthetic_secret}"}), ("working_line", {"working_line": synthetic_secret}), ("issue_id", {"issue_id": synthetic_secret}), ("bug_class", {"bug_class": synthetic_secret}), ("summary", {"summary": synthetic_secret}), ("reason", {"reason": synthetic_secret}), ("result", {"result": synthetic_secret}), ("module_change_module", {"module_change_values": [f"{synthetic_secret}=Verified secondary module"]}), ("module_change_summary", {"module_change_values": [f"secondary.module={synthetic_secret}"]}), ("file", {"files": [f"src/{synthetic_secret}.py"]}), ("verification", {"verification": [synthetic_secret]}), ("decision", {"decisions": [synthetic_secret]}), ("risk", {"risks": [synthetic_secret]})]
        for field_name, overrides in cases:
            arguments = {"project": "GameOne", "module": "combat.damage", "event_type": "architecture", "summary": "Verified secret guard", "reason": "Exercise every persisted field", "result": "Focused checks pass", "verification_status": "passed", "files": ["src/combat.py"], "events_path": self.store}
            arguments.update(overrides)
            with self.subTest(field=field_name), self.assertRaises(ValueError):
                MEMORY.record_event(**arguments)
            self.assertFalse(self.store.exists())

    def test_secret_guard_matches_lint_patterns_and_raw_windows_paths(self):
        private_values = [("api-key", "api key=" + "a" * 12), ("cookie", "cookie:" + "b" * 12), ("credential", "credential=" + "c" * 12), ("windows-home", "C:" + "\\" + "Users" + "\\" + "example" + "\\" + "private-project" + "\\" + "source.py")]
        for pattern_name, private_value in private_values:
            with self.subTest(pattern=pattern_name), self.assertRaises(ValueError):
                MEMORY.record_event("GameOne", "combat.damage", "verification", "Verified privacy contract", "Exercise the runtime privacy gate", "Focused checks pass", "passed", files=["src/combat.py"], verification=[private_value], events_path=self.store)
            self.assertFalse(self.store.exists())
        semantic_event = {"project": "GameOne", "summary": "Verified privacy contract", "reason": "Exercise raw semantic leaves", "result": "Focused checks pass", "module_changes": [{"module": "combat.damage", "summary": "Verified privacy contract"}], "verification": [private_values[-1][1]]}
        with self.assertRaises(ValueError):
            MEMORY._validate_event_semantics(semantic_event)

    def test_fresh_provenance_persists_only_hashes(self):
        task_name = "private task label"
        task_group = "private group label"
        MEMORY.record_event("GameOne", "combat.damage", "verification", "Verified hashed provenance", "Exercise relation metadata", "Focused checks pass", "passed", files=["src/combat.py"], recorded_at="2026-08-01T10:00:00Z", events_path=self.store, task_name=task_name, task_group=task_group, session_id="11111111-1111-4111-8111-111111111111")
        event = MEMORY._read_events(self.store)[0]
        raw_store = self.store.read_text(encoding="utf-8")
        self.assertNotIn(task_name, raw_store)
        self.assertNotIn(task_group, raw_store)
        self.assertNotIn("task_name", event)
        self.assertNotIn("task_group", event)
        self.assertNotIn("session_id", event)
        self.assertRegex(event["session_key"], r"^[0-9a-f]{24}$")
        self.assertRegex(event["task_scope_key"], r"^[0-9a-f]{24}$")
        self.assertRegex(event["task_group_key"], r"^[0-9a-f]{24}$")
        related = MEMORY.search_events("GameOne", "combat.damage", compact=True, events_path=self.store, task_name="different task", task_group=task_group, session_id="22222222-2222-4222-8222-222222222222")["matches"][0]
        self.assertEqual(related["provenance_relation"], "related_task_group")

    def test_migrate_provenance_cli_hashes_legacy_labels_and_is_idempotent(self):
        written = MEMORY.record_event("GameOne", "combat.damage", "verification", "Verified legacy provenance", "Exercise guarded migration", "Focused checks pass", "passed", files=["src/combat.py"], recorded_at="2026-08-01T10:00:00Z", events_path=self.store)
        event = MEMORY._read_events(self.store)[0]
        original_fingerprint = event["fingerprint"]
        event.update({"session_id": "11111111-1111-4111-8111-111111111111", "session_key": "", "task_name": "Legacy Task Label", "task_group": "Legacy Group Label", "task_scope_key": "", "task_group_key": "", "task_scope_mode": "unscoped"})
        MEMORY._write_events([event], self.store)
        command = [sys.executable, "-B", str(SCRIPT_PATH), "--store", str(self.store), "migrate-provenance"]
        first = subprocess.run(command, cwd=self.case_root, text=True, capture_output=True, check=False)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(json.loads(first.stdout)["status"], "migrated")
        migrated = MEMORY._read_events(self.store)[0]
        self.assertEqual(migrated["event_id"], written["event_id"])
        self.assertEqual(migrated["fingerprint"], original_fingerprint)
        self.assertEqual(migrated["task_scope_key"], MEMORY._task_scope_key("GameOne", "combat.damage", MEMORY._normalize_task_name("Legacy Task Label")))
        self.assertEqual(migrated["task_group_key"], MEMORY._task_group_key("GameOne", MEMORY._normalize_task_name("Legacy Group Label"), MEMORY._normalize_task_name("Legacy Task Label")))
        self.assertRegex(migrated["session_key"], r"^[0-9a-f]{24}$")
        self.assertNotIn("task_name", migrated)
        self.assertNotIn("task_group", migrated)
        self.assertNotIn("session_id", migrated)
        migrated_bytes = self.store.read_bytes()
        second = subprocess.run(command, cwd=self.case_root, text=True, capture_output=True, check=False)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(json.loads(second.stdout)["status"], "no-op")
        self.assertEqual(self.store.read_bytes(), migrated_bytes)
        guarded_store = self.case_root / "guarded-events.jsonl"
        invalid = dict(migrated)
        invalid.update({"task_scope_key": "invalid", "task_name": "Legacy Task Label"})
        MEMORY._write_events([invalid], guarded_store)
        guarded_bytes = guarded_store.read_bytes()
        with self.assertRaises(ValueError):
            MEMORY.migrate_provenance(guarded_store)
        self.assertEqual(guarded_store.read_bytes(), guarded_bytes)

    def test_redact_private_cli_is_recursive_idempotent_and_preserves_files(self):
        written = MEMORY.record_event("GameOne", "combat.damage", "verification", "Verified privacy migration", "Exercise exact historical redaction", "Focused checks pass", "passed", files=["src/combat.py"], recorded_at="2026-08-01T10:00:00Z", events_path=self.store)
        event = MEMORY._read_events(self.store)[0]
        original_event_id = event["event_id"]
        original_fingerprint = event["fingerprint"]
        private_path = str(Path("/", "Users", "example", "private-project", "source.py"))
        private_cookie = "cookie=" + "c" * 12
        event["summary"] = f"Verified local source {private_path}"
        event["module_changes"][0]["summary"] = f"Verified local source {private_path}"
        event["verification"] = [f"Stored {private_cookie}"]
        MEMORY._write_events([event], self.store)
        command = [sys.executable, "-B", str(SCRIPT_PATH), "--store", str(self.store), "redact-private", "--event-id", written["event_id"]]
        completed = subprocess.run(command, cwd=self.case_root, text=True, capture_output=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        output = json.loads(completed.stdout)
        redacted = MEMORY._read_events(self.store)[0]
        self.assertEqual(output["status"], "redacted-private")
        self.assertEqual(output["auto_classification"], {"status": "skipped", "reason": "non-default-store"})
        self.assertEqual(output["event_id"], original_event_id)
        self.assertEqual(redacted["event_id"], original_event_id)
        self.assertEqual(redacted["files"], ["src/combat.py"])
        self.assertEqual(redacted["summary"], "Verified local source [private data omitted]")
        self.assertEqual(redacted["module_changes"][0]["summary"], "Verified local source [private data omitted]")
        self.assertEqual(redacted["verification"], ["Stored [private data omitted]"])
        self.assertNotEqual(redacted["fingerprint"], original_fingerprint)
        self.assertEqual(redacted["fingerprint"], MEMORY._fingerprint(redacted))
        self.assertNotIn(private_path, completed.stdout + completed.stderr)
        self.assertNotIn(private_cookie, completed.stdout + completed.stderr)
        redacted_bytes = self.store.read_bytes()
        repeated = subprocess.run(command, cwd=self.case_root, text=True, capture_output=True, check=False)
        self.assertEqual(repeated.returncode, 0, repeated.stdout + repeated.stderr)
        self.assertEqual(json.loads(repeated.stdout)["status"], "no-op")
        self.assertEqual(self.store.read_bytes(), redacted_bytes)

    def test_redact_private_rejects_invalid_missing_non_object_and_leaves_files_unchanged(self):
        with self.assertRaisesRegex(ValueError, "invalid format"):
            MEMORY.redact_private_event("../invalid", self.store)
        self.assertFalse(self.store.exists())
        written = MEMORY.record_event("GameOne", "combat.damage", "verification", "Verified guarded redaction", "Exercise exact event selection", "Focused checks pass", "passed", files=["src/combat.py"], events_path=self.store)
        original_bytes = self.store.read_bytes()
        with self.assertRaisesRegex(ValueError, "does not exist"):
            MEMORY.redact_private_event("20260809T010101Z-abcdef123456", self.store)
        self.assertEqual(self.store.read_bytes(), original_bytes)
        events = MEMORY._read_events(self.store)
        MEMORY._write_events([*events, "not-an-object"], self.store)
        non_object_bytes = self.store.read_bytes()
        with self.assertRaisesRegex(ValueError, "non-object"):
            MEMORY.redact_private_event(written["event_id"], self.store)
        self.assertEqual(self.store.read_bytes(), non_object_bytes)
        duplicate_id_store = self.case_root / "duplicate-id-events.jsonl"
        MEMORY._write_events([events[0], dict(events[0])], duplicate_id_store)
        duplicate_id_bytes = duplicate_id_store.read_bytes()
        with self.assertRaisesRegex(ValueError, "not unique"):
            MEMORY.redact_private_event(written["event_id"], duplicate_id_store)
        self.assertEqual(duplicate_id_store.read_bytes(), duplicate_id_bytes)
        guarded_store = self.case_root / "guarded-events.jsonl"
        guarded_event = dict(events[0])
        guarded_event["files"] = [str(Path("/", "Users", "example", "private-project", "source.py"))]
        MEMORY._write_events([guarded_event], guarded_store)
        guarded_bytes = guarded_store.read_bytes()
        with mock.patch.object(MEMORY, "_run_auto_classification") as classifier:
            output = MEMORY.redact_private_event(written["event_id"], guarded_store)
        classifier.assert_not_called()
        self.assertEqual(output["status"], "no-op")
        self.assertEqual(guarded_store.read_bytes(), guarded_bytes)

    def test_redact_private_rejects_semantic_duplicate_without_writing(self):
        canonical = MEMORY.record_event("GameOne", "combat.damage", "verification", "Verified source [private data omitted]", "Exercise duplicate protection", "Focused checks pass", "passed", files=["src/combat.py"], recorded_at="2026-08-01T10:00:00Z", events_path=self.store)
        target = MEMORY.record_event("GameOne", "combat.damage", "verification", "Verified temporary source", "Exercise duplicate protection", "Focused checks pass", "passed", files=["src/combat.py"], recorded_at="2026-08-01T10:01:00Z", events_path=self.store)
        events = MEMORY._read_events(self.store)
        target_event = next(event for event in events if event["event_id"] == target["event_id"])
        private_path = str(Path("/", "Users", "example", "private-project", "source.py"))
        target_event["summary"] = f"Verified source {private_path}"
        target_event["module_changes"] = [{"module": "combat.damage", "summary": target_event["summary"]}]
        MEMORY._write_events(events, self.store)
        original_bytes = self.store.read_bytes()
        command = [sys.executable, "-B", str(SCRIPT_PATH), "--store", str(self.store), "redact-private", "--event-id", target["event_id"]]
        completed = subprocess.run(command, cwd=self.case_root, text=True, capture_output=True, check=False)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("semantic-duplicate-conflict", completed.stderr)
        self.assertIn(canonical["event_id"], completed.stderr)
        self.assertNotIn("private-project", completed.stdout + completed.stderr)
        self.assertEqual(self.store.read_bytes(), original_bytes)
        with mock.patch.object(MEMORY, "_run_auto_classification") as classifier, self.assertRaisesRegex(ValueError, "semantic-duplicate-conflict"):
            MEMORY.redact_private_event(target["event_id"], self.store)
        classifier.assert_not_called()

    def test_project_name_may_contain_test_without_being_placeholder_content(self):
        result = MEMORY.record_event("Test Project", "quality.tests", "verification", "Verified generated memory runtime", "Exercise the generated architecture", "All runtime checks pass", "passed", files=["src/runtime.py"], events_path=self.store)
        self.assertEqual(result["status"], "written")

    def test_project_name_rejects_path_components_before_write(self):
        for project_name in ("../OtherProject", "Group/Project", r"Group\Project"):
            with self.subTest(project=project_name), self.assertRaisesRegex(ValueError, "folder-safe"):
                MEMORY.record_event(project_name, "quality.tests", "verification", "Verified project identity", "Exercise the project owner boundary", "Focused checks pass", "passed", files=["src/runtime.py"], events_path=self.store)
            self.assertFalse(self.store.exists())

    def test_placeholder_semantics_are_rejected_before_write(self):
        with self.assertRaises(ValueError):
            MEMORY.record_event("GameOne", "combat.damage", "verification", "tmp", "Exercise the runtime path", "Focused checks pass", "passed", files=["src/combat.py"], events_path=self.store)
        self.assertFalse(self.store.exists())

    def test_files_must_be_project_relative(self):
        with self.assertRaises(ValueError):
            MEMORY.record_event("GameOne", "combat.damage", "general", "Changed damage", "Update calculation", "Focused checks pass", "passed", files=[str(Path("/", "private", "source.py"))], events_path=self.store)
        with self.assertRaises(ValueError):
            MEMORY.record_event("GameOne", "combat.damage", "general", "Changed damage", "Update calculation", "Focused checks pass", "passed", files=["C:drive-relative.py"], events_path=self.store)

    def test_amend_replace_file_cli_is_exact_and_normalized(self):
        written = MEMORY.record_event("GameOne", "combat.damage", "verification", "Verified file evidence", "Exercise exact file replacement", "Focused checks pass", "passed", files=["src/old.py", "src/older.py"], events_path=self.store)
        command = [sys.executable, "-B", str(SCRIPT_PATH), "--store", str(self.store), "--vault", str(self.case_root), "amend", "--event-id", written["event_id"], "--replace-file", r"src\old.py=src\new.py"]
        completed = subprocess.run(command, cwd=self.case_root, text=True, capture_output=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["status"], "updated")
        self.assertEqual(MEMORY._read_events(self.store)[0]["files"], ["src/new.py", "src/older.py"])
        original_store = self.store.read_bytes()
        with self.assertRaises(ValueError):
            MEMORY.amend_event(written["event_id"], events_path=self.store, replace_files=["src/missing.py=src/other.py"])
        self.assertEqual(self.store.read_bytes(), original_store)

    def test_render_creates_only_generated_root_views(self):
        recent = self.case_root / "vault" / "Recent Work.md"
        dashboard = self.case_root / "vault" / "Memory Dashboard.md"
        issues = self.case_root / "vault" / "Issues.md"
        MEMORY.record_event("GameOne", "combat.damage", "feature", "Updated combat", "Improve gameplay", "Focused checks pass", "passed", recorded_at="2026-08-01T10:00:00Z", events_path=self.store)
        MEMORY.render_views(self.store, recent, dashboard, issues, now=datetime(2026, 8, 1, 18, 0, tzinfo=timezone.utc))
        self.assertIn("1 outcomes", recent.read_text(encoding="utf-8"))
        self.assertFalse((self.case_root / "vault" / "Journal").exists())
        self.assertFalse((self.case_root / "vault" / "Archive").exists())

    def test_vault_owner_writes_reject_escaping_symlinks_before_mutation(self):
        vault = self.case_root / "vault"
        sentinel = self.case_root / "external-owner.md"
        sentinel.write_text("EXTERNAL OWNER CONTENT\n", encoding="utf-8")
        projects_index = vault / "Projects" / "index.md"
        self._symlink_or_skip(sentinel, projects_index)
        with self.assertRaises(ValueError):
            MEMORY.add_project("GameOne", vault)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "EXTERNAL OWNER CONTENT\n")
        recent = vault / "Recent Work.md"
        self._symlink_or_skip(sentinel, recent)
        with self.assertRaises(ValueError):
            MEMORY.render_views(self.store, recent, vault / "Memory Dashboard.md", vault / "Issues.md")
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "EXTERNAL OWNER CONTENT\n")
        captured_owner = vault / "Preferences" / "AI Captured Preferences.md"
        self._symlink_or_skip(sentinel, captured_owner)
        candidate = {"kind": "technical-trait", "area": "technical", "statement": "Values exact bounded project evidence.", "evidence": "Repeated verified project-memory outcomes.", "basis": "verified_work_pattern", "confidence": "high", "source": "ending"}
        capture_store = self.case_root / "capture-events.jsonl"
        with self.assertRaises(ValueError):
            MEMORY.record_memory_candidates([candidate], events_path=capture_store, preferences_root=vault)
        self.assertFalse(capture_store.exists())

    def test_classifier_runs_after_store_lock_for_redaction_and_capture_owner_runs_inside_lock(self):
        original_lock = MEMORY._with_store_lock
        original_owner_writer = MEMORY._write_memory_owner_pages
        state = {"lock_depth": 0, "classifier_outside": False, "classifier_calls": 0, "owner_inside": False}

        def tracked_lock(events_path, operation):
            def tracked_operation(events):
                state["lock_depth"] += 1
                try:
                    return operation(events)
                finally:
                    state["lock_depth"] -= 1
            return original_lock(events_path, tracked_operation)

        def tracked_classifier(events_path):
            state["classifier_outside"] = state["lock_depth"] == 0
            state["classifier_calls"] += 1
            return {"status": "skipped", "reason": "focused-test"}

        def tracked_owner_writer(events, vault_root):
            state["owner_inside"] = state["lock_depth"] > 0
            return original_owner_writer(events, vault_root)

        candidate = {"kind": "technical-trait", "area": "technical", "statement": "Values serialized owner projections.", "evidence": "Verified concurrent capture behavior.", "basis": "verified_work_pattern", "confidence": "high", "source": "ending"}
        with mock.patch.object(MEMORY, "_with_store_lock", side_effect=tracked_lock), mock.patch.object(MEMORY, "_run_auto_classification", side_effect=tracked_classifier), mock.patch.object(MEMORY, "_write_memory_owner_pages", side_effect=tracked_owner_writer):
            captured = MEMORY.record_memory_candidates([candidate], events_path=self.store, preferences_root=self.case_root, recorded_at="2026-08-01T10:00:00Z")
            events = MEMORY._read_events(self.store)
            private_path = str(Path("/", "Users", "example", "private-project", "source.py"))
            events[0]["summary"] = f"Verified local source {private_path}"
            events[0]["module_changes"][0]["summary"] = events[0]["summary"]
            MEMORY._write_events(events, self.store)
            state.update({"classifier_outside": False, "classifier_calls": 0})
            redacted = MEMORY.redact_private_event(captured["event_id"], self.store)
            no_op = MEMORY.redact_private_event(captured["event_id"], self.store)
        self.assertTrue(state["classifier_outside"])
        self.assertEqual(state["classifier_calls"], 1)
        self.assertTrue(state["owner_inside"])
        self.assertEqual(redacted["auto_classification"], {"status": "skipped", "reason": "focused-test"})
        self.assertNotIn("auto_classification", no_op)

    def test_memory_candidates_are_a_noop_when_none_are_relevant(self):
        result = MEMORY.record_memory_candidates([], events_path=self.store, preferences_root=self.case_root)
        self.assertEqual(result, {"status": "no-candidates", "written": False, "candidates": 0})
        self.assertFalse(self.store.exists())
        self.assertFalse((self.case_root / "Preferences").exists())

    def test_memory_candidates_write_one_event_and_owner_pages(self):
        ui_page = self.case_root / "Preferences" / "UI Style Preferences.md"
        ui_page.parent.mkdir(parents=True)
        ui_page.write_text("# UI Style Preferences\n\nExisting user-owned content.\n", encoding="utf-8")
        candidates = [{"kind": "preference", "area": "ui", "statement": "Prefer compact parallel status rows with visible progress bars.", "evidence": "The user explicitly requested a clearer compact monitoring layout.", "basis": "explicit_user_request", "confidence": "high", "source": "ending"}, {"kind": "technical-trait", "area": "technical", "statement": "Values evidence-backed lifecycle state over status prose.", "evidence": "Repeated corrections requested observable status and restart guidance.", "basis": "repeated_user_correction", "confidence": "high", "source": "ending"}]
        result = MEMORY.record_memory_candidates(candidates, project="Global Preferences", events_path=self.store, preferences_root=self.case_root, recorded_at="2026-08-05T12:00:00Z")
        duplicate = MEMORY.record_memory_candidates(candidates, project="Global Preferences", events_path=self.store, preferences_root=self.case_root, recorded_at="2026-08-06T12:00:00Z")
        events = MEMORY._read_events(self.store)
        self.assertEqual(result["status"], "written")
        self.assertEqual(duplicate["status"], "duplicate")
        self.assertEqual(len(events), 1)
        self.assertIn("Prefer compact parallel status rows", ui_page.read_text(encoding="utf-8"))
        self.assertIn("Values evidence-backed lifecycle state", (self.case_root / "Preferences" / "AI Captured Preferences.md").read_text(encoding="utf-8"))
        self.assertIn("Existing user-owned content.", ui_page.read_text(encoding="utf-8"))

    def test_memory_candidates_reject_private_content(self):
        candidate = {"kind": "preference", "area": "general", "statement": f"Use {Path('/', 'Users', 'example', 'private-project')} as the source.", "evidence": "Explicit request.", "basis": "explicit_user_request", "confidence": "high", "source": "ending"}
        with self.assertRaises(ValueError):
            MEMORY.record_memory_candidates([candidate], events_path=self.store, preferences_root=self.case_root)

    def test_remove_invalid_accepts_exact_placeholder_event(self):
        MEMORY.record_event("GameOne", "combat.damage", "verification", "Verified damage path", "Exercise the runtime", "Focused checks pass", "passed", files=["src/combat.py"], events_path=self.store)
        event = MEMORY._read_events(self.store)[0]
        event.update({"summary": "tmp", "reason": "tmp", "result": "tmp", "module_changes": [{"module": "combat.damage", "summary": "tmp"}]})
        MEMORY._write_events([event], self.store)
        output = MEMORY.remove_invalid_event(event["event_id"], events_path=self.store)
        self.assertEqual(output["status"], "removed-invalid")
        self.assertEqual(MEMORY._read_events(self.store), [])

    def test_remove_invalid_rejects_valid_event(self):
        written = MEMORY.record_event("GameOne", "combat.damage", "verification", "Verified damage path", "Exercise the runtime", "Focused checks pass", "passed", files=["src/combat.py"], events_path=self.store)
        with self.assertRaises(ValueError):
            MEMORY.remove_invalid_event(written["event_id"], events_path=self.store)

    def test_remove_invalid_accepts_proven_semantic_duplicate(self):
        written = MEMORY.record_event("GameOne", "combat.damage", "verification", "Verified damage path", "Exercise the runtime", "Focused checks pass", "passed", files=["src/combat.py"], events_path=self.store)
        canonical = MEMORY._read_events(self.store)[0]
        duplicate = dict(canonical)
        duplicate.update({"event_id": "20260802T100000Z-abcdef123456", "recorded_at": "2026-08-02T10:00:00Z", "last_seen": "2026-08-02T10:00:00Z", "session_key": "2" * 24, "task_name": "different-provenance"})
        MEMORY._write_events([canonical, duplicate], self.store)
        output = MEMORY.remove_invalid_event(duplicate["event_id"], duplicate_of=written["event_id"], events_path=self.store)
        self.assertEqual(output["status"], "removed-invalid")
        self.assertEqual([event["event_id"] for event in MEMORY._read_events(self.store)], [written["event_id"]])

    def test_remove_invalid_rejects_event_referenced_by_superseding_result(self):
        written = MEMORY.record_event("GameOne", "combat.damage", "verification", "Verified damage path", "Exercise the runtime", "Focused checks pass", "passed", files=["src/combat.py"], events_path=self.store)
        target = MEMORY._read_events(self.store)[0]
        target.update({"summary": "tmp", "reason": "tmp", "result": "tmp", "module_changes": [{"module": "combat.damage", "summary": "tmp"}]})
        child = dict(target)
        child.update({"event_id": "20260802T100000Z-fedcba654321", "summary": "Replacement outcome", "reason": "Corrected invalid semantics", "result": "Focused checks pass", "module_changes": [{"module": "combat.damage", "summary": "Replacement outcome"}], "supersedes": written["event_id"]})
        MEMORY._write_events([target, child], self.store)
        with self.assertRaises(ValueError):
            MEMORY.remove_invalid_event(written["event_id"], events_path=self.store)


if __name__ == "__main__":
    unittest.main()
