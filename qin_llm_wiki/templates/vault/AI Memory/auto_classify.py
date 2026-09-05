#!/usr/bin/env python3
"""Classify verified events into bounded reusable-lesson candidates."""

import argparse
import hashlib
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

if os.name == "nt":
    import msvcrt
elif os.name == "posix":
    import fcntl
else:
    raise RuntimeError(f"Unsupported host OS for memory classification locking: {os.name}")


VAULT_ROOT = Path(__file__).resolve().parents[1]
EVENTS_PATH = Path(__file__).resolve().parent / "events.jsonl"
CANDIDATE_PATH = Path("Knowledge/Reusable Lessons/Candidates.md")
TAXONOMY_KEYS = ("memory-process", "code-architecture", "game-architecture", "ui-interaction", "technology-decisions", "verification")
TAXONOMY_TITLES = {"memory-process": "Memory and Process", "code-architecture": "Code Architecture", "game-architecture": "Game Architecture", "ui-interaction": "UI and Interaction", "technology-decisions": "Technology Decisions", "verification": "Verification"}
TAXONOMY_PATHS = {"memory-process": Path("Knowledge/Reusable Lessons/Memory and Process.md"), "code-architecture": Path("Knowledge/Reusable Lessons/Code Architecture.md"), "game-architecture": Path("Knowledge/Reusable Lessons/Game Architecture.md"), "ui-interaction": Path("Knowledge/Reusable Lessons/UI and Interaction.md"), "technology-decisions": Path("Knowledge/Reusable Lessons/Technology Decisions.md"), "verification": Path("Knowledge/Reusable Lessons/Verification.md")}
TAXONOMY_KEYWORDS = {"memory-process": ("memory", "cache", "persist", "process", "queue", "cleanup", "lifecycle"), "code-architecture": ("architecture", "schema", "ownership", "boundary", "module", "contract", "source of truth"), "game-architecture": ("gameplay", "game", "scene", "physics", "input", "prefab", "runtime"), "ui-interaction": ("ui", "layout", "button", "visual", "clipping", "spacing", "feedback", "responsive"), "technology-decisions": ("technology", "shader", "renderer", "provider", "api", "version", "platform"), "verification": ("verify", "verification", "test", "capture", "render", "evidence", "artifact", "acceptance", "regression")}
CLUSTER_GROUPS = {"memory-process": (("process-lifecycle", ("process", "cleanup", "lifecycle", "queue")), ("cache-persistence", ("cache", "persist", "restart", "recovery"))), "code-architecture": (("ownership-boundary", ("ownership", "boundary", "source of truth", "contract")), ("schema-module", ("schema", "module", "serialization", "migration"))), "game-architecture": (("rules-presentation", ("gameplay", "scene", "presentation", "physics")), ("input-control", ("input", "control", "button", "touch"))), "ui-interaction": (("layout-readability", ("layout", "clipping", "spacing", "responsive", "readable")), ("feedback-lifecycle", ("feedback", "button", "status", "progress"))), "technology-decisions": (("renderer-platform", ("shader", "renderer", "texture", "platform")), ("provider-api", ("provider", "api", "model", "json"))), "verification": (("runtime-artifact", ("runtime", "capture", "render", "artifact", "screenshot")), ("regression-gate", ("regression", "acceptance", "retest", "gate")))}
SENSITIVE_PATTERNS = (re.compile(r"(?:password|api[_ -]?key|secret|token|cookie|credential)\s*[:=]", re.IGNORECASE), re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), re.compile(r"(?<![A-Za-z0-9])/(?:Users|home)/[^\s]+", re.IGNORECASE), re.compile(r"(?<![A-Za-z0-9])[A-Z]:\\Users\\[^\s]+", re.IGNORECASE), re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"))
PROJECTION_REDACTIONS = (r"(?i)_System/", r"(?i)raw/", r"(?i)Journal/", r"(?i)Archive/", r"(?i)History\.md", r"(?i)Activity Index\.md", r"(?i)Untitled(?: \d+)?\.canvas")
PLACEHOLDER_VALUES = {"tmp", "temp", "test", "dummy", "placeholder", "todo", "tbd", "n/a", "na", "none", "xxx"}


def _single_line(value, maximum=240):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:maximum]


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


def _safe_target(vault_root, relative_path):
    root = Path(vault_root).resolve()
    target = root / relative_path
    current = root
    for part in Path(relative_path).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"classification target must not be a symlink: {Path(relative_path).as_posix()}")
    try:
        target.resolve(strict=False).relative_to(root)
    except (OSError, RuntimeError, ValueError) as error:
        raise ValueError(f"classification target escapes the vault: {Path(relative_path).as_posix()}") from error
    return target


def _write_text_atomic(path, text):
    pending = path.with_name(path.name + ".pending")
    with pending.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    pending.replace(path)


def _projection_text(value, maximum=240):
    text = _single_line(value, maximum)
    for pattern in PROJECTION_REDACTIONS:
        text = re.sub(pattern, "[legacy path omitted]", text)
    return text


def _read_events(events_path):
    path = Path(events_path)
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _event_text(event):
    values = [event.get("project", ""), event.get("summary", ""), event.get("reason", ""), event.get("result", ""), event.get("event_type", ""), event.get("bug_class", "")]
    values.extend(change.get("module", "") for change in event.get("module_changes", []) if isinstance(change, dict))
    values.extend(change.get("summary", "") for change in event.get("module_changes", []) if isinstance(change, dict))
    values.extend(event.get("files", []))
    values.extend(event.get("decisions", []))
    values.extend(event.get("risks", []))
    values.extend(candidate.get(field_name, "") for candidate in event.get("memory_candidates", []) if isinstance(candidate, dict) for field_name in ("statement", "evidence", "area", "kind"))
    return " ".join(str(value) for value in values).lower()


def _placeholder_token(value):
    return re.sub(r"[^a-z0-9/]+", "", str(value or "").strip().lower())


def _is_placeholder_event(event):
    values = [event.get("summary"), event.get("reason"), event.get("result")]
    values.extend(change.get("summary") for change in event.get("module_changes", []) if isinstance(change, dict))
    values.extend(candidate.get(field_name) for candidate in event.get("memory_candidates", []) if isinstance(candidate, dict) for field_name in ("statement", "evidence"))
    return any(_placeholder_token(value) in PLACEHOLDER_VALUES for value in values)


def _explicit_preference(event):
    return str(event.get("project", "")).casefold() == "global preferences" and (event.get("event_type") == "preference" or bool(event.get("memory_candidates")))


def _classify_event(event):
    text = _event_text(event)
    scores = {key: sum(1 for keyword in TAXONOMY_KEYWORDS[key] if keyword in text) for key in TAXONOMY_KEYS}
    if event.get("event_type") == "preference":
        scores["ui-interaction"] += 2
    if event.get("event_type") == "verification":
        scores["verification"] += 2
    if event.get("event_type") == "architecture":
        scores["code-architecture"] += 1
    ordered = sorted(TAXONOMY_KEYS, key=lambda key: (scores[key], -TAXONOMY_KEYS.index(key)), reverse=True)
    category = ordered[0] if scores[ordered[0]] else "unclassified"
    top_score = scores[ordered[0]]
    second_score = scores[ordered[1]]
    confidence = 0.0 if not top_score else min(0.99, 0.35 + top_score * 0.1 + max(0, top_score - second_score) * 0.08)
    cluster = "general"
    if category in CLUSTER_GROUPS:
        cluster_scores = {name: sum(1 for keyword in keywords if keyword in text) for name, keywords in CLUSTER_GROUPS[category]}
        cluster = max(cluster_scores, key=cluster_scores.get) if max(cluster_scores.values()) else "general"
    high_signal = event.get("verification_status") in {"passed", "partial"} and bool(event.get("verification") or event.get("decisions") or event.get("bug_class") or event.get("event_type") in {"bug-fix", "architecture", "preference", "verification", "new-module"})
    sensitive = any(pattern.search(text) for pattern in SENSITIVE_PATTERNS)
    return {"category": category, "cluster": cluster, "confidence": round(confidence, 3), "sensitive": sensitive, "explicit_preference": _explicit_preference(event), "high_signal": high_signal}


def _candidate_groups(events):
    groups = defaultdict(list)
    blocked = 0
    unclassified = 0
    invalid_placeholders = 0
    for event in events:
        if _is_placeholder_event(event):
            invalid_placeholders += 1
            continue
        classification = _classify_event(event)
        if classification["sensitive"]:
            blocked += 1
            continue
        if classification["category"] == "unclassified" or not classification["high_signal"]:
            unclassified += 1
            continue
        groups[f"{classification['category']}:{classification['cluster']}"].append({"event": event, "classification": classification})
    return groups, blocked, unclassified, invalid_placeholders


def _lesson_signature(event):
    module_names = sorted(str(change.get("module") or "").strip().casefold() for change in event.get("module_changes", []) if isinstance(change, dict) and change.get("module"))
    payload = {
        "event_type": str(event.get("event_type") or "").strip().casefold(),
        "summary": _single_line(event.get("summary"), 600).casefold(),
        "reason": _single_line(event.get("reason"), 600).casefold(),
        "result": _single_line(event.get("result"), 600).casefold(),
        "modules": module_names,
        "decisions": sorted(_single_line(value, 600).casefold() for value in event.get("decisions", [])),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _group_projects(group):
    return sorted({str(item["event"].get("project") or "Unknown") for item in group})


def _group_confidence(group):
    highest = max(item["classification"]["confidence"] for item in group)
    return round(min(0.99, highest + max(0, len(_group_projects(group)) - 1) * 0.04), 3)


def _group_is_auto_promoted(group):
    all_passed = all(item["event"].get("verification_status") == "passed" for item in group)
    explicit_preference = all(item["classification"]["explicit_preference"] for item in group)
    confidence = _group_confidence(group)
    # Repeated project outcomes are review candidates, not permission to create a global rule.
    return bool(explicit_preference and all_passed and confidence >= 0.85)


def _promotion_groups(groups):
    promoted = {}
    for group_key, group in groups.items():
        coherent = defaultdict(list)
        for item in group:
            coherent[_lesson_signature(item["event"])].append(item)
        for signature, subgroup in coherent.items():
            if _group_is_auto_promoted(subgroup):
                promoted[f"{group_key}:{signature}"] = subgroup
    return promoted


def _lesson_id(group_key):
    return f"RL-AUTO-{hashlib.sha256(group_key.encode('utf-8')).hexdigest()[:12]}"


def _latest_item(group):
    return max(group, key=lambda item: item["event"].get("last_seen") or item["event"].get("recorded_at") or "")


def _project_link(vault_root, project):
    return f"[[Projects/{project}/index|{project}]]" if (Path(vault_root) / "Projects" / project / "index.md").is_file() else project


def _group_title(group):
    return _projection_text(_latest_item(group)["event"].get("summary") or "Reusable lesson", 160)


def _group_sources(vault_root, group):
    return ", ".join(_project_link(vault_root, project) for project in _group_projects(group))


def _group_event_ids(group):
    latest = sorted(group, key=lambda item: item["event"].get("recorded_at", ""), reverse=True)[:5]
    return ", ".join(f"`{item['event'].get('event_id', '')}`" for item in latest) + (f"; {len(group)} total in event store" if len(group) > 5 else "")


def _candidate_markdown(vault_root, groups, promoted_groups, blocked, unclassified, invalid_placeholders, classified_at):
    lines = ["# Auto-Classified Lesson Queue", "", "Generated from verified events. This machine-managed evidence index never replaces the event store or curated current rules.", "", f"- Classified at: {classified_at}", f"- Candidate groups: {len(groups)}", f"- Privacy-blocked events: {blocked}", f"- Invalid placeholder events: {invalid_placeholders}", f"- Unclassified or low-signal events: {unclassified}", "", "## Promotion policy", "", "- `AUTO-PROMOTE` requires an explicit Global Preferences outcome, passed verification, and high confidence. Repeated project outcomes remain candidates until the selected model writes a genuinely reusable rule.", "- `CANDIDATE` remains review evidence and does not change a shared rule.", "- Sensitive or placeholder events are never copied into this queue.", ""]
    for group_key, group in sorted(groups.items()):
        category, cluster = group_key.split(":", 1)
        lines.extend([f"### {_lesson_id(group_key)} — {_group_title(group)}", "", f"- Category: {TAXONOMY_TITLES[category]}", f"- Cluster: {cluster}", "- Decision: CANDIDATE", f"- Confidence: {_group_confidence(group)}", f"- Support projects: {len(_group_projects(group))}", f"- Source projects: {_group_sources(vault_root, group)}", f"- Source events: {_group_event_ids(group)}", ""])
    for group_key, group in sorted(promoted_groups.items()):
        category, cluster, _ = group_key.split(":", 2)
        lines.extend([f"### {_lesson_id(group_key)} — {_group_title(group)}", "", f"- Category: {TAXONOMY_TITLES[category]}", f"- Cluster: {cluster}", "- Decision: AUTO-PROMOTE", f"- Confidence: {_group_confidence(group)}", f"- Support projects: {len(_group_projects(group))}", f"- Source projects: {_group_sources(vault_root, group)}", f"- Source events: {_group_event_ids(group)}", ""])
    return "\n".join(lines)


def _category_header(category):
    title = TAXONOMY_TITLES[category]
    return f"# {title}\n\nThis owner contains concise reusable lessons distilled from verified project events. Current source and explicit user intent always win over an older lesson.\n\n- [[Knowledge/Reusable Lessons/index|Reusable Lessons]]\n\n## Curated lessons\n"


def _lesson_markdown(vault_root, group_key, group, classified_at):
    category, cluster, _ = group_key.split(":", 2)
    latest_event = _latest_item(group)["event"]
    scope = "user-preference" if any(item["classification"]["explicit_preference"] for item in group) else "cross-project"
    evidence = "; ".join(f"{item['event'].get('project', 'Unknown')}: {_projection_text(item['event'].get('result') or item['event'].get('summary'), 180)} [{item['event'].get('verification_status', 'unknown')}]" for item in group[:4])
    candidate_rules = [candidate.get("statement", "") for candidate in latest_event.get("memory_candidates", [])]
    rule = _projection_text("; ".join(candidate_rules) or latest_event.get("result") or latest_event.get("summary"), 300)
    return "\n".join([f"### {_lesson_id(group_key)} — {_group_title(group)}", "- Status: ACTIVE", f"- Scope: {scope}", f"- Category: {TAXONOMY_TITLES[category]}", f"- Cluster: {cluster}", f"- Confidence: {_group_confidence(group)}", f"- Support projects: {len(_group_projects(group))}", f"- Reusable rule: {rule}", f"- Applies when: A new task matches the {cluster} pattern in this category.", "- Avoid when: Current source, current user intent, or fresh runtime evidence conflicts with this lesson.", f"- Evidence: {evidence}", f"- Source projects: {_group_sources(vault_root, group)}", f"- Source events: {_group_event_ids(group)}", f"- Last classified: {classified_at}"])


def _upsert_auto_block(path, category, lesson_id, lesson):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text(encoding="utf-8") if path.is_file() else _category_header(category)
    start = f"<!-- AUTO-LESSON:{lesson_id} -->"
    end = f"<!-- END-AUTO-LESSON:{lesson_id} -->"
    block = f"{start}\n{lesson}\n{end}"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    updated = pattern.sub(block, text, count=1) if pattern.search(text) else text.rstrip() + "\n\n" + block + "\n"
    _write_text_atomic(path, updated)


def _remove_stale_auto_blocks(path, active_ids):
    if not path.is_file():
        return
    pattern = re.compile(r"(?ms)^<!-- AUTO-LESSON:(?P<lesson_id>RL-AUTO-[0-9a-f]+) -->.*?^<!-- END-AUTO-LESSON:(?P=lesson_id) -->\n?")
    text = path.read_text(encoding="utf-8")
    cleaned = pattern.sub(lambda match: match.group(0) if match.group("lesson_id") in active_ids else "", text)
    if cleaned != text:
        _write_text_atomic(path, cleaned.rstrip() + "\n")


def sync_catalog(vault_root=VAULT_ROOT, events_path=EVENTS_PATH, apply=True, focus_event_id=""):
    root = Path(vault_root).expanduser().resolve()
    store_path = Path(events_path).expanduser().resolve()
    store_path.parent.mkdir(parents=True, exist_ok=True)

    def classify_current_store():
        events = _read_events(store_path)
        groups, blocked, unclassified, invalid_placeholders = _candidate_groups(events)
        classified_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        active_groups = _promotion_groups(groups)
        if apply:
            targets = {"candidate": _safe_target(root, CANDIDATE_PATH)}
            targets.update({category: _safe_target(root, relative_path) for category, relative_path in TAXONOMY_PATHS.items()})
            for target in targets.values():
                target.parent.mkdir(parents=True, exist_ok=True)
            _write_text_atomic(targets["candidate"], _candidate_markdown(root, groups, active_groups, blocked, unclassified, invalid_placeholders, classified_at))
            active_ids = {_lesson_id(group_key) for group_key in active_groups}
            for category in TAXONOMY_PATHS:
                category_path = targets[category]
                if not category_path.is_file():
                    _write_text_atomic(category_path, _category_header(category))
                _remove_stale_auto_blocks(category_path, active_ids)
            for group_key, group in active_groups.items():
                category = group_key.split(":", 1)[0]
                _upsert_auto_block(targets[category], category, _lesson_id(group_key), _lesson_markdown(root, group_key, group, classified_at))
        return {"status": "written" if apply else "dry-run", "events": len(events), "candidate_groups": len(groups), "auto_promoted": len(active_groups), "privacy_blocked_events": blocked, "invalid_placeholder_events": invalid_placeholders, "unclassified_or_low_signal_events": unclassified, "focus_event_id": focus_event_id, "candidate_path": CANDIDATE_PATH.as_posix(), "category_paths": [path.as_posix() for path in TAXONOMY_PATHS.values()]}

    with (store_path.parent / ".lock").open("a+", encoding="utf-8") as lock_handle:
        _lock(lock_handle)
        return classify_current_store()


def recall(vault_root=VAULT_ROOT, events_path=EVENTS_PATH, query="", category="", limit=5, project=""):
    events = [event for event in _read_events(events_path) if str(event.get("project", "")).casefold() in {project.strip().casefold(), "global preferences"}]
    groups, _, _, _ = _candidate_groups(events)
    promoted_groups = _promotion_groups(groups)
    terms = [term for term in re.findall(r"[\w.+-]+", query.lower()) if len(term) >= 2][:12]
    matches = []
    for group_key, group in {**groups, **promoted_groups}.items():
        if group_key not in promoted_groups:
            group = [item for item in group if project and str(item["event"].get("project", "")).casefold() == project.strip().casefold()]
            if not group:
                continue
        parts = group_key.split(":", 2)
        group_category, cluster = parts[:2]
        if category and group_category != category:
            continue
        searchable = " ".join([group_category, TAXONOMY_TITLES.get(group_category, ""), cluster, *(_event_text(item["event"]) for item in group)]).lower()
        if terms and not all(term in searchable for term in terms):
            continue
        matches.append({"lesson_id": _lesson_id(group_key), "category": group_category, "category_title": TAXONOMY_TITLES[group_category], "cluster": cluster, "decision": "AUTO-PROMOTE" if group_key in promoted_groups else "CANDIDATE", "confidence": _group_confidence(group), "support_projects": len(_group_projects(group)), "source_projects": _group_projects(group), "title": _group_title(group), "category_path": TAXONOMY_PATHS[group_category].as_posix()})
    matches.sort(key=lambda match: (match["decision"] != "AUTO-PROMOTE", -match["confidence"], match["category"], match["cluster"]))
    return {"status": "ok" if matches else "no-matches", "query": query, "matches": matches[: max(1, min(limit, 25))]}


def main():
    parser = argparse.ArgumentParser(description="Classify verified events into bounded reusable-lesson categories.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    sync_parser = subparsers.add_parser("sync")
    sync_parser.add_argument("--vault", type=Path, default=VAULT_ROOT)
    sync_parser.add_argument("--events", type=Path, default=EVENTS_PATH)
    sync_parser.add_argument("--dry-run", action="store_true")
    sync_parser.add_argument("--focus-event-id", default="")
    recall_parser = subparsers.add_parser("recall")
    recall_parser.add_argument("--vault", type=Path, default=VAULT_ROOT)
    recall_parser.add_argument("--events", type=Path, default=EVENTS_PATH)
    recall_parser.add_argument("--query", default="")
    recall_parser.add_argument("--project", default="", help="Exact project for candidates; omitted returns only global preferences")
    recall_parser.add_argument("--category", choices=TAXONOMY_KEYS, default="")
    recall_parser.add_argument("--limit", type=int, default=5)
    arguments = parser.parse_args()
    output = sync_catalog(arguments.vault, arguments.events, apply=not arguments.dry_run, focus_event_id=arguments.focus_event_id) if arguments.command == "sync" else recall(arguments.vault, arguments.events, arguments.query, arguments.category, arguments.limit, arguments.project)
    print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
