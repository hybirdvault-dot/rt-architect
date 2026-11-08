#!/bin/sh
#
# Dump the slog2 buffer to a file on the QNX target.
#
# The RTARCH lines are then extracted from the host with the Python CLI, which
# searches for the RTARCH marker anywhere in each line (so the slog2 header
# prefix does not matter).
#
# Usage:  sh scripts/extract_slog2.sh [output_path_on_target]
#         default output: /tmp/raw_slog2.txt

set -e

OUT="${1:-/tmp/raw_slog2.txt}"

echo "Dumping slog2 buffers to $OUT ..."
slog2info > "$OUT"

echo "Wrote $OUT"
wc -l "$OUT"
echo
echo "Next: copy $OUT to the Linux host, then run:"
echo "  .venv/bin/rtarch $OUT -s scenarios/brake_demo.json -o real_report.html"
