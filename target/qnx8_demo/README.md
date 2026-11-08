# RTArchitect — QNX 8.0 target demo

Dead-simple QNX services that generate a real `RTARCH` event log for the host
analysis tool.

```
sensor_service ──SENSOR_FRAME──▶ perception_service ──BRAKE_CMD──▶ brake_controller
telemetry_client ──TELEMETRY_REQ─────────────────────────────────▶ brake_controller
diagnostics_client ──DIAG_REQ────────────────────────────────────▶ brake_controller
```

## Layout

| Path | Purpose |
|---|---|
| `include/rtarch_ipc.h` | Logging layer, clock helper, service discovery |
| `sensor_service/` | Client: sensor frames every 5 ms |
| `perception_service/` | Server for sensor, client of brake |
| `brake_controller/` | **FLAWED** single-threaded server |
| `telemetry_client/` | Low-priority load, every 50 ms |
| `diagnostics_client/` | Low-priority load, every 100 ms |
| `scripts/` | Run and log-extraction helpers |

## Build

```sh
make            # uses /opt/qnx800 by default
make QNX_HOST=/path/to/qnx800/host/linux/x86_64
make clean
```

## Run

Copy the binaries into the QNX 8.0 QEMU guest, then:

```sh
sh scripts/run_flawed_demo.sh     # start services, run 8 s, stop
sh scripts/extract_slog2.sh       # slog2info > /tmp/raw_slog2.txt
```

Copy `/tmp/raw_slog2.txt` to the Linux host and analyse it:

```sh
.venv/bin/rtarch raw_slog2.txt -s scenarios/brake_demo.json -o real_report.html
```

## The flaw

`brake_controller` is a single thread that processes requests strictly in
arrival order. Low-priority telemetry and diagnostics requests take
`LOWPRIO_DELAY_MS` (8 ms) to service, while a high-priority brake command takes
`BRAKE_DELAY_MS` (1 ms). A brake command arriving behind low-priority work waits
for the full 8 ms — classic head-of-line blocking.

Because the service times are artificial, they are the knob to tune when
matching a real target's timing. See `docs/qnx_setup.md` for the full
installation and extraction guide.

## Expected findings

With `scenarios/brake_demo.json` the flawed demo should produce:

| Rule | Why |
|---|---|
| `CRITICAL-PATH-001` | brake p95 processing exceeds the 5 ms deadline |
| `BOTTLENECK-001` | brake has in-degree 3 and slow processing |
| `HEAD-OF-LINE-001` | high-priority brake commands blocked by low-priority work |
| `QUEUE-WAIT-001` | queue wait dominates the perception→brake edge |
| `SPOF-001` | brake is on the critical path with no alternative |

If real QNX timing differs, tune `deadline_ms` and the thresholds in the
scenario JSON — never in the code.
