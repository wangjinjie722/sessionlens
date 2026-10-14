"""Best-effort secret removal; no claim of exhaustive PII detection."""
import re
from pathlib import Path

_PATTERNS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "[REDACTED PRIVATE KEY]"),
    (re.compile(r"\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{15,}|github_pat_[A-Za-z0-9_]{15,}|AKIA[A-Z0-9]{16})\b"), "[REDACTED TOKEN]"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{8,}"), r"\1[REDACTED]"),
    (re.compile(r'''(?i)((?:[\w-]*(?:api[_-]?key|secret|password|access[_-]?token|auth[_-]?token))["']?\s*[:=]\s*)(?:"[^"\n]*"|'[^'\n]*'|[^\s,;}]+)'''), r"\1[REDACTED]"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[REDACTED EMAIL]"),
    (re.compile(r"(?i)(https?://)[^\s/@:]+:[^\s/@]+@"), r"\1[REDACTED]@"),
]


def redact(text: str) -> str:
    text = str(text).replace(str(Path.home()), "~")
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    # Keep untrusted log text from emitting terminal control sequences.
    return re.sub(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]", "", text)


def excerpt(text: str, limit: int = 280) -> str:
    text = redact(text).strip()
    return text if len(text) <= limit else text[:limit] + "…"
