"""Transparent heuristics. Scores measure observed process signals, not success."""
import hashlib
import re
from collections import Counter
from datetime import datetime, timezone

from .models import Event, Session
from .privacy import excerpt, redact

RULES = {
    "tool_failure": {
        "title": "Tool execution failures / 工具执行失败",
        "severity": "medium",
        "hypothesis": "Inputs, environment, or tool contracts may need attention. Some failures are expected probes or failing tests.",
        "suggestion": "Inspect the first failing result. Check required inputs and environment before retrying; distinguish expected nonzero exits from execution failures.",
        "candidate_instruction": "When a tool fails, inspect its error and verify the relevant input or precondition before retrying. Treat expected diagnostic failures separately.",
    },
    "failed_retry": {
        "title": "Unchanged retry after failure / 失败后原样重试",
        "severity": "high",
        "hypothesis": "The agent may be retrying without incorporating failure feedback. Transient failures can justify a bounded retry.",
        "suggestion": "Add a retry budget. For deterministic errors, change inputs or repair the precondition; for transient errors, use bounded backoff.",
        "candidate_instruction": "Do not repeat an identical failed tool call without checking whether the failure is transient. For deterministic failures, correct the cause first; stop and explain when the retry budget is exhausted.",
    },
    "user_correction": {
        "title": "Possible user corrections / 疑似用户纠正",
        "severity": "medium",
        "hypothesis": "A user may be restating a missed requirement, but could also be introducing a new requirement or quoting someone else.",
        "suggestion": "Review the cited user messages against the preceding request. Add only confirmed recurring constraints to the project instructions.",
        "candidate_instruction": "Before acting, identify the user's explicit constraints. When corrected, update the plan and check that subsequent actions follow the corrected requirement.",
    },
    "large_output": {
        "title": "Large tool outputs / 工具输出过长",
        "severity": "low",
        "hypothesis": "Large outputs may crowd out useful context. Transcript length is not proof that the model consumed the entire output.",
        "suggestion": "Use targeted searches, bounded reads, and output limits. Retain file references so details can be retrieved when needed.",
        "candidate_instruction": "Prefer targeted reads and bounded tool outputs. If a result is large, narrow the query or keep a concise summary with a retrievable source reference.",
    },
}

CORRECTION = re.compile(
    r"(?:你(?:又|还是|仍然|没有|没按)|我(?:刚才|之前|已经)说|不是这个意思|理解错了|不要再|说了不要|我要的是|"
    r"\b(?:that's not what i|that is not what i|i (?:already|explicitly) (?:said|asked)|you (?:ignored|misunderstood)|stop (?:doing|repeating)|do not do that again)\b)", re.I
)


def evidence(event: Event) -> dict:
    return {"line": event.line, "kind": event.kind, "tool": redact(event.tool), "excerpt": excerpt(event.text or event.arguments), "turn": event.turn}


def analyze(session: Session) -> dict:
    events = session.events
    calls = [e for e in events if e.kind == "tool_call"]
    results = [e for e in events if e.kind == "tool_result"]
    users = [e for e in events if e.kind == "user" and e.text.strip()]
    failures = [e for e in results if e.failed]
    pending_failures: dict[tuple[str, str], tuple[Event, Event]] = {}
    by_id = {e.call_id: e for e in calls if e.call_id}
    retries: list[Event] = []
    retry_evidence: list[Event] = []
    last_turn = None
    for e in events:
        if e.turn != last_turn:
            pending_failures.clear()
            last_turn = e.turn
        if e.kind == "tool_result":
            call = by_id.get(e.call_id)
            if call:
                key = (call.tool, call.arguments)
                if e.failed:
                    pending_failures[key] = (call, e)
                else:
                    pending_failures.pop(key, None)
        elif e.kind == "tool_call":
            key = (e.tool, e.arguments)
            if key in pending_failures:
                _, failure = pending_failures.pop(key)
                retries.append(e)
                retry_evidence.extend([failure, e])
    # Never label the first user message as a correction; no preceding interaction.
    corrections = [e for e in users[1:] if CORRECTION.search(e.text[:2000])]
    large = [e for e in results if len(e.text) > 12000]
    groups = [("tool_failure", failures, failures), ("failed_retry", retries, retry_evidence), ("user_correction", corrections, corrections), ("large_output", large, large)]
    findings = []
    for rule, occurrences, proof in groups:
        if not occurrences:
            continue
        unique = {e.line: e for e in proof}
        findings.append({"rule": rule, **RULES[rule], "count": len(occurrences), "confidence": "medium" if rule == "user_correction" else "high", "validation": "unverified", "evidence": [evidence(e) for e in list(unique.values())[:8]]})
    dimensions = {}
    if results:
        dimensions["tool_reliability"] = {"score": round(100 * (1 - len(failures) / len(results))), "weight": 0.5, "numerator": len(failures), "denominator": len(results), "meaning": "Share of observed tool results without explicit execution failure"}
        dimensions["context_economy"] = {"score": round(100 * (1 - len(large) / len(results))), "weight": 0.2, "numerator": len(large), "denominator": len(results), "meaning": "Share of tool outputs at or below 12,000 characters; a heuristic, not token cost"}
    if calls and failures:
        dimensions["retry_discipline"] = {"score": max(0, round(100 * (1 - len(retries) / max(len(failures), 1)))), "weight": 0.3, "numerator": len(retries), "denominator": len(failures), "meaning": "Penalty for identical retries after an observed failure within the same user turn"}
    score = round(sum(d["score"] * d["weight"] for d in dimensions.values()) / sum(d["weight"] for d in dimensions.values())) if dimensions else None
    warnings = list(session.warnings)
    if len(results) < 5:
        warnings.append("Small or missing tool sample: the process score has limited coverage.")
    matched = sum(e.call_id in by_id for e in results)
    if matched < len(results):
        warnings.append("Some tool results have no matching call; retry diagnosis may be incomplete.")
    if calls and len(results) < len(calls):
        warnings.append("Some calls have no recorded result. The session may be active or incomplete; no failure penalty is assigned.")
    return {
        "schema_version": 1,
        "id": hashlib.sha256(session.path.encode()).hexdigest()[:12],
        "source": session.source,
        "session_id": redact(session.session_id),
        "path": redact(session.path),
        "project": redact(session.cwd),
        "title": excerpt(users[0].text, 100) if users else "Session without a visible user task",
        "score": score,
        "score_label": "Observed process quality / 可观察过程质量",
        "score_version": "heuristic-v1",
        "task_success": "unknown",
        "coverage": "limited" if session.truncated or session.malformed or len(results) < 5 or matched < len(results) else "observed-tool-events",
        "dimensions": dimensions,
        "stats": {"events": len(events), "user_messages": len(users), "tool_calls": len(calls), "tool_results": len(results), "tool_failures": len(failures), "unchanged_failed_retries": len(retries), "possible_corrections": len(corrections), "large_outputs": len(large), "lines_read": session.lines},
        "findings": sorted(findings, key=lambda f: {"high": 0, "medium": 1, "low": 2}[f["severity"]]),
        "warnings": [redact(w) for w in warnings],
    }


def report(sessions: list[Session]) -> dict:
    items = [analyze(s) for s in sessions]
    counts = Counter(f["rule"] for item in items for f in item["findings"])
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "local-heuristic",
        "privacy": "Local analysis; no network requests. Excerpts are best-effort redacted. Reports may still contain sensitive business content.",
        "score_notice": "Scores describe observable process signals, not task success or prompt quality. A score of 100 means no measured penalty, not a perfect agent. Compare only similar tasks and coverage. Suggestions are unverified until tested.",
        "sessions": items,
        "recurring_patterns": [{"rule": rule, "title": RULES[rule]["title"], "sessions": count} for rule, count in counts.most_common() if count > 1],
        "warnings": [],
    }
