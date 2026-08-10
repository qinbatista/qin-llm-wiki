#!/usr/bin/env python3
import argparse
import hashlib
import importlib.util
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath

if os.name == "nt":
    import msvcrt
elif os.name == "posix":
    import fcntl
else:
    raise RuntimeError(f"Unsupported host OS for AI memory locking: {os.name}")


VAULT_ROOT = Path(__file__).resolve().parents[1]
MEMORY_ROOT = Path(__file__).resolve().parent
EVENTS_PATH = MEMORY_ROOT / "events.jsonl"
RECENT_WORK_PATH = VAULT_ROOT / "Recent Work.md"
DASHBOARD_PATH = VAULT_ROOT / "Memory Dashboard.md"
ISSUES_PATH = VAULT_ROOT / "Issues.md"
SCHEMA_VERSION = 2
EVENT_TYPES = ("feature", "bug-fix", "refactor", "architecture", "operation", "preference", "new-module", "documentation", "verification", "general")
VERIFICATION_STATUSES = ("passed", "partial", "failed", "not-run")
ISSUE_STATUSES = ("ACTIVE", "MONITORING", "RESOLVED", "ARCHIVED")
AUTO_CLASSIFIER_PATH = MEMORY_ROOT / "auto_classify.py"
SESSION_ID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
SCOPE_KEY_PATTERN = re.compile(r"^[0-9a-f]{24}$", re.IGNORECASE)
EVENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
TASK_NAME_MAX_LENGTH = 96
PLACEHOLDER_VALUES = {"tmp", "temp", "test", "dummy", "placeholder", "todo", "tbd", "n/a", "na", "none", "xxx"}
SEMANTIC_EVENT_FIELDS = ("project", "working_line", "record_kind", "event_type", "summary", "reason", "result", "verification_status", "module_changes", "issue_id", "issue_status", "bug_class", "files", "verification", "decisions", "risks", "memory_candidates", "supersedes")
REDACTABLE_EVENT_FIELDS = tuple(field_name for field_name in SEMANTIC_EVENT_FIELDS if field_name != "files")
PRIVATE_REDACTION = "[private data omitted]"
MEMORY_CANDIDATE_KINDS = ("preference", "technical-trait")
MEMORY_CANDIDATE_AREAS = ("ui", "workflow", "technical", "general")
MEMORY_CANDIDATE_BASES = ("explicit_user_request", "repeated_user_correction", "verified_work_pattern")
MEMORY_CANDIDATE_CONFIDENCE = ("high", "medium")
MEMORY_BLOCK_START = "<!-- BEGIN CODEX CAPTURED PREFERENCES -->"
MEMORY_BLOCK_END = "<!-- END CODEX CAPTURED PREFERENCES -->"
MEMORY_SENSITIVE_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9_-])(?:sk|rk|pk)-[A-Za-z0-9_-]{12,}"),
    re.compile(r"(?:api[_ -]?key|secret|password|token|cookie|credential)\s*[:=]\s*[^\s,;]{8,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"https?://[^\s/:]+:[^\s/@]+@", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9])/(?:Users|home)/[^\s]+", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9])[A-Z]:\\Users\\[^\s]+", re.IGNORECASE),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
)


def _normalize_task_name(value):
    raw_value = re.sub(r"\s+", " ", str(value or "")).strip()
    if not raw_value:
        return ""
    normalized = raw_value.lower()
    normalized = re.sub(r"(?:sk-[a-z0-9_-]{8,}|/(?:users|home)/[^ ]+|[a-z]:\\[^ ]+)", "private", normalized, flags=re.IGNORECASE)
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")[:TASK_NAME_MAX_LENGTH]
    return slug or f"task-{hashlib.sha256(raw_value.encode('utf-8')).hexdigest()[:12]}"


def _session_key(value):
    normalized = str(value or "").strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24] if SESSION_ID_PATTERN.fullmatch(normalized) else ""


def _normalize_scope_key(value):
    normalized = str(value or "").strip().lower()
    return normalized if SCOPE_KEY_PATTERN.fullmatch(normalized) else ""


def _task_scope_key(project, module, task_name):
    payload = "|".join((str(project or "").strip().lower(), "project-result", str(module or "").strip().lower(), str(task_name or "").strip().lower()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24] if task_name else ""


def _task_group_key(project, task_group="", task_name=""):
    relation_name = task_group or task_name
    if not str(relation_name or "").strip():
        return ""
    normalized = _normalize_task_name(relation_name)
    return hashlib.sha256(f"{str(project or '').strip().lower()}|task-group|{normalized}".encode("utf-8")).hexdigest()[:24]


def _scope_mode(session_key="", task_scope_key="", task_group_key=""):
    return "session+task+group" if session_key and task_scope_key and task_group_key else "session+task" if session_key and task_scope_key else "session+group" if session_key and task_group_key else "session" if session_key else "task+group" if task_scope_key and task_group_key else "task" if task_scope_key else "group" if task_group_key else "unscoped"


def _scope_context(project, module, task_name="", session_id="", session_key="", task_scope_key="", task_group="", task_group_key=""):
    active_task_name = task_name or os.environ.get("LLM_WIKI_TASK_NAME", "")
    active_task_group = task_group or os.environ.get("LLM_WIKI_TASK_GROUP", "")
    active_session_id = session_id or os.environ.get("LLM_WIKI_SESSION_ID", "")
    normalized_task_name = _normalize_task_name(active_task_name)
    normalized_task_group = _normalize_task_name(active_task_group) if str(active_task_group or "").strip() else ""
    normalized_session_key = _session_key(active_session_id) or _normalize_scope_key(session_key)
    normalized_scope_key = _normalize_scope_key(task_scope_key) or _task_scope_key(project, module, normalized_task_name)
    normalized_group_key = _normalize_scope_key(task_group_key) or _task_group_key(project, normalized_task_group, normalized_task_name)
    return {"session_key": normalized_session_key, "task_scope_key": normalized_scope_key, "task_group_key": normalized_group_key, "task_scope_mode": _scope_mode(normalized_session_key, normalized_scope_key, normalized_group_key)}


def _event_scope_relation(event, scope):
    active_session_key = str(scope.get("session_key") or "")
    active_task_scope = str(scope.get("task_scope_key") or "")
    active_group_key = str(scope.get("task_group_key") or "")
    event_session_key = str(event.get("session_key") or "")
    event_task_scope = str(event.get("task_scope_key") or "")
    event_group_key = str(event.get("task_group_key") or "")
    if not (active_session_key or active_task_scope or active_group_key):
        return "unscoped_query"
    same_session = bool(active_session_key and event_session_key == active_session_key)
    if active_task_scope and event_task_scope == active_task_scope:
        return "same_session_task" if same_session else "related_task_scope"
    if active_group_key and event_group_key == active_group_key:
        return "same_session_task_group" if same_session else "related_task_group"
    if same_session and not (active_task_scope or active_group_key):
        return "same_session"
    return "unrelated_session"


def _confined_write_path(vault_root, candidate_path, field_name):
    root = Path(vault_root).expanduser().resolve()
    candidate = Path(os.path.abspath(os.fspath(Path(candidate_path).expanduser())))
    try:
        relative_path = candidate.relative_to(root)
    except ValueError as error:
        raise ValueError(f"{field_name} must stay inside the vault") from error
    current_path = root
    for part in relative_path.parts:
        current_path /= part
        if current_path.is_symlink():
            raise ValueError(f"{field_name} must not use a symlink")
    try:
        candidate.resolve(strict=False).relative_to(root)
    except (OSError, RuntimeError, ValueError) as error:
        raise ValueError(f"{field_name} must stay inside the vault") from error
    return candidate


def _write_confined_text(vault_root, candidate_path, text, field_name):
    path = _confined_write_path(vault_root, candidate_path, field_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending_path = _confined_write_path(vault_root, path.with_name(path.name + ".pending"), f"{field_name} pending file")
    pending_path.write_text(text, encoding="utf-8")
    pending_path.replace(path)


def _migrate_event_provenance(event):
    changed = False
    for field_name in ("session_key", "task_scope_key", "task_group_key"):
        value = str(event.get(field_name) or "").strip().lower()
        if value and not SCOPE_KEY_PATTERN.fullmatch(value):
            raise ValueError(f"legacy {field_name} is not a 24-character hash")
        if event.get(field_name, "") != value:
            event[field_name] = value
            changed = True
    legacy_session_id = str(event.get("session_id") or "").strip()
    if legacy_session_id and not event.get("session_key"):
        session_key = _session_key(legacy_session_id)
        if not session_key:
            raise ValueError("legacy session_id is not a supported UUID")
        event["session_key"] = session_key
        changed = True
    task_name = str(event.get("task_name") or "").strip()
    task_group = str(event.get("task_group") or "").strip()
    if task_name and not event.get("task_scope_key"):
        primary_module = next((str(change.get("module") or "").strip() for change in event.get("module_changes", []) if isinstance(change, dict) and change.get("module")), "")
        if not primary_module:
            raise ValueError("legacy task_name requires a module before it can be removed")
        event["task_scope_key"] = _task_scope_key(event.get("project", ""), primary_module, _normalize_task_name(task_name))
        changed = True
    if (task_group or task_name) and not event.get("task_group_key"):
        event["task_group_key"] = _task_group_key(event.get("project", ""), _normalize_task_name(task_group), _normalize_task_name(task_name))
        changed = True
    for field_name in ("session_id", "task_name", "task_group"):
        if field_name in event:
            event.pop(field_name)
            changed = True
    scope_mode = _scope_mode(event.get("session_key", ""), event.get("task_scope_key", ""), event.get("task_group_key", ""))
    if event.get("task_scope_mode") != scope_mode:
        event["task_scope_mode"] = scope_mode
        changed = True
    return changed


def _lock(lock_handle):
    if os.name == "nt":
        lock_handle.seek(0, os.SEEK_END)
        if lock_handle.tell() == 0:
            lock_handle.write("\0")
            lock_handle.flush()
        lock_handle.seek(0)
        msvcrt.locking(lock_handle.fileno(), msvcrt.LK_LOCK, 1)
    else:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)


def _single_line(value, field_name, required=True, max_length=1200):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if required and not text:
        raise ValueError(f"{field_name} is required")
    home_markers = ("/" + "Users/", "C:" + "\\Users\\")
    if any(marker.lower() in text.lower() for marker in home_markers):
        raise ValueError(f"{field_name} must not contain a user home path")
    return text[:max_length]


def _brief(value, max_length=90):
    text = _single_line(value, "brief", required=False, max_length=max_length)
    return text if len(str(value or "").strip()) <= max_length else text.rstrip() + "…"


def _normalize_recorded_at(value):
    raw_value = str(value or "").strip()
    if not raw_value:
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    parseable_value = raw_value[:-1] + "+00:00" if raw_value.endswith(("Z", "z")) else raw_value
    try:
        parsed_value = datetime.fromisoformat(parseable_value)
    except ValueError as error:
        raise ValueError("recorded-at must be a valid ISO 8601 UTC timestamp") from error
    if parsed_value.tzinfo is None or parsed_value.utcoffset() != timedelta(0):
        raise ValueError("recorded-at must include the UTC timezone")
    return parsed_value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _placeholder_token(value):
    return re.sub(r"[^a-z0-9/]+", "", str(value or "").strip().lower())


def _placeholder_fields(event):
    values = [("summary", event.get("summary")), ("reason", event.get("reason")), ("result", event.get("result"))]
    values.extend((f"module_changes[{index}].summary", change.get("summary")) for index, change in enumerate(event.get("module_changes") or []) if isinstance(change, dict))
    return [field_name for field_name, value in values if _placeholder_token(value) in PLACEHOLDER_VALUES]


def _validate_event_semantics(event):
    placeholder_fields = _placeholder_fields(event)
    if placeholder_fields:
        raise ValueError(f"placeholder memory content is forbidden: {', '.join(placeholder_fields)}")
    semantic_values = []
    pending_values = list(_semantic_event_payload(event).values())
    while pending_values:
        value = pending_values.pop()
        if isinstance(value, dict):
            pending_values.extend(value.values())
        elif isinstance(value, (list, tuple)):
            pending_values.extend(value)
        elif value is not None:
            semantic_values.append(str(value))
    if any(pattern.search(value) for value in semantic_values for pattern in MEMORY_SENSITIVE_PATTERNS):
        raise ValueError("memory event contains private or secret-like content")


def _semantic_event_payload(event):
    payload = {field_name: event.get(field_name) for field_name in SEMANTIC_EVENT_FIELDS}
    payload["project"] = str(payload.get("project") or "").strip().casefold()
    return payload


def _read_events(events_path=EVENTS_PATH):
    path = Path(events_path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_events(events, events_path=EVENTS_PATH):
    path = Path(events_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending_path = path.with_name(path.name + ".pending")
    if path.is_symlink() or pending_path.is_symlink():
        raise ValueError("event store and pending file must not be symlinks")
    pending_path.write_text("".join(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n" for event in events), encoding="utf-8")
    pending_path.replace(path)


def _with_path_lock(lock_path, operation):
    path = Path(lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("memory lock file must not be a symlink")
    with path.open("a", encoding="utf-8") as lock_handle:
        _lock(lock_handle)
        return operation()


def _with_store_lock(events_path, operation):
    path = Path(events_path)
    return _with_path_lock(path.parent / ".lock", lambda: operation(_read_events(path)))


def _run_auto_classification(events_path):
    if Path(events_path).resolve() != EVENTS_PATH.resolve():
        return {"status": "skipped", "reason": "non-default-store"}
    try:
        specification = importlib.util.spec_from_file_location("llm_wiki_auto_classify", AUTO_CLASSIFIER_PATH)
        if specification is None or specification.loader is None:
            return {"status": "failed", "reason": "classifier-module-unavailable"}
        classifier = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(classifier)
        projection_paths = [classifier.CANDIDATE_PATH, *classifier.TAXONOMY_PATHS.values()]
        for relative_path in projection_paths:
            _confined_write_path(VAULT_ROOT, Path(VAULT_ROOT) / relative_path, "auto-classification owner path")
        return classifier.sync_catalog(VAULT_ROOT, EVENTS_PATH, apply=True)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return {"status": "failed", "reason": f"{type(error).__name__}: {error}"}


def _normalize_files(files):
    normalized = []
    for value in files or []:
        file_path = str(value).strip().replace("\\", "/")
        if not file_path:
            continue
        windows_path = PureWindowsPath(file_path)
        if PurePosixPath(file_path).is_absolute() or windows_path.is_absolute() or windows_path.drive or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", file_path) or ".." in PurePosixPath(file_path).parts:
            raise ValueError("files must be project-relative paths")
        if file_path not in normalized:
            normalized.append(file_path)
    return normalized


def _module_changes(primary_module, summary, values):
    changes = []
    for value in values or []:
        if "=" not in value:
            raise ValueError("module-change must use MODULE=SUMMARY")
        module, module_summary = value.split("=", 1)
        change = {"module": _single_line(module, "module-change module", max_length=160), "summary": _single_line(module_summary, "module-change summary", max_length=600)}
        if change not in changes:
            changes.append(change)
    if not changes:
        changes.append({"module": primary_module, "summary": summary})
    elif primary_module not in [change["module"] for change in changes]:
        changes.insert(0, {"module": primary_module, "summary": summary})
    return changes


def _memory_text(value, field_name, max_length=280):
    text = _single_line(value, field_name, max_length=max_length)
    if _placeholder_token(text) in PLACEHOLDER_VALUES:
        raise ValueError(f"{field_name} must not be placeholder content")
    if any(pattern.search(text) for pattern in MEMORY_SENSITIVE_PATTERNS):
        raise ValueError(f"{field_name} contains private or secret-like content")
    if "```" in text or "[MEMORY_CANDIDATE]" in text:
        raise ValueError(f"{field_name} must be a compact statement, not a raw prompt marker")
    return text


def _normalize_memory_candidate(candidate):
    if not isinstance(candidate, dict):
        raise ValueError("memory candidate must be an object")
    allowed = {"kind", "area", "statement", "evidence", "basis", "confidence", "source"}
    unexpected = sorted(set(candidate) - allowed)
    if unexpected:
        raise ValueError(f"memory candidate contains unsupported fields: {', '.join(unexpected)}")
    kind = _single_line(candidate.get("kind"), "memory candidate kind", max_length=40)
    area = _single_line(candidate.get("area"), "memory candidate area", max_length=40)
    basis = _single_line(candidate.get("basis"), "memory candidate basis", max_length=80)
    confidence = _single_line(candidate.get("confidence"), "memory candidate confidence", max_length=20)
    source = _single_line(candidate.get("source", "ending"), "memory candidate source", max_length=20)
    if kind not in MEMORY_CANDIDATE_KINDS:
        raise ValueError(f"memory candidate kind must be one of {', '.join(MEMORY_CANDIDATE_KINDS)}")
    if area not in MEMORY_CANDIDATE_AREAS:
        raise ValueError(f"memory candidate area must be one of {', '.join(MEMORY_CANDIDATE_AREAS)}")
    if basis not in MEMORY_CANDIDATE_BASES:
        raise ValueError(f"memory candidate basis must be one of {', '.join(MEMORY_CANDIDATE_BASES)}")
    if confidence not in MEMORY_CANDIDATE_CONFIDENCE:
        raise ValueError(f"memory candidate confidence must be one of {', '.join(MEMORY_CANDIDATE_CONFIDENCE)}")
    if source != "ending":
        raise ValueError("memory candidate source must be ending")
    return {
        "kind": kind,
        "area": area,
        "statement": _memory_text(candidate.get("statement"), "memory candidate statement"),
        "evidence": _memory_text(candidate.get("evidence"), "memory candidate evidence"),
        "basis": basis,
        "confidence": confidence,
        "source": source,
    }


def _normalize_memory_candidates(candidates):
    if candidates is None:
        return []
    if not isinstance(candidates, list):
        raise ValueError("memory candidates must be a list")
    if len(candidates) > 8:
        raise ValueError("memory candidates may contain at most 8 items")
    normalized = []
    seen = set()
    for candidate in candidates:
        value = _normalize_memory_candidate(candidate)
        key = (value["kind"], value["area"], value["statement"].casefold())
        if key in seen:
            raise ValueError("memory candidates must not contain duplicate statements")
        seen.add(key)
        normalized.append(value)
    return normalized


def _fingerprint(event):
    payload = _semantic_event_payload(event)
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _redact_private_value(value):
    if isinstance(value, str):
        redacted_value = value
        for pattern in MEMORY_SENSITIVE_PATTERNS:
            redacted_value = pattern.sub(PRIVATE_REDACTION, redacted_value)
        return redacted_value, redacted_value != value
    if isinstance(value, list):
        redacted_values = []
        changed = False
        for nested_value in value:
            redacted_value, nested_changed = _redact_private_value(nested_value)
            redacted_values.append(redacted_value)
            changed = changed or nested_changed
        return redacted_values, changed
    if isinstance(value, dict):
        redacted_values = {}
        changed = False
        for key, nested_value in value.items():
            redacted_value, nested_changed = _redact_private_value(nested_value)
            redacted_values[key] = redacted_value
            changed = changed or nested_changed
        return redacted_values, changed
    return value, False


def _issue_status_for_verification(verification_status):
    return {"passed": "RESOLVED", "partial": "MONITORING", "failed": "ACTIVE", "not-run": "MONITORING"}[verification_status]


def add_project(project, vault_root=VAULT_ROOT):
    project_name = _single_line(project, "project", max_length=160)
    if "/" in project_name or "\\" in project_name or project_name in {".", ".."}:
        raise ValueError("project must be one folder-safe name")
    if any(pattern.search(project_name) for pattern in MEMORY_SENSITIVE_PATTERNS):
        raise ValueError("project contains private or secret-like content")
    root = Path(vault_root).expanduser().resolve()
    project_path = _confined_write_path(root, root / "Projects" / project_name, "project owner directory")
    index_path = _confined_write_path(root, project_path / "index.md", "project index")
    knowledge_path = _confined_write_path(root, project_path / "Knowledge.md", "project knowledge")
    projects_index_path = _confined_write_path(root, root / "Projects" / "index.md", "projects index")
    lock_path = _confined_write_path(root, root / "AI Memory" / ".lock", "vault owner lock")

    def operation():
        project_path.mkdir(parents=True, exist_ok=True)
        if not index_path.exists():
            _write_confined_text(root, index_path, f"# {project_name}\n\nThis project owner links the current project rules and stable module knowledge.\n\n- [[Projects/{project_name}/Knowledge|Knowledge]]\n- [[Projects/index|Projects]]\n- [[Start Here|Home]]\n", "project index")
        if not knowledge_path.exists():
            _write_confined_text(root, knowledge_path, f"# {project_name} Knowledge\n\n## Current project rules\n\nAdd current module truth here. Chronology belongs only in `AI Memory/events.jsonl`.\n", "project knowledge")
        projects_index_text = projects_index_path.read_text(encoding="utf-8") if projects_index_path.exists() else "# Projects\n"
        link = f"- [[Projects/{project_name}/index|{project_name}]]"
        if link not in projects_index_text:
            _write_confined_text(root, projects_index_path, projects_index_text.rstrip() + "\n\n" + link + "\n", "projects index")
        return {"status": "written", "project": project_name, "path": f"Projects/{project_name}"}

    return _with_path_lock(lock_path, operation)


def record_event(project, module, event_type, summary, reason, result, verification_status, module_change_values=None, working_line="", issue_id="", issue_status="", bug_class="", files=None, verification=None, decisions=None, risks=None, recorded_at="", events_path=EVENTS_PATH, memory_candidates=None, task_name="", session_id="", session_key="", task_scope_key="", task_group="", task_group_key=""):
    timestamp = _normalize_recorded_at(recorded_at)
    primary_module = _single_line(module, "module", max_length=160)
    normalized_summary = _single_line(summary, "summary")
    normalized_issue_id = _single_line(issue_id, "issue-id", required=False, max_length=160)
    normalized_issue_status = _single_line(issue_status, "issue-status", required=False, max_length=20).upper()
    if event_type not in EVENT_TYPES:
        raise ValueError(f"event-type must be one of {', '.join(EVENT_TYPES)}")
    if verification_status not in VERIFICATION_STATUSES:
        raise ValueError(f"verification-status must be one of {', '.join(VERIFICATION_STATUSES)}")
    normalized_memory_candidates = _normalize_memory_candidates(memory_candidates)
    if normalized_issue_id and not normalized_issue_status:
        normalized_issue_status = _issue_status_for_verification(verification_status)
    if normalized_issue_status and normalized_issue_status not in ISSUE_STATUSES:
        raise ValueError(f"issue-status must be one of {', '.join(ISSUE_STATUSES)}")
    if normalized_issue_status and not normalized_issue_id:
        raise ValueError("issue-status requires issue-id")
    if event_type == "bug-fix" and not normalized_issue_id:
        raise ValueError("bug-fix events require a stable issue-id")
    normalized_project = _single_line(project, "project", max_length=160)
    if "/" in normalized_project or "\\" in normalized_project or normalized_project in {".", ".."}:
        raise ValueError("project must be one folder-safe name")
    scope = _scope_context(normalized_project, primary_module, task_name, session_id, session_key, task_scope_key, task_group, task_group_key)
    event = {"schema_version": SCHEMA_VERSION, "event_id": "", "recorded_at": timestamp, "last_seen": timestamp, "project": normalized_project, "project_root": "", "working_line": _single_line(working_line, "working-line", required=False, max_length=240), "record_kind": "memory" if normalized_memory_candidates else "issue" if normalized_issue_id else "event", "event_type": event_type, "summary": normalized_summary, "reason": _single_line(reason, "reason"), "result": _single_line(result, "result"), "verification_status": verification_status, "module_changes": _module_changes(primary_module, normalized_summary, module_change_values), "issue_id": normalized_issue_id, "issue_status": normalized_issue_status, "bug_class": _single_line(bug_class, "bug-class", required=False, max_length=120), "attempt_count": 1, **scope, "files": _normalize_files(files), "verification": list(dict.fromkeys(_single_line(value, "verification", max_length=600) for value in verification or [])), "decisions": list(dict.fromkeys(_single_line(value, "decision", max_length=600) for value in decisions or [])), "risks": list(dict.fromkeys(_single_line(value, "risk", max_length=600) for value in risks or [])), "memory_candidates": normalized_memory_candidates, "supersedes": "", "source": "ai-memory-v2"}
    _validate_event_semantics(event)
    event["fingerprint"] = _fingerprint(event)
    event["event_id"] = f"{timestamp.replace('-', '').replace(':', '')[:15]}Z-{event['fingerprint'][:12]}"

    def operation(events):
        if normalized_issue_id:
            existing = next((candidate for candidate in events if candidate.get("project", "").lower() == event["project"].lower() and candidate.get("issue_id") == normalized_issue_id), None)
            if existing:
                _migrate_event_provenance(existing)
                semantic_keys = ("last_seen", "working_line", "event_type", "summary", "reason", "result", "verification_status", "module_changes", "issue_status", "bug_class", "files", "verification", "decisions", "risks", "memory_candidates", "fingerprint")
                existing.update({key: event[key] for key in semantic_keys})
                if any(event.get(key) for key in ("session_key", "task_scope_key", "task_group_key")):
                    existing.update({key: event[key] for key in ("session_key", "task_scope_key", "task_group_key", "task_scope_mode")})
                existing["attempt_count"] = int(existing.get("attempt_count", 1)) + 1
                events.sort(key=lambda candidate: candidate.get("last_seen") or candidate.get("recorded_at") or "")
                _write_events(events, events_path)
                return {"status": "updated", "event_id": existing["event_id"], "issue_id": normalized_issue_id, "attempt_count": existing["attempt_count"]}
        semantic_payload = _semantic_event_payload(event)
        duplicate = next((candidate for candidate in events if _semantic_event_payload(candidate) == semantic_payload), None)
        if duplicate:
            return {"status": "duplicate", "event_id": duplicate["event_id"]}
        events.append(event)
        events.sort(key=lambda candidate: candidate.get("last_seen") or candidate.get("recorded_at") or "")
        _write_events(events, events_path)
        return {"status": "written", "event_id": event["event_id"], "issue_id": normalized_issue_id, "attempt_count": 1}

    output = _with_store_lock(events_path, operation)
    if output.get("status") in {"written", "updated"}:
        output["auto_classification"] = _run_auto_classification(events_path)
    return output


def _memory_candidate_key(candidate):
    return (candidate.get("kind", ""), candidate.get("area", ""), candidate.get("statement", "").casefold())


def _captured_memory_rows(events):
    selected = {}
    for event in events:
        seen_at = event.get("last_seen") or event.get("recorded_at") or ""
        for candidate in event.get("memory_candidates", []):
            key = _memory_candidate_key(candidate)
            row = selected.setdefault(key, {**candidate, "last_seen": seen_at, "occurrences": 0})
            row["occurrences"] += 1
            if seen_at >= row["last_seen"]:
                row.update({**candidate, "last_seen": seen_at})
    return sorted(selected.values(), key=lambda row: (row.get("kind", ""), row.get("area", ""), row.get("statement", "").casefold()))


def _memory_owner_path(candidate, vault_root):
    preferences_root = Path(vault_root) / "Preferences"
    if candidate.get("area") == "ui":
        ui_path = preferences_root / "UI Style Preferences.md"
        if ui_path.exists():
            return ui_path
    return preferences_root / "AI Captured Preferences.md"


def _replace_memory_block(existing, block):
    if MEMORY_BLOCK_START in existing and MEMORY_BLOCK_END in existing:
        prefix, remainder = existing.split(MEMORY_BLOCK_START, 1)
        _, suffix = remainder.split(MEMORY_BLOCK_END, 1)
        return f"{prefix.rstrip()}\n\n{block}\n\n{suffix.lstrip()}".rstrip() + "\n"
    return f"{existing.rstrip()}\n\n{block}\n" if existing.strip() else block + "\n"


def _write_memory_owner_pages(events, vault_root):
    rows = _captured_memory_rows(events)
    if not rows:
        return []
    grouped = defaultdict(list)
    root = Path(vault_root).expanduser().resolve()
    for row in rows:
        grouped[_memory_owner_path(row, root)].append(row)
    written = []
    for path, owner_rows in grouped.items():
        path = _confined_write_path(root, path, "captured preference owner")
        existing = path.read_text(encoding="utf-8") if path.exists() else "# AI Captured Preferences\n"
        lines = [MEMORY_BLOCK_START, "## Ending-confirmed memory", ""]
        for kind in ("preference", "technical-trait"):
            kind_rows = [row for row in owner_rows if row.get("kind") == kind]
            if not kind_rows:
                continue
            title = "Personal preferences" if kind == "preference" else "Technical working traits"
            lines.extend([f"### {title}", ""])
            for row in kind_rows:
                last_seen = str(row.get("last_seen", ""))[:10] or "unknown"
                lines.append(f"- {row['statement']} — evidence: {row['evidence']}; basis: {row['basis']}; confidence: {row['confidence']}; last seen: {last_seen}; occurrences: {row['occurrences']}")
            lines.append("")
        lines.append(MEMORY_BLOCK_END)
        updated = _replace_memory_block(existing, "\n".join(lines))
        if updated != existing:
            _write_confined_text(root, path, updated, "captured preference owner")
            written.append(path.relative_to(root).as_posix())
    return written


def record_memory_candidates(candidates, project="Global Preferences", module="ending-memory", verification_status="passed", working_line="global-personal-memory", recorded_at="", events_path=EVENTS_PATH, preferences_root=VAULT_ROOT):
    normalized = _normalize_memory_candidates(candidates)
    if not normalized:
        return {"status": "no-candidates", "written": False, "candidates": 0}
    if verification_status not in VERIFICATION_STATUSES:
        raise ValueError(f"verification-status must be one of {', '.join(VERIFICATION_STATUSES)}")
    owner_root = Path(preferences_root).expanduser().resolve()
    for candidate in normalized:
        _confined_write_path(owner_root, _memory_owner_path(candidate, owner_root), "captured preference owner")
    summary = f"Captured {len(normalized)} Ending-confirmed personal memory candidate{'s' if len(normalized) != 1 else ''}"
    result = record_event(project, module, "preference", summary, "Ending found explicit preference or verified working-pattern evidence.", "Candidates passed bounded privacy and evidence validation.", verification_status, working_line=working_line, verification=["Ending candidate analysis"], decisions=[candidate["statement"] for candidate in normalized], recorded_at=recorded_at, events_path=events_path, memory_candidates=normalized)
    owner_documents = _with_store_lock(events_path, lambda events: _write_memory_owner_pages(events, owner_root))
    return {**result, "written": result.get("status") in {"written", "updated"}, "candidates": len(normalized), "owner_documents": owner_documents}


def _normalize_file_replacements(values):
    replacements = []
    replaced_paths = set()
    for value in values or []:
        if "=" not in str(value):
            raise ValueError("replace-file must use OLD=NEW")
        old_path, new_path = str(value).split("=", 1)
        normalized_old = _normalize_files([old_path])
        normalized_new = _normalize_files([new_path])
        if not normalized_old or not normalized_new or normalized_old[0] == normalized_new[0]:
            raise ValueError("replace-file must name two different project-relative paths")
        if normalized_old[0] in replaced_paths:
            raise ValueError("replace-file must not replace the same path twice")
        replaced_paths.add(normalized_old[0])
        replacements.append((normalized_old[0], normalized_new[0]))
    return replacements


def amend_event(event_id, files=None, verification=None, decisions=None, risks=None, events_path=EVENTS_PATH, summary="", result="", module_change_values=None, replace_risks=None, replace_files=None):
    normalized_event_id = _single_line(event_id, "event-id", max_length=160)
    normalized_replacements = _normalize_file_replacements(replace_files)

    def operation(events):
        event = next((candidate for candidate in events if candidate.get("event_id") == normalized_event_id), None)
        if event is None:
            raise ValueError("event-id does not exist")
        _migrate_event_provenance(event)
        current_files = list(event.get("files", []))
        missing_source = next((old_path for old_path, _ in normalized_replacements if old_path not in current_files), "")
        if missing_source:
            raise ValueError(f"replace-file source does not exist on event: {missing_source}")
        replacement_map = dict(normalized_replacements)
        current_files = [replacement_map.get(file_path, file_path) for file_path in current_files]
        event["files"] = list(dict.fromkeys([*current_files, *_normalize_files(files)]))
        for field_name, values in (("verification", verification), ("decisions", decisions), ("risks", risks)):
            normalized_values = [_single_line(value, field_name, max_length=600) for value in values or []]
            event[field_name] = list(dict.fromkeys([*event.get(field_name, []), *normalized_values]))
        if summary:
            event["summary"] = _single_line(summary, "summary")
        if result:
            event["result"] = _single_line(result, "result")
        if module_change_values:
            primary_module = event.get("module_changes", [{}])[0].get("module", "project-wide")
            event["module_changes"] = _module_changes(primary_module, event["summary"], module_change_values)
        if replace_risks is not None:
            event["risks"] = list(dict.fromkeys(_single_line(value, "risk", max_length=600) for value in replace_risks))
        _validate_event_semantics(event)
        event["fingerprint"] = _fingerprint(event)
        _write_events(events, events_path)
        return {"status": "updated", "event_id": normalized_event_id, "events": len(events)}

    output = _with_store_lock(events_path, operation)
    if output.get("status") == "updated":
        output["auto_classification"] = _run_auto_classification(events_path)
    return output


def migrate_provenance(events_path=EVENTS_PATH):
    def operation(events):
        changed_events = sum(1 for event in events if _migrate_event_provenance(event))
        if changed_events:
            _write_events(events, events_path)
        return {"status": "migrated" if changed_events else "no-op", "events": len(events), "migrated_events": changed_events}

    return _with_store_lock(events_path, operation)


def redact_private_event(event_id, events_path=EVENTS_PATH):
    normalized_event_id = str(event_id or "").strip()
    if not EVENT_ID_PATTERN.fullmatch(normalized_event_id):
        raise ValueError("event-id has invalid format")

    def operation(events):
        if any(not isinstance(event, dict) for event in events):
            raise ValueError("event store contains a non-object record")
        if any(not EVENT_ID_PATTERN.fullmatch(str(event.get("event_id") or "")) for event in events):
            raise ValueError("event store contains an invalid event-id")
        matching_events = [event for event in events if event.get("event_id") == normalized_event_id]
        if not matching_events:
            raise ValueError("event-id does not exist")
        if len(matching_events) != 1:
            raise ValueError("event-id is not unique")
        target = matching_events[0]
        redacted_event = dict(target)
        redacted_fields = []
        for field_name in REDACTABLE_EVENT_FIELDS:
            if field_name not in target:
                continue
            redacted_value, changed = _redact_private_value(target[field_name])
            if changed:
                redacted_event[field_name] = redacted_value
                redacted_fields.append(field_name)
        if not redacted_fields:
            return {"status": "no-op", "event_id": normalized_event_id, "redacted_fields": [], "events": len(events)}
        _validate_event_semantics(redacted_event)
        redacted_event["fingerprint"] = _fingerprint(redacted_event)
        duplicate = next((event for event in events if event.get("event_id") != normalized_event_id and _fingerprint(event) == redacted_event["fingerprint"]), None)
        if duplicate is not None:
            raise ValueError(f"semantic-duplicate-conflict duplicate_event_id={duplicate['event_id']}")
        events[events.index(target)] = redacted_event
        _write_events(events, events_path)
        return {"status": "redacted-private", "event_id": normalized_event_id, "redacted_fields": redacted_fields, "events": len(events)}

    output = _with_store_lock(events_path, operation)
    if output.get("status") == "redacted-private":
        output["auto_classification"] = _run_auto_classification(events_path)
    return output


def _compact_event(event):
    modules = [change.get("module", "") for change in event.get("module_changes", []) if change.get("module")]
    return {"event_id": event.get("event_id", ""), "last_seen": event.get("last_seen", ""), "project": event.get("project", ""), "modules": modules, "event_type": event.get("event_type", ""), "summary": event.get("summary", ""), "result": event.get("result", ""), "verification_status": event.get("verification_status", ""), "issue_id": event.get("issue_id", ""), "issue_status": event.get("issue_status", ""), "attempt_count": event.get("attempt_count", 1), "files": event.get("files", []), "memory_candidates": event.get("memory_candidates", []), "scope_relation": event.get("scope_relation", "project_result_provenance"), "provenance_relation": event.get("provenance_relation", "unscoped_query")}


def search_events(project="", module="", query="", issue_status="", limit=5, compact=False, events_path=EVENTS_PATH, task_name="", session_id="", session_key="", task_scope_key="", task_group="", task_group_key=""):
    terms = [term for term in re.findall(r"[\w.+-]+", query.lower()) if len(term) >= 2][:12]
    normalized_project = project.strip()
    scope = _scope_context(normalized_project, module or "project-wide", task_name, session_id, session_key, task_scope_key, task_group, task_group_key)
    matches = []
    ordered_events = sorted(_read_events(events_path), key=lambda event: event.get("last_seen") or event.get("recorded_at") or "", reverse=True)
    for event in ordered_events:
        if normalized_project and event.get("project", "").lower() != normalized_project.lower():
            continue
        module_changes = event.get("module_changes", [])
        modules = [change.get("module", "") for change in module_changes]
        if module and module.strip().lower() not in [value.lower() for value in modules]:
            continue
        if issue_status and event.get("issue_status", "").upper() != issue_status.strip().upper():
            continue
        module_summaries = [change.get("summary", "") for change in module_changes]
        candidate_text = [value for candidate in event.get("memory_candidates", []) for value in (candidate.get("statement", ""), candidate.get("evidence", ""), candidate.get("area", ""), candidate.get("kind", ""))]
        searchable = " ".join([event.get("project", ""), event.get("summary", ""), event.get("reason", ""), event.get("result", ""), event.get("event_type", ""), event.get("bug_class", ""), event.get("issue_id", ""), *modules, *module_summaries, *event.get("files", []), *event.get("decisions", []), *event.get("risks", []), *candidate_text]).lower()
        if terms and not all(term in searchable for term in terms):
            continue
        matched_event = dict(event)
        for field_name in ("session_id", "task_name", "task_group"):
            matched_event.pop(field_name, None)
        matched_event["scope_relation"] = "project_result_provenance"
        matched_event["provenance_relation"] = _event_scope_relation(event, scope)
        matches.append(_compact_event(matched_event) if compact else matched_event)
        if len(matches) >= max(1, min(limit, 25)):
            break
    return {"status": "ok" if matches else "no-matches", "matches": matches}


def remove_invalid_event(event_id, duplicate_of="", events_path=EVENTS_PATH):
    normalized_event_id = _single_line(event_id, "event-id", max_length=160)
    normalized_duplicate_of = _single_line(duplicate_of, "duplicate-of", required=False, max_length=160)

    def operation(events):
        target = next((event for event in events if event.get("event_id") == normalized_event_id), None)
        if target is None:
            raise ValueError("event-id does not exist")
        if any(event.get("supersedes") == normalized_event_id for event in events if event is not target):
            raise ValueError("event-id is referenced by a superseding result")
        placeholder_fields = _placeholder_fields(target)
        reason = "placeholder-content" if placeholder_fields else ""
        if not reason and normalized_duplicate_of:
            canonical = next((event for event in events if event.get("event_id") == normalized_duplicate_of), None)
            if canonical is None:
                raise ValueError("duplicate-of event does not exist")
            if canonical is target or _semantic_event_payload(target) != _semantic_event_payload(canonical):
                raise ValueError("events are not semantic duplicates")
            reason = f"semantic-duplicate-of:{normalized_duplicate_of}"
        if not reason:
            raise ValueError("remove-invalid only permits placeholder content or a proven semantic duplicate")
        events.remove(target)
        _write_events(events, events_path)
        return {"status": "removed-invalid", "event_id": normalized_event_id, "reason": reason, "events": len(events)}

    output = _with_store_lock(events_path, operation)
    if output.get("status") == "removed-invalid":
        output["auto_classification"] = _run_auto_classification(events_path)
    return output


def _parse_time(value):
    return datetime.fromisoformat(_normalize_recorded_at(value).replace("Z", "+00:00"))


def _project_link(project, vault_root=VAULT_ROOT):
    return f"[[Projects/{project}/index|{project}]]" if (Path(vault_root) / "Projects" / project / "index.md").exists() else project


def render_views(events_path=EVENTS_PATH, recent_work_path=RECENT_WORK_PATH, dashboard_path=DASHBOARD_PATH, issues_path=ISSUES_PATH, now=None):
    recent_path = Path(os.path.abspath(os.fspath(Path(recent_work_path).expanduser())))
    vault_root = recent_path.parent.resolve()
    recent_path = _confined_write_path(vault_root, recent_path, "Recent Work owner")
    dashboard_path = _confined_write_path(vault_root, dashboard_path, "Memory Dashboard owner")
    issues_path = _confined_write_path(vault_root, issues_path, "Issues owner")
    current_time = now or datetime.now(timezone.utc)

    def operation(events):
        cutoff = current_time - timedelta(days=30)
        daily = defaultdict(list)
        project_events = defaultdict(list)
        for event in events:
            project_events[event.get("project", "Unknown")].append(event)
            seen_time = _parse_time(event.get("last_seen") or event.get("recorded_at"))
            if seen_time >= cutoff:
                daily[(seen_time.date().isoformat(), event.get("project", "Unknown"))].append(event)
        recent_lines = ["# Recent Work", "", "Generated from `AI Memory/events.jsonl`. Do not add manual event lines.", "", "## Last 30 Days", "", "<!-- BEGIN AI MEMORY DAILY SUMMARY -->"]
        for date_project in sorted(daily, reverse=True):
            date, project = date_project
            grouped = daily[date_project]
            modules = sorted({change.get("module", "") for event in grouped for change in event.get("module_changes", []) if change.get("module")})
            summaries = [_brief(summary) for summary in list(dict.fromkeys(event.get("summary", "") for event in grouped))[:2]]
            recent_lines.append(f"- {date} · {_project_link(project, vault_root)} · {len(grouped)} outcomes · modules: {', '.join(modules[:4]) or 'project-wide'} · {'; '.join(summaries)}")
        recent_lines.extend(["<!-- END AI MEMORY DAILY SUMMARY -->", "", "Use compact search for exact history.", "", "- [[Start Here]]", ""])
        _write_confined_text(vault_root, recent_path, "\n".join(recent_lines), "Recent Work owner")
        dashboard_lines = ["# Project Memory Dashboard", "", f"Generated: {current_time.isoformat(timespec='seconds').replace('+00:00', 'Z')}", "", "| Project | Events | Issues | Active / Monitoring | Modules | Last update |", "|---|---:|---:|---:|---:|---|"]
        for project in sorted(project_events):
            grouped = project_events[project]
            issues = [event for event in grouped if event.get("issue_id")]
            active = [event for event in issues if event.get("issue_status") in {"ACTIVE", "MONITORING"}]
            modules = {change.get("module") for event in grouped for change in event.get("module_changes", []) if change.get("module")}
            last_update = max(event.get("last_seen") or event.get("recorded_at") or "" for event in grouped)[:10]
            dashboard_lines.append(f"| {_project_link(project, vault_root)} | {len(grouped)} | {len(issues)} | {len(active)} | {len(modules)} | {last_update} |")
        dashboard_lines.extend(["", "- [[Issues]]", "- [[Start Here]]", ""])
        _write_confined_text(vault_root, dashboard_path, "\n".join(dashboard_lines), "Memory Dashboard owner")
        ordered_events = sorted(events, key=lambda event: event.get("last_seen") or event.get("recorded_at") or "", reverse=True)
        current_issues = [event for event in ordered_events if event.get("issue_status") in {"ACTIVE", "MONITORING"}]
        resolved_issues = [event for event in ordered_events if event.get("issue_status") == "RESOLVED"][:20]
        issue_lines = ["# Issues", "", "Generated from stable issue IDs in `AI Memory/events.jsonl`.", "", "## Active and Monitoring"]
        issue_lines.extend([f"- {event.get('issue_status')} · {_project_link(event.get('project', 'Unknown'), vault_root)} · `{event.get('module_changes', [{}])[0].get('module', 'project-wide')}` · {_brief(event.get('summary', ''), 140)}" for event in current_issues[:50]] or ["- None recorded."])
        issue_lines.extend(["", "## Recent Resolved Bugs"])
        issue_lines.extend([f"- {event.get('last_seen', '')[:10]} · {_project_link(event.get('project', 'Unknown'), vault_root)} · `{event.get('module_changes', [{}])[0].get('module', 'project-wide')}` · {_brief(event.get('summary', ''), 140)}" for event in resolved_issues] or ["- None recorded."])
        issue_lines.extend(["", "- [[Memory Dashboard]]", "- [[Start Here]]", ""])
        _write_confined_text(vault_root, issues_path, "\n".join(issue_lines), "Issues owner")
        return {"status": "written", "events": len(events), "projects": len(project_events)}

    return _with_store_lock(events_path, operation)


def memory_status(events_path=EVENTS_PATH):
    events = _read_events(events_path)
    event_ids = [event.get("event_id") for event in events]
    projects = {event.get("project") for event in events}
    modules = {change.get("module") for event in events for change in event.get("module_changes", []) if change.get("module")}
    return {"status": "ready", "schema_version": SCHEMA_VERSION, "events": len(events), "projects": len(projects), "modules": len(modules), "duplicate_event_ids": len(event_ids) - len(set(event_ids)), "store": Path(events_path).name}


def main():
    parser = argparse.ArgumentParser(description="AI-first project, module, and bounded preference memory")
    parser.add_argument("--store", type=Path, default=EVENTS_PATH)
    parser.add_argument("--vault", type=Path, default=VAULT_ROOT)
    subparsers = parser.add_subparsers(dest="command", required=True)
    project_parser = subparsers.add_parser("add-project")
    project_parser.add_argument("--name", required=True)
    record_parser = subparsers.add_parser("record")
    record_parser.add_argument("--project", required=True)
    record_parser.add_argument("--module", required=True)
    record_parser.add_argument("--module-change", action="append", default=[])
    record_parser.add_argument("--event-type", choices=EVENT_TYPES, required=True)
    record_parser.add_argument("--summary", required=True)
    record_parser.add_argument("--reason", required=True)
    record_parser.add_argument("--result", required=True)
    record_parser.add_argument("--verification-status", choices=VERIFICATION_STATUSES, required=True)
    record_parser.add_argument("--working-line", default="")
    record_parser.add_argument("--issue-id", default="")
    record_parser.add_argument("--issue-status", choices=ISSUE_STATUSES, default="")
    record_parser.add_argument("--bug-class", default="")
    record_parser.add_argument("--file", action="append", default=[])
    record_parser.add_argument("--verification", action="append", default=[])
    record_parser.add_argument("--decision", action="append", default=[])
    record_parser.add_argument("--risk", action="append", default=[])
    record_parser.add_argument("--recorded-at", default="")
    record_parser.add_argument("--task-name", default=os.environ.get("LLM_WIKI_TASK_NAME", ""))
    record_parser.add_argument("--task-group", default=os.environ.get("LLM_WIKI_TASK_GROUP", ""))
    record_parser.add_argument("--session-id", default=os.environ.get("LLM_WIKI_SESSION_ID", ""))
    capture_parser = subparsers.add_parser("capture-memory")
    capture_parser.add_argument("--candidate-file", type=Path, required=True)
    capture_parser.add_argument("--project", default="Global Preferences")
    capture_parser.add_argument("--module", default="ending-memory")
    capture_parser.add_argument("--verification-status", choices=VERIFICATION_STATUSES, default="passed")
    capture_parser.add_argument("--working-line", default="global-personal-memory")
    capture_parser.add_argument("--recorded-at", default="")
    amend_parser = subparsers.add_parser("amend")
    amend_parser.add_argument("--event-id", required=True)
    amend_parser.add_argument("--file", action="append", default=[])
    amend_parser.add_argument("--verification", action="append", default=[])
    amend_parser.add_argument("--decision", action="append", default=[])
    amend_parser.add_argument("--risk", action="append", default=[])
    amend_parser.add_argument("--summary", default="")
    amend_parser.add_argument("--result", default="")
    amend_parser.add_argument("--module-change", action="append", default=[])
    amend_parser.add_argument("--replace-risk", action="append")
    amend_parser.add_argument("--replace-file", action="append", default=[])
    remove_parser = subparsers.add_parser("remove-invalid")
    remove_parser.add_argument("--event-id", required=True)
    remove_parser.add_argument("--duplicate-of", default="")
    redact_parser = subparsers.add_parser("redact-private")
    redact_parser.add_argument("--event-id", required=True)
    subparsers.add_parser("migrate-provenance")
    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("--project", default="")
    search_parser.add_argument("--module", default="")
    search_parser.add_argument("--query", default="")
    search_parser.add_argument("--issue-status", choices=ISSUE_STATUSES, default="")
    search_parser.add_argument("--limit", type=int, default=5)
    search_parser.add_argument("--compact", action="store_true")
    search_parser.add_argument("--task-name", default=os.environ.get("LLM_WIKI_TASK_NAME", ""))
    search_parser.add_argument("--task-group", default=os.environ.get("LLM_WIKI_TASK_GROUP", ""))
    search_parser.add_argument("--session-id", default=os.environ.get("LLM_WIKI_SESSION_ID", ""))
    subparsers.add_parser("render")
    subparsers.add_parser("status")
    arguments = parser.parse_args()
    if arguments.command == "add-project":
        output = add_project(arguments.name, arguments.vault.expanduser().resolve())
    elif arguments.command == "record":
        output = record_event(arguments.project, arguments.module, arguments.event_type, arguments.summary, arguments.reason, arguments.result, arguments.verification_status, arguments.module_change, arguments.working_line, arguments.issue_id, arguments.issue_status, arguments.bug_class, arguments.file, arguments.verification, arguments.decision, arguments.risk, arguments.recorded_at, arguments.store, task_name=arguments.task_name, session_id=arguments.session_id, task_group=arguments.task_group)
    elif arguments.command == "capture-memory":
        payload = json.loads(arguments.candidate_file.expanduser().resolve().read_text(encoding="utf-8"))
        candidates = payload.get("candidates") if isinstance(payload, dict) else payload
        output = record_memory_candidates(candidates, arguments.project, arguments.module, arguments.verification_status, arguments.working_line, arguments.recorded_at, arguments.store, arguments.vault.expanduser().resolve())
    elif arguments.command == "amend":
        output = amend_event(arguments.event_id, arguments.file, arguments.verification, arguments.decision, arguments.risk, arguments.store, arguments.summary, arguments.result, arguments.module_change, arguments.replace_risk, arguments.replace_file)
    elif arguments.command == "remove-invalid":
        output = remove_invalid_event(arguments.event_id, arguments.duplicate_of, arguments.store)
    elif arguments.command == "redact-private":
        output = redact_private_event(arguments.event_id, arguments.store)
    elif arguments.command == "migrate-provenance":
        output = migrate_provenance(arguments.store)
    elif arguments.command == "search":
        output = search_events(arguments.project, arguments.module, arguments.query, arguments.issue_status, arguments.limit, arguments.compact, arguments.store, arguments.task_name, arguments.session_id, task_group=arguments.task_group)
    elif arguments.command == "render":
        vault_path = arguments.vault.expanduser().resolve()
        output = render_views(arguments.store, vault_path / "Recent Work.md", vault_path / "Memory Dashboard.md", vault_path / "Issues.md")
    else:
        output = memory_status(arguments.store)
    print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
