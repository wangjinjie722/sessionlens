import argparse
import json
import os
import sys
import time
from pathlib import Path

from . import __version__
from .diagnostics import report
from .privacy import redact
from .render import serialize, write_private
from .sources import discover, parse, roots


def positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def parser() -> argparse.ArgumentParser:
    app = argparse.ArgumentParser(description="Automatically diagnose local Codex and Claude Code sessions. 默认本地分析，不上传会话。")
    app.add_argument("--version", action="version", version=__version__)
    sub = app.add_subparsers(dest="command")
    for command, help_text in [("scan", "Analyze recent local sessions (default)"), ("watch", "Watch for new or changed sessions; Ctrl+C stops"), ("list", "List discovered sessions without reading their contents")]:
        p = sub.add_parser(command, help=help_text)
        p.add_argument("--source", choices=["auto", "codex", "claude"], default="auto")
        p.add_argument("--path", action="append", help="Optional transcript file/directory; repeatable. Default: automatic discovery")
        p.add_argument("--limit", type=positive, default=10, help="Maximum recent sessions (default: 10)")
        if command == "list":
            continue
        p.add_argument("--project", help="Only sessions whose recorded working directory is this directory or a child")
        p.add_argument("--format", choices=["text", "json", "html"], default="text")
        p.add_argument("--output", type=Path, help="Write an atomic report to this file")
        if command == "scan":
            p.add_argument("--deep", action="store_true", help="Send redacted selected excerpts to the configured model endpoint (opt-in)")
            p.add_argument("--model", help="Model name for --deep, or set SESSIONLENS_MODEL")
            p.add_argument("--deep-limit", type=positive, default=3, help="Maximum model calls (default: 3)")
            p.add_argument("--language", choices=["zh", "en"], default="zh", help="Model review language")
            p.add_argument("--preview-deep", action="store_true", help="Print the exact selected/redacted event contexts without sending them")
        else:
            p.add_argument("--interval", type=positive, default=10, help="Seconds between scans (default: 10)")
            p.add_argument("--once", action="store_true", help="Run one watch cycle then exit")
    sub.add_parser("doctor", help="Check local session sources and model configuration without exposing credentials")
    p = sub.add_parser("demo", help="Analyze a bundled synthetic session; no access to your history")
    p.add_argument("--format", choices=["text", "json", "html"], default="text")
    p.add_argument("--output", type=Path)
    return app


def under_project(cwd: str, project: str) -> bool:
    if not cwd:
        return False
    try:
        Path(cwd).expanduser().resolve().relative_to(Path(project).expanduser().resolve())
        return True
    except (ValueError, OSError):
        return False


class Scanner:
    def __init__(self):
        self.cache = {}

    def scan(self, args):
        candidates = discover(args.source, args.path)
        selected, warnings, signatures = [], [], []
        next_cache = {}
        for source, path in candidates:
            try:
                stat = path.stat()
                stamp = (stat.st_mtime_ns, stat.st_size, stat.st_ino)
                cached = self.cache.get(str(path))
                session = cached[1] if cached and cached[0] == stamp else parse(path, source)
                if not session.recognized:
                    warnings.append(f"Unsupported session skipped: {redact(str(path))}")
                    continue
                if args.project and not under_project(session.cwd, args.project):
                    continue
                selected.append(session)
                signatures.append((str(path), stamp))
                next_cache[str(path)] = (stamp, session)
                if len(selected) >= args.limit:
                    break
            except (OSError, ValueError, RecursionError) as exc:
                warnings.append(f"Could not read {redact(str(path))}: {type(exc).__name__}")
        self.cache = next_cache
        data = report(selected)
        data["warnings"] = warnings
        return selected, data, (tuple(signatures), tuple(warnings))


def output(data: dict, args) -> None:
    content = serialize(data, args.format)
    if args.output:
        write_private(args.output, content)
        print(f"Report: {args.output.expanduser().resolve()}", file=sys.stderr)
    else:
        print(content, end="", flush=True)


def run(args) -> int:
    if args.command == "doctor":
        checks = []
        for name, root in roots():
            checks.append({"source": name, "path": redact(str(root)), "exists": root.is_dir(), "readable": os.access(root, os.R_OK), "sessions": len(discover(name))})
        print(json.dumps({"version": __version__, "python": sys.version.split()[0], "sources": checks, "network_default": "off", "model_configured": bool(os.environ.get("SESSIONLENS_MODEL")), "api_key_present": bool(os.environ.get("SESSIONLENS_API_KEY") or os.environ.get("OPENAI_API_KEY"))}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "demo":
        output(report([parse(Path(__file__).with_name("demo.jsonl"))]), args)
        return 0
    if args.path and any(not Path(p).expanduser().exists() for p in args.path):
        raise ValueError("An explicit --path does not exist. Check the path and retry.")
    if args.command == "list":
        entries = discover(args.source, args.path)[:args.limit]
        for source, path in entries:
            print(f"{source}\t{redact(str(path))}")
        if not entries:
            print("No local sessions found. Run sessionlens doctor or specify --path.", file=sys.stderr)
            return 1
        return 0
    if getattr(args, "deep", False) and getattr(args, "preview_deep", False):
        raise ValueError("Choose --deep or --preview-deep, not both.")
    if getattr(args, "deep", False):
        from .llm import settings
        settings(args.model)
    if args.command == "watch" and args.format != "text" and not args.output:
        raise ValueError("watch with JSON/HTML needs --output so every update remains a valid document.")
    scanner = Scanner()
    previous = None
    while True:
        sessions, data, signature = scanner.scan(args)
        if not sessions:
            data["warnings"].append("No matching local sessions. Run sessionlens doctor, check --project, or specify --path.")
        if signature != previous:
            previous = signature
            if getattr(args, "preview_deep", False):
                from .llm import select_context
                contexts = [{"session_id": item["session_id"], "events": select_context(session, item)} for session, item in list(zip(sessions, data["sessions"]))[:args.deep_limit]]
                preview = json.dumps({"notice": "No data sent. These are the exact event excerpts that --deep would submit, together with a fixed diagnostic system prompt.", "contexts": contexts}, ensure_ascii=False, indent=2) + "\n"
                if args.output:
                    write_private(args.output, preview)
                else:
                    print(preview, end="")
                return 0 if sessions else 1
            if getattr(args, "deep", False):
                from .llm import review
                data["mode"] = "local+model"
                data["privacy"] = "Selected best-effort redacted excerpts were submitted to the explicitly configured model endpoint. No automatic execution or changes."
                for session, item in list(zip(sessions, data["sessions"]))[:args.deep_limit]:
                    print(f"Deep review: {item['source']} {item['id']} (selected excerpts)", file=sys.stderr)
                    try:
                        item["deep_review"] = review(session, item, args.model, args.language)
                    except ValueError as exc:
                        item["warnings"].append(str(exc))
                        data["warnings"].append("A model review failed; local diagnostics remain available.")
                if len(sessions) > args.deep_limit:
                    data["warnings"].append(f"Deep review limited to {args.deep_limit} sessions; remaining sessions use local rules only.")
            output(data, args)
        if args.command != "watch" or args.once:
            if not sessions:
                return 1
            if any("model review failed" in w for w in data["warnings"]):
                return 3
            return 0
        time.sleep(args.interval)


def main(argv=None) -> int:
    # Windows CMD can use a legacy code page. Preserve usability even when a
    # transcript contains characters the console cannot represent.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        argv = ["scan"]
    args = parser().parse_args(argv)
    try:
        return run(args)
    except KeyboardInterrupt:
        print("\nSessionLens stopped.", file=sys.stderr)
        return 130
    except BrokenPipeError:
        return 0
    except (OSError, ValueError) as exc:
        print("sessionlens: " + redact(str(exc)), file=sys.stderr)
        return 2
