#!/usr/bin/env bash
#
# Build and run the FIXED brake_controller simulation.
#
# Produces examples/logs/sim_fixed_slog2.txt and then analyses it with the
# RTArchitect CLI.  Expected: BOTTLENECK-001, HEAD-OF-LINE-001 and
# CRITICAL-PATH-001 clear; SPOF-001 remains.
#
# NOTE: host-side simulation, not QNX.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$ROOT/../.." && pwd)"
cd "$ROOT"

make clean >/dev/null
make

LOG="$REPO/examples/logs/sim_fixed_slog2.txt"
mkdir -p "$(dirname "$LOG")"

echo "Running FIXED simulation..."
./rtarch_sim fixed > "$LOG" 2>&1

echo "Log written: $LOG"
echo "RTARCH events: $(grep -c RTARCH "$LOG")"
echo

cd "$REPO"
.venv/bin/rtarch "$LOG" \
  --scenario scenarios/brake_demo.json \
  --output examples/reports/sim_fixed_report.html
