#!/usr/bin/env bash
# Analyze the flawed demo log and write examples/reports/flawed_report.html.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

exec .venv/bin/rtarch tests/golden/synthetic_flawed.log \
  --scenario scenarios/brake_demo.json \
  --output examples/reports/flawed_report.html
