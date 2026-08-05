import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
TEMPLATE_ROOT = PACKAGE_ROOT / "templates" / "vault"
MANAGED_FILES = ("AGENTS.md", "CLAUDE.md", "instruction.md", "AI Memory/ai_memory.py", "AI Memory/memory_lint.py", "AI Memory/tests/test_ai_memory.py")
SEED_FILES = ("Start Here.md", "Projects/index.md", "Knowledge/index.md", "Knowledge/Project Learning.md", "Knowledge/Privacy and Safety.md", "Preferences/index.md", "Preferences/AI Captured Preferences.md", "Skills/index.md")
REQUIRED_ROOT_ENTRIES = ("AGENTS.md", "CLAUDE.md", "instruction.md", "Start Here.md", "Recent Work.md", "Issues.md", "Memory Dashboard.md", "AI Memory", "Projects", "Knowledge", "Preferences", "Skills")
REQUIRED_RUNTIME_FILES = ("AI Memory/ai_memory.py", "AI Memory/memory_lint.py", "AI Memory/tests/test_ai_memory.py", "AI Memory/events.jsonl")
FORBIDDEN_ENTRIES = ("_System", "raw", "Journal", "Archive")
SKIPPED_SCAN_PARTS = {".git", ".venv", "__pycache__", ".pytest_cache", "Cache", "build", "dist"}
TEXT_SUFFIXES = {".md", ".py", ".toml", ".txt", ".json", ".yaml", ".yml", ".ini", ".cfg"}


def _display_path(path):
    resolved_path = Path(path).resolve()
    try:
        return resolved_path.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return resolved_path.name


def _template_text(relative_path, wiki_name):
    return (TEMPLATE_ROOT / relative_path).read_text(encoding="utf-8").replace("{{WIKI_NAME}}", wiki_name)


def _managed_drift(vault_path, wiki_name):
    drift = []
    for relative_path in MANAGED_FILES:
        target_path = vault_path / relative_path
        if target_path.exists() and target_path.read_text(encoding="utf-8") != _template_text(relative_path, wiki_name):
            drift.append(relative_path)
    return drift


def _write_architecture(vault_path, wiki_name, force_managed):
    drift = _managed_drift(vault_path, wiki_name)
    if drift and not force_managed:
        return {"status": "drift", "managed_files": drift, "message": "Managed files differ; review them and rerun with --force-managed."}
    vault_path.mkdir(parents=True, exist_ok=True)
    for directory_name in ("AI Memory/tests", "Projects", "Knowledge", "Preferences", "Skills"):
        (vault_path / directory_name).mkdir(parents=True, exist_ok=True)
    written = []
    for relative_path in MANAGED_FILES:
        target_path = vault_path / relative_path
        template_text = _template_text(relative_path, wiki_name)
        if not target_path.exists() or target_path.read_text(encoding="utf-8") != template_text:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(template_text, encoding="utf-8")
            written.append(relative_path)
    for relative_path in SEED_FILES:
        target_path = vault_path / relative_path
        if not target_path.exists():
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(_template_text(relative_path, wiki_name), encoding="utf-8")
            written.append(relative_path)
    events_path = vault_path / "AI Memory" / "events.jsonl"
    if not events_path.exists():
        events_path.write_text("", encoding="utf-8")
        written.append("AI Memory/events.jsonl")
    runtime_path = vault_path / "AI Memory" / "ai_memory.py"
    completed = subprocess.run([sys.executable, str(runtime_path), "render"], text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        return {"status": "error", "written": written, "message": completed.stderr.strip() or completed.stdout.strip()}
    return {"status": "written", "vault": _display_path(vault_path), "written": written, "preserved": ["AI Memory/events.jsonl", "Projects/", "Knowledge/", "Preferences/", "Skills/"]}


def architecture_signature(vault_path):
    root_types = {}
    for relative_path in REQUIRED_ROOT_ENTRIES:
        target_path = vault_path / relative_path
        root_types[relative_path] = "directory" if target_path.is_dir() else "file" if target_path.is_file() else "missing"
    runtime = {relative_path: (vault_path / relative_path).is_file() for relative_path in REQUIRED_RUNTIME_FILES}
    forbidden = {relative_path: (vault_path / relative_path).exists() for relative_path in FORBIDDEN_ENTRIES}
    return {"schema": 1, "root": root_types, "runtime": runtime, "forbidden": forbidden}


def verify_vault(vault_path):
    errors = []
    signature = architecture_signature(vault_path)
    for relative_path, path_type in signature["root"].items():
        if path_type == "missing":
            errors.append(f"Missing required root entry: {relative_path}")
    for relative_path, exists in signature["runtime"].items():
        if not exists:
            errors.append(f"Missing runtime file: {relative_path}")
    for relative_path, exists in signature["forbidden"].items():
        if exists:
            errors.append(f"Forbidden legacy layer exists: {relative_path}")
    events_path = vault_path / "AI Memory" / "events.jsonl"
    event_ids = []
    issue_keys = []
    if events_path.exists():
        for line_number, line in enumerate(events_path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as error:
                errors.append(f"Event line {line_number} is invalid JSON: {error.msg}")
                continue
            required_fields = ("schema_version", "event_id", "recorded_at", "last_seen", "project", "record_kind", "event_type", "summary", "reason", "result", "verification_status", "module_changes", "files")
            missing_fields = [field_name for field_name in required_fields if field_name not in event]
            if missing_fields:
                errors.append(f"Event line {line_number} is missing: {', '.join(missing_fields)}")
            event_ids.append(str(event.get("event_id", "")))
            if event.get("issue_id"):
                issue_keys.append((event.get("project"), event.get("issue_id")))
    duplicate_event_ids = sorted({event_id for event_id in event_ids if event_ids.count(event_id) > 1})
    duplicate_issue_keys = sorted({f"{project}:{issue_id}" for project, issue_id in issue_keys if issue_keys.count((project, issue_id)) > 1})
    if duplicate_event_ids:
        errors.append(f"Duplicate event IDs: {', '.join(duplicate_event_ids)}")
    if duplicate_issue_keys:
        errors.append(f"Duplicate issue lifecycle rows: {', '.join(duplicate_issue_keys)}")
    return {"status": "pass" if not errors else "fail", "vault": _display_path(vault_path), "errors": errors, "signature": signature, "events": len(event_ids)}


def _sensitive_patterns():
    home_posix = re.compile(re.escape("/" + "Users/") + r"[^/\s]+/")
    home_windows = re.compile(re.escape("C:" + "\\Users\\"), re.IGNORECASE)
    credential_prefix = re.compile(r"(?:gh" + r"[opsu]_" + r"[A-Za-z0-9]{12,}|s" + r"k-" + r"[A-Za-z0-9_-]{12,}|AKIA" + r"[A-Z0-9]{12,})")
    private_key = re.compile("BEGIN " + "(?:RSA |OPENSSH |EC )?PRIVATE KEY")
    email_address = re.compile(r"(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w.-])")
    credential_url = re.compile(r"https?://[^\s/:]+:[^\s/@]+@", re.IGNORECASE)
    return (("posix-home-path", home_posix), ("windows-home-path", home_windows), ("credential-prefix", credential_prefix), ("private-key", private_key), ("email-address", email_address), ("credential-url", credential_url))


def privacy_check(scan_path):
    findings = []
    candidate_paths = [scan_path] if scan_path.is_file() else sorted(path for path in scan_path.rglob("*") if path.is_file())
    for candidate_path in candidate_paths:
        relative_parts = candidate_path.relative_to(scan_path).parts if scan_path.is_dir() else (candidate_path.name,)
        if any(part in SKIPPED_SCAN_PARTS for part in relative_parts):
            continue
        if candidate_path.suffix.lower() not in TEXT_SUFFIXES and candidate_path.name not in {"LICENSE", "MANIFEST.in"}:
            continue
        text = candidate_path.read_text(encoding="utf-8", errors="replace")
        for pattern_name, pattern in _sensitive_patterns():
            if pattern.search(text):
                findings.append({"file": candidate_path.relative_to(scan_path).as_posix() if scan_path.is_dir() else candidate_path.name, "pattern": pattern_name})
    return {"status": "pass" if not findings else "fail", "path": _display_path(scan_path), "findings": findings}


def compare_architecture(reference_path, candidate_path):
    reference = verify_vault(reference_path)
    candidate = verify_vault(candidate_path)
    same = reference["signature"] == candidate["signature"] and reference["status"] == "pass" and candidate["status"] == "pass"
    return {"status": "pass" if same else "fail", "same_architecture": same, "reference": reference, "candidate": candidate}


def main():
    parser = argparse.ArgumentParser(description="Generate and maintain a privacy-safe AI-first Obsidian LLM Wiki.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command_name in ("init", "update"):
        command_parser = subparsers.add_parser(command_name)
        command_parser.add_argument("--vault", type=Path, required=True)
        command_parser.add_argument("--name", default="My LLM Wiki")
        command_parser.add_argument("--force-managed", action="store_true")
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--vault", type=Path, required=True)
    verify_parser.add_argument("--json", action="store_true")
    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("--reference", type=Path, required=True)
    compare_parser.add_argument("--candidate", type=Path, required=True)
    privacy_parser = subparsers.add_parser("privacy-check")
    privacy_parser.add_argument("--path", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    if arguments.command in {"init", "update"}:
        output = _write_architecture(arguments.vault.expanduser().resolve(), arguments.name, arguments.force_managed)
    elif arguments.command == "verify":
        output = verify_vault(arguments.vault.expanduser().resolve())
    elif arguments.command == "compare":
        output = compare_architecture(arguments.reference.expanduser().resolve(), arguments.candidate.expanduser().resolve())
    else:
        output = privacy_check(arguments.path.expanduser().resolve())
    print(json.dumps(output, ensure_ascii=False, indent=2 if getattr(arguments, "json", False) else None))
    raise SystemExit(0 if output["status"] in {"pass", "written"} else 1)


if __name__ == "__main__":
    main()
