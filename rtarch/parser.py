"""Parse RTARCH structured events out of a raw slog2 capture.

Threat-4 shield: only lines carrying the ``RTARCH`` marker are considered.
The filter is implemented in pure Python (no shell ``grep`` dependency) so the
tool stays portable and unit-testable, while behaving identically to the
documented ``grep "RTARCH"`` pre-filter.
"""

import re
from typing import List, Optional, Tuple

from .models import Phase, RTArchEvent

RTARCH_MARKER = "RTARCH"

# The marker is searched anywhere in the line so that real slog2 headers
# (timestamp / cpu / tid prefixes) do not defeat the parser.
_RTARCH_LINE_RE = re.compile(r"RTARCH\s+(.+)$")
_KEY_VALUE_RE = re.compile(r"(\w+)=(\S+)")

_REQUIRED_FIELDS = (
    "v",
    "ts_ns",
    "phase",
    "trace_id",
    "msg_id",
    "src_pid",
    "src_name",
    "dst_pid",
    "dst_name",
    "msg_type",
    "prio",
)


def filter_rtarch_lines(raw_log_path: str) -> List[str]:
    """Return only the lines that carry RTARCH events, stripped of whitespace."""
    matched: List[str] = []
    with open(raw_log_path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if RTARCH_MARKER in line:
                matched.append(line.strip())
    return matched


def parse_event(line: str) -> Optional[RTArchEvent]:
    """Parse one RTARCH line, returning ``None`` when it is malformed."""
    match = _RTARCH_LINE_RE.search(line.strip())
    if not match:
        return None

    pairs = dict(_KEY_VALUE_RE.findall(match.group(1)))
    if any(field not in pairs for field in _REQUIRED_FIELDS):
        return None

    try:
        return RTArchEvent(
            v=int(pairs["v"]),
            ts_ns=int(pairs["ts_ns"]),
            phase=Phase(pairs["phase"]),
            trace_id=int(pairs["trace_id"]),
            msg_id=int(pairs["msg_id"]),
            src_pid=int(pairs["src_pid"]),
            src_name=pairs["src_name"],
            dst_pid=int(pairs["dst_pid"]),
            dst_name=pairs["dst_name"],
            msg_type=pairs["msg_type"],
            prio=int(pairs["prio"]),
        )
    except (ValueError, KeyError):
        return None


def parse_log_with_stats(raw_log_path: str) -> Tuple[List[RTArchEvent], int]:
    """Parse a raw log file.

    Returns ``(events, skipped)`` where ``skipped`` counts RTARCH-marked lines
    that could not be parsed (malformed / missing fields).
    """
    events: List[RTArchEvent] = []
    skipped = 0

    for line in filter_rtarch_lines(raw_log_path):
        event = parse_event(line)
        if event is None:
            skipped += 1
        else:
            events.append(event)

    return events, skipped


def parse_log(raw_log_path: str) -> List[RTArchEvent]:
    """Parse a raw log file and return only the successfully parsed events."""
    events, _ = parse_log_with_stats(raw_log_path)
    return events
