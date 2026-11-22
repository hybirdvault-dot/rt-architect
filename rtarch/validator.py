"""Validate AI-generated explanations before they reach the report.

Three independent checks, any of which rejects the output:

(a) the response identifies the finding it claims to explain;
(b) the explanation states the finding's observed values and contains no number
    that is absent from the finding's evidence, so the model cannot invent or
    distort a number;
(c) the explanation (and the refactor plan) name no QNX API outside the
    approved allowlist, so the model cannot recommend calls that do not exist.

A rejected response is discarded and the deterministic template is used
instead. The report is always produced.

Number matching is token-based, not substring-based: a value is only "present"
when it appears as a standalone numeric token, so a missing deadline cannot be
satisfied by the "5" inside "p95". API matching scans call sites and
API-shaped identifiers against an explicit allowlist, so unprefixed names such
as ``mmap`` or ``ThreadCreate`` cannot slip past a prefix regex.
"""

import re

from .models import Finding

# QNX APIs this project actually uses, plus the ones an explainer may
# legitimately recommend. Anything else is treated as hallucination.
APPROVED_APIS = frozenset({
    "MsgSend",
    "MsgReceive",
    "MsgReply",
    "ChannelCreate",
    "ConnectAttach",
    "slog2",
    "slog2f",
    "slog2info",
    "name_attach",
    "name_open",
    "delay",
    "pthread_mutexattr_setprotocol",
    "pthread_setschedparam",
    "SchedSet",
})

# Identifier prefixes that mark a token as API-shaped. Deliberately broader than
# a narrow Msg|Connect|... list so unprefixed-but-QNX names (mmap, ThreadCreate,
# InterruptAttachEvent) cannot slip through.
_API_PREFIXES = (
    "Msg", "Connect", "Channel", "Sched", "pthread", "slog2", "name_", "delay",
    "Timer", "Sync", "Clock", "Interrupt", "Thread", "mmap", "munmap", "shm_",
    "dispatch", "procmgr", "select_",
)

# A number token: digits with an optional decimal part and an optional percent
# sign, bounded by non-word / non-dot / non-hyphen characters so "p95" and
# "F-001" do not yield spurious numbers.
_NUMBER_RE = re.compile(r"(?<![\w.\-])(\d+(?:\.\d+)?)(%?)(?![\w]|\.\d)")
_CALL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_IDENT_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\b")


def extract_numbers(text: str) -> list[str]:
    """Every numeric token in prose, as written (e.g. ``12.447``, ``75.0%``)."""
    return [m.group(1) + m.group(2) for m in _NUMBER_RE.finditer(text)]


def _numeric_forms(value: object) -> set:
    """Every string form a numeric ground-truth value may legitimately take."""
    forms: set = set()

    if isinstance(value, bool) or value is None:
        return forms

    if isinstance(value, int):
        forms.add(str(value))
        if abs(value) >= 100000:          # nanoseconds -> milliseconds
            forms.add(f"{value / 1e6:.1f}")
            forms.add(f"{value / 1e6:.2f}")
    elif isinstance(value, float):
        for digits in (0, 1, 2, 3, 4):
            forms.add(f"{value:.{digits}f}")
        if 0.0 < value <= 1.0:            # ratio -> percentage
            forms.add(f"{value * 100:.0f}%")
            forms.add(f"{value * 100:.1f}%")
        if abs(value) >= 100000:
            forms.add(f"{value / 1e6:.1f}")
            forms.add(f"{value / 1e6:.2f}")

    return forms


def _ground_truth_numbers(finding: Finding) -> set:
    """Numbers the explanation is allowed to contain.

    Evidence is the primary ground truth; observed and threshold values and the
    condition/title text are included so the model can quote them.
    """
    allowed = set()
    for value in list(finding.observed.values()) + list(finding.thresholds.values()):
        allowed |= _numeric_forms(value)
    for text in list(finding.evidence) + [
        finding.condition, finding.title, finding.finding_id,
    ]:
        allowed.update(extract_numbers(text))
    return allowed


def numbers_match(explanation: str, finding: Finding, require_observed: bool = True) -> tuple[bool, list[str]]:
    """Return ``(ok, violations)``.

    Rejects numbers that are absent from the finding's evidence (invented or
    distorted) and, when ``require_observed`` is set, observed values that the
    explanation never states.
    """
    violations: list[str] = []
    explained = set(extract_numbers(explanation))
    allowed = _ground_truth_numbers(finding)

    for token in sorted(explained - allowed):
        violations.append(f"invented number {token!r} not present in the finding evidence")

    if require_observed:
        for key, value in finding.observed.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            if not (_numeric_forms(value) & explained):
                violations.append(f"observed value {key}={value!r} is not stated in the explanation")

    return (not violations), violations


def find_unknown_apis(text: str) -> list[str]:
    """Identifiers that look like API references but are not in the allowlist."""
    unknown = set()
    for match in _CALL_RE.finditer(text):
        name = match.group(1)
        if name not in APPROVED_APIS and (name[0].isupper() or "_" in name):
            unknown.add(name)
    for match in _IDENT_RE.finditer(text):
        name = match.group(1)
        if name in APPROVED_APIS:
            continue
        if name.startswith(_API_PREFIXES):
            unknown.add(name)
    return sorted(unknown)


def validate_ai_output(output: object, finding: Finding) -> bool:
    """Return True only when the AI response is safe to publish."""
    if not isinstance(output, dict):
        return False

    # (a) the response must identify this exact finding
    if output.get("finding_id") != finding.finding_id:
        return False

    explanation = output.get("explanation")
    if not isinstance(explanation, str) or not explanation.strip():
        return False

    # (b) numbers must match the evidence
    ok, _ = numbers_match(explanation, finding, require_observed=True)
    if not ok:
        return False

    # (c) no unknown QNX APIs in the explanation or the refactor plan
    plan = output.get("refactor_plan")
    if plan is None:
        plan = []
    if not isinstance(plan, list):
        return False

    texts = [explanation]
    for item in plan:
        if not isinstance(item, str):
            return False
        texts.append(item)

    for index, text in enumerate(texts):
        if find_unknown_apis(text):
            return False
        # plan items are checked for invented numbers only; they are not
        # required to restate the observed values
        ok, _ = numbers_match(text, finding, require_observed=(index == 0))
        if not ok:
            return False

    return True
