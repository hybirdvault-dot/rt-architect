#!/bin/sh
#
# Run the FLAWED brake_controller demo on a QNX 8.0 target.
#
# Starts all five services, lets them run for a few seconds, then stops them.
# The RTARCH events accumulate in the slog2 buffer set "rtarch"; extract them
# with scripts/extract_slog2.sh.
#
# Usage:  sh scripts/run_flawed_demo.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

rm -f /tmp/rtarch_*.addr

echo "Starting RTArchitect flawed demo..."

./brake_controller &
BRAKE=$!

./perception_service brake_controller &
PERCEPTION=$!

./telemetry_client brake_controller &
TELEMETRY=$!

./diagnostics_client brake_controller &
DIAGNOSTICS=$!

./sensor_service perception_service &
SENSOR=$!

# Wait long enough for every client to finish its iteration count.
# sensor: 200 x 5 ms, telemetry: 100 x 50 ms, diagnostics: 50 x 100 ms
echo "Running (6 s)..."
sleep 6

echo "Stopping services..."
kill "$SENSOR" "$TELEMETRY" "$DIAGNOSTICS" "$PERCEPTION" "$BRAKE" 2>/dev/null || true
wait 2>/dev/null || true

echo "Done. Extract the log with:  sh scripts/extract_slog2.sh"
