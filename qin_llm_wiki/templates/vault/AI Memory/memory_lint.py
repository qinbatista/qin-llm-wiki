#!/usr/bin/env python3
import argparse
import json
import re
import unicodedata
from collections import Counter, deque
from pathlib import Path, PurePosixPath, PureWindowsPath


REQUIRED_PROJECT_FILES = ("index.md", "Knowledge.md")
REQUIRED_EVENT_FIELDS = ("schema_version", "event_id", "recorded_at", "last_seen", "project", "record_kind", "event_type", "summary", "reason", "result", "verification_status", "module_changes", "files")
REQUIRED_ROOT_PATHS = ("Start Here.md", "AGENTS.md", "CLAUDE.md", "GEMINI.md", "instruction.md", "Recent Work.md", "Memory Dashboard.md", "Issues.md", "Projects", "Preferences", "Knowledge", "Skills", "AI Memory")
REQUIRED_RUNTIME_FILES = ("AI Memory/ai_memory.py", "AI Memory/auto_classify.py", "AI Memory/memory_lint.py", "AI Memory/hidden_process.py", "AI Memory/tests/test_ai_memory.py", "AI Memory/tests/test_auto_classify.py", "AI Memory/tests/test_memory_lint.py", "AI Memory/tests/test_hidden_process.py", "AI Memory/events.jsonl")
REQUIRED_REUSABLE_LESSON_FILES = ("Knowledge/Reusable Lessons/index.md", "Knowledge/Reusable Lessons/Candidates.md", "Knowledge/Reusable Lessons/Memory and Process.md", "Knowledge/Reusable Lessons/Code Architecture.md", "Knowledge/Reusable Lessons/Game Architecture.md", "Knowledge/Reusable Lessons/UI and Interaction.md", "Knowledge/Reusable Lessons/Technology Decisions.md", "Knowledge/Reusable Lessons/Verification.md")
REQUIRED_BOOK_REFERENCE_FILES = ("Knowledge/Book References/index.md", "Knowledge/Book References/Unity and Game Development.md", "Knowledge/Book References/Computer Graphics and Shaders.md", "Knowledge/Book References/Programming and Software Engineering.md")
REQUIRED_OWNER_LINKS = (("Knowledge/index.md", "Knowledge/Reusable Lessons/index"), ("Knowledge/index.md", "Knowledge/Book References/index"), ("Knowledge/Reusable Lessons/index.md", "Knowledge/Reusable Lessons/Candidates"), ("Preferences/index.md", "Preferences/AI Captured Preferences"))
MANAGED_ROOTS = ("Projects", "Preferences", "Knowledge", "Skills", "AI Memory")
ROOT_ENTRY_FILES = ("Start Here.md", "AGENTS.md", "CLAUDE.md", "GEMINI.md", "instruction.md")
ALLOW_EMPTY_FILES = {"AI Memory/.lock", "AI Memory/events.jsonl"}
TEXT_SUFFIXES = {".md", ".py", ".json", ".jsonl", ".canvas", ".txt", ".yaml", ".yml"}
FORBIDDEN_PATHS = ("_System", "raw", "Journal", "Archive", "History", "LLM Wiki Home.md", "Knowledge/Activity Index.md", "Knowledge/instruction.md", "Skills/Activity Index.md", "Skills/instruction.md", "Projects/instruction.md")
STALE_FRAGMENTS = ("_System/ai_memory.py", "_System/AI Memory", "Journal/", "Archive/", "Activity Index.md", "History.md", "LLM Wiki Home")
LEGACY_OWNER_FRAGMENTS = ("event to History", "events to History", "evidence remains in History", "anchor in History", "project hub and History")
GHOST_FILE_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}
GHOST_DIRECTORY_NAMES = {"__pycache__", ".pytest_cache"}
GHOST_SUFFIXES = {".pyc", ".pyo"}
PLACEHOLDER_VALUES = {"tmp", "temp", "test", "dummy", "placeholder", "todo", "tbd", "n/a", "na", "none", "xxx"}
PLACEHOLDER_PAGE_TOKENS = {"tmp", "temp", "test", "dummy", "placeholder", "todo", "tbd", "na", "none", "xxx", "fixme"}
SCOPE_KEY_PATTERN = re.compile(r"^[0-9a-f]{24}$", re.IGNORECASE)
TASK_SCOPE_MODES = {"unscoped", "session", "task", "group", "session+task", "session+group", "task+group", "session+task+group"}
WIKILINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")
MARKDOWN_LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
MARKDOWN_LINK_WITH_LABEL_PATTERN = re.compile(r"(?<!!)\[([^\]]*)\]\([^)]+\)")
MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
FENCED_CODE_PATTERN = re.compile(r"```.*?```|~~~.*?~~~", re.DOTALL)
INLINE_CODE_PATTERN = re.compile(r"`[^`\n]*`")
SEMANTIC_EVENT_FIELDS = ("project", "working_line", "record_kind", "event_type", "summary", "reason", "result", "verification_status", "module_changes", "issue_id", "issue_status", "bug_class", "files", "verification", "decisions", "risks", "memory_candidates", "supersedes")
FORBIDDEN_EVENT_FIELDS = {"session_id", "thread_id", "task_name", "task_group", "raw_prompt", "raw_result", "reasoning", "chain_of_thought"}
SENSITIVE_PATTERNS = (re.compile(r"(?<![A-Za-z0-9_-])(?:sk|rk|pk)-[A-Za-z0-9_-]{12,}"), re.compile(r"(?:api[_ -]?key|secret|password|token|cookie|credential)\s*[:=]\s*[^\s,;]{8,}", re.IGNORECASE), re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), re.compile(r"https?://[^\s/:]+:[^\s/@]+@", re.IGNORECASE), re.compile(r"(?<![A-Za-z0-9])/(?:Users|home)/[^\s]+", re.IGNORECASE), re.compile(r"(?<![A-Za-z0-9])[A-Z]:\\Users\\[^\s]+", re.IGNORECASE), re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"))


def _relative(vault_path, path):
    return path.relative_to(vault_path).as_posix()


def _without_code(text):
    return INLINE_CODE_PATTERN.sub("", FENCED_CODE_PATTERN.sub("", text))


def _placeholder_token(value):
    return re.sub(r"[^a-z0-9/]+", "", str(value or "").strip().lower())


def _split_wikilink(target):
    target_value = target.replace(r"\|", "|").split("|", 1)[0].strip()
    path_part, separator, anchor = target_value.partition("#")
    return path_part.strip(), anchor.strip() if separator else ""


def _inside_vault(vault_path, candidate):
    try:
        candidate.resolve().relative_to(vault_path.resolve())
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _anchor_exists(path, anchor):
    if not anchor:
        return True
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    if anchor.startswith("^"):
        return re.search(rf"(?m)^\s*\^{re.escape(anchor[1:])}\s*$", text) is not None
    expected = re.sub(r"\s+", " ", anchor).strip().casefold()
    headings = [re.sub(r"\s+", " ", match.group(1)).strip().casefold() for match in re.finditer(r"(?m)^#{1,6}\s+(.+?)\s*#*\s*$", text)]
    return expected in headings


def resolve_wikilink_path(vault_path, source_path, target):
    target_path, anchor = _split_wikilink(target)
    if not target_path:
        return source_path if source_path.is_file() and _anchor_exists(source_path, anchor) else None
    raw_path = Path(target_path)
    if raw_path.is_absolute() or ".." in raw_path.parts:
        return None
    candidates = [vault_path / raw_path, source_path.parent / raw_path]
    candidates.extend([vault_path / f"{target_path}.md", source_path.parent / f"{target_path}.md"])
    if not target_path.lower().endswith(".md") and len(raw_path.parts) == 1:
        candidates.extend(sorted(vault_path.rglob(f"{raw_path.name}.md")))
    seen = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except (OSError, RuntimeError):
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if not _inside_vault(vault_path, candidate) or not candidate.is_file() or candidate.stat().st_size <= 0:
            continue
        try:
            candidate.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if _anchor_exists(candidate, anchor):
            return candidate
    return None


def current_markdown_paths(vault_path):
    return sorted(path for path in vault_path.rglob("*.md") if not any(part in {".git", ".obsidian", "Cache", "build", "dist"} for part in path.relative_to(vault_path).parts))


def historical_source_copy(vault_path, path):
    return "Legacy Codex Notes" in path.relative_to(vault_path).parts and path.name != "index.md"


def managed_file_paths(vault_path):
    paths = {path for path in vault_path.iterdir() if path.is_file() and path.name != ".obsidian"}
    for root_name in MANAGED_ROOTS:
        root = vault_path / root_name
        if root.exists():
            paths.update(path for path in root.rglob("*") if path.is_file() or path.is_symlink())
    return sorted(paths)


def _markdown_has_semantic_content(text):
    stripped = FENCED_CODE_PATTERN.sub("", text)
    stripped = re.sub(r"<!--.*?-->", "", stripped, flags=re.DOTALL)
    stripped = re.sub(r"(?m)^\s*#{1,6}.*$", "", stripped)
    stripped = WIKILINK_PATTERN.sub("", stripped)
    stripped = re.sub(r"(?m)^\s*[-*]\s*$", "", stripped)
    return bool(re.search(r"[\w\u4e00-\u9fff]", stripped))


def _normalized_markdown_semantics(text, preserve_wikilink_targets=True):
    normalized = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    normalized = re.sub(r"(?m)^\s*#\s+.*$", "", normalized, count=1)
    normalized = re.sub(r"(?m)^\s*(?:```|~~~)[^\n]*$", "", normalized)
    normalized = re.sub(r"`([^`\n]*)`", r"\1", normalized)
    normalized = MARKDOWN_IMAGE_PATTERN.sub("", normalized)
    normalized = MARKDOWN_LINK_WITH_LABEL_PATTERN.sub(r"\1", normalized)
    if preserve_wikilink_targets:
        normalized = WIKILINK_PATTERN.sub(lambda match: f" wikilink-target {match.group(1).split('|', 1)[0].strip()} ", normalized)
    else:
        normalized = WIKILINK_PATTERN.sub("", normalized)
    normalized = re.sub(r"(?m)^\s*#{1,6}\s*", "", normalized)
    normalized = re.sub(r"(?m)^\s*(?:[-*+]|\d+[.)]|>)\s*", "", normalized)
    normalized = unicodedata.normalize("NFKC", normalized).casefold()
    return re.sub(r"[^\w\u4e00-\u9fff]+", " ", normalized).strip()


def _markdown_is_placeholder_only(text):
    semantic_text = _normalized_markdown_semantics(text, preserve_wikilink_targets=False)
    tokens = semantic_text.split()
    return bool(tokens) and all(token in PLACEHOLDER_PAGE_TOKENS for token in tokens)


def inspect_path_hygiene(vault_path):
    errors = []
    for path in sorted(vault_path.rglob("*")):
        relative_parts = path.relative_to(vault_path).parts
        if any(part in {".git", ".obsidian"} for part in relative_parts):
            continue
        relative_path = _relative(vault_path, path)
        if path.parent == vault_path and re.fullmatch(r"(?:Recent Work|Issues|Memory Dashboard) \d+\.md", path.name):
            errors.append(f"Duplicate generated view remains: {relative_path}; review unique edits before removing the copy")
        malformed_part = next((part for part in relative_parts if "|" in part), "")
        if malformed_part:
            errors.append(f"Malformed path component contains '|': {relative_path}")
        if path.name in GHOST_FILE_NAMES or any(part in GHOST_DIRECTORY_NAMES for part in relative_parts) or path.suffix.lower() in GHOST_SUFFIXES:
            errors.append(f"Ghost artifact remains: {relative_path}")
        if re.fullmatch(r"untitled(?: \d+)?\.canvas", path.name, flags=re.IGNORECASE):
            errors.append(f"Ghost canvas remains: {relative_path}")
        if re.fullmatch(r"untitled.*\.md", path.name, flags=re.IGNORECASE):
            errors.append(f"Ghost Markdown remains: {relative_path}")
    return errors


def inspect_managed_file_access(vault_path):
    errors = []
    managed_files = managed_file_paths(vault_path)
    for path in managed_files:
        relative_path = _relative(vault_path, path)
        if path.is_symlink() and not _inside_vault(vault_path, path):
            errors.append(f"Managed symlink escapes vault: {relative_path}")
            continue
        try:
            size = path.stat().st_size
        except OSError as error:
            errors.append(f"Unreadable managed file {relative_path}: {error}")
            continue
        if size == 0:
            project_lock = path.name == ".memory.lock" and len(path.relative_to(vault_path).parts) == 3 and path.relative_to(vault_path).parts[0] == "Projects"
            if relative_path not in ALLOW_EMPTY_FILES and not project_lock:
                errors.append(f"Empty managed file: {relative_path}")
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            try:
                path.read_bytes()
            except OSError as error:
                errors.append(f"Unreadable managed file {relative_path}: {error}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            errors.append(f"Unreadable UTF-8 managed file {relative_path}: {error}")
            continue
        if not text.strip():
            errors.append(f"Blank managed file: {relative_path}")
        if path.suffix.lower() == ".md" and not _markdown_has_semantic_content(text):
            errors.append(f"Headings-only or navigation-only memory page: {relative_path}")
        elif path.suffix.lower() == ".md" and _markdown_is_placeholder_only(text):
            errors.append(f"Placeholder-only memory page: {relative_path}")
        if path.suffix.lower() in {".json", ".canvas"}:
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as error:
                errors.append(f"Invalid JSON managed file {relative_path}: {error.msg}")
            else:
                if path.suffix.lower() == ".canvas" and payload in ({}, []):
                    errors.append(f"Empty canvas payload: {relative_path}")
        elif path.suffix.lower() == ".jsonl" and relative_path != "AI Memory/events.jsonl":
            for line_number, line in enumerate(text.splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    json.loads(line)
                except json.JSONDecodeError as error:
                    errors.append(f"Invalid JSONL managed file {relative_path}:{line_number}: {error.msg}")
    return managed_files, errors


def _nonportable_destination(destination):
    value = destination.strip().strip("<>")
    lowered = value.lower()
    return lowered.startswith(("file:", "obsidian:", "vscode:")) or value.startswith(("/Users/", "/home/", "\\\\")) or re.match(r"^[A-Za-z]:[\\/]", value) is not None


def inspect_markdown_access(vault_path):
    errors = []
    for path in current_markdown_paths(vault_path):
        relative_path = _relative(vault_path, path)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            errors.append(f"Unreadable UTF-8 Markdown {relative_path}: {error}")
            continue
        inspectable_text = _without_code(text)
        for index, destination in enumerate(MARKDOWN_IMAGE_PATTERN.findall(inspectable_text)):
            if _nonportable_destination(destination):
                errors.append(f"Non-portable local image URI in {relative_path}: image[{index}]")
        for index, destination in enumerate(MARKDOWN_LINK_PATTERN.findall(inspectable_text)):
            if _nonportable_destination(destination):
                errors.append(f"Non-portable local URI in {relative_path}: link[{index}]")
        for index, raw_target in enumerate(WIKILINK_PATTERN.findall(inspectable_text)):
            if resolve_wikilink_path(vault_path, path, raw_target) is None:
                errors.append(f"Broken or inaccessible wikilink in {relative_path}: wikilink[{index}]")
    return errors


def inspect_markdown_semantic_duplicates(vault_path):
    grouped_paths = {}
    for path in current_markdown_paths(vault_path):
        try:
            semantic_text = _normalized_markdown_semantics(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError):
            continue
        if len(semantic_text) < 12 or len(semantic_text.split()) < 3:
            continue
        grouped_paths.setdefault(semantic_text, []).append(path)
    errors = []
    for paths in grouped_paths.values():
        if len(paths) > 1:
            errors.append(f"Semantic duplicate Markdown pages: {', '.join(_relative(vault_path, path) for path in sorted(paths))}")
    return errors


def inspect_markdown_reachability(vault_path):
    markdown_paths = set(current_markdown_paths(vault_path))
    queue = deque(vault_path / relative_path for relative_path in ROOT_ENTRY_FILES if (vault_path / relative_path).is_file())
    reachable = set(queue)
    while queue:
        source = queue.popleft()
        try:
            text = source.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for raw_target in WIKILINK_PATTERN.findall(_without_code(text)):
            target = resolve_wikilink_path(vault_path, source, raw_target)
            if target in markdown_paths and target not in reachable:
                reachable.add(target)
                queue.append(target)
    errors = [f"Unreachable memory page: {_relative(vault_path, path)}" for path in sorted(markdown_paths - reachable)]
    return reachable, errors


def _event_file_is_relative(value):
    normalized = str(value or "").strip().replace("\\", "/")
    windows_path = PureWindowsPath(normalized)
    return bool(normalized) and not PurePosixPath(normalized).is_absolute() and not windows_path.is_absolute() and not windows_path.drive and re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", normalized) is None and ".." not in PurePosixPath(normalized).parts


def _string_leaves(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from _string_leaves(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _string_leaves(child)
    elif isinstance(value, str):
        yield value


def _unique_json_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("JSON object contains duplicate keys")
        value[key] = item
    return value


def _normalize_working_line(value):
    if not isinstance(value, str) or not value.strip().startswith("{"):
        return value
    try:
        parsed = json.loads(value, object_pairs_hook=_unique_json_object)
        json.dumps(parsed, allow_nan=False)
    except (ValueError, RecursionError):
        return value
    return parsed if isinstance(parsed, dict) else value


def inspect_event_store(events_path):
    errors = []
    events = []
    if not events_path.exists():
        return events, ["Missing AI event store: AI Memory/events.jsonl"]
    try:
        lines = events_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        return events, [f"Unreadable AI event store: {error}"]
    event_ids = []
    semantic_payloads = []
    issue_groups = {}
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            errors.append(f"AI event line {line_number}: invalid JSON: {error.msg}")
            continue
        if not isinstance(event, dict):
            errors.append(f"AI event line {line_number}: event must be an object")
            continue
        missing_fields = [field_name for field_name in REQUIRED_EVENT_FIELDS if field_name not in event]
        if missing_fields:
            errors.append(f"AI event line {line_number}: missing {', '.join(missing_fields)}")
        forbidden_fields = sorted(FORBIDDEN_EVENT_FIELDS.intersection(event))
        if forbidden_fields:
            errors.append(f"AI event line {line_number}: forbidden private fields {', '.join(forbidden_fields)}")
        for field_name in ("summary", "reason", "result"):
            if _placeholder_token(event.get(field_name)) in PLACEHOLDER_VALUES:
                errors.append(f"AI event line {line_number}: placeholder {field_name} is forbidden")
        module_changes = event.get("module_changes")
        if not isinstance(module_changes, list) or not module_changes or any(not isinstance(change, dict) or not change.get("module") or not change.get("summary") for change in module_changes):
            errors.append(f"AI event line {line_number}: module_changes must contain module and summary")
        else:
            for index, change in enumerate(module_changes):
                if _placeholder_token(change.get("summary")) in PLACEHOLDER_VALUES:
                    errors.append(f"AI event line {line_number}: placeholder module_changes[{index}].summary is forbidden")
        for index, candidate in enumerate(event.get("memory_candidates") or []):
            if not isinstance(candidate, dict):
                errors.append(f"AI event line {line_number}: memory_candidates[{index}] must be an object")
                continue
            for field_name in ("statement", "evidence"):
                if _placeholder_token(candidate.get(field_name)) in PLACEHOLDER_VALUES:
                    errors.append(f"AI event line {line_number}: placeholder memory_candidates[{index}].{field_name} is forbidden")
        for index, file_value in enumerate(event.get("files") or []):
            if not _event_file_is_relative(file_value):
                errors.append(f"AI event line {line_number}: files[{index}] is not project-relative")
        # Imported outcome events may describe a fix without an issue lifecycle.
        if event.get("record_kind") == "issue" and not event.get("issue_id"):
            errors.append(f"AI event line {line_number}: issue record requires a stable issue_id")
        if event.get("issue_status") and not event.get("issue_id"):
            errors.append(f"AI event line {line_number}: issue_status requires issue_id")
        scope_fields = {key: event.get(key, "") for key in ("session_key", "task_scope_key", "task_group_key", "task_scope_mode")}
        if any(scope_fields.values()):
            for field_name in ("session_key", "task_scope_key", "task_group_key"):
                if scope_fields[field_name] and not SCOPE_KEY_PATTERN.fullmatch(str(scope_fields[field_name])):
                    errors.append(f"AI event line {line_number}: {field_name} is not a 24-character hash")
            if scope_fields["task_scope_mode"] not in TASK_SCOPE_MODES:
                errors.append(f"AI event line {line_number}: task_scope_mode is invalid")
        semantic_payload = {field_name: event.get(field_name) for field_name in SEMANTIC_EVENT_FIELDS}
        if any(pattern.search(value) for value in _string_leaves(semantic_payload) for pattern in SENSITIVE_PATTERNS):
            errors.append(f"AI event line {line_number}: private or secret-like content is forbidden")
        semantic_payload["project"] = str(semantic_payload.get("project") or "").strip().casefold()
        semantic_payload["working_line"] = _normalize_working_line(semantic_payload.get("working_line"))
        semantic_payloads.append(json.dumps(semantic_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        event_ids.append(str(event.get("event_id", "")).lower())
        if event.get("issue_id"):
            issue_key = (str(event.get("project") or "").strip().casefold(), str(event.get("issue_id")))
            issue_groups.setdefault(issue_key, []).append(event)
        events.append(event)
    duplicate_ids = [event_id for event_id, count in Counter(event_ids).items() if event_id and count > 1]
    if duplicate_ids:
        errors.append(f"Duplicate AI event IDs: {', '.join(sorted(duplicate_ids)[:10])}")
    for payload, count in Counter(semantic_payloads).items():
        if count <= 1:
            continue
        duplicate_events = [event.get("event_id", "") for event, candidate in zip(events, semantic_payloads) if candidate == payload]
        errors.append(f"Semantic duplicate AI events: {', '.join(duplicate_events)}")
    for (project, issue_id), revisions in issue_groups.items():
        if len(revisions) < 2:
            continue
        by_identifier = {event.get("event_id"): event for event in revisions}
        predecessors = [event.get("supersedes") for event in revisions if event.get("supersedes") in by_identifier]
        heads = [identifier for identifier in by_identifier if identifier not in predecessors]
        visited = set()
        cursor = heads[0] if len(heads) == 1 else None
        while cursor in by_identifier and cursor not in visited:
            visited.add(cursor)
            cursor = by_identifier[cursor].get("supersedes")
        if len(predecessors) != len(revisions) - 1 or len(set(predecessors)) != len(predecessors) or len(visited) != len(revisions):
            errors.append(f"Invalid issue revision chain: {project}:{issue_id}")
    return events, errors


def inspect_vault(vault_path):
    root = Path(vault_path).expanduser().resolve()
    errors = []
    warnings = []
    for relative_path in REQUIRED_ROOT_PATHS:
        if not (root / relative_path).exists():
            errors.append(f"Missing visible root entry: {relative_path}")
    for label, required_files in (("AI memory runtime", REQUIRED_RUNTIME_FILES), ("reusable lesson structure", REQUIRED_REUSABLE_LESSON_FILES), ("external book reference", REQUIRED_BOOK_REFERENCE_FILES)):
        for relative_path in required_files:
            if not (root / relative_path).is_file():
                errors.append(f"Missing {label} file: {relative_path}")
    for owner_path, target in REQUIRED_OWNER_LINKS:
        path = root / owner_path
        if path.is_file() and f"[[{target}" not in path.read_text(encoding="utf-8"):
            errors.append(f"Missing owner navigation link in {owner_path}: {target}")
    for relative_path in FORBIDDEN_PATHS:
        if (root / relative_path).exists():
            errors.append(f"Legacy clutter remains: {relative_path}")
    projects_path = root / "Projects"
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
                errors.append(f"{project_name}: legacy file remains: {legacy_name}")
    protocol_fragments = {"AGENTS.md": ("AI Memory/events.jsonl", "AI Memory/ai_memory.py recall", "user-selected model", "Ending only", "--all-projects"), "CLAUDE.md": ("AGENTS",), "GEMINI.md": ("AGENTS",), "instruction.md": ("AGENTS",)}
    for relative_path, fragments in protocol_fragments.items():
        path = root / relative_path
        if not path.is_file():
            errors.append(f"Missing required protocol file: {relative_path}")
            continue
        text = path.read_text(encoding="utf-8")
        for fragment in fragments:
            if fragment.casefold() not in text.casefold():
                errors.append(f"Missing protocol fragment in {relative_path}: {fragment}")
    for path in current_markdown_paths(root):
        relative_path = _relative(root, path)
        if relative_path in {"Memory Dashboard.md", "Recent Work.md", "Issues.md"} or historical_source_copy(root, path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for fragment in STALE_FRAGMENTS:
            if fragment in text:
                errors.append(f"Stale structure reference in {relative_path}: {fragment}")
        for fragment in LEGACY_OWNER_FRAGMENTS:
            if fragment.casefold() in text.casefold():
                errors.append(f"Legacy chronology owner in {relative_path}: {fragment}")
    errors.extend(inspect_path_hygiene(root))
    managed_files, file_errors = inspect_managed_file_access(root)
    errors.extend(file_errors)
    errors.extend(inspect_markdown_access(root))
    errors.extend(inspect_markdown_semantic_duplicates(root))
    reachable, reachability_errors = inspect_markdown_reachability(root)
    errors.extend(reachability_errors)
    for relative_path in (".obsidian/workspace.json", ".obsidian/workspace-mobile.json"):
        workspace_path = root / relative_path
        if not workspace_path.exists():
            continue
        workspace_text = workspace_path.read_text(encoding="utf-8", errors="replace")
        for fragment in ("_System/", "Journal/", "Archive/", "raw/"):
            if fragment in workspace_text:
                warnings.append(f"Stale workspace reference in {relative_path}: {fragment} (UI state was not modified)")
    generated_markers = {"Recent Work.md": "<!-- BEGIN AI MEMORY DAILY SUMMARY -->", "Memory Dashboard.md": "# Project Memory Dashboard", "Issues.md": "# Issues"}
    for relative_path, marker in generated_markers.items():
        path = root / relative_path
        if path.exists() and marker not in path.read_text(encoding="utf-8"):
            errors.append(f"Generated view is invalid: {relative_path}")
    events, event_errors = inspect_event_store(root / "AI Memory" / "events.jsonl")
    errors.extend(event_errors)
    candidates_path = root / "Knowledge" / "Reusable Lessons" / "Candidates.md"
    if candidates_path.is_file() and re.search(r"(?mi)^### .* — (?:tmp|temp|test|dummy|placeholder|todo|tbd|n/a|none)\s*$", candidates_path.read_text(encoding="utf-8")):
        errors.append("Auto-classified placeholder lesson remains in Knowledge/Reusable Lessons/Candidates.md")
    modules = {change.get("module") for event in events for change in event.get("module_changes", []) if isinstance(change, dict) and change.get("module")}
    indexed_projects = {str(event.get("project") or "").strip().casefold() for event in events if event.get("project")}
    return {"status": "pass" if not errors else "fail", "vault": root.name, "projects": len(project_names), "managed_files": len(managed_files), "reachable_pages": len(reachable), "errors": errors, "warnings": warnings, "ai_memory": {"events": len(events), "projects": len(indexed_projects), "modules": len(modules)}}


def main():
    parser = argparse.ArgumentParser(description="Validate a visible root-first LLM Wiki without modifying it.")
    parser.add_argument("--vault", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args()
    audit = inspect_vault(arguments.vault.expanduser().resolve())
    if arguments.json:
        print(json.dumps(audit, ensure_ascii=False, indent=2))
    else:
        print(f"LLM Wiki lint: {audit['status'].upper()} — {audit['projects']} project folders, {audit['managed_files']} managed files, {audit['reachable_pages']} reachable pages, {audit['ai_memory']['events']} events, {audit['ai_memory']['projects']} indexed projects, {audit['ai_memory']['modules']} modules, {len(audit['errors'])} errors, {len(audit['warnings'])} warnings")
        for error in audit["errors"]:
            print(f"ERROR: {error}")
        for warning in audit["warnings"]:
            print(f"WARNING: {warning}")
    raise SystemExit(0 if audit["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
