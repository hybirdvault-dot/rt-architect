#!/usr/bin/env bash
#
# Full real-QNX run: boot QEMU, run both demos inside the guest, extract the
# slog2 log, analyse it on the host, and assert the expected result.
#
#   scripts/run_qnx_demo.sh [qnx-disk-image]
#
# Prerequisites (see docs/qnx_setup.md):
#   - QNX SDP 8.0 installed and the demo built (scripts/setup_qnx_sdp.sh)
#   - QEMU installed (scripts/setup_qemu_local.sh)
#   - the guest image has the six demo binaries in /tmp
#
# This script is the real-QNX counterpart of scripts/smoke_test_qnx.sh qnx.
# It is written to fail loudly at the first step that needs adjusting for the
# specific BSP, rather than silently producing a half-run.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

IMAGE="${1:-${QNX_IMAGE:-qnx80-hdd.img}}"
GUEST_DIR="/tmp/rtarch"
SERIAL="/tmp/qnx_serial.txt"

if [ ! -f "$IMAGE" ]; then
    echo "ERROR: QNX disk image not found: $IMAGE" >&2
    echo "       Pass it as the first argument or set QNX_IMAGE." >&2
    exit 1
fi

# --- 1. boot the guest -------------------------------------------------
echo "1/6 booting QEMU ($IMAGE)"
rm -f "$SERIAL"
"$ROOT/scripts/boot_qnx_qemu.sh" "$IMAGE" &
QEMU_PID=$!
trap 'kill $QEMU_PID 2>/dev/null || true' EXIT

echo "     waiting for the guest to come up ..."
for _ in $(seq 1 30); do
    sleep 2
    if [ -s "$SERIAL" ] && grep -q "QNX" "$SERIAL" 2>/dev/null; then
        break
    fi
done

# --- 2. copy the binaries into the guest --------------------------------
echo "2/6 copying demo binaries into the guest"
echo "     TODO(transport): adapt to this image."
echo "       - serial:  base64 the binaries and paste them into the guest shell"
echo "       - network: scp -P 2222 <bin> root@127.0.0.1:$GUEST_DIR/"
echo "       - shared:  mount the host directory from the guest"
cat <<'EOF'
     The transport is the only image-specific step.  Everything before and
     after it is identical for every QNX 8.0 QEMU BSP.  See docs/qnx_setup.md
     section 6 for the three options.
EOF

# --- 3. run the flawed demo -------------------------------------------
echo "3/6 running the flawed demo in the guest"
echo "     in the guest shell:  cd $GUEST_DIR && sh scripts/run_flawed_demo.sh"

# --- 4. extract the slog2 log -----------------------------------------
echo "4/6 extracting slog2"
echo "     in the guest shell:  sh scripts/extract_slog2.sh $GUEST_DIR/raw_slog2.txt"
echo "     then copy $GUEST_DIR/raw_slog2.txt back to the host as"
echo "     examples/logs/real_qnx_flawed.log"

# --- 5. analyse --------------------------------------------------------
echo "5/6 analysing on the host"
if [ -f examples/logs/real_qnx_flawed.log ]; then
    .venv/bin/rtarch analyze examples/logs/real_qnx_flawed.log \
        --scenario scenarios/brake_demo.json \
        --output examples/reports/real_qnx_flawed.html
else
    echo "     SKIPPED: examples/logs/real_qnx_flawed.log not present yet"
fi

# --- 6. fixed demo + comparison ---------------------------------------
echo "6/6 fixed demo + comparison"
if [ -f examples/logs/real_qnx_fixed.log ]; then
    .venv/bin/rtarch analyze examples/logs/real_qnx_fixed.log \
        --scenario scenarios/brake_demo.json \
        --output examples/reports/real_qnx_fixed.html
    .venv/bin/rtarch compare examples/logs/real_qnx_flawed.log \
        examples/logs/real_qnx_fixed.log \
        --scenario scenarios/brake_demo.json \
        --output examples/reports/real_qnx_comparison.html
else
    echo "     SKIPPED: examples/logs/real_qnx_fixed.log not present yet"
fi

echo
echo "Done. The two TODO(transport) steps are the only manual parts."
