# RTArchitect — Devpost submission draft

> **Tagline:** QNX System Profiler is a microscope. RTArchitect is the architect.

---

## Project description

A QNX System Profiler shows you *what happened*. RTArchitect tells you *what is
wrong with the architecture*.

RTArchitect is a deterministic-first QNX IPC architectural analysis tool. It
instruments the QNX message-passing layer, exports a structured event log, and
turns that log into an evidence-backed architectural verdict: a service
interaction graph, real-time latency metrics, and a rule engine that names the
actual structural problem — a bottleneck, head-of-line blocking, queue-wait
dominance, a missed critical-path deadline, or a single point of failure.

Every finding states its condition, the observed values and the thresholds that
triggered it. There is no "the AI thinks maybe…". A reviewer can check the
arithmetic in seconds.

### The problem

QNX systems are built from services that talk over synchronous message passing.
The failure modes that matter — priority inversion, a single FIFO server that
lets telemetry starve brake commands, a fan-in hub that is also the slowest node
— are invisible in a profiler trace. They are architectural. Seeing them
requires reconstructing the service graph and reasoning about latency across
it, which is exactly the tedious, error-prone work RTArchitect automates.

### How it works

Five QNX services (`sensor_service`, `perception_service`, `brake_controller`,
`telemetry_client`, `diagnostics_client`) run on a QNX 8.0 target under QEMU.
Every service includes `rtarch_ipc.h`, which stamps each message with a
`CLOCK_MONOTONIC` timestamp and emits a structured `RTARCH` event on `slog2` for
the SEND, RECV and REPLY phases.

On a Linux host, the tool filters those events out of the raw slog2 capture,
parses them into typed models, builds a directed service graph, computes
per-node and per-edge p50/p95/p99 latency, and runs a deterministic rule engine.
The result is a self-contained HTML report with a static SVG service graph, the
findings and their evidence, and the full metric tables. No JavaScript, no
external assets.

### The demo

The demo runs the same tool against two architectures.

In the flawed version, `brake_controller` is a single thread that processes
every request in arrival order. Low-priority telemetry and diagnostics requests
take eight times longer to service than a brake command, so a brake command
arriving behind them waits for the full low-priority service time. RTArchitect
reports six findings, including `BOTTLENECK-001` and `HEAD-OF-LINE-001`, with
the evidence: brake p95 processing 13.2 ms against a 5 ms deadline, brake-command
p95 queue wait 8.3 ms.

The fixed version splits the service into two threads on two named channels.
Brake commands go to a fast path; telemetry and diagnostics go to a slow path.
Nothing else changes. The same tool, the same scenario, the same thresholds —
`BOTTLENECK-001` and the deadline violations disappear.

And `SPOF-001` stays. Splitting threads does not add redundancy. The brake
controller is still one process, and if it dies the critical path dies with it.
A tool that reports zero findings after every fix is a rubber stamp; RTArchitect
keeps the finding that is still true and tells you the next fix is redundancy.

### Why deterministic first

The rule engine always runs and always produces the same answer for the same
log. AI explanation is an optional layer on top: guarded by a try/except, a hard
five-second bound, and an output validator that rejects invented numbers and
unknown QNX APIs. If the AI fails, a deterministic template takes over and the
report is still complete. The analysis never depends on a network call.

### Generality

Nothing about the demo services is hardcoded. Deadlines, critical paths,
thresholds and the service topology come from a scenario JSON file. The same
binary analyses any QNX system that emits `RTARCH` events — demonstrated by a
second scenario, `medical_pump`, which fires the same five rules on a completely
different topology (`pump_controller`, `alarm_service`, `logging_client`,
`config_client`, `calibration_client`).

### Tech stack

QNX 8.0 · C · slog2 · MsgSend/MsgReceive/MsgReply · Python 3.10+ · Pydantic ·
NetworkX · Jinja2 · Typer · Rich · pytest

### License

MIT. See [LICENSE](../LICENSE).

### Status

Phase 1 and the host simulation are complete and tested. The QNX 8.0 QEMU run
is the remaining step; see the project README for the live status.

---

## Devpost "Built with" tags

```
QNX 8.0
C
Python
NetworkX
Pydantic
Jinja2
Typer
Rich
pytest
QEMU
```

## Devpost "What I learned" (suggested angle)

> Profiling shows you a symptom; architecture analysis shows you the disease.
> The hard part was not the graph or the metrics — it was making every finding
> reproducible and checkable, so that a reviewer never has to take the tool's
> word for anything.
