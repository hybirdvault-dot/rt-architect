# Rule Catalog

All rules are deterministic functions of the metrics and the scenario
thresholds. Every finding carries the observed values and the thresholds that
triggered it.

## CRITICAL-PATH-001 — critical path deadline violation

| | |
|---|---|
| **Severity** | critical |
| **Condition** | `p95_processing_ns > deadline_ns` for a service on the critical path |
| **Observed** | p95 processing time, deadline |
| **Thresholds** | `deadline_ms` |
| **Recommendation** | Reduce the latency of the worst edge on the critical path |

## BOTTLENECK-001 — architectural bottleneck

| | |
|---|---|
| **Severity** | critical |
| **Condition** | `in_degree > max_in_degree` **and** `p95_processing_ns > deadline_ns * processing_deadline_fraction` |
| **Observed** | in-degree, p95 processing time, deadline |
| **Thresholds** | `max_in_degree`, `processing_deadline_fraction` |
| **Recommendation** | Split the service into fast-path and slow-path handlers |

## HEAD-OF-LINE-001 — head-of-line blocking

| | |
|---|---|
| **Severity** | warning |
| **Condition** | `high_priority_blocked_count > 0` **and** `low_priority_work_ratio > low_priority_work_ratio_threshold` |
| **Observed** | blocked high-priority count, low-priority work ratio |
| **Thresholds** | `low_priority_work_ratio` |
| **Recommendation** | Use a priority-based message queue or separate channels |

A high-priority block is a request with `prio >= priority_threshold` whose queue
wait exceeded `deadline_ns * blocked_queue_wait_ratio`.

## QUEUE-WAIT-001 — queue wait dominance

| | |
|---|---|
| **Severity** | warning |
| **Condition** | `p95_queue_wait_ns / p95_total_ns > queue_wait_ratio` |
| **Observed** | p95 queue wait, p95 total latency, ratio |
| **Thresholds** | `queue_wait_ratio` |
| **Recommendation** | Reduce server load or increase the server thread pool |

## SPOF-001 — single point of failure

| | |
|---|---|
| **Severity** | warning |
| **Condition** | `on_critical_path` **and** `in_degree > spof_min_in_degree` |
| **Observed** | in-degree, critical-path membership |
| **Thresholds** | `spof_min_in_degree` |
| **Recommendation** | Add redundancy or failover for this service |

## Ordering and deduplication

Findings are sorted by:

1. severity — critical, then warning, then info
2. node name — alphabetical
3. rule ID — alphabetical

They are deduplicated by `(rule_id, node)` and numbered sequentially in final
display order (`F-001`, `F-002`, ...).
