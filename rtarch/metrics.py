"""Compute deterministic real-time metrics from RTARCH events.

Latency model (per request, keyed by ``trace_id`` + ``msg_id``):

    queue_wait   = RECV.ts_ns - SEND.ts_ns
    processing   = REPLY.ts_ns - RECV.ts_ns
    total        = REPLY.ts_ns - SEND.ts_ns
"""

from collections import defaultdict

from .models import EdgeMetrics, NodeMetrics, Phase, RTArchEvent


def percentile(data: list[int], p: float) -> int:
    """Nearest-rank percentile over integers (deterministic, no interpolation)."""
    if not data:
        return 0
    ordered = sorted(data)
    idx = int(len(ordered) * p / 100)
    return ordered[min(idx, len(ordered) - 1)]


def group_triples(
    events: list[RTArchEvent],
) -> dict[tuple[int, int], dict[str, RTArchEvent]]:
    """Group events by ``(trace_id, msg_id)`` and index them by phase."""
    triples: dict[tuple[int, int], dict[str, RTArchEvent]] = defaultdict(dict)
    for event in events:
        triples[(event.trace_id, event.msg_id)][event.phase.value] = event
    return dict(triples)


def _completed_triples(
    triples: dict[tuple[int, int], dict[str, RTArchEvent]],
) -> list[tuple[RTArchEvent, RTArchEvent, RTArchEvent]]:
    """Return ``(SEND, RECV, REPLY)`` for every fully observed request."""
    completed: list[tuple[RTArchEvent, RTArchEvent, RTArchEvent]] = []
    for phases in triples.values():
        send = phases.get("SEND")
        recv = phases.get("RECV")
        reply = phases.get("REPLY")
        if send is not None and recv is not None and reply is not None:
            completed.append((send, recv, reply))
    return completed


def compute_edge_metrics(events: list[RTArchEvent]) -> dict[str, EdgeMetrics]:
    """Compute per-edge latency metrics from complete SEND/RECV/REPLY triples."""
    triples = group_triples(events)

    queue_by_edge: dict[str, list[int]] = defaultdict(list)
    processing_by_edge: dict[str, list[int]] = defaultdict(list)
    total_by_edge: dict[str, list[int]] = defaultdict(list)
    types_by_edge: dict[str, set] = defaultdict(set)

    for send, recv, reply in _completed_triples(triples):
        key = f"{send.src_name}->{recv.dst_name}"
        queue_by_edge[key].append(recv.ts_ns - send.ts_ns)
        processing_by_edge[key].append(reply.ts_ns - recv.ts_ns)
        total_by_edge[key].append(reply.ts_ns - send.ts_ns)
        types_by_edge[key].add(send.msg_type)

    metrics: dict[str, EdgeMetrics] = {}
    for key in sorted(queue_by_edge):
        src, dst = key.split("->", 1)
        queue = queue_by_edge[key]
        processing = processing_by_edge[key]
        total = total_by_edge[key]

        metrics[key] = EdgeMetrics(
            src_name=src,
            dst_name=dst,
            msg_type=",".join(sorted(types_by_edge[key])),
            count=len(queue),
            p50_queue_wait_ns=percentile(queue, 50),
            p95_queue_wait_ns=percentile(queue, 95),
            p99_queue_wait_ns=percentile(queue, 99),
            p50_processing_ns=percentile(processing, 50),
            p95_processing_ns=percentile(processing, 95),
            p99_processing_ns=percentile(processing, 99),
            p50_total_ns=percentile(total, 50),
            p95_total_ns=percentile(total, 95),
            p99_total_ns=percentile(total, 99),
        )

    return metrics


def compute_node_metrics(
    graph,
    edge_metrics: dict[str, EdgeMetrics],
    events: list[RTArchEvent],
    scenario: dict,
) -> dict[str, NodeMetrics]:
    """Compute per-service metrics.

    Rule-3 inputs are derived here:

    * ``high_priority_blocked_count`` — high-priority requests whose queue wait
      exceeded ``deadline_ns * blocked_queue_wait_ratio``.
    * ``low_priority_work_ratio`` — low-priority received messages divided by
      all received messages for that service.

    Priority classes are split at the scenario's ``priority_threshold``.
    """
    thresholds = scenario.get("thresholds", {})
    deadline_ns = int(float(scenario.get("deadline_ms", 5.0)) * 1_000_000)
    priority_threshold = int(thresholds.get("priority_threshold", 20))
    blocked_ratio = float(thresholds.get("blocked_queue_wait_ratio", 0.2))
    blocked_threshold_ns = int(deadline_ns * blocked_ratio)

    critical_path = set(scenario.get("critical_path", []))
    triples = group_triples(events)

    received: dict[str, dict[str, int]] = defaultdict(
        lambda: {"high": 0, "low": 0, "total": 0}
    )
    blocked: dict[str, int] = defaultdict(int)
    processing_samples: dict[str, list[int]] = defaultdict(list)

    for event in events:
        if event.phase is Phase.RECV:
            bucket = received[event.dst_name]
            bucket["total"] += 1
            if event.prio >= priority_threshold:
                bucket["high"] += 1
            else:
                bucket["low"] += 1

    for send, recv, reply in _completed_triples(triples):
        processing_samples[recv.dst_name].append(reply.ts_ns - recv.ts_ns)
        if recv.prio >= priority_threshold:
            queue_wait = recv.ts_ns - send.ts_ns
            if queue_wait > blocked_threshold_ns:
                blocked[recv.dst_name] += 1

    node_metrics: dict[str, NodeMetrics] = {}
    for node in graph.nodes():
        incoming = [em for em in edge_metrics.values() if em.dst_name == node]
        p95_processing = percentile(processing_samples.get(node, []), 95)
        total_received = sum(em.count for em in incoming)

        node_received = received.get(node, {"high": 0, "low": 0, "total": 0})
        low_ratio = (
            node_received["low"] / node_received["total"]
            if node_received["total"]
            else 0.0
        )

        node_metrics[node] = NodeMetrics(
            name=node,
            in_degree=graph.in_degree(node),
            out_degree=graph.out_degree(node),
            p95_processing_ns=p95_processing,
            total_messages_received=total_received,
            on_critical_path=node in critical_path,
            high_priority_blocked_count=blocked.get(node, 0),
            low_priority_work_ratio=round(low_ratio, 4),
        )

    return node_metrics
