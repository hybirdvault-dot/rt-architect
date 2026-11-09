"""Tests for the optional AI explainer and its output validator."""

import os
import time

import pytest

from rtarch.ai import deterministic_fallback, explain_findings
from rtarch.models import Finding
from rtarch.validator import validate_ai_output


def _finding(**overrides):
    values = dict(
        finding_id="F-001",
        rule_id="BOTTLENECK-001",
        severity="critical",
        title="svc is an architectural bottleneck",
        condition="in_degree > 3 AND p95_processing_ns > deadline_ns * 0.5",
        node="svc",
        observed={"in_degree": 3, "p95_processing_ms": 7.0},
        thresholds={"max_in_degree": 3},
        evidence=["svc has in-degree 3"],
        recommendation="Split the service into fast-path and slow-path handlers.",
    )
    values.update(overrides)
    return Finding(**values)


def _valid_payload(finding):
    values = [
        f"{value}"
        for value in finding.observed.values()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    return {
        "finding_id": finding.finding_id,
        "explanation": (
            f"{finding.title}. Observed values are " + ", ".join(values) + "."
        ),
        "refactor_plan": ["split the service"],
    }


# --- (a) finding_id ----------------------------------------------------


def test_accepts_valid_output():
    finding = _finding()
    assert validate_ai_output(_valid_payload(finding), finding) is True


def test_rejects_missing_finding_id():
    finding = _finding()
    payload = _valid_payload(finding)
    del payload["finding_id"]
    assert validate_ai_output(payload, finding) is False


def test_rejects_wrong_finding_id():
    finding = _finding()
    payload = _valid_payload(finding)
    payload["finding_id"] = "F-999"
    assert validate_ai_output(payload, finding) is False


# --- (b) numbers must match evidence -----------------------------------


def test_rejects_invented_number():
    finding = _finding()
    payload = _valid_payload(finding)
    payload["explanation"] = "svc has in-degree 3 and p95 processing of 99.0 ms."
    assert validate_ai_output(payload, finding) is False


def test_rejects_missing_observed_value():
    finding = _finding()
    payload = _valid_payload(finding)
    payload["explanation"] = "svc has in-degree 3."
    assert validate_ai_output(payload, finding) is False


def test_accepts_percentage_form_of_ratio():
    finding = _finding(observed={"low_priority_work_ratio": 0.75})
    payload = {
        "finding_id": "F-001",
        "explanation": "Low-priority work is 75.0% of received traffic.",
        "refactor_plan": [],
    }
    assert validate_ai_output(payload, finding) is True


# --- (c) approved QNX APIs only ----------------------------------------


def test_rejects_unknown_qnx_api():
    finding = _finding()
    payload = _valid_payload(finding)
    payload["explanation"] += " Call MsgFrobnicate() to fix it."
    assert validate_ai_output(payload, finding) is False


def test_allows_approved_qnx_api():
    finding = _finding()
    payload = _valid_payload(finding)
    payload["explanation"] += " Use MsgSend() with a priority channel."
    assert validate_ai_output(payload, finding) is True


def test_ordinary_prose_is_not_flagged_as_an_api():
    finding = _finding()
    payload = _valid_payload(finding)
    payload["explanation"] += " The Service observed this behaviour."
    assert validate_ai_output(payload, finding) is True


# --- shape -------------------------------------------------------------


def test_rejects_non_dict_output():
    assert validate_ai_output("not a dict", _finding()) is False


def test_rejects_malformed_refactor_plan():
    finding = _finding()
    payload = _valid_payload(finding)
    payload["refactor_plan"] = "split it"
    assert validate_ai_output(payload, finding) is False


# --- fallback behaviour ------------------------------------------------


def test_disabled_ai_is_a_noop():
    finding = _finding()
    result = explain_findings([finding], {}, enabled=False)
    assert result[0].ai_explanation is None


def test_fallback_when_provider_unconfigured(monkeypatch):
    monkeypatch.delenv("API_BASE_URL", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    finding = _finding()
    explain_findings([finding], {"deadline_ms": 5.0}, enabled=True)
    assert finding.ai_explanation
    assert "in-degree 3" in finding.ai_explanation
    assert finding.ai_refactor_plan == []


def test_fallback_when_ai_returns_invalid_output(monkeypatch):
    import rtarch.ai as ai_module

    monkeypatch.setenv("API_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.setattr(
        ai_module,
        "_call_ai",
        lambda finding, scenario: {"finding_id": "F-999", "explanation": "nope"},
    )
    finding = _finding()
    explain_findings([finding], {"deadline_ms": 5.0}, enabled=True)
    assert finding.ai_explanation
    assert "in-degree 3" in finding.ai_explanation


def test_fallback_when_ai_raises(monkeypatch):
    import rtarch.ai as ai_module

    def boom(finding, scenario):
        raise RuntimeError("provider down")

    monkeypatch.setattr(ai_module, "_call_ai", boom)
    finding = _finding()
    explain_findings([finding], {"deadline_ms": 5.0}, enabled=True)
    assert finding.ai_explanation


def test_ai_call_is_bounded_by_timeout(monkeypatch):
    import rtarch.ai as ai_module

    def slow(finding, scenario):
        time.sleep(2.0)
        return _valid_payload(finding)

    monkeypatch.setattr(ai_module, "_call_ai", slow)
    monkeypatch.setattr(ai_module, "AI_TIMEOUT_S", 0.2)

    finding = _finding()
    start = time.monotonic()
    explain_findings([finding], {"deadline_ms": 5.0}, enabled=True)
    elapsed = time.monotonic() - start

    assert finding.ai_explanation          # deterministic fallback was used
    assert elapsed < 1.5                   # did not wait for the slow call


def test_deterministic_fallback_is_always_available():
    finding = _finding()
    text = deterministic_fallback(finding, {"deadline_ms": 5.0})
    assert "svc" in text
    assert "7.00" in text
