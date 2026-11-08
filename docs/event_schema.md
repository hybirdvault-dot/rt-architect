# RTARCH Event Schema (LOCKED)

**Status:** locked. Do not change after Day 5 without a schema-version bump.

## Format

Every event is one line beginning with the `RTARCH` marker and a set of
`key=value` pairs:

```
RTARCH v=1 ts_ns=<nanoseconds> phase=<SEND|RECV|REPLY> trace_id=<uint64>
       msg_id=<uint32> src_pid=<int> src_name=<string> dst_pid=<int>
       dst_name=<string> msg_type=<string> prio=<int>
```

## Example — one complete request

```
RTARCH v=1 ts_ns=1000000000 phase=SEND  trace_id=1001 msg_id=42 src_pid=101 src_name=sensor_service     dst_pid=201 dst_name=perception_service msg_type=SENSOR_FRAME prio=25
RTARCH v=1 ts_ns=1008000000 phase=RECV  trace_id=1001 msg_id=42 src_pid=101 src_name=sensor_service     dst_pid=201 dst_name=perception_service msg_type=SENSOR_FRAME prio=25
RTARCH v=1 ts_ns=1015000000 phase=REPLY trace_id=1001 msg_id=42 src_pid=201 src_name=perception_service dst_pid=101 dst_name=sensor_service     msg_type=SENSOR_ACK   prio=25
```

## Fields

| Field | Type | Purpose |
|---|---|---|
| `v` | int | Schema version (always `1`) |
| `ts_ns` | uint64 | Nanosecond timestamp from `CLOCK_MONOTONIC` |
| `phase` | string | `SEND`, `RECV`, or `REPLY` |
| `trace_id` | uint64 | Follows one request across services |
| `msg_id` | uint32 | Identifies one request/reply pair |
| `src_pid` | int | Source process ID |
| `src_name` | string | Source service name |
| `dst_pid` | int | Destination process ID |
| `dst_name` | string | Destination service name |
| `msg_type` | string | Message type (`SENSOR_FRAME`, `BRAKE_CMD`, ...) |
| `prio` | int | Thread priority (QNX priority, 1–63) |

## Why these fields

- **`ts_ns`** — our own `CLOCK_MONOTONIC` reading; never slog2's clock.
- **`phase`** — `SEND`/`RECV`/`REPLY` gives us queue wait and processing time.
- **`trace_id`** — follows a request across multiple services (critical path).
- **`msg_id`** — matches the three phases of one request.
- **`prio`** — detects priority inversion and head-of-line blocking.

## Latency model

```
queue_wait_ns = RECV.ts_ns - SEND.ts_ns
processing_ns = REPLY.ts_ns - RECV.ts_ns
total_ns      = REPLY.ts_ns - SEND.ts_ns
```

## Robustness

The parser searches for the `RTARCH` marker anywhere in a line, so real slog2
headers (timestamp / cpu / tid prefixes) do not defeat it. Lines that contain
the marker but are missing required fields are counted as malformed and skipped
rather than aborting the run.
