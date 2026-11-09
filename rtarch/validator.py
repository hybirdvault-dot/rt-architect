"""Validate AI-generated explanations before they reach the report.

Three independent checks, any of which rejects the output:

(a) the response identifies the finding it claims to explain;
(b) every numeric value in the finding's evidence appears in the explanation,
    so the model cannot invent or distort a number;
(c) the explanation does not name QNX APIs outside the approved allowlist,
    so the model cannot recommend calls that do not exist.

A rejected response is discarded and the deterministic template is used
instead. The report is always produced.
"""

import re
from typing import Dict, List

from .models import Finding

# QNX APIs this project actually uses, plus the ones an explainer may
# legitimately recommend. Anything else is treated as hallucination.
APPROVED_APIS = [
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
]

# Identifiers that look like QNX APIs.  Restricting the pattern to QNX-ish
# prefixes keeps ordinary prose ("Observed", "Service") from being flagged.
_QNX_API_RE = re.compile(
    r"\b((?:Msg|Connect|Channel|Sched|pthread|slog2|name_|delay|Timer|Sync|Clock)"
    r"[A-Za-z0-9_]*)\b"
)


def _numeric_forms(value: object) -> List[str]:
    """Every string form a number may legitimately take in prose."""
    forms = set()

    if isinstance(value, bool) or value is None:
        return sorted(forms)

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

    return sorted(forms)


def _numbers_match(explanation: str, finding: Finding) -> bool:
    for key, value in finding.observed.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        forms = _numeric_forms(value)
        if forms and not any(form in explanation for form in forms):
            return False
    return True


def _apis_allowed(explanation: str) -> bool:
    mentioned = set(_QNX_API_RE.findall(explanation))
    for name in mentioned:
        if name not in APPROVED_APIS:
            return False
    return True


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
    if not _numbers_match(explanation, finding):
        return False

    # (c) no unknown QNX APIs
    if not _apis_allowed(explanation):
        return False

    plan = output.get("refactor_plan")
    if plan is not None and not isinstance(plan, list):
        return False

    return True
