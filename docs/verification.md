# Verification

## Automated tests

```bash
.venv/bin/python -m pytest
```

28 tests cover:

- **Parser** — golden log parsing, field values, `RTARCH` pre-filter, malformed
  line skipping, empty files, and tolerance of real slog2 line prefixes.
- **Metrics** — queue wait / processing / total calculations, message types,
  node in-degree, and the Rule-3 inputs (high-priority blocked count,
  low-priority work ratio).
- **Rules** — all five rules fire on the flawed log, the fixed log produces zero
  findings, ordering and deduplication, and every finding is evidence-backed.
- **Report** — HTML contains findings, the SVG graph, metric tables, and the
  clean-architecture message.
- **CLI** — end-to-end invocation via Typer's `CliRunner`.

## Golden logs

| Log | Purpose |
|---|---|
| `tests/golden/synthetic_flawed.log` | Flawed single-threaded `brake_controller`; triggers all five rules |
| `tests/golden/synthetic_fixed.log` | Split fast/slow handlers; triggers nothing |

## Manual end-to-end check

```bash
.venv/bin/rtarch tests/golden/synthetic_flawed.log \
  --scenario scenarios/brake_demo.json \
  --output /tmp/flawed.html
# Expected: 2 critical, 3 warning, 0 info

.venv/bin/rtarch tests/golden/synthetic_fixed.log \
  --scenario scenarios/brake_demo_fixed.json \
  --output /tmp/fixed.html
# Expected: 0 critical, 0 warning, 0 info
```

## Definition of done

- [x] Parser reads the locked `RTARCH` v1 schema
- [x] Graph topology matches the service call relationships
- [x] Metrics are correct on the golden logs
- [x] All five rules fire on the flawed log
- [x] The fixed log produces zero findings
- [x] The HTML report renders without horizontal overflow
- [x] The CLI exits 0 and writes the report
- [x] `pytest` is green
