"""Read-only adapters for observed local transcript formats.

Never executes content, follows transcript links, or reads auth/config files.
"""
import json
import os
import re
from pathlib import Path

from .models import Event, Session

MAX_LINE = 4 * 1024 * 1024
MAX_BYTES = 64 * 1024 * 1024
MAX_EVENTS = 40000


def roots(source: str = "auto") -> list[tuple[str, Path]]:
    candidates = [
        ("codex", Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "sessions"),
        ("claude", Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))) / "projects"),
    ]
    return [(name, root) for name, root in candidates if source in ("auto", name)]


def discover(source: str = "auto", paths: list[str] | None = None) -> list[tuple[str, Path]]:
    locations = [(source, Path(p).expanduser()) for p in paths] if paths else roots(source)
    found: dict[Path, tuple[str, Path, int]] = {}
    for name, root in locations:
        if root.is_symlink():
            continue
        if root.is_file():
            candidates = [root]
        elif root.is_dir():
            candidates = []
            for parent, dirs, files in os.walk(root, followlinks=False):
                dirs[:] = [d for d in dirs if not Path(parent, d).is_symlink()]
                candidates.extend(Path(parent, f) for f in files if f.endswith(".jsonl"))
        else:
            continue
        for path in candidates:
            try:
                if path.is_symlink() or not path.is_file():
                    continue
                # Claude tool result sidecars are not sessions.
                if not paths and "tool-results" in path.parts:
                    continue
                resolved = path.resolve()
                found[resolved] = (name, resolved, path.stat().st_mtime_ns)
            except OSError:
                continue
    return [(name, path) for name, path, _ in sorted(found.values(), key=lambda x: (-x[2], str(x[1])))]


def text_content(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(text_content(x) for x in value if isinstance(x, (dict, str)))
    if isinstance(value, dict):
        if value.get("type") in ("thinking", "reasoning", "image", "document", "image_url"):
            return ""
        if isinstance(value.get("text"), str):
            return value["text"]
        if "content" in value:
            return text_content(value["content"])
        return json.dumps(value, ensure_ascii=False)
    return ""


def arguments(value) -> str:
    if isinstance(value, str):
        try:
            return json.dumps(json.loads(value), sort_keys=True, ensure_ascii=False)
        except (ValueError, TypeError):
            return value
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def output_failed(value, text: str, tool: str, args: str) -> bool:
    """Use execution status, not occurrences of words like 'error' in source code."""
    if isinstance(value, list):
        # Codex desktop wraps exec results as content blocks. Decode only
        # recognized execution envelopes, not arbitrary JSON in file contents.
        for block in value:
            if not isinstance(block, dict):
                continue
            raw = block.get("text", "")
            try:
                envelope = json.loads(raw)
            except (ValueError, TypeError):
                continue
            if isinstance(envelope, dict) and ("chunk_id" in envelope or "wall_time_seconds" in envelope):
                if output_failed(envelope, "", tool, args):
                    return True
    obj = value
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except (ValueError, TypeError):
            obj = None
    code = None
    if isinstance(obj, dict):
        if obj.get("isError") is True or obj.get("is_error") is True:
            return True
        code = obj.get("exit_code", obj.get("exitCode"))
        meta = obj.get("metadata")
        if code is None and isinstance(meta, dict):
            code = meta.get("exit_code")
    if code is None:
        match = re.search(r"(?im)^\s*(?:Process exited with code|Process exit code:|Exit code:)\s*(-?\d+)\s*$", text)
        if match:
            code = int(match.group(1))
    # rg/grep return 1 for a successful search with zero matches.
    if code == 1:
        try:
            data = json.loads(args)
            command = data.get("cmd", data.get("command", "")) if isinstance(data, dict) else ""
        except (ValueError, TypeError):
            command = ""
        if re.match(r"^\s*(?:rg|grep)\s", command) and not re.search(r"[;|&\n]", command):
            return False
    return (isinstance(code, int) and not isinstance(code, bool) and code != 0) or bool(
        re.match(r"^(?:Error executing tool\b|Error calling tool\b|Tool execution failed\b)", text.strip(), re.I)
    )


def parse(path: Path, source: str = "auto") -> Session:
    session = Session(source=source, path=str(path), session_id=path.stem)
    calls: dict[str, Event] = {}
    seen: set[str] = set()
    fallback: list[Event] = []
    turn = 0
    consumed = 0

    def emit(kind, line, text="", tool="", call_id="", args="", failed=False, timestamp=""):
        nonlocal turn
        if kind == "user":
            # Machine-injected context is not a user correction or an actual task.
            if text.lstrip().startswith(("<environment_context>", "<permissions instructions>", "<INSTRUCTIONS>", "# AGENTS.md instructions", "<external_codex_apps_open_page>")):
                return
            turn += 1
        event = Event(line, kind, text, tool, call_id, args, failed, timestamp, turn)
        session.events.append(event)
        if kind == "tool_call" and call_id:
            calls[call_id] = event

    with path.open("rb") as handle:
        while True:
            raw = handle.readline(MAX_LINE + 1)
            if not raw:
                break
            session.lines += 1
            consumed += len(raw)
            if consumed > MAX_BYTES or len(session.events) >= MAX_EVENTS:
                session.truncated = True
                session.warnings.append("Read limit reached; report covers only the beginning of this session.")
                break
            if len(raw) > MAX_LINE:
                session.malformed += 1
                while raw and not raw.endswith(b"\n"):
                    raw = handle.readline(MAX_LINE + 1)
                    consumed += len(raw)
                    if consumed > MAX_BYTES:
                        session.truncated = True
                        break
                if session.truncated:
                    break
                continue
            try:
                record = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                session.malformed += 1
                continue
            if not isinstance(record, dict):
                session.malformed += 1
                continue
            typ = record.get("type")
            if session.source == "auto":
                if typ in ("session_meta", "response_item", "event_msg", "turn_context"):
                    session.source = "codex"
                elif typ in ("user", "assistant") and isinstance(record.get("message"), dict):
                    session.source = "claude"
            line, timestamp = session.lines, str(record.get("timestamp", ""))
            if session.source == "codex":
                p = record.get("payload", {})
                if not isinstance(p, dict):
                    session.malformed += 1
                    continue
                if typ == "session_meta":
                    session.recognized += 1
                    session.session_id = str(p.get("id", p.get("session_id", path.stem)))
                    session.cwd = str(p.get("cwd", ""))
                elif typ == "response_item":
                    kind = p.get("type")
                    if kind not in ("message", "function_call", "custom_tool_call", "function_call_output", "custom_tool_call_output"):
                        continue
                    session.recognized += 1
                    identity = p.get("id")
                    if identity and str(identity) in seen:
                        continue
                    if identity:
                        seen.add(str(identity))
                    if kind == "message" and p.get("role") in ("user", "assistant"):
                        emit(p["role"], line, text_content(p.get("content", [])), timestamp=timestamp)
                    elif kind in ("function_call", "custom_tool_call"):
                        emit("tool_call", line, tool=str(p.get("name", "unknown")), call_id=str(p.get("call_id", "")), args=arguments(p.get("arguments", p.get("input", {}))), timestamp=timestamp)
                    elif kind in ("function_call_output", "custom_tool_call_output"):
                        cid = str(p.get("call_id", ""))
                        call = calls.get(cid)
                        value = p.get("output", "")
                        text = text_content(value)
                        name, args = (call.tool, call.arguments) if call else ("unknown", "")
                        emit("tool_result", line, text, name, cid, failed=output_failed(value, text, name, args), timestamp=timestamp)
                elif typ == "event_msg" and p.get("type") in ("user_message", "agent_message"):
                    session.recognized += 1
                    fallback.append(Event(line, "user" if p["type"] == "user_message" else "assistant", text_content(p.get("message", "")), timestamp=timestamp))
            elif session.source == "claude":
                if typ not in ("user", "assistant"):
                    continue
                message = record.get("message")
                if not isinstance(message, dict):
                    session.malformed += 1
                    continue
                session.recognized += 1
                identity = record.get("uuid")
                if identity and str(identity) in seen:
                    continue
                if identity:
                    seen.add(str(identity))
                session.session_id = str(record.get("sessionId", session.session_id))
                session.cwd = str(record.get("cwd", session.cwd))
                content = message.get("content", [])
                if isinstance(content, str):
                    if content:
                        emit(typ, line, content, timestamp=timestamp)
                    continue
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    kind = block.get("type")
                    if kind == "text":
                        emit(typ, line, text_content(block), timestamp=timestamp)
                    elif kind == "tool_use":
                        emit("tool_call", line, tool=str(block.get("name", "unknown")), call_id=str(block.get("id", "")), args=arguments(block.get("input", {})), timestamp=timestamp)
                    elif kind == "tool_result":
                        cid = str(block.get("tool_use_id", ""))
                        call = calls.get(cid)
                        name, args = (call.tool, call.arguments) if call else ("unknown", "")
                        value = block.get("content", "")
                        text = text_content(value)
                        extra = record.get("toolUseResult")
                        failed = block.get("is_error") is True or output_failed(extra if isinstance(extra, dict) else value, text, name, args)
                        emit("tool_result", line, text, name, cid, failed=failed, timestamp=timestamp)
    # Older Codex streams sometimes contain only event messages. Do not double
    # count event_msg mirrors when canonical response messages are available.
    for kind in ("user", "assistant"):
        if not any(e.kind == kind for e in session.events):
            session.events.extend(e for e in fallback if e.kind == kind)
    session.events.sort(key=lambda e: e.line)
    turn = 0
    for event in session.events:
        if event.kind == "user":
            turn += 1
        event.turn = turn
    if session.malformed:
        session.warnings.append(f"Skipped {session.malformed} malformed/oversized record(s); an active file may have a partial final line.")
    if not session.recognized:
        session.warnings.append("Unsupported or empty transcript format.")
    if not session.events:
        session.warnings.append("No usable message or tool events found.")
    return session
