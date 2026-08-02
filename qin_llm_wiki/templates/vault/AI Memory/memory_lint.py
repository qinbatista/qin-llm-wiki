#!/usr/bin/env python3
import argparse
import json
from collections import Counter
from pathlib import Path


REQUIRED_PROJECT_FILES = ("index.md", "Knowledge.md")
REQUIRED_EVENT_FIELDS = ("schema_version", "event_id", "recorded_at", "last_seen", "project", "record_kind", "event_type", "summary", "reason", "result", "verification_status", "module_changes", "files")
REQUIRED_ROOT_PATHS = ("Start Here.md", "AGENTS.md", "CLAUDE.md", "instruction.md", "Recent Work.md", "Memory Dashboard.md", "Issues.md", "Projects", "Preferences", "Knowledge", "Skills", "AI Memory")
REQUIRED_RUNTIME_FILES = ("AI Memory/ai_memory.py", "AI Memory/memory_lint.py", "AI Memory/tests/test_ai_memory.py", "AI Memory/events.jsonl")
FORBIDDEN_PATHS = ("_System", "raw", "Journal", "Archive", "LLM Wiki Home.md", "Untitled.canvas", "Knowledge/Activity Index.md", "Skills/Activity Index.md", "Projects/instruction.md")


def inspect_event_store(events_path):
    errors = []
    events = []
    if not events_path.exists():
        return events, ["Missing AI event store: AI Memory/events.jsonl"]
    event_ids = []
    issue_keys = []
    for line_number, line in enumerate(events_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            errors.append(f"AI event line {line_number}: invalid JSON: {error.msg}")
            continue
        missing_fields = [field_name for field_name in REQUIRED_EVENT_FIELDS if field_name not in event]
        if missing_fields:
            errors.append(f"AI event line {line_number}: missing {', '.join(missing_fields)}")
        module_changes = event.get("module_changes")
        if not isinstance(module_changes, list) or not module_changes or any(not isinstance(change, dict) or not change.get("module") or not change.get("summary") for change in module_changes):
            errors.append(f"AI event line {line_number}: invalid module_changes")
        event_ids.append(str(event.get("event_id", "")))
        if event.get("issue_id"):
            issue_keys.append((event.get("project"), event.get("issue_id")))
        events.append(event)
    duplicate_event_ids = [event_id for event_id, count in Counter(event_ids).items() if event_id and count > 1]
    duplicate_issue_keys = [f"{project}:{issue_id}" for (project, issue_id), count in Counter(issue_keys).items() if count > 1]
    if duplicate_event_ids:
        errors.append(f"Duplicate AI event IDs: {', '.join(sorted(duplicate_event_ids))}")
    if duplicate_issue_keys:
        errors.append(f"Duplicate issue lifecycle rows: {', '.join(sorted(duplicate_issue_keys))}")
    return events, errors


def inspect_vault(vault_path):
    errors = []
    for relative_path in REQUIRED_ROOT_PATHS:
        if not (vault_path / relative_path).exists():
            errors.append(f"Missing visible root entry: {relative_path}")
    for relative_path in REQUIRED_RUNTIME_FILES:
        if not (vault_path / relative_path).is_file():
            errors.append(f"Missing runtime file: {relative_path}")
    for relative_path in FORBIDDEN_PATHS:
        if (vault_path / relative_path).exists():
            errors.append(f"Forbidden legacy layer exists: {relative_path}")
    projects_path = vault_path / "Projects"
    projects_index_path = projects_path / "index.md"
    projects_index_text = projects_index_path.read_text(encoding="utf-8") if projects_index_path.exists() else ""
    project_names = sorted(project_path.name for project_path in projects_path.iterdir() if project_path.is_dir() and not project_path.name.startswith(".")) if projects_path.exists() else []
    for project_name in project_names:
        project_path = projects_path / project_name
        missing_files = [file_name for file_name in REQUIRED_PROJECT_FILES if not (project_path / file_name).is_file()]
        if missing_files:
            errors.append(f"{project_name}: missing {', '.join(missing_files)}")
        if f"[[Projects/{project_name}/index" not in projects_index_text:
            errors.append(f"{project_name}: missing from Projects/index.md")
        for legacy_name in ("History.md", "Activity Index.md", "instruction.md"):
            if (project_path / legacy_name).exists():
                errors.append(f"{project_name}: forbidden file exists: {legacy_name}")
    protocol_fragments = {"AGENTS.md": ("AI Memory/events.jsonl", "at most five compact events", "one event"), "CLAUDE.md": ("AGENTS.md", "AI Memory/ai_memory.py", "Do not create"), "instruction.md": ("AGENTS.md", "AI Memory/events.jsonl"), "Knowledge/Project Learning.md": ("One outcome, one event", "ACTIVE", "MONITORING", "RESOLVED")}
    for relative_path, fragments in protocol_fragments.items():
        text = (vault_path / relative_path).read_text(encoding="utf-8") if (vault_path / relative_path).exists() else ""
        for fragment in fragments:
            if fragment.lower() not in text.lower():
                errors.append(f"Missing protocol fragment in {relative_path}: {fragment}")
    generated_markers = {"Recent Work.md": "<!-- BEGIN AI MEMORY DAILY SUMMARY -->", "Memory Dashboard.md": "# Project Memory Dashboard", "Issues.md": "# Issues"}
    for relative_path, marker in generated_markers.items():
        if (vault_path / relative_path).exists() and marker not in (vault_path / relative_path).read_text(encoding="utf-8"):
            errors.append(f"Generated view is invalid: {relative_path}")
    events, event_errors = inspect_event_store(vault_path / "AI Memory" / "events.jsonl")
    errors.extend(event_errors)
    modules = {change.get("module") for event in events for change in event.get("module_changes", []) if isinstance(change, dict) and change.get("module")}
    projects = {event.get("project") for event in events}
    return {"status": "pass" if not errors else "fail", "vault": vault_path.name, "projects": len(project_names), "errors": errors, "ai_memory": {"events": len(events), "projects": len(projects), "modules": len(modules)}}


def main():
    parser = argparse.ArgumentParser(description="Validate the root-first LLM Wiki structure without modifying it.")
    parser.add_argument("--vault", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args()
    audit = inspect_vault(arguments.vault.expanduser().resolve())
    if arguments.json:
        print(json.dumps(audit, ensure_ascii=False, indent=2))
    else:
        print(f"LLM Wiki lint: {audit['status'].upper()} — {audit['projects']} project folders, {audit['ai_memory']['events']} events, {audit['ai_memory']['projects']} indexed projects, {audit['ai_memory']['modules']} modules, {len(audit['errors'])} errors")
        for error in audit["errors"]:
            print(f"ERROR: {error}")
    raise SystemExit(0 if audit["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
