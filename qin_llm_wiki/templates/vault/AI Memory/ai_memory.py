#!/usr/bin/env python3
import argparse
import hashlib
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
ISSUE_STATUSES = ("ACTIVE", "MONITORING", "RESOLVED")
MEMORY_CANDIDATE_KINDS = ("preference", "technical-trait")
MEMORY_CANDIDATE_AREAS = ("ui", "workflow", "technical", "general")
MEMORY_CANDIDATE_BASES = ("explicit_user_request", "repeated_user_correction", "verified_work_pattern")
MEMORY_CANDIDATE_CONFIDENCE = ("high", "medium")
MEMORY_BLOCK_START = "<!-- BEGIN CODEX CAPTURED PREFERENCES -->"
MEMORY_BLOCK_END = "<!-- END CODEX CAPTURED PREFERENCES -->"
MEMORY_SENSITIVE_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9_-])(?:sk|rk|pk)-[A-Za-z0-9_-]{12,}"),
    re.compile(r"(?:api[_-]?key|secret|password|token)\s*[:=]\s*[^\s,;]{8,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"https?://[^\s/:]+:[^\s/@]+@", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9])/(?:Users|home)/[^\s]+", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9])[A-Z]:\\Users\\[^\s]+", re.IGNORECASE),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
)


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


def _read_events(events_path=EVENTS_PATH):
    path = Path(events_path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_events(events, events_path=EVENTS_PATH):
    path = Path(events_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending_path = path.with_name(path.name + ".pending")
    pending_path.write_text("".join(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n" for event in events), encoding="utf-8")
    pending_path.replace(path)


def _with_store_lock(events_path, operation):
    path = Path(events_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with (path.parent / ".lock").open("a", encoding="utf-8") as lock_handle:
        _lock(lock_handle)
        return operation(_read_events(path))


def _normalize_files(files):
    normalized = []
    for value in files or []:
        file_path = str(value).strip().replace("\\", "/")
        if not file_path:
            continue
        if PurePosixPath(file_path).is_absolute() or PureWindowsPath(file_path).is_absolute() or ".." in PurePosixPath(file_path).parts:
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
    fields = ("project", "working_line", "event_type", "summary", "reason", "result", "verification_status", "module_changes", "issue_id", "issue_status", "bug_class", "files", "decisions", "risks")
    if event.get("memory_candidates"):
        fields = (*fields, "memory_candidates")
    payload = {field: event.get(field) for field in fields}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _issue_status_for_verification(verification_status):
    return {"passed": "RESOLVED", "partial": "MONITORING", "failed": "ACTIVE", "not-run": "MONITORING"}[verification_status]


def add_project(project, vault_root=VAULT_ROOT):
    project_name = _single_line(project, "project", max_length=160)
    if "/" in project_name or "\\" in project_name or project_name in {".", ".."}:
        raise ValueError("project must be one folder-safe name")
    project_path = Path(vault_root) / "Projects" / project_name
    project_path.mkdir(parents=True, exist_ok=True)
    index_path = project_path / "index.md"
    knowledge_path = project_path / "Knowledge.md"
    if not index_path.exists():
        index_path.write_text(f"# {project_name}\n\n- [[Projects/{project_name}/Knowledge|Knowledge]]\n- [[Projects/index|Projects]]\n- [[Start Here|Home]]\n", encoding="utf-8")
    if not knowledge_path.exists():
        knowledge_path.write_text(f"# {project_name} Knowledge\n\n## Current project rules\n\nAdd current module truth here. Chronology belongs only in `AI Memory/events.jsonl`.\n", encoding="utf-8")
    projects_index_path = Path(vault_root) / "Projects" / "index.md"
    projects_index_text = projects_index_path.read_text(encoding="utf-8") if projects_index_path.exists() else "# Projects\n"
    link = f"- [[Projects/{project_name}/index|{project_name}]]"
    if link not in projects_index_text:
        projects_index_path.write_text(projects_index_text.rstrip() + "\n\n" + link + "\n", encoding="utf-8")
    return {"status": "written", "project": project_name, "path": f"Projects/{project_name}"}


def record_event(project, module, event_type, summary, reason, result, verification_status, module_change_values=None, working_line="", issue_id="", issue_status="", bug_class="", files=None, verification=None, decisions=None, risks=None, recorded_at="", events_path=EVENTS_PATH, memory_candidates=None):
    timestamp = recorded_at or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
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
    event = {"schema_version": SCHEMA_VERSION, "event_id": "", "recorded_at": timestamp, "last_seen": timestamp, "project": _single_line(project, "project", max_length=160), "project_root": "", "working_line": _single_line(working_line, "working-line", required=False, max_length=240), "record_kind": "memory" if normalized_memory_candidates else "issue" if normalized_issue_id else "event", "event_type": event_type, "summary": normalized_summary, "reason": _single_line(reason, "reason"), "result": _single_line(result, "result"), "verification_status": verification_status, "module_changes": _module_changes(primary_module, normalized_summary, module_change_values), "issue_id": normalized_issue_id, "issue_status": normalized_issue_status, "bug_class": _single_line(bug_class, "bug-class", required=False, max_length=120), "attempt_count": 1, "files": _normalize_files(files), "verification": list(dict.fromkeys(verification or [])), "decisions": list(dict.fromkeys(decisions or [])), "risks": list(dict.fromkeys(risks or [])), "memory_candidates": normalized_memory_candidates, "supersedes": "", "source": "ai-memory-v2"}
    event["fingerprint"] = _fingerprint(event)
    event["event_id"] = f"{timestamp.replace('-', '').replace(':', '')[:15]}Z-{event['fingerprint'][:12]}"

    def operation(events):
        if normalized_issue_id:
            existing = next((candidate for candidate in events if candidate.get("project", "").lower() == event["project"].lower() and candidate.get("issue_id") == normalized_issue_id), None)
            if existing:
                existing.update({key: event[key] for key in ("last_seen", "working_line", "event_type", "summary", "reason", "result", "verification_status", "module_changes", "issue_status", "bug_class", "files", "verification", "decisions", "risks", "memory_candidates", "fingerprint")})
                existing["attempt_count"] = int(existing.get("attempt_count", 1)) + 1
                _write_events(events, events_path)
                return {"status": "updated", "event_id": existing["event_id"], "issue_id": normalized_issue_id, "attempt_count": existing["attempt_count"]}
        duplicate = next((candidate for candidate in events if candidate.get("fingerprint") == event["fingerprint"]), None)
        if duplicate:
            return {"status": "duplicate", "event_id": duplicate["event_id"]}
        events.append(event)
        events.sort(key=lambda candidate: candidate.get("last_seen") or candidate.get("recorded_at") or "")
        _write_events(events, events_path)
        return {"status": "written", "event_id": event["event_id"], "issue_id": normalized_issue_id, "attempt_count": 1}

    return _with_store_lock(events_path, operation)


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
    root = Path(vault_root)
    for row in rows:
        grouped[_memory_owner_path(row, root)].append(row)
    written = []
    for path, owner_rows in grouped.items():
        path.parent.mkdir(parents=True, exist_ok=True)
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
            pending = path.with_name(path.name + ".pending")
            pending.write_text(updated, encoding="utf-8")
            pending.replace(path)
            written.append(path.relative_to(root).as_posix())
    return written


def record_memory_candidates(candidates, project="Global Preferences", module="ending-memory", verification_status="passed", working_line="global-personal-memory", recorded_at="", events_path=EVENTS_PATH, preferences_root=VAULT_ROOT):
    normalized = _normalize_memory_candidates(candidates)
    if not normalized:
        return {"status": "no-candidates", "written": False, "candidates": 0}
    if verification_status not in VERIFICATION_STATUSES:
        raise ValueError(f"verification-status must be one of {', '.join(VERIFICATION_STATUSES)}")
    summary = f"Captured {len(normalized)} Ending-confirmed personal memory candidate{'s' if len(normalized) != 1 else ''}"
    result = record_event(project, module, "preference", summary, "Ending found explicit preference or verified working-pattern evidence.", "Candidates passed bounded privacy and evidence validation.", verification_status, working_line=working_line, verification=["Ending candidate analysis"], decisions=[candidate["statement"] for candidate in normalized], recorded_at=recorded_at, events_path=events_path, memory_candidates=normalized)
    owner_documents = _write_memory_owner_pages(_read_events(events_path), preferences_root)
    return {**result, "written": result.get("status") in {"written", "updated"}, "candidates": len(normalized), "owner_documents": owner_documents}


def amend_event(event_id, files=None, verification=None, decisions=None, risks=None, events_path=EVENTS_PATH, summary="", result="", module_change_values=None, replace_risks=None):
    normalized_event_id = _single_line(event_id, "event-id", max_length=160)

    def operation(events):
        event = next((candidate for candidate in events if candidate.get("event_id") == normalized_event_id), None)
        if event is None:
            raise ValueError("event-id does not exist")
        for field_name, values in (("files", _normalize_files(files)), ("verification", verification), ("decisions", decisions), ("risks", risks)):
            event[field_name] = list(dict.fromkeys([*event.get(field_name, []), *(values or [])]))
        if summary:
            event["summary"] = _single_line(summary, "summary")
        if result:
            event["result"] = _single_line(result, "result")
        if module_change_values:
            primary_module = event.get("module_changes", [{}])[0].get("module", "project-wide")
            event["module_changes"] = _module_changes(primary_module, event["summary"], module_change_values)
        if replace_risks is not None:
            event["risks"] = list(dict.fromkeys(replace_risks))
        event["fingerprint"] = _fingerprint(event)
        _write_events(events, events_path)
        return {"status": "updated", "event_id": normalized_event_id, "events": len(events)}

    return _with_store_lock(events_path, operation)


def _compact_event(event):
    modules = [change.get("module", "") for change in event.get("module_changes", []) if change.get("module")]
    return {"event_id": event.get("event_id", ""), "last_seen": event.get("last_seen", ""), "project": event.get("project", ""), "modules": modules, "event_type": event.get("event_type", ""), "summary": event.get("summary", ""), "result": event.get("result", ""), "verification_status": event.get("verification_status", ""), "issue_id": event.get("issue_id", ""), "issue_status": event.get("issue_status", ""), "attempt_count": event.get("attempt_count", 1), "files": event.get("files", []), "memory_candidates": event.get("memory_candidates", [])}


def search_events(project="", module="", query="", issue_status="", limit=5, compact=False, events_path=EVENTS_PATH):
    terms = [term for term in re.findall(r"[\w.+-]+", query.lower()) if len(term) >= 2][:12]
    matches = []
    for event in reversed(_read_events(events_path)):
        if project and event.get("project", "").lower() != project.strip().lower():
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
        matches.append(_compact_event(event) if compact else event)
        if len(matches) >= max(1, min(limit, 25)):
            break
    return {"status": "ok" if matches else "no-matches", "matches": matches}


def _parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _project_link(project):
    return f"[[Projects/{project}/index|{project}]]" if (VAULT_ROOT / "Projects" / project / "index.md").exists() else project


def render_views(events_path=EVENTS_PATH, recent_work_path=RECENT_WORK_PATH, dashboard_path=DASHBOARD_PATH, issues_path=ISSUES_PATH, now=None):
    events = _read_events(events_path)
    current_time = now or datetime.now(timezone.utc)
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
        recent_lines.append(f"- {date} · {_project_link(project)} · {len(grouped)} outcomes · modules: {', '.join(modules[:4]) or 'project-wide'} · {'; '.join(summaries)}")
    recent_lines.extend(["<!-- END AI MEMORY DAILY SUMMARY -->", "", "Use compact search for exact history.", "", "- [[Start Here]]", ""])
    Path(recent_work_path).write_text("\n".join(recent_lines), encoding="utf-8")
    dashboard_lines = ["# Project Memory Dashboard", "", f"Generated: {current_time.isoformat(timespec='seconds').replace('+00:00', 'Z')}", "", "| Project | Events | Issues | Active / Monitoring | Modules | Last update |", "|---|---:|---:|---:|---:|---|"]
    for project in sorted(project_events):
        grouped = project_events[project]
        issues = [event for event in grouped if event.get("issue_id")]
        active = [event for event in issues if event.get("issue_status") in {"ACTIVE", "MONITORING"}]
        modules = {change.get("module") for event in grouped for change in event.get("module_changes", []) if change.get("module")}
        last_update = max(event.get("last_seen") or event.get("recorded_at") or "" for event in grouped)[:10]
        dashboard_lines.append(f"| {_project_link(project)} | {len(grouped)} | {len(issues)} | {len(active)} | {len(modules)} | {last_update} |")
    dashboard_lines.extend(["", "- [[Issues]]", "- [[Start Here]]", ""])
    Path(dashboard_path).write_text("\n".join(dashboard_lines), encoding="utf-8")
    current_issues = [event for event in reversed(events) if event.get("issue_status") in {"ACTIVE", "MONITORING"}]
    resolved_issues = [event for event in reversed(events) if event.get("issue_status") == "RESOLVED"][:20]
    issue_lines = ["# Issues", "", "Generated from stable issue IDs in `AI Memory/events.jsonl`.", "", "## Active and Monitoring"]
    issue_lines.extend([f"- {event.get('issue_status')} · {_project_link(event.get('project', 'Unknown'))} · `{event.get('module_changes', [{}])[0].get('module', 'project-wide')}` · {_brief(event.get('summary', ''), 140)}" for event in current_issues[:50]] or ["- None recorded."])
    issue_lines.extend(["", "## Recent Resolved Bugs"])
    issue_lines.extend([f"- {event.get('last_seen', '')[:10]} · {_project_link(event.get('project', 'Unknown'))} · `{event.get('module_changes', [{}])[0].get('module', 'project-wide')}` · {_brief(event.get('summary', ''), 140)}" for event in resolved_issues] or ["- None recorded."])
    issue_lines.extend(["", "- [[Memory Dashboard]]", "- [[Start Here]]", ""])
    Path(issues_path).write_text("\n".join(issue_lines), encoding="utf-8")
    return {"status": "written", "events": len(events), "projects": len(project_events)}


def memory_status(events_path=EVENTS_PATH):
    events = _read_events(events_path)
    event_ids = [event.get("event_id") for event in events]
    projects = {event.get("project") for event in events}
    modules = {change.get("module") for event in events for change in event.get("module_changes", []) if change.get("module")}
    return {"status": "ready", "schema_version": SCHEMA_VERSION, "events": len(events), "projects": len(projects), "modules": len(modules), "duplicate_event_ids": len(event_ids) - len(set(event_ids)), "store": Path(events_path).name}


def main():
    parser = argparse.ArgumentParser(description="AI-first project and module memory")
    parser.add_argument("--store", type=Path, default=EVENTS_PATH)
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
    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("--project", default="")
    search_parser.add_argument("--module", default="")
    search_parser.add_argument("--query", default="")
    search_parser.add_argument("--issue-status", choices=ISSUE_STATUSES, default="")
    search_parser.add_argument("--limit", type=int, default=5)
    search_parser.add_argument("--compact", action="store_true")
    subparsers.add_parser("render")
    subparsers.add_parser("status")
    arguments = parser.parse_args()
    if arguments.command == "add-project":
        output = add_project(arguments.name)
    elif arguments.command == "record":
        output = record_event(arguments.project, arguments.module, arguments.event_type, arguments.summary, arguments.reason, arguments.result, arguments.verification_status, arguments.module_change, arguments.working_line, arguments.issue_id, arguments.issue_status, arguments.bug_class, arguments.file, arguments.verification, arguments.decision, arguments.risk, arguments.recorded_at, arguments.store)
    elif arguments.command == "capture-memory":
        payload = json.loads(arguments.candidate_file.expanduser().resolve().read_text(encoding="utf-8"))
        candidates = payload.get("candidates") if isinstance(payload, dict) else payload
        output = record_memory_candidates(candidates, arguments.project, arguments.module, arguments.verification_status, arguments.working_line, arguments.recorded_at, arguments.store, VAULT_ROOT)
    elif arguments.command == "amend":
        output = amend_event(arguments.event_id, arguments.file, arguments.verification, arguments.decision, arguments.risk, arguments.store, arguments.summary, arguments.result, arguments.module_change, arguments.replace_risk)
    elif arguments.command == "search":
        output = search_events(arguments.project, arguments.module, arguments.query, arguments.issue_status, arguments.limit, arguments.compact, arguments.store)
    elif arguments.command == "render":
        output = render_views(arguments.store)
    else:
        output = memory_status(arguments.store)
    print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
