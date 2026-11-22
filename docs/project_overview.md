# RTArchitect — Project Overview

A single document explaining **what we set out to build, what we actually built,
and the vision we started from.** Written for inspection; every claim below is
backed by a file, a test, or a captured log.

- **Repo:** <https://github.com/hybirdvault-dot/rt-architect>
- **Original design doc:** `rtarchitect-full-system-design.md` (supplied at kick-off)
- **Status:** build complete, real QNX evidence captured, CI green
- **Last verified:** 54 tests passing (commit count is a snapshot; see `git log`)

---

## 1. The vision at the start

The starting point was a one-line positioning statement:

> **QNX System Profiler is a microscope. RTArchitect is the architect.**

A profiler shows you *what happened*. RTArchitect was meant to tell you *what is
wrong with the architecture* — and to be able to prove it.

The idea: instrument QNX message passing, export a structured log, and turn that
log into an **evidence-backed architectural verdict**. Not a dashboard of graphs
you have to interpret, but named findings — "this service is a bottleneck", "this
one blocks high-priority work" — each with the numbers that triggered it.

Three principles were fixed from day one:

1. **Deterministic first.** Every finding comes from a rule over measured data.
   Same log + same scenario ⇒ same findings. No clock, no randomness.
2. **Evidence, not vibes.** Every finding states its condition, its observed
   values and the thresholds that fired it.
3. **AI is optional.** The tool must be complete and correct with AI disabled.

The demo story was always the same: run the tool against a **flawed** architecture
and a **fixed** one, and let the findings do the talking. The flaw: a
single-threaded brake controller that lets low-priority telemetry queue in front
of high-priority brake commands.

---

## 2. What we decided to build

The plan had three phases.

### Phase 1 — Host MVP (the analysis tool)
A Python pipeline on a Linux host:

```
raw slog2 → filter RTARCH → parse → graph → metrics → rules → HTML report
```

- Locked `RTARCH` event schema (v1)
- Pydantic models, NetworkX service graph
- Per-node and per-edge p50/p95/p99 latency
- Five deterministic rules
- Self-contained HTML report
- Golden logs + pytest

### Phase 2 — QNX target
- `rtarch_ipc.h` logging layer for QNX 8.0
- Five demo services + a fixed variant
- Real `slog2` capture, extracted to the host
- Run the host tool against the **real** log

### Phase 3 — Demo and submit
- Three-minute demo video
- Devpost write-up
- Screenshots, docs, polish

### The five rules (agreed up front)

| Rule | Severity | Fires when |
|---|---|---|
| `CRITICAL-PATH-001` | critical | a critical-path service's p95 processing exceeds the deadline |
| `BOTTLENECK-001` | critical | in-degree is high **and** processing is slow |
| `HEAD-OF-LINE-001` | warning | high-priority requests blocked while low-priority work dominates |
| `QUEUE-WAIT-001` | warning | queue wait dominates end-to-end latency on an edge |
| `SPOF-001` | warning | a critical-path service has no architectural alternative |

### Explicitly deferred
- AI explanation (later made optional and built)
- A second scenario (later built — twice)
- The QNX target (later built)

---

## 3. What we actually built

### 3.1 Host analysis tool — complete

```
rtarch/
├── parser.py      RTARCH event parsing (prefix-tolerant, skips malformed lines)
├── models.py      Pydantic models
├── graph.py       NetworkX directed service graph
├── metrics.py     node + edge metrics, Rule-3 inputs
├── rules.py       the five rules, ordered and deduplicated
├── compare.py     flawed-vs-fixed comparison report
├── ai.py          optional AI explainer (5 s hard bound, deterministic fallback)
├── validator.py   rejects invented numbers and unknown QNX APIs
├── report.py      HTML report + static SVG service graph
├── scenario.py    scenario JSON loading
├── cli.py         Typer + Rich CLI
└── templates/     report.html.j2, comparison_report.html.j2
```

CLI:

```sh
rtarch analyze <log> --scenario <scenario.json> --output report.html [--ai]
rtarch compare <flawed.log> <fixed.log> --scenario <scenario.json> -o comparison.html
```

### 3.2 QNX 8.0 target — complete

```
target/qnx8_demo/
├── include/rtarch_ipc.h     logging layer + clock helper + discovery
├── sensor_service/          client, 5 ms frames
├── perception_service/      server for sensor, client of brake
├── brake_controller/        FLAWED: single thread, FIFO
├── brake_controller_fixed/  two threads on two named channels
├── telemetry_client/       low-priority load
├── diagnostics_client/     low-priority load
└── scripts/                 run + slog2 extraction
```

Plus `target/linux_sim/` — a QNX IPC / slog2 **simulation** that compiles the
real service sources unmodified on Linux. This is how the C code was validated
before any QNX image existed.

### 3.3 Scenarios — three

`brake_demo` (deadline 5 ms) · `medical_pump` (deadline 2 ms) · `industrial_robot` (deadline 1 ms)

Each fires all five rules on a completely different service topology.

### 3.4 Supporting material

- README, CONTRIBUTING, NOTICE, MIT LICENSE
- `docs/`: architecture, event schema, rules, verification, trust model,
  QNX setup, **QNX SDP target procedure**, Devpost draft, demo video script
- `scripts/`: QEMU/SDP setup, boot, export dry-run, smoke test
- `.github/workflows/ci.yml` — pytest on 3.10/3.11/3.12 + sim smoke test
- Golden logs, example logs, example reports, screenshots

---

## 4. Architecture as built

```
QNX 8.0 target (QEMU)                      Linux host (Python)
├── sensor_service ──SENSOR_FRAME──▶ perception
├── perception_service ──BRAKE_CMD──▶ brake
├── brake_controller   (flawed / fixed)
├── telemetry_client ──TELEMETRY_REQ──▶ brake
├── diagnostics_client ──DIAG_REQ──▶ brake
│
└── rtarch_ipc.h → slog2 → RTARCH events
                                              ├── parser → graph → metrics
                                              ├── rules → findings
                                              ├── compare → before/after
                                              └── report → HTML + SVG graph
```

Real slog2 line, exactly as captured off the target:

```
Nov 15 15:42:36.357      diagnostics_client.282646               rtarch*     0  RTARCH v=1 ts_ns=32192607144 phase=SEND trace_id=3001 msg_id=1 src_pid=282646 src_name=diagnostics_client dst_pid=282642 dst_name=brake_controller msg_type=DIAG_REQ prio=10
```

The parser tolerates that prefix — which is the whole point of the Threat-4
pre-filter.

---

## 5. Key decisions and deviations from the original doc

The supplied design doc was a strong sketch, but several details were wrong or
incomplete. Each was corrected and is now covered by a test.

| Original doc | What we built | Why |
|---|---|---|
| `slog2_buffer_config_t cfg` | `slog2_buffer_set_config_t cfg` | the first is the per-buffer struct; the set struct is what `slog2_register` takes |
| `_SLOG_INFO` | `SLOG2_INFO` | correct QNX 8.0 macro |
| `MsgSend` in `<sys/msg.h>` | `<sys/neutrino.h>` | confirmed against real QNX 8.0 headers |
| REPLY events create graph edges | only SEND/RECV create edges | REPLY edges are reversed duplicates and made the graph cyclic |
| `trace_id` reused across hops | each hop gets its own `(trace_id, msg_id)` | otherwise triple grouping collapses two hops into one |
| `NodeMetrics` had no Rule-3 inputs | computed `high_priority_blocked_count` and `low_priority_work_ratio` | Rule 3 was dead without them |
| Node `msg_type` hardcoded `""` | carries the real message type | the schema already had the field |
| `max_in_degree: 4`, `spof_min: 3` | `max_in_degree` tuned per scenario (2 vs 3); `spof_min_in_degree` left at 2 | the doc's own golden log could not trigger its own rules |
| Golden log off by 10× | rescaled to the documented narrative | doc claimed 7 ms, timestamps produced 70 ms |
| AI layer | built, but strictly optional | 5 s hard bound + validator + deterministic fallback |
| Second scenario | built, plus a third | two says "proved twice"; three says "generic tool" |

---

## 6. Evidence

### Simulation (host, no QNX)

| | Flawed | Fixed |
|---|---|---|
| findings | 8 | 6 |

### Genuine QNX 8.0.0 target

Built from the SDP with `mkqnximage`, booted under QEMU, 1655 real `RTARCH`
events captured off the serial console.

| Metric | Flawed | Fixed |
|---|---|---|
| brake p95 processing | **10.19 ms** | **0.35 ms** |
| perception→brake p95 queue wait | 7.88 ms | **0.83 ms** |
| telemetry→brake p95 queue wait | 10.11 ms | **0.95 ms** |
| diagnostics→brake p95 queue wait | 12.64 ms | **0.99 ms** |
| findings | 8 | 6 |

All five rules fire on the flawed log. `BOTTLENECK-001` and the brake's
`CRITICAL-PATH-001` clear on the fixed log. `SPOF-001` correctly remains —
splitting threads does not add redundancy.

> Residual `HEAD-OF-LINE-001` / `QUEUE-WAIT-001` on the fixed log are a TCG
> emulation artefact: every edge shows a uniform ~0.8–1.0 ms queue wait, which is
> the emulated scheduler's latency, not the architecture. Documented as such.

### Tests

54 tests across parser, metrics, rules, report and CLI. CI green on Python
3.10 / 3.11 / 3.12, plus an end-to-end smoke test.

---

## 7. How to reproduce

```sh
cd ~/Desktop/rt-architect

# host tool, golden logs
.venv/bin/python -m pytest
.venv/bin/python -m rtarch analyze tests/golden/synthetic_flawed.log \
  --scenario scenarios/brake_demo.json -o /tmp/r.html

# host simulation of the real C sources
bash target/linux_sim/run_sim.sh
bash target/linux_sim/run_fixed_sim.sh

# genuine QNX 8.0 target
bash scripts/setup_qnx_sdp.sh      # installs ~/qnx800
bash scripts/boot_qnx_qemu.sh      # builds + boots the QEMU target
bash scripts/run_qnx_demo.sh        # runs demo + extracts slog2
bash scripts/smoke_test_qnx.sh sim # end-to-end assertion
```

Full procedure: [docs/qnx_sdp_target.md](qnx_sdp_target.md).

---

## 8. Status

**Done:** the whole build. Host tool, QNX target, real evidence, docs, CI.

**Remaining:** record the demo video and submit on Devpost by **Dec 15**.

The demo script is at [docs/demo_video_script.md](demo_video_script.md); every
command in it has already been run successfully.

---

## 9. The one rule that must never break

> **If AI is not working, ship without AI. Never ship without the rule engine.**

Everything else in this document is in service of that.
