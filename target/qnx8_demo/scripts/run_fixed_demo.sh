#!/bin/sh
#
# Run the FIXED brake_controller demo on a QNX 8.0 target.
#
# The brake is split into two threads on two named channels:
#   rtarch/brake_fast  <- BRAKE_CMD        (perception_service)
#   rtarch/brake_slow  <- TELEMETRY_REQ / DIAG_REQ
#
# Usage:  sh scripts/run_fixed_demo.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

rm -f /tmp/rtarch_*.addr

echo "Starting RTArchitect FIXED demo..."

./brake_controller_fixed &
BRAKE=$!

./perception_service brake_fast brake_controller &
PERCEPTION=$!

./telemetry_client brake_slow brake_controller &
TELEMETRY=$!

./diagnostics_client brake_slow brake_controller &
DIAGNOSTICS=$!

./sensor_service perception_service &
SENSOR=$!

# Same iteration counts as the flawed demo.
echo "Running (6 s)..."
sleep 6

echo "Stopping services..."
kill "$SENSOR" "$TELEMETRY" "$DIAGNOSTICS" "$PERCEPTION" "$BRAKE" 2>/dev/null || true
wait 2>/dev/null || true

echo "Done. Extract the log with:  sh scripts/extract_slog2.sh"
