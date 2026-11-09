# Linux simulation of the QNX target

This directory compiles the **real** service sources from `target/qnx8_demo/`
against a host-side QNX compatibility shim, so the whole pipeline can be
exercised on Linux before a QNX 8.0 toolchain or QEMU image is available.

```
qnx8_demo/sensor_service/main.c  ──compile──▶  sensor_service.o  ─┐
qnx8_demo/perception_service/…   ──compile──▶  perception_….o    ─┤
qnx8_demo/brake_controller/…     ──compile──▶  brake_….o         ─┼─▶ rtarch_sim
qnx8_demo/telemetry_client/…     ──compile──▶  telemetry_….o     ─┤
qnx8_demo/diagnostics_client/…   ──compile──▶  diagnostics_….o   ─┘
                              shim.c  (QNX IPC + slog2 emulation)
                              sim_main.c (thread harness)
```

## What the shim emulates

| QNX API | Simulation |
|---|---|
| `slog2_register` / `slog2_reset` / `slog2f` | stdout, with a realistic slog2-style header prefix |
| `ChannelCreate` / `ConnectAttach` | in-process condition-variable queues |
| `MsgSend` / `MsgReceive` / `MsgReply` | synchronous request/reply with blocking send |
| `delay()` | `usleep()` |

The header declarations match the real QNX 8.0 API (verified against the QNX
8.0 library reference), so the service sources compile unmodified.

## Run

```sh
bash run_sim.sh          # flawed brake_controller
bash run_fixed_sim.sh    # fixed brake_controller (two threads, two channels)
```

Each run writes `examples/logs/sim_<mode>_slog2.txt` and then runs the
RTArchitect CLI on it, producing `examples/reports/sim_<mode>_report.html`.

## Limitations — read this

- **This is not QNX.** It is a functional simulation. It validates the C
  sources, the RTARCH log format, the parser and the rule engine. It does not
  validate QNX scheduling, real-time priorities, or slog2 buffer behaviour.
- Real-time priorities are not applied (`pthread_setschedparam` fails without
  privileges); the head-of-line blocking effect comes from the single-threaded
  FIFO server and the artificial `delay()`, which is exactly the flaw under
  test.
- All services share one process, so `src_pid`/`dst_pid` are identical. The
  analysis uses service *names*, so this does not affect the findings.
- **Timing is host-sensitive.** Every service runs as a thread in one process,
  so the measured queue waits include Linux scheduler noise. On a quiet host the
  fixed demo shows only `SPOF-001`; on a loaded host the brake-command queue
  wait is inflated by preemption and the noise-sensitive rules
  (`HEAD-OF-LINE-001`, `QUEUE-WAIT-001`, and the propagated
  `CRITICAL-PATH-001`) can still fire. That is an artefact of the simulation
  environment, not of the architecture under test — the deterministic signal
  (brake p95 processing 13 ms → 0.65 ms, brake-command p95 queue wait 8.3 ms →
  ~0.1 ms median) is unambiguous. The real QNX target is the authority.

For the real thing, see `docs/qnx_setup.md`.
