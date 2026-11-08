# Architecture

## Overview

RTArchitect is a deterministic-first QNX IPC architectural analysis tool. It
instruments QNX message passing, exports structured logs, and analyses them on
a Linux host to produce evidence-backed architectural findings.

```
QNX 8.0 Target (QEMU)                 Linux Host (Python)
├── sensor_service ──MsgSend──→ perception
├── perception_service ──MsgSend──→ brake
├── brake_controller  (flawed: single-threaded)
├── telemetry_client ──MsgSend──→ brake
├── diagnostics_client ──MsgSend──→ brake
│
└── rtarch_ipc.h  →  slog2  →  RTARCH events
                                      │
                                      ▼
                          parser → graph → metrics → rules → report
```

## Pipeline

The host-side pipeline is strictly one-directional. Each stage is a pure
function of the previous stage's output, which keeps the analysis deterministic
and easy to test.

| Stage | Module | Responsibility |
|---|---|---|
| 1 | `rtarch/parser.py` | Filter `RTARCH` lines, parse into Pydantic models |
| 2 | `rtarch/graph.py` | Build a NetworkX directed service graph |
| 3 | `rtarch/metrics.py` | Compute per-node and per-edge p50/p95/p99 metrics |
| 4 | `rtarch/rules.py` | Run the five deterministic rules |
| 5 | `rtarch/report.py` | Render the self-contained HTML report |

## Design decisions

### Only SEND and RECV define graph edges

A `REPLY` event travels back along an existing request edge. Adding it as a
graph edge would create a reversed duplicate for every request and turn the
service graph into a cyclic graph. Edges are therefore derived from `SEND` and
`RECV` events only; `REPLY` is used solely for the processing-time metric.

### Latency model

Every request is identified by `(trace_id, msg_id)`. When all three phases are
present:

```
queue_wait = RECV.ts_ns - SEND.ts_ns
processing = REPLY.ts_ns - RECV.ts_ns
total      = REPLY.ts_ns - SEND.ts_ns
```

### All timestamps come from CLOCK_MONOTONIC

The target uses `CLOCK_MONOTONIC` directly and never trusts slog2's automatic
timestamp. This keeps all latencies relative to one clock source.

### Nothing service-specific is hardcoded

Service names, deadlines, critical paths and thresholds all come from the
scenario JSON. The same binary analyses any QNX system that emits `RTARCH`
events.

### Findings are ordered and deduplicated

Findings are sorted by severity, then node name, then rule ID, deduplicated by
`(rule_id, node)`, and only then assigned sequential IDs. Identical input
always produces an identical report.

## Report

The report is a single self-contained HTML file: no JavaScript, no external
assets. It embeds a static SVG service graph laid out by topological
generation, the findings with their evidence, and the full node/edge metric
tables.
