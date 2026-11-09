# RTArchitect — demo video script (3:00)

Shoot this against the host simulation. Every command below runs on this Linux
box with no QNX licence and no QNX image. When the real QNX run lands, only the
**10-second QNX insert at 0:10** is re-recorded; nothing else changes.

- **Aspect:** 16:9, 1080p minimum
- **Font:** terminal at 18–20 pt, monospace
- **Music:** optional, low, under the voiceover only
- **Colour:** the report is dark by design — do not switch it to light mode

---

## Pre-record setup (do this once)

```bash
cd ~/Desktop/rt-architect
.venv/bin/pip install -e .          # already done if the README was followed
.venv/bin/python -m pytest -q        # 54 green, so the 2:30 shot is honest
```

Have these ready:

1. A terminal, 160×45, dark background.
2. A browser window for the HTML report (opened at 0:30, not before).
3. `docs/screenshots/` open in a file manager for the 2:30 project-tree shot.

Terminal preamble (run once, leave it on screen):

```bash
clear
echo "RTArchitect — deterministic-first QNX IPC architectural analysis"
echo
```

---

## 0:00–0:10 — Tagline

**Screen:** black. White monospace text fades in, one line at a time.

```
QNX System Profiler is a microscope.
RTArchitect is the architect.
```

**Voiceover:** "A QNX System Profiler shows you what happened. RTArchitect
tells you what is wrong with the architecture."

**B-roll notes:** hold each line ~2.5 s. Cut to the terminal on "architect."

---

## 0:10–0:20 — The flawed demo is running

**Screen:** terminal, split vertically.
**Top pane:** the simulation running. **Bottom pane:** the slog2 stream.

Type and run:

```bash
cd ~/Desktop/rt-architect
bash target/linux_sim/run_sim.sh
```

While it runs, show the raw event stream:

```bash
tail -f examples/logs/sim_flawed_slog2.txt
```

**Voiceover:** "Five QNX services talk over synchronous message passing. Every
send, receive and reply is stamped with a CLOCK_MONOTONIC timestamp and written
to a structured log."

**B-roll notes:** zoom the bottom pane so the `RTARCH` lines fill the frame for
two seconds. Point at `phase=SEND`, `phase=RECV`, `phase=REPLY`.

> **QNX insert (10 s, re-recorded later):** the same five services running
> inside the QEMU guest, `slog2info` streaming. Same voiceover.

---

## 0:20–0:30 — Export and analyse

**Screen:** terminal, single pane.

```bash
.venv/bin/python -m rtarch analyze examples/logs/sim_flawed_slog2.txt \
  --scenario scenarios/brake_demo.json \
  --output examples/reports/flawed_report.html
```

**Voiceover:** "The log comes back to the Linux host. One command turns it into
an architectural verdict."

**B-roll notes:** hold on the Rich output table — the five findings with their
IDs. Let the cursor sit on `F-001 BOTTLENECK-001`.

---

## 0:30–0:50 — The report

**Screen:** browser. Open `examples/reports/flawed_report.html`.

```bash
xdg-open examples/reports/flawed_report.html
```

Click the summary cards, then scroll to the first finding. Expand the evidence
panel. Highlight `BOTTLENECK-001`.

**Voiceover:** "Six findings, each with its condition, its observed values and
the thresholds that triggered it. No 'the AI thinks maybe'."

**B-roll notes:** screen-record the scroll. Zoom the evidence list. Cut to the
SVG service graph — the red node is the brake controller.

---

## 0:50–1:00 — The numbers

**Screen:** terminal + report side by side.

```bash
grep -A4 "brake_controller" examples/reports/flawed_report.html | head -20
```

**Voiceover:** "Brake controller: in-degree three, p95 processing 7 ms, against
a 5 ms deadline. Telemetry and diagnostics are queued in front of brake
commands."

**B-roll notes:** highlight the p95 column and the deadline in the metric
tables. A slow push-in on "13.17 ms" from the simulation run.

---

## 1:00–1:20 — The explanation

**Screen:** report, scrolled to the AI explanation block under a finding.

```bash
.venv/bin/python -m rtarch analyze examples/logs/sim_flawed_slog2.txt \
  --scenario scenarios/brake_demo.json \
  --output examples/reports/flawed_ai.html --ai
```

**Voiceover:** "An optional AI layer explains each finding in plain language.
It is guarded by a five-second timeout and a validator that rejects invented
numbers. If it fails, the deterministic template takes over — the analysis never
depends on the network."

**B-roll notes:** show the "AI Analysis" block. If the provider is not
configured, show the fallback text and say so on camera — that is the honest
demo and it is arguably a stronger one.

---

## 1:20–1:40 — The fix

**Screen:** terminal.

```bash
bash target/linux_sim/run_fixed_sim.sh
```

Then the money shot — the side-by-side comparison:

```bash
.venv/bin/python -m rtarch compare \
  examples/logs/sim_flawed_slog2.txt \
  examples/logs/sim_fixed_slog2.txt \
  --scenario scenarios/brake_demo.json \
  --output examples/reports/comparison.html

xdg-open examples/reports/comparison.html
```

**Voiceover:** "Same tool, same scenario, same thresholds. The brake is now two
threads on two channels. Look at the delta."

**B-roll notes:** full-screen the comparison report. Let the viewer read the
finding-diff table: `cleared`, `cleared`, `cleared`. Then the edge-metrics table:
queue wait 8.3 ms → ~0.1 ms.

---

## 1:40–1:50 — The honest finding

**Screen:** comparison report, bottom half. `SPOF-001` is still present.

**Voiceover:** "Two findings gone, one stays — the one that is actually
architectural. Splitting threads did not add redundancy. The next fix is
failover, not another thread. A tool that reports zero findings after every fix
is a rubber stamp."

**B-roll notes:** hold on the single remaining `SPOF-001` row. Do not cut away
too quickly — this is the credibility shot.

---

## 1:50–2:10 — Generality

**Screen:** terminal.

```bash
.venv/bin/python -m rtarch analyze tests/golden/synthetic_pump.log \
  --scenario scenarios/medical_pump.json \
  --output examples/reports/pump_report.html

.venv/bin/python -m rtarch analyze tests/golden/synthetic_robot.log \
  --scenario scenarios/industrial_robot.json \
  --output examples/reports/robot_report.html
```

**Voiceover:** "Nothing is hardcoded. A medical pump at two milliseconds, a
robot motor controller at one — the same five rules fire on topologies the demo
never mentions."

**B-roll notes:** cut between the two reports. Flash the three scenario JSONs
side by side. Then the three golden logs.

---

## 2:10–2:30 — Deterministic-first

**Screen:** report, evidence panel, then the raw log.

```bash
grep RTARCH examples/logs/sim_flawed_slog2.txt | head -5
```

**Voiceover:** "Deterministic-first. Every finding is reproducible from the
log, and every number in the report is arithmetic the reviewer can check in
seconds."

**B-roll notes:** put the log line and the finding side by side on screen. The
viewer should be able to trace one number from the log to the report.

---

## 2:30–2:50 — The repo

**Screen:** project tree, then the test run.

```bash
find . -type f -not -path './.git/*' -not -path './.venv/*' | sort | head -40
.venv/bin/python -m pytest -v
```

**Voiceover:** "Fifty-four tests, a real C target, a host simulation of the
same sources, three scenario datasets, and a rule engine with no AI dependency."

**B-roll notes:** hold on the `pytest -v` summary line. Cut to
`docs/screenshots/` and the README.

---

## 2:50–3:00 — Close

**Screen:** black. Text fades in.

```
Open source. MIT. Built for QNX 8.0.
```

**Voiceover:** "RTArchitect. Open source, MIT licensed, built for QNX 8.0."

**B-roll notes:** hold 3 s. Cut to the GitHub URL.

---

## Recording checklist

- [ ] `pytest -q` is green before you roll (the 2:30 claim is 54 tests)
- [ ] The simulation run at 0:10 has at least 1 500 events
- [ ] The report at 0:30 is the one generated at 0:20 (do not regenerate)
- [ ] The comparison report at 1:20 is generated in the same take
- [ ] If `--ai` is used at 1:00, confirm the provider is configured; otherwise
      show the deterministic fallback and say so
- [ ] Audio: record room tone for 30 s first, keep the voice −6 dB under music

## Substitutions if a shot will not cooperate

| If… | then… |
|---|---|
| The sim is slow on the recording machine | pre-run it and screen-record the replay |
| `--ai` cannot be configured in time | shoot the fallback and keep the honest line |
| The comparison report looks sparse | use the golden logs instead of the sim logs at 1:20 |
| The terminal is too small to read | increase the font before recording, not after |
