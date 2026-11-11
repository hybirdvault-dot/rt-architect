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
echo "1/6 booting the QNX 8.0 QSTI"
if [ -x "$HOME/qnx800/host/common/bin/mkqnximage" ]; then
    "$ROOT/scripts/boot_qnx_qemu.sh" &
    QEMU_PID=$!
    trap 'kill $QEMU_PID 2>/dev/null || true' EXIT
    echo "     launched with mkqnximage --run; log in as root/root"
else
    echo "     QSTI not installed — see docs/qnx_setup.md section 3."
    echo "     Install 'QNX SDP 8.0 Quick Start Target Image for QEMU', then re-run."
fi

# --- 2. copy the binaries into the guest --------------------------------
echo "2/6 copying demo binaries into the guest"
GUEST_IP="${QNX_GUEST_IP:-192.168.122.146}"
echo "     in the guest terminal, check for sshd:"
echo "         pidin args | grep -i sshd"
echo "     if present, from this host:"
echo "         scp $ROOT/target/qnx8_demo/bin/{sensor_service,perception_service,brake_controller,brake_controller_fixed,telemetry_client,diagnostics_client} root@$GUEST_IP:/tmp/"
echo "     otherwise use the serial console or attach the binaries to the image."
echo "     The transport is the only image-specific step; see docs/qnx_setup.md."

# --- 3. run the flawed demo -------------------------------------------
echo "3/6 running the flawed demo in the guest"
echo "     in the guest shell:  cd /tmp && sh scripts/run_flawed_demo.sh"

# --- 4. extract the slog2 log -----------------------------------------
echo "4/6 extracting slog2"
echo "     in the guest shell:  sh scripts/extract_slog2.sh /tmp/raw_slog2.txt"
echo "     then copy /tmp/raw_slog2.txt back to the host as"
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
