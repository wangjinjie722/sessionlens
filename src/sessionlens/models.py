from dataclasses import dataclass, field


@dataclass
class Event:
    line: int
    kind: str
    text: str = ""
    tool: str = ""
    call_id: str = ""
    arguments: str = ""
    failed: bool = False
    timestamp: str = ""
    turn: int = 0


@dataclass
class Session:
    source: str
    path: str
    session_id: str = ""
    cwd: str = ""
    events: list[Event] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    lines: int = 0
    malformed: int = 0
    truncated: bool = False
    recognized: int = 0
