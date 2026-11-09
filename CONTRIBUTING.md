# Contributing to RTArchitect

## Quick start

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest          # 50 tests
```

Everything below works without a QNX license or a QNX image.

## How to run the demo

**Host simulation (no QNX needed)**

```sh
bash target/linux_sim/run_sim.sh        # flawed demo  -> 6 findings
bash target/linux_sim/run_fixed_sim.sh  # fixed demo   -> BOTTLENECK-001 clears
bash scripts/smoke_test_qnx.sh sim      # end-to-end assertion
```

**Real QNX 8.0 target**

```sh
source /opt/qnx800/qnxsdp-env.sh
(cd target/qnx8_demo && make)
bash scripts/setup_qemu_local.sh
bash scripts/boot_qnx_qemu.sh qnx80-hdd.img
# inside the guest:
sh scripts/run_flawed_demo.sh
sh scripts/extract_slog2.sh
# back on the host:
.venv/bin/rtarch /tmp/raw_slog2.txt -s scenarios/brake_demo.json -o report.html
```

## Project layout

```
rtarch/          Python analysis pipeline (parser -> graph -> metrics -> rules -> report)
target/qnx8_demo QNX 8.0 C services and the fixed variant
target/linux_sim host-side QNX IPC / slog2 simulation of those same sources
scenarios/       scenario JSON: deadline, critical path, thresholds
tests/           pytest suite and golden logs
examples/        example logs and generated reports
scripts/         QEMU, smoke-test and export helpers
docs/            architecture, schema, rules, verification, trust model
```

## Adding a scenario

A scenario is pure data. Copy `scenarios/brake_demo.json`, change the service
names, the deadline, the critical path and the thresholds, and add a matching
golden log under `tests/golden/`. No Python changes are required — that property
is the point of the design, and `tests/test_rules.py` asserts it.

## Adding a rule

1. Add a rule ID and severity to `rtarch/rules.py`.
2. Add a deterministic fallback template to `rtarch/ai.py`.
3. Add a threshold to the scenario JSONs that need it.
4. Add a test in `tests/test_rules.py`.

Rules must be deterministic functions of the metrics and the scenario. Never
read the clock, never use randomness, and never let a rule depend on the AI.

## The one rule that must never break

> **If AI is not working, ship without AI. Never ship without the rule engine.**

The AI layer is strictly optional. `--ai` must never change a finding, a number
or the exit status of the tool.

## Commit style

```
feat(parser): add RTARCH event parser
fix(graph): exclude REPLY events from edge construction
feat(target): add brake_controller_fixed
docs: add QNX setup guide
test: cover the medical_pump scenario
```

Commits are atomic: one logical change each, tests passing before push.

## Code of conduct

Be direct, cite evidence, and never claim a finding the data does not support.
The tool's credibility is the product.
