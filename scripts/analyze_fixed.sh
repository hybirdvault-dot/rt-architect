#!/usr/bin/env bash
# Analyze the fixed demo log and write examples/reports/fixed_report.html.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

exec .venv/bin/rtarch tests/golden/synthetic_fixed.log \
  --scenario scenarios/brake_demo_fixed.json \
  --output examples/reports/fixed_report.html
