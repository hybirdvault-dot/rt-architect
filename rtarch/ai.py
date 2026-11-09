"""Optional AI explainer.

Deterministic-first: the rule engine is the source of truth, and this module
only annotates its findings. It is guarded by three independent mechanisms so
that a broken AI provider can never break the analysis:

1. ``try``/``except`` around every call;
2. a hard 5 second wall-clock bound (daemon thread + join timeout), on top of
   the HTTP client's own timeout;
3. output validation, then a deterministic template fallback.

Configuration is entirely through environment variables so that any
OpenAI-compatible endpoint can be used:

    API_BASE_URL   e.g. https://longcat.ai/platform/v1   (no default)
    API_KEY        the provider API key                 (no default)
    MODEL_NAME     e.g. gpt-4o-mini                    (default: gpt-4o-mini)

If ``API_BASE_URL`` or ``API_KEY`` is unset, AI is skipped and the report is
produced from deterministic templates only.
"""

import json
import os
import queue
import threading
from typing import Dict, List, Optional

from .models import Finding
from .validator import validate_ai_output

AI_TIMEOUT_S = 5.0

FALLBACK_TEMPLATES = {
    "CRITICAL-PATH-001": (
        "Service {node} has a p95 processing time of {p95_ms:.2f} ms against a "
        "deadline of {deadline_ms:.2f} ms. The service sits on the critical path, "
        "so every request that reaches it misses the deadline. Identify the "
        "slowest incoming edge and reduce its latency."
    ),
    "BOTTLENECK-001": (
        "Service {node} has in-degree {in_degree} and a p95 processing time of "
        "{p95_ms:.2f} ms, which exceeds {fraction:.0%} of the {deadline_ms:.2f} ms "
        "deadline. It concentrates traffic and is slower than the deadline "
        "allows, so it is an architectural bottleneck. Split it into a fast path "
        "and a slow path."
    ),
    "HEAD-OF-LINE-001": (
        "Service {node} blocked {blocked} high-priority request(s) while "
        "low-priority work accounted for {ratio:.1%} of received traffic. A "
        "single FIFO server lets background traffic delay critical requests. "
        "Serve priorities on separate channels."
    ),
    "QUEUE-WAIT-001": (
        "On the edge into {node} the p95 queue wait is {qw_ms:.2f} ms out of a "
        "p95 total latency of {total_ms:.2f} ms ({ratio:.1%}). Receivers are "
        "spending more time waiting than senders spend working, so the server is "
        "overloaded or under-threaded."
    ),
    "SPOF-001": (
        "Service {node} is on the critical path with in-degree {in_degree}. If it "
        "fails, the critical path fails with it. Add redundancy or failover; no "
        "amount of thread splitting removes a single point of failure."
    ),
}

GENERIC_FALLBACK = (
    "{title}. Observed: {observed}. Recommendation: {recommendation}"
)


def explain_findings(
    findings: List[Finding],
    scenario: Dict,
    enabled: bool = False,
) -> List[Finding]:
    """Attach an explanation to every finding.

    With ``enabled=False`` (the default) this is a no-op and the deterministic
    core is untouched. With ``enabled=True`` each finding gets either a
    validated AI explanation or the deterministic template.
    """
    if not enabled:
        return findings

    for finding in findings:
        try:
            result = _call_ai_guarded(finding, scenario)
            if result is None or not validate_ai_output(result, finding):
                raise ValueError("AI output failed validation")
            finding.ai_explanation = result["explanation"]
            finding.ai_refactor_plan = list(result.get("refactor_plan") or [])
        except Exception:
            finding.ai_explanation = deterministic_fallback(finding, scenario)
            finding.ai_refactor_plan = []

    return findings


def deterministic_fallback(finding: Finding, scenario: Dict) -> str:
    """A deterministic, always-available explanation."""
    template = FALLBACK_TEMPLATES.get(finding.rule_id, GENERIC_FALLBACK)

    if finding.rule_id == "QUEUE-WAIT-001":
        observed = finding.observed
        return template.format(
            node=finding.node or "unknown",
            qw_ms=observed.get("p95_queue_wait_ms", 0.0),
            total_ms=observed.get("p95_total_ms", 0.0),
            ratio=observed.get("ratio", 0.0),
        )

    if finding.rule_id == "BOTTLENECK-001":
        observed = finding.observed
        return template.format(
            node=finding.node or "unknown",
            in_degree=observed.get("in_degree", 0),
            p95_ms=observed.get("p95_processing_ms", 0.0),
            fraction=finding.thresholds.get("processing_deadline_fraction", 0.5),
            deadline_ms=scenario.get("deadline_ms", 5.0),
        )

    if finding.rule_id == "CRITICAL-PATH-001":
        observed = finding.observed
        return template.format(
            node=finding.node or "unknown",
            p95_ms=observed.get("p95_processing_ms", 0.0),
            deadline_ms=observed.get("deadline_ms", scenario.get("deadline_ms", 5.0)),
        )

    if finding.rule_id == "HEAD-OF-LINE-001":
        observed = finding.observed
        return template.format(
            node=finding.node or "unknown",
            blocked=observed.get("high_priority_blocked_count", 0),
            ratio=observed.get("low_priority_work_ratio", 0.0),
        )

    if finding.rule_id == "SPOF-001":
        observed = finding.observed
        return template.format(
            node=finding.node or "unknown",
            in_degree=observed.get("in_degree", 0),
        )

    return template.format(
        title=finding.title,
        observed=finding.observed,
        recommendation=finding.recommendation,
    )


def _call_ai_guarded(finding: Finding, scenario: Dict) -> Optional[Dict]:
    """Run the AI call in a daemon thread and hard-bound it to 5 seconds."""
    result_queue: "queue.Queue" = queue.Queue(maxsize=1)

    def worker() -> None:
        try:
            result_queue.put((_call_ai(finding, scenario), None))
        except Exception as exc:            # noqa: BLE001 - re-raised below
            result_queue.put((None, exc))

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(AI_TIMEOUT_S)

    if thread.is_alive():
        raise TimeoutError(f"AI call exceeded {AI_TIMEOUT_S:.0f}s")

    result, error = result_queue.get()
    if error is not None:
        raise error
    return result


def _build_messages(finding: Finding, scenario: Dict) -> List[Dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are a QNX real-time systems architect explaining a "
                "deterministic analysis finding. Respond with JSON only: "
                '{"finding_id": string, "explanation": string, '
                '"refactor_plan": string[]}. '
                "Every number in the explanation must come from the finding's "
                "observed values. Only reference QNX APIs that actually exist."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "scenario": scenario.get("scenario"),
                    "deadline_ms": scenario.get("deadline_ms"),
                    "finding": finding.model_dump(),
                },
                indent=2,
            ),
        },
    ]


def _call_ai(finding: Finding, scenario: Dict) -> Optional[Dict]:
    """Call an OpenAI-compatible chat endpoint. Raises on any failure."""
    base_url = os.environ.get("API_BASE_URL")
    api_key = os.environ.get("API_KEY")

    if not base_url or not api_key:
        raise RuntimeError("AI provider not configured (API_BASE_URL / API_KEY)")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "the 'openai' package is required for --ai; install "
            "requirements-ai.txt or run without --ai"
        ) from exc

    client = OpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=AI_TIMEOUT_S,
        max_retries=0,
    )

    model = os.environ.get("MODEL_NAME") or "gpt-4o-mini"

    response = client.chat.completions.create(
        model=model,
        messages=_build_messages(finding, scenario),
        response_format={"type": "json_object"},
        timeout=AI_TIMEOUT_S,
    )

    content = response.choices[0].message.content
    if not content:
        raise ValueError("empty AI response")

    return json.loads(content)
