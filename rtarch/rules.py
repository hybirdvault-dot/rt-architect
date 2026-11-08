"""Deterministic rule engine.

Five rules, each emitting evidence-backed findings.  No AI, no randomness,
no wall-clock input: identical inputs always produce identical findings.

Output ordering is part of the contract:

    1. severity  (critical -> warning -> info)
    2. node name (alphabetical)
    3. rule id   (alphabetical)

Findings are deduplicated by ``(rule_id, node)`` and then numbered
sequentially in final display order (``F-001`` ... ).
"""

from collections import OrderedDict
from typing import Dict, List

from .models import EdgeMetrics, Finding, NodeMetrics

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def run_rules(
    node_metrics: Dict[str, NodeMetrics],
    edge_metrics: Dict[str, EdgeMetrics],
    scenario: Dict,
) -> List[Finding]:
    """Run all five deterministic rules and return ordered, deduplicated findings."""
    thresholds = scenario.get("thresholds", {})
    deadline_ns = int(float(scenario.get("deadline_ms", 5.0)) * 1_000_000)

    raw: List[Finding] = []
    raw.extend(_rule_critical_path_deadline(node_metrics, scenario, deadline_ns))
    raw.extend(_rule_bottleneck(node_metrics, deadline_ns, thresholds))
    raw.extend(_rule_head_of_line(node_metrics, thresholds))
    raw.extend(_rule_queue_wait(edge_metrics, thresholds))
    raw.extend(_rule_single_point_of_failure(node_metrics, thresholds))

    return _finalize(raw)


def _finalize(findings: List[Finding]) -> List[Finding]:
    """Deduplicate, order and sequentially number findings."""
    deduped: "OrderedDict[tuple, Finding]" = OrderedDict()
    for finding in findings:
        key = (finding.rule_id, finding.node)
        if key not in deduped:
            deduped[key] = finding

    ordered = sorted(
        deduped.values(),
        key=lambda f: (
            SEVERITY_ORDER.get(f.severity, 99),
            f.node or "",
            f.rule_id,
        ),
    )

    for index, finding in enumerate(ordered, start=1):
        finding.finding_id = f"F-{index:03d}"

    return ordered


def _rule_critical_path_deadline(
    node_metrics: Dict[str, NodeMetrics],
    scenario: Dict,
    deadline_ns: int,
) -> List[Finding]:
    """CRITICAL-PATH-001: a critical-path service exceeds the deadline."""
    findings: List[Finding] = []

    for node_name in scenario.get("critical_path", []):
        nm = node_metrics.get(node_name)
        if nm is None:
            continue
        if nm.p95_processing_ns <= deadline_ns:
            continue

        findings.append(
            Finding(
                finding_id="",
                rule_id="CRITICAL-PATH-001",
                severity="critical",
                title=f"{node_name} violates the critical path deadline",
                condition="p95_processing_ns > deadline_ns",
                node=node_name,
                observed={
                    "p95_processing_ns": nm.p95_processing_ns,
                    "p95_processing_ms": round(nm.p95_processing_ns / 1e6, 3),
                    "deadline_ns": deadline_ns,
                    "deadline_ms": deadline_ns / 1e6,
                },
                thresholds={"deadline_ns": deadline_ns},
                evidence=[
                    f"{node_name} p95 processing time is {nm.p95_processing_ns / 1e6:.2f} ms",
                    f"the critical path deadline is {deadline_ns / 1e6:.2f} ms",
                    "processing time exceeds the deadline",
                ],
                recommendation=(
                    "Identify the worst edge on the critical path and reduce its "
                    "latency."
                ),
            )
        )

    return findings


def _rule_bottleneck(
    node_metrics: Dict[str, NodeMetrics],
    deadline_ns: int,
    thresholds: Dict,
) -> List[Finding]:
    """BOTTLENECK-001: a service is both a fan-in hub and slow."""
    max_in_degree = int(thresholds.get("max_in_degree", 4))
    fraction = float(thresholds.get("processing_deadline_fraction", 0.5))
    processing_floor = deadline_ns * fraction

    findings: List[Finding] = []

    for node_name, nm in node_metrics.items():
        if nm.in_degree <= max_in_degree:
            continue
        if nm.p95_processing_ns <= processing_floor:
            continue

        findings.append(
            Finding(
                finding_id="",
                rule_id="BOTTLENECK-001",
                severity="critical",
                title=f"{node_name} is an architectural bottleneck",
                condition=(
                    f"in_degree > {max_in_degree} AND "
                    f"p95_processing_ns > deadline_ns * {fraction}"
                ),
                node=node_name,
                observed={
                    "in_degree": nm.in_degree,
                    "p95_processing_ns": nm.p95_processing_ns,
                    "p95_processing_ms": round(nm.p95_processing_ns / 1e6, 3),
                    "deadline_ms": deadline_ns / 1e6,
                },
                thresholds={
                    "max_in_degree": max_in_degree,
                    "processing_deadline_fraction": fraction,
                },
                evidence=[
                    f"{node_name} has in-degree {nm.in_degree} (>{max_in_degree})",
                    f"{node_name} p95 processing time is {nm.p95_processing_ns / 1e6:.2f} ms",
                    f"the deadline is {deadline_ns / 1e6:.2f} ms",
                    f"processing exceeds {fraction * 100:.0f}% of the deadline",
                ],
                recommendation=(
                    "Split the service into fast-path and slow-path handlers, or "
                    "separate high-priority control traffic from low-priority "
                    "telemetry traffic."
                ),
            )
        )

    return findings


def _rule_head_of_line(
    node_metrics: Dict[str, NodeMetrics],
    thresholds: Dict,
) -> List[Finding]:
    """HEAD-OF-LINE-001: high-priority work is blocked by low-priority work."""
    ratio_threshold = float(thresholds.get("low_priority_work_ratio", 0.4))

    findings: List[Finding] = []

    for node_name, nm in node_metrics.items():
        if nm.high_priority_blocked_count <= 0:
            continue
        if nm.low_priority_work_ratio <= ratio_threshold:
            continue

        findings.append(
            Finding(
                finding_id="",
                rule_id="HEAD-OF-LINE-001",
                severity="warning",
                title=f"{node_name} has head-of-line blocking",
                condition=(
                    f"high_priority_blocked_count > 0 AND "
                    f"low_priority_work_ratio > {ratio_threshold}"
                ),
                node=node_name,
                observed={
                    "high_priority_blocked_count": nm.high_priority_blocked_count,
                    "low_priority_work_ratio": nm.low_priority_work_ratio,
                },
                thresholds={"low_priority_work_ratio": ratio_threshold},
                evidence=[
                    (
                    f"{node_name} blocked {nm.high_priority_blocked_count} "
                    "high-priority request(s)"
                    ),
                    (
                    f"low-priority work is {nm.low_priority_work_ratio * 100:.1f}% "
                    f"of received traffic (threshold {ratio_threshold * 100:.0f}%)"
                    ),
                ],
                recommendation=(
                    "Use a priority-based message queue or separate channels so "
                    "low-priority traffic cannot starve high-priority requests."
                ),
            )
        )

    return findings


def _rule_queue_wait(
    edge_metrics: Dict[str, EdgeMetrics],
    thresholds: Dict,
) -> List[Finding]:
    """QUEUE-WAIT-001: queue wait dominates the end-to-end latency of an edge."""
    ratio_threshold = float(thresholds.get("queue_wait_ratio", 0.5))

    findings: List[Finding] = []

    for em in edge_metrics.values():
        if em.p95_total_ns <= 0:
            continue
        ratio = em.p95_queue_wait_ns / em.p95_total_ns
        if ratio <= ratio_threshold:
            continue

        findings.append(
            Finding(
                finding_id="",
                rule_id="QUEUE-WAIT-001",
                severity="warning",
                title=f"Queue wait dominates on {em.src_name} -> {em.dst_name}",
                condition=f"p95_queue_wait_ns > p95_total_ns * {ratio_threshold}",
                node=em.dst_name,
                observed={
                    "p95_queue_wait_ns": em.p95_queue_wait_ns,
                    "p95_queue_wait_ms": round(em.p95_queue_wait_ns / 1e6, 3),
                    "p95_total_ns": em.p95_total_ns,
                    "p95_total_ms": round(em.p95_total_ns / 1e6, 3),
                    "ratio": round(ratio, 4),
                },
                thresholds={"queue_wait_ratio": ratio_threshold},
                evidence=[
                    f"p95 queue wait is {em.p95_queue_wait_ns / 1e6:.2f} ms",
                    f"p95 total latency is {em.p95_total_ns / 1e6:.2f} ms",
                    f"queue wait is {ratio * 100:.1f}% of total latency",
                ],
                recommendation=(
                    "Reduce server load or increase the server thread pool; the "
                    "receiver is spending more time waiting than the sender "
                    "spends working."
                ),
            )
        )

    return findings


def _rule_single_point_of_failure(
    node_metrics: Dict[str, NodeMetrics],
    thresholds: Dict,
) -> List[Finding]:
    """SPOF-001: a critical-path service has no architectural alternative."""
    min_in_degree = int(thresholds.get("spof_min_in_degree", 3))

    findings: List[Finding] = []

    for node_name, nm in node_metrics.items():
        if not nm.on_critical_path:
            continue
        if nm.in_degree <= min_in_degree:
            continue

        findings.append(
            Finding(
                finding_id="",
                rule_id="SPOF-001",
                severity="warning",
                title=f"{node_name} is a single point of failure",
                condition=f"on_critical_path AND in_degree > {min_in_degree}",
                node=node_name,
                observed={
                    "in_degree": nm.in_degree,
                    "on_critical_path": nm.on_critical_path,
                },
                thresholds={"spof_min_in_degree": min_in_degree},
                evidence=[
                    f"{node_name} is on the critical path",
                    f"{node_name} has in-degree {nm.in_degree}",
                    "if this node fails, the critical path fails",
                ],
                recommendation=(
                    "Add redundancy or failover for this service, or distribute "
                    "its responsibility across independent services."
                ),
            )
        )

    return findings
