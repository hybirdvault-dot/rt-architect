#!/usr/bin/env python3
"""Reference implementation for the P0-2 validator fix.

Self-contained and runnable. Reproduces every bug the original validator accepted
and demonstrates the fixed logic. Run:

    python verify/reference_validator_fix.py

All 7 regression tests must pass.

The five fixes (see Fix-and-Upgrade Plan P0-2):
  1. invented numbers      -> bidirectional number check (explanation subset of ground truth)
  2. substring collision   -> token-boundary regex (a number bounded by non-word chars)
  3. prefix-regex blind spot -> explicit allowlist + call-site/prefix identifier scan
  4. refactor_plan unscanned -> plan items scanned for numbers and APIs
  5. wrong field scanned   -> ground truth is evidence (primary) plus observed/thresholds
"""

import re
import sys

APPROVED_APIS = frozenset({
    "MsgSend", "MsgReceive", "MsgReply", "ChannelCreate", "ConnectAttach",
    "slog2", "slog2f", "slog2info", "name_attach", "name_open", "delay",
    "pthread_mutexattr_setprotocol", "pthread_setschedparam", "SchedSet",
})

# Identifier prefixes that mark a token as API-shaped. Deliberately broader than the
# original Msg|Connect|... list so unprefixed-but-QNX names (mmap, ThreadCreate,
# InterruptAttachEvent) cannot slip through.
_API_PREFIXES = (
    "Msg", "Connect", "Channel", "Sched", "pthread", "slog2", "name_", "delay",
    "Timer", "Sync", "Clock", "Interrupt", "Thread", "mmap", "munmap", "shm_",
    "dispatch", "procmgr", "select_",
)

# A number token: digits with an optional decimal part and an optional percent sign,
# bounded by non-word / non-dot / non-hyphen characters so "p95" and "F-001" do not
# yield spurious numbers.
_NUMBER_RE = re.compile(r"(?<![\w.\-])(\d+(?:\.\d+)?)(%?)(?![\w]|\.\d)")
_CALL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_IDENT_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\b")


def extract_numbers(text):
    """Every numeric token in prose, as written (e.g. '12.447', '75.0%')."""
    return [m.group(1) + m.group(2) for m in _NUMBER_RE.finditer(text)]


def _numeric_forms(value):
    """Every string form a numeric ground-truth value may legitimately take."""
    forms = set()
    if isinstance(value, bool) or value is None:
        return forms
    if isinstance(value, int):
        forms.add(str(value))
        if abs(value) >= 100000:            # nanoseconds -> milliseconds
            forms.add(f"{value / 1e6:.1f}")
            forms.add(f"{value / 1e6:.2f}")
    elif isinstance(value, float):
        for digits in (0, 1, 2, 3, 4):
            forms.add(f"{value:.{digits}f}")
        if 0.0 < value <= 1.0:              # ratio -> percentage
            forms.add(f"{value * 100:.0f}%")
            forms.add(f"{value * 100:.1f}%")
        if abs(value) >= 100000:
            forms.add(f"{value / 1e6:.1f}")
            forms.add(f"{value / 1e6:.2f}")
    return forms


def _ground_truth_numbers(finding):
    """Numbers the explanation is allowed to contain (evidence primary + observed/thresholds)."""
    allowed = set()
    for value in list(finding.get("observed", {}).values()) + \
               list(finding.get("thresholds", {}).values()):
        allowed |= _numeric_forms(value)
    for text in list(finding.get("evidence", [])) + [
        finding.get("condition", ""), finding.get("title", ""),
        finding.get("finding_id", ""),
    ]:
        allowed.update(extract_numbers(text))
    return allowed


def numbers_match(explanation, finding, require_observed=True):
    """Return (ok, violations). Rejects invented numbers and missing observed values."""
    violations = []
    explained = set(extract_numbers(explanation))
    allowed = _ground_truth_numbers(finding)

    for token in sorted(explained - allowed):
        violations.append(f"invented number {token!r} not present in the finding evidence")

    if require_observed:
        for key, value in finding.get("observed", {}).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            if not (_numeric_forms(value) & explained):
                violations.append(f"observed value {key}={value!r} is not stated in the explanation")

    return (not violations), violations


def find_unknown_apis(text):
    """Identifiers that look like API references but are not in the allowlist."""
    unknown = set()
    for m in _CALL_RE.finditer(text):
        name = m.group(1)
        if name not in APPROVED_APIS and (name[0].isupper() or "_" in name):
            unknown.add(name)
    for m in _IDENT_RE.finditer(text):
        name = m.group(1)
        if name in APPROVED_APIS:
            continue
        if name.startswith(_API_PREFIXES):
            unknown.add(name)
    return sorted(unknown)


def validate(output, finding):
    """True only when the AI response is safe to publish."""
    if not isinstance(output, dict):
        return False
    if output.get("finding_id") != finding.get("finding_id"):
        return False
    explanation = output.get("explanation")
    if not isinstance(explanation, str) or not explanation.strip():
        return False

    ok, _violations = numbers_match(explanation, finding)
    if not ok:
        return False

    texts = [explanation]
    plan = output.get("refactor_plan")
    if plan is None:
        plan = []
    if not isinstance(plan, list):
        return False
    for item in plan:
        if not isinstance(item, str):
            return False
        texts.append(item)

    for text in texts:
        if find_unknown_apis(text):
            return False
        ok, _violations = numbers_match(text, finding, require_observed=(text is explanation))
        if not ok:
            return False
    return True


# --------------------------------------------------------------------------- tests

def _finding(**over):
    base = {
        "finding_id": "F-001", "rule_id": "BOTTLENECK-001", "severity": "critical",
        "title": "svc is an architectural bottleneck",
        "condition": "in_degree > 3 AND p95_processing_ns > deadline_ns * 0.5",
        "node": "svc",
        "observed": {"in_degree": 3, "p95_processing_ms": 7.0},
        "thresholds": {"max_in_degree": 3},
        "evidence": ["svc has in-degree 3"],
        "recommendation": "Split the service.",
    }
    base.update(over)
    return base


def _payload(finding, **over):
    nums = [str(v) for v in finding["observed"].values()
            if isinstance(v, (int, float)) and not isinstance(v, bool)]
    out = {
        "finding_id": finding["finding_id"],
        "explanation": f"{finding['title']}. Observed values are " + ", ".join(nums) + ".",
        "refactor_plan": ["split the service"],
    }
    out.update(over)
    return out


def _run():
    results = []

    def check(name, cond):
        results.append((name, bool(cond)))

    f = _finding()

    # 1. invented extra number alongside the full truth -> reject
    check("invented_extra_number_rejected",
          validate(_payload(f, explanation="in_degree 3, p95 7.0, but the queue held 9999.0 messages"), f) is False)

    # 2. substring collision: missing 7.0, "7" only inside "p95" -> reject
    check("substring_collision_rejected",
          validate(_payload(f, explanation="in_degree 3, p95 processing was bad."), f) is False)

    # 3. distorted number (rounding / transposition / unit) -> reject
    check("distorted_rounding_rejected",
          validate(_payload(f, explanation="in_degree 3, p95 about 70.0 ms."), f) is False)

    # 4. hallucinated APIs: unprefixed and prefixed -> reject
    check("hallucinated_unprefixed_api_rejected",
          validate(_payload(f, explanation="in_degree 3, p95 7.0. Use mmap and ThreadCreate."), f) is False)
    check("hallucinated_prefixed_api_rejected",
          validate(_payload(f, explanation="in_degree 3, p95 7.0. Call MsgFrobnicate() to fix it."), f) is False)

    # 5. refactor_plan injection (API + invented number) -> reject
    check("refactor_plan_injection_rejected",
          validate(_payload(f, refactor_plan=["Call QuantumTeleportKernel(0xdead)", "set in_degree to 9999"]), f) is False)

    # 6. valid output -> accept
    check("valid_output_accepted", validate(_payload(f), f) is True)

    # 7. percentage form of a ratio -> accept
    fr = _finding(observed={"low_priority_work_ratio": 0.75}, evidence=["low priority work is 75.0%"],
                  thresholds={}, condition="")
    check("percentage_form_accepted",
          validate({"finding_id": "F-001",
                    "explanation": "Low-priority work is 75.0% of received traffic.",
                    "refactor_plan": []}, fr) is True)

    passed = sum(1 for _, ok in results if ok)
    for name, ok in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"\n{passed}/{len(results)} tests passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(_run())
