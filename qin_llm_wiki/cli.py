import argparse
import errno
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path, PureWindowsPath

from .hidden_process import hidden_process_options


PACKAGE_ROOT = Path(__file__).resolve().parent
TEMPLATE_ROOT = PACKAGE_ROOT / "templates" / "vault"
MANAGED_FILES = ("AGENTS.md", "CLAUDE.md", "GEMINI.md", "instruction.md", "AI Memory/ai_memory.py", "AI Memory/auto_classify.py", "AI Memory/memory_lint.py", "AI Memory/hidden_process.py", "AI Memory/tests/test_ai_memory.py", "AI Memory/tests/test_auto_classify.py", "AI Memory/tests/test_memory_lint.py", "AI Memory/tests/test_hidden_process.py")
SEED_FILES = ("Start Here.md", "Projects/index.md", "Knowledge/index.md", "Knowledge/Project Learning.md", "Knowledge/Memory Retrieval.md", "Knowledge/Privacy and Safety.md", "Knowledge/Reusable Lessons/index.md", "Knowledge/Reusable Lessons/Candidates.md", "Knowledge/Reusable Lessons/Memory and Process.md", "Knowledge/Reusable Lessons/Code Architecture.md", "Knowledge/Reusable Lessons/Game Architecture.md", "Knowledge/Reusable Lessons/UI and Interaction.md", "Knowledge/Reusable Lessons/Technology Decisions.md", "Knowledge/Reusable Lessons/Verification.md", "Knowledge/Book References/index.md", "Knowledge/Book References/Programming and Software Engineering.md", "Knowledge/Book References/Unity and Game Development.md", "Knowledge/Book References/Computer Graphics and Shaders.md", "Preferences/index.md", "Preferences/AI Captured Preferences.md", "Skills/index.md")
REQUIRED_ROOT_ENTRIES = ("AGENTS.md", "CLAUDE.md", "GEMINI.md", "instruction.md", "Start Here.md", "Recent Work.md", "Issues.md", "Memory Dashboard.md", "AI Memory", "Projects", "Knowledge", "Preferences", "Skills")
REQUIRED_RUNTIME_FILES = ("AI Memory/ai_memory.py", "AI Memory/auto_classify.py", "AI Memory/memory_lint.py", "AI Memory/hidden_process.py", "AI Memory/tests/test_ai_memory.py", "AI Memory/tests/test_auto_classify.py", "AI Memory/tests/test_memory_lint.py", "AI Memory/tests/test_hidden_process.py", "AI Memory/events.jsonl")
REQUIRED_KNOWLEDGE_FILES = ("Knowledge/Reusable Lessons/index.md", "Knowledge/Reusable Lessons/Candidates.md", "Knowledge/Book References/index.md")
FORBIDDEN_ENTRIES = ("_System", "raw", "Journal", "Archive", "History")
SKIPPED_SCAN_PARTS = {".git", ".venv", "__pycache__", ".pytest_cache", "Cache", "build", "dist"}
TEXT_SUFFIXES = {".md", ".py", ".toml", ".txt", ".json", ".jsonl", ".yaml", ".yml", ".ini", ".cfg"}
VERIFY_CACHE_RELATIVE = Path("Cache") / "temp-llm-wiki-architecture"
MUTATION_DIRECTORIES = ("AI Memory", "AI Memory/tests", "Projects", "Knowledge", "Preferences", "Skills")
GENERATED_FILES = ("Recent Work.md", "Memory Dashboard.md", "Issues.md")
SEED_REQUIRED_FRAGMENTS = {
    "Start Here.md": ("- [[Knowledge/Memory Retrieval|Memory Retrieval]]",),
    "Knowledge/index.md": ("- [[Knowledge/Reusable Lessons/index|Reusable Lessons]]", "- [[Knowledge/Book References/index|Book References]]", "- [[Knowledge/Memory Retrieval|Memory Retrieval]]"),
    "Knowledge/Project Learning.md": ("Current lifecycle: recall only the exact project; skip absent memory; verify in the original task; Ending only summarizes and writes durable facts with the user-selected model and effort.",),
    "Knowledge/Privacy and Safety.md": ("- Run production memory writes only for real outcomes. Put probes, fixtures, and failure simulations in an explicit disposable store and vault under the active project's `Cache/temp-<task>/` tree.", "- Treat malformed path components, bytecode, system metadata, empty canvases, placeholder events, and unreachable pages as integrity failures rather than hidden clutter."),
    "Knowledge/Reusable Lessons/index.md": ("- [[Knowledge/Reusable Lessons/Candidates|Candidate Queue]]",),
    "Preferences/index.md": ("- [[Preferences/AI Captured Preferences|AI Captured Preferences]]",),
}


def _display_path(path):
    absolute_path = Path(os.path.abspath(os.fspath(Path(path).expanduser())))
    try:
        return absolute_path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return absolute_path.name


def _template_text(relative_path, wiki_name):
    return (TEMPLATE_ROOT / relative_path).read_text(encoding="utf-8").replace("{{WIKI_NAME}}", wiki_name)


def _sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path):
    return _sha256_bytes(Path(path).read_bytes()) if Path(path).is_file() else ""


def _jsonl_repair_target(vault_path, relative_path):
    portable_path = str(relative_path).replace("\\", "/")
    parts = portable_path.split("/")
    if PureWindowsPath(portable_path).drive or any(part in {"", ".", ".."} or ":" in part for part in parts):
        raise ValueError("Repair path must be a confined vault-relative path.")
    if portable_path.casefold() == "ai memory/events.jsonl":
        raise ValueError("The primary event store requires the guarded ai_memory repair APIs.")
    target = vault_path.joinpath(*parts)
    if target.suffix.lower() != ".jsonl":
        raise ValueError("Repair target must be an existing JSONL file.")
    paths = [vault_path, *(vault_path.joinpath(*parts[:index]) for index in range(1, len(parts) + 1))]
    locks = list(dict.fromkeys((vault_path / "AI Memory" / ".lock", target.parent / ".lock")))
    for path in (*paths, *(lock.parent for lock in locks), *locks):
        if path.is_symlink():
            raise ValueError("Repair target, ancestors, and locks must not be symlinks.")
        try:
            path.resolve().relative_to(vault_path.resolve())
        except (OSError, RuntimeError, ValueError):
            raise ValueError("Repair path escapes the vault boundary.") from None
    if not vault_path.is_dir() or not target.is_file() or any(not lock.parent.is_dir() for lock in locks):
        raise ValueError("Repair target and memory lock directories must already exist.")
    if any(lock.exists() and not lock.is_file() for lock in locks):
        raise ValueError("Memory locks must be regular files.")
    primary_store = vault_path / "AI Memory" / "events.jsonl"
    if primary_store.exists() and target.samefile(primary_store):
        raise ValueError("The primary event store requires the guarded ai_memory repair APIs.")
    return target, locks


def _split_concatenated_jsonl(content):
    def reject_constant(_value):
        raise ValueError("Invalid JSON constant")

    decoder = json.JSONDecoder(parse_constant=reject_constant)
    lines = content.decode("utf-8").split("\n")
    records = added_newlines = 0
    for line_number, line in enumerate(lines, 1):
        position = 0
        insertions = []
        line_records = 0
        while position < len(line):
            while position < len(line) and line[position] in " \t\r":
                position += 1
            if position == len(line):
                break
            start = position
            try:
                value, position = decoder.raw_decode(line, start)
            except (ValueError, RecursionError):
                raise ValueError(f"Invalid or incomplete JSON on line {line_number}; no repair applied.") from None
            if not isinstance(value, dict):
                raise ValueError(f"Non-object JSON on line {line_number}; no repair applied.")
            if line_records:
                insertions.append(start)
            records += 1
            line_records += 1
        for start in reversed(insertions):
            line = line[:start] + "\n" + line[start:]
        lines[line_number - 1] = line
        added_newlines += len(insertions)
    return "\n".join(lines).encode("utf-8"), records, added_newlines


@contextmanager
def _jsonl_repair_lock(path):
    # Match ai_memory's parent/.lock protocol on both supported OS families.
    if os.name == "nt":
        import msvcrt
    elif os.name == "posix":
        import fcntl
    else:
        raise ValueError("JSONL repair locking is unsupported on this host.")
    flags = os.O_RDWR | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags, 0o600), "a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        deadline = time.monotonic() + 5
        while True:
            try:
                if os.name == "nt":
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise ValueError("Memory lock is busy; no repair applied.") from None
                time.sleep(0.05)
            except OSError as error:
                if os.name != "nt" or error.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                    raise
                if time.monotonic() >= deadline:
                    raise ValueError("Memory lock is busy; no repair applied.") from None
                time.sleep(0.05)
        yield


def repair_jsonl(vault_path, relative_path, expected_sha256):
    """Insert only missing object separators after validating the entire file."""
    vault_path = Path(os.path.abspath(os.fspath(Path(vault_path).expanduser())))
    pending_path = None
    try:
        if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
            raise ValueError("Expected SHA-256 must contain exactly 64 hexadecimal characters.")
        target, locks = _jsonl_repair_target(vault_path, relative_path)
        original = target.read_bytes()
        before_sha256 = _sha256_bytes(original)
        if before_sha256 != expected_sha256.lower():
            raise ValueError("Expected SHA-256 does not match; no repair applied.")
        repaired, records, added_newlines = _split_concatenated_jsonl(original)
        result = {"status": "unchanged", "file": target.relative_to(vault_path).as_posix(), "records": records, "added_newlines": added_newlines, "before_sha256": before_sha256, "after_sha256": _sha256_bytes(repaired)}
        if not added_newlines:
            return result
        with ExitStack() as stack:
            for lock in locks:
                _jsonl_repair_target(vault_path, relative_path)
                stack.enter_context(_jsonl_repair_lock(lock))
            _jsonl_repair_target(vault_path, relative_path)
            if target.read_bytes() != original:
                raise ValueError("JSONL changed while acquiring its locks; no repair applied.")
            mode = target.stat().st_mode & 0o777
            descriptor, temporary_name = tempfile.mkstemp(prefix=".jsonl-repair-", suffix=".pending", dir=target.parent)
            pending_path = Path(temporary_name)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(repaired)
                handle.flush()
                os.fsync(handle.fileno())
            pending_path.chmod(mode)
            _jsonl_repair_target(vault_path, relative_path)
            if target.read_bytes() != original:
                raise ValueError("JSONL changed before replacement; no repair applied.")
            pending_path.replace(target)
            pending_path = None
        result["status"] = "written"
        return result
    except (ValueError, OSError) as error:
        message = str(error) if isinstance(error, ValueError) and not isinstance(error, UnicodeError) else f"JSONL repair failed ({type(error).__name__}); no content was emitted."
        return {"status": "error", "message": message}
    finally:
        if pending_path is not None:
            pending_path.unlink(missing_ok=True)


def _managed_drift(vault_path, template_texts):
    drift = []
    for relative_path in MANAGED_FILES:
        target_path = vault_path / relative_path
        template_bytes = template_texts[relative_path].encode("utf-8")
        if target_path.exists() and target_path.read_bytes() != template_bytes:
            drift.append({"file": relative_path, "current_sha256": _file_sha256(target_path), "template_sha256": _sha256_bytes(template_bytes)})
    return drift


def _seed_fragment_updates(vault_path):
    updates = {}
    for relative_path, required_fragments in SEED_REQUIRED_FRAGMENTS.items():
        target_path = vault_path / relative_path
        if not target_path.exists():
            continue
        current_bytes = target_path.read_bytes()
        current_text = current_bytes.decode("utf-8")
        existing_targets = set(re.findall(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", current_text.replace(r"\|", "|")))
        missing_fragments = []
        for fragment in required_fragments:
            navigation = re.fullmatch(r"- \[\[([^\]|]+)\|[^\]]+\]\]", fragment)
            if fragment not in current_text and not (navigation and navigation.group(1) in existing_targets):
                missing_fragments.append(fragment)
        if not missing_fragments:
            continue
        separator = b"" if current_bytes.endswith(b"\n\n") else b"\n" if current_bytes.endswith(b"\n") else b"\n\n"
        appended_bytes = ("\n".join(missing_fragments) + "\n").encode("utf-8")
        updates[relative_path] = {"content": current_bytes + separator + appended_bytes, "fragments": len(missing_fragments)}
    return updates


def _mutation_boundary_errors(vault_path):
    file_targets = {vault_path / relative_path for relative_path in (*MANAGED_FILES, *SEED_FILES, "AI Memory/events.jsonl", *GENERATED_FILES)}
    directory_targets = {vault_path, *(vault_path / relative_path for relative_path in MUTATION_DIRECTORIES)}
    for target_path in file_targets:
        current_path = target_path.parent
        while True:
            directory_targets.add(current_path)
            if current_path == vault_path:
                break
            current_path = current_path.parent
    errors = []
    try:
        resolved_vault = vault_path.resolve(strict=False)
    except (OSError, RuntimeError) as error:
        return [f"Cannot resolve vault mutation boundary: {error}"]
    for path in sorted(directory_targets | file_targets, key=lambda candidate: (len(candidate.parts), candidate.as_posix())):
        label = "." if path == vault_path else path.relative_to(vault_path).as_posix()
        if path.is_symlink():
            errors.append(f"Mutation target or ancestor must not be a symlink: {label}")
        try:
            path.resolve(strict=False).relative_to(resolved_vault)
        except (OSError, RuntimeError, ValueError):
            errors.append(f"Mutation target escapes the vault boundary: {label}")
    for path in sorted(directory_targets, key=lambda candidate: (len(candidate.parts), candidate.as_posix())):
        if path.exists() and not path.is_dir():
            label = "." if path == vault_path else path.relative_to(vault_path).as_posix()
            errors.append(f"Mutation directory has the wrong type: {label}")
    for path in sorted(file_targets, key=lambda candidate: candidate.as_posix()):
        if path.exists() and not path.is_file():
            errors.append(f"Mutation file has the wrong type: {path.relative_to(vault_path).as_posix()}")
    return list(dict.fromkeys(errors))


def _run_json_command(arguments, cwd=None, environment=None):
    completed = subprocess.run(arguments, cwd=cwd, env=environment, text=True, capture_output=True, check=False, **hidden_process_options())
    payload = None
    if completed.stdout.strip():
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = None
    return {"exit_code": completed.returncode, "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip(), "payload": payload}


def _write_architecture(vault_path, wiki_name, force_managed):
    vault_path = Path(os.path.abspath(os.fspath(Path(vault_path).expanduser())))
    boundary_errors = _mutation_boundary_errors(vault_path)
    if boundary_errors:
        return {"status": "error", "vault": _display_path(vault_path), "written": [], "errors": boundary_errors, "message": "Vault mutation boundary preflight failed before any write."}
    try:
        template_texts = {relative_path: _template_text(relative_path, wiki_name) for relative_path in (*MANAGED_FILES, *SEED_FILES)}
        drift = _managed_drift(vault_path, template_texts)
        seed_fragment_updates = _seed_fragment_updates(vault_path)
        events_path = vault_path / "AI Memory" / "events.jsonl"
        if events_path.exists():
            events_path.read_bytes()
    except (OSError, UnicodeError) as error:
        return {"status": "error", "vault": _display_path(vault_path), "written": [], "errors": [f"Vault mutation preflight could not read required input: {error}"], "message": "Vault mutation preflight failed before any write."}
    if drift and not force_managed:
        return {"status": "drift", "vault": _display_path(vault_path), "managed_files": drift, "message": "Managed files differ. Review the current and template digests before explicitly accepting replacement with --force-managed."}
    drift_files = {entry["file"] for entry in drift}
    managed_writes = [relative_path for relative_path in MANAGED_FILES if not (vault_path / relative_path).exists() or relative_path in drift_files]
    seed_writes = [relative_path for relative_path in SEED_FILES if not (vault_path / relative_path).exists()]
    create_events = not events_path.exists()
    vault_path.mkdir(parents=True, exist_ok=True)
    for directory_name in MUTATION_DIRECTORIES:
        (vault_path / directory_name).mkdir(parents=True, exist_ok=True)
    written = []
    for relative_path in managed_writes:
        target_path = vault_path / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(template_texts[relative_path], encoding="utf-8")
        written.append(relative_path)
    for relative_path in seed_writes:
        target_path = vault_path / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(template_texts[relative_path], encoding="utf-8")
        written.append(relative_path)
    migrated_seed_fragments = {}
    for relative_path, update in seed_fragment_updates.items():
        (vault_path / relative_path).write_bytes(update["content"])
        migrated_seed_fragments[relative_path] = update["fragments"]
        written.append(relative_path)
    if create_events:
        events_path.write_text("", encoding="utf-8")
        written.append("AI Memory/events.jsonl")
    runtime_path = vault_path / "AI Memory" / "ai_memory.py"
    render = _run_json_command([sys.executable, "-B", str(runtime_path), "--store", str(events_path), "--vault", str(vault_path), "render"])
    if render["exit_code"] != 0 or not isinstance(render["payload"], dict) or render["payload"].get("status") != "written":
        return {"status": "error", "written": written, "message": render["stderr"] or render["stdout"] or "Generated view rendering failed."}
    return {"status": "written", "vault": _display_path(vault_path), "written": written, "migrated_seed_fragments": migrated_seed_fragments, "preserved": ["AI Memory/events.jsonl", "Projects/", "Knowledge/", "Preferences/", "Skills/"], "render": render["payload"]}


def _capability_signature(vault_path):
    runtime_path = vault_path / "AI Memory" / "ai_memory.py"
    lint_path = vault_path / "AI Memory" / "memory_lint.py"
    contract_path = vault_path / "AGENTS.md"
    runtime_text = runtime_path.read_text(encoding="utf-8") if runtime_path.is_file() else ""
    lint_text = lint_path.read_text(encoding="utf-8") if lint_path.is_file() else ""
    contract_text = contract_path.read_text(encoding="utf-8") if contract_path.is_file() else ""
    return {"single_event_store": "AI Memory/events.jsonl" in contract_text, "auto_classification": (vault_path / "AI Memory" / "auto_classify.py").is_file() and "auto_classify.py" in contract_text, "cross_session_project_results": "project_result_provenance" in runtime_text and "not retrieval barriers" in contract_text, "guarded_exact_id_removal": "remove-invalid" in runtime_text and "remove-invalid" in contract_text, "strict_utf8_and_reachability": "inspect_markdown_reachability" in lint_text and "Unreadable UTF-8" in lint_text, "ghost_and_malformed_path_guard": "Ghost artifact remains" in lint_text and "Malformed path component" in lint_text, "reusable_lessons": (vault_path / "Knowledge" / "Reusable Lessons" / "index.md").is_file(), "book_references": (vault_path / "Knowledge" / "Book References" / "index.md").is_file()}


def architecture_signature(vault_path):
    root_types = {}
    for relative_path in REQUIRED_ROOT_ENTRIES:
        target_path = vault_path / relative_path
        root_types[relative_path] = "directory" if target_path.is_dir() else "file" if target_path.is_file() else "missing"
    runtime = {relative_path: (vault_path / relative_path).is_file() for relative_path in REQUIRED_RUNTIME_FILES}
    knowledge = {relative_path: (vault_path / relative_path).is_file() for relative_path in REQUIRED_KNOWLEDGE_FILES}
    forbidden = {relative_path: (vault_path / relative_path).exists() for relative_path in FORBIDDEN_ENTRIES}
    return {"schema": 2, "root": root_types, "runtime": runtime, "knowledge": knowledge, "forbidden": forbidden, "capabilities": _capability_signature(vault_path)}


def _basic_structure_errors(vault_path):
    errors = []
    signature = architecture_signature(vault_path)
    errors.extend(f"Missing required root entry: {relative_path}" for relative_path, path_type in signature["root"].items() if path_type == "missing")
    errors.extend(f"Missing runtime file: {relative_path}" for relative_path, exists in signature["runtime"].items() if not exists)
    errors.extend(f"Missing knowledge file: {relative_path}" for relative_path, exists in signature["knowledge"].items() if not exists)
    errors.extend(f"Forbidden legacy layer exists: {relative_path}" for relative_path, exists in signature["forbidden"].items() if exists)
    errors.extend(f"Missing architecture capability: {capability}" for capability, present in signature["capabilities"].items() if not present)
    return errors, signature


def _prepare_disposable_directory(vault_path, name):
    cache_root = (vault_path / VERIFY_CACHE_RELATIVE).resolve()
    cache_root.mkdir(parents=True, exist_ok=True)
    target_path = cache_root / name
    if target_path.parent.resolve() != cache_root or target_path.is_symlink():
        raise ValueError("Disposable verification path escaped the vault Cache/temp-<task> boundary")
    if target_path.exists():
        shutil.rmtree(target_path)
    target_path.mkdir(parents=True)
    return target_path


def _runtime_unit_tests(vault_path):
    test_cache = _prepare_disposable_directory(vault_path, "runtime-tests")
    environment = os.environ.copy()
    environment["QIN_LLM_WIKI_TEST_CACHE"] = str(test_cache)
    command = [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(vault_path / "AI Memory" / "tests"), "-p", "test_*.py", "-v"]
    completed = subprocess.run(command, cwd=vault_path, env=environment, text=True, capture_output=True, check=False, **hidden_process_options())
    shutil.rmtree(test_cache)
    return {"status": "pass" if completed.returncode == 0 else "fail", "exit_code": completed.returncode, "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()}


def _runtime_replay(vault_path):
    replay_root = _prepare_disposable_directory(vault_path, "runtime-replay")
    replay_vault = replay_root / "vault"
    replay_vault.mkdir(parents=True)
    store_path = replay_root / "store" / "events.jsonl"
    runtime_path = vault_path / "AI Memory" / "ai_memory.py"
    classifier_path = vault_path / "AI Memory" / "auto_classify.py"
    default_store_path = vault_path / "AI Memory" / "events.jsonl"
    default_store_before = _file_sha256(default_store_path)
    record_command = [sys.executable, "-B", str(runtime_path), "--store", str(store_path), "--vault", str(replay_vault), "record", "--project", "ArchitectureCheck", "--module", "memory.runtime", "--event-type", "verification", "--summary", "Verified disposable memory runtime", "--reason", "Exercise the record search render flow", "--result", "Focused replay checks pass", "--verification-status", "passed", "--file", "src/runtime.py", "--verification", "Disposable replay passed", "--task-name", "producer-check", "--session-id", "11111111-1111-4111-8111-111111111111"]
    record = _run_json_command(record_command)
    search_command = [sys.executable, "-B", str(runtime_path), "--store", str(store_path), "--vault", str(replay_vault), "search", "--project", "ArchitectureCheck", "--module", "memory.runtime", "--query", "disposable runtime", "--limit", "5", "--compact", "--task-name", "independent-check", "--session-id", "22222222-2222-4222-8222-222222222222"]
    search = _run_json_command(search_command)
    render = _run_json_command([sys.executable, "-B", str(runtime_path), "--store", str(store_path), "--vault", str(replay_vault), "render"])
    classify = _run_json_command([sys.executable, "-B", str(classifier_path), "sync", "--vault", str(replay_vault), "--events", str(store_path)])
    search_match = search["payload"].get("matches", [{}])[0] if isinstance(search["payload"], dict) and search["payload"].get("matches") else {}
    checks = {"record": record["exit_code"] == 0 and isinstance(record["payload"], dict) and record["payload"].get("status") == "written", "cross_session_search": search["exit_code"] == 0 and search_match.get("scope_relation") == "project_result_provenance" and search_match.get("provenance_relation") == "unrelated_session", "render": render["exit_code"] == 0 and all((replay_vault / name).is_file() for name in ("Recent Work.md", "Memory Dashboard.md", "Issues.md")), "auto_classify": classify["exit_code"] == 0 and isinstance(classify["payload"], dict) and classify["payload"].get("status") == "written", "default_store_unchanged": _file_sha256(default_store_path) == default_store_before}
    output = {"status": "pass" if all(checks.values()) else "fail", "exit_code": 0 if all(checks.values()) else 1, "checks": checks, "errors": [name for name, passed in checks.items() if not passed]}
    shutil.rmtree(replay_root)
    return output


def verify_vault(vault_path, run_runtime=True):
    root = Path(vault_path).expanduser().resolve()
    check_runs = []
    errors, signature = _basic_structure_errors(root)
    check_runs.append({"check_id": "architecture-structure", "status": "pass" if not errors else "fail", "exit_code": 0 if not errors else 1, "errors": list(errors)})
    lint_payload = None
    lint_path = root / "AI Memory" / "memory_lint.py"
    if lint_path.is_file():
        lint = _run_json_command([sys.executable, "-B", str(lint_path), "--vault", str(root), "--json"])
        lint_payload = lint["payload"] if isinstance(lint["payload"], dict) else None
        lint_errors = lint_payload.get("errors", []) if lint_payload else [lint["stderr"] or lint["stdout"] or "Lint returned non-JSON output"]
        lint_status = "pass" if lint["exit_code"] == 0 and lint_payload and lint_payload.get("status") == "pass" else "fail"
        check_runs.append({"check_id": "vault-integrity", "status": lint_status, "exit_code": lint["exit_code"], "errors": lint_errors, "warnings": lint_payload.get("warnings", []) if lint_payload else []})
        if lint_status == "fail":
            errors.extend(lint_errors)
    elif not any("memory_lint.py" in error for error in errors):
        errors.append("Missing runtime file: AI Memory/memory_lint.py")
    if run_runtime and not errors:
        runtime_tests = _runtime_unit_tests(root)
        check_runs.append({"check_id": "runtime-unit-tests", **runtime_tests})
        if runtime_tests["status"] != "pass":
            errors.append(runtime_tests["stderr"] or runtime_tests["stdout"] or "Runtime unit tests failed")
        replay = _runtime_replay(root)
        check_runs.append({"check_id": "record-search-render-replay", **replay})
        if replay["status"] != "pass":
            errors.append(f"Runtime replay failed: {', '.join(replay['errors'])}")
    elif run_runtime:
        check_runs.append({"check_id": "runtime-unit-tests", "status": "not-run", "exit_code": None, "reason": "Earlier architecture or integrity check failed"})
        check_runs.append({"check_id": "record-search-render-replay", "status": "not-run", "exit_code": None, "reason": "Earlier architecture or integrity check failed"})
    events = lint_payload.get("ai_memory", {}).get("events", 0) if lint_payload else 0
    warnings = lint_payload.get("warnings", []) if lint_payload else []
    return {"status": "pass" if not errors and all(check["status"] == "pass" for check in check_runs) else "fail", "vault": _display_path(root), "errors": errors, "warnings": warnings, "signature": signature, "events": events, "check_runs": check_runs}


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


def compare_architecture(reference_path, candidate_path, run_runtime=False):
    reference = verify_vault(reference_path, run_runtime=run_runtime)
    candidate = verify_vault(candidate_path, run_runtime=run_runtime)
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
    verify_parser.add_argument("--quick", action="store_true")
    verify_parser.add_argument("--json", action="store_true")
    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("--reference", type=Path, required=True)
    compare_parser.add_argument("--candidate", type=Path, required=True)
    compare_parser.add_argument("--deep", action="store_true")
    privacy_parser = subparsers.add_parser("privacy-check")
    privacy_parser.add_argument("--path", type=Path, default=Path.cwd())
    repair_parser = subparsers.add_parser("repair-jsonl", help="Insert missing newlines between complete objects in an auxiliary JSONL file.")
    repair_parser.add_argument("--vault", type=Path, required=True)
    repair_parser.add_argument("--path", required=True)
    repair_parser.add_argument("--expected-sha256", required=True)
    arguments = parser.parse_args()
    if arguments.command in {"init", "update"}:
        output = _write_architecture(arguments.vault, arguments.name, arguments.force_managed)
    elif arguments.command == "verify":
        output = verify_vault(arguments.vault.expanduser().resolve(), run_runtime=not arguments.quick)
    elif arguments.command == "compare":
        output = compare_architecture(arguments.reference.expanduser().resolve(), arguments.candidate.expanduser().resolve(), run_runtime=arguments.deep)
    elif arguments.command == "repair-jsonl":
        output = repair_jsonl(arguments.vault, arguments.path, arguments.expected_sha256)
    else:
        output = privacy_check(arguments.path.expanduser().resolve())
    print(json.dumps(output, ensure_ascii=False, indent=2 if getattr(arguments, "json", False) else None))
    raise SystemExit(0 if output["status"] in {"pass", "written", "unchanged"} else 1)


if __name__ == "__main__":
    main()
