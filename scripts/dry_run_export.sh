#!/usr/bin/env bash
#
# Dry-run the log export path against the host simulation.
#
# On real QNX the handoff is:  slog2info > raw_slog2.txt   (inside the guest)
#                              scp raw_slog2.txt .        (to the host)
#                              rtarch raw_slog2.txt ...   (analyse)
#
# This script proves the host half of that handoff with zero manual editing:
# it takes a raw slog2 capture, keeps only the RTARCH lines exactly as the
# parser does, and runs the CLI. Point it at a real slog2info dump once the
# QNX image arrives.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RAW_LOG="${1:-examples/logs/sim_flawed_slog2.txt}"
SCENARIO="${2:-scenarios/brake_demo.json}"
OUT="${3:-/tmp/dry_run_report.html}"

if [ ! -f "$RAW_LOG" ]; then
    echo "ERROR: log not found: $RAW_LOG" >&2
    exit 1
fi

FILTERED="$(mktemp)"
trap 'rm -f "$FILTERED"' EXIT

echo "Raw log:      $RAW_LOG ($(wc -l < "$RAW_LOG") lines)"
grep RTARCH "$RAW_LOG" > "$FILTERED" || true
echo "RTARCH lines: "$(wc -l < "$FILTERED")
echo

.venv/bin/rtarch "$FILTERED" --scenario "$SCENARIO" --output "$OUT"
echo
echo "Filtered log: $FILTERED"
echo "Report:       $OUT"
