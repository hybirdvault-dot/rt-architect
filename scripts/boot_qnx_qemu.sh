#!/usr/bin/env bash
#
# Boot the QNX 8.0 Quick Start Target Image for QEMU (QSTI).
#
# Preferred path: the QSTI ships its own launcher, which knows the right
# QEMU flags for the image.
#
#   source ~/qnx800/qnxsdp-env.sh
#   cd ~/qnx800/images/qemu/qemu
#   mkqnximage --run
#
# Fallback: if the QSTI is not installed, boot a raw disk image with the
# locally installed QEMU (scripts/setup_qemu_local.sh).
#
# Usage:
#   scripts/boot_qnx_qemu.sh                 # use mkqnximage --run
#   scripts/boot_qnx_qemu.sh <disk.img>      # fall back to raw QEMU

set -euo pipefail

QNX_SDP="${QNX_SDP:-$HOME/qnx800}"
QSTI_DIR="$QNX_SDP/images/qemu/qemu"
MKQNXIMAGE="$QNX_SDP/host/common/bin/mkqnximage"
QEMU_BIN="${QEMU_BIN:-$HOME/rt-architect-tools/qemu/bin/qemu-system-x86_64}"
RAW_IMAGE="${1:-${QNX_IMAGE:-qnx80-hdd.img}}"
SERIAL_OUT="${SERIAL_OUT:-/tmp/qnx_serial.txt}"

if [ -x "$MKQNXIMAGE" ] && [ -d "$QSTI_DIR" ]; then
    echo "Booting the QNX SDP 8.0 Quick Start Target Image for QEMU"
    echo "  image dir: $QSTI_DIR"
    echo "  login:     root / root"
    echo
    # shellcheck disable=SC1090
    source "$QNX_SDP/qnxsdp-env.sh"
    cd "$QSTI_DIR"
    exec mkqnximage --run
fi

# --- fallback: raw QEMU ------------------------------------------------
if [ ! -x "$QEMU_BIN" ]; then
    echo "ERROR: neither the QSTI nor a local QEMU was found." >&2
    echo "       QSTI:  install 'QNX SDP 8.0 Quick Start Target Image for QEMU'" >&2
    echo "       QEMU:  bash scripts/setup_qemu_local.sh" >&2
    exit 1
fi

if [ ! -f "$RAW_IMAGE" ]; then
    echo "ERROR: QNX disk image not found: $RAW_IMAGE" >&2
    echo "       Set QNX_IMAGE or pass it as the first argument." >&2
    exit 1
fi

echo "QSTI not found — booting $RAW_IMAGE with local QEMU"
echo "  serial console -> $SERIAL_OUT"
echo "  quit QEMU with: Ctrl-A then X"
echo

exec "$QEMU_BIN" \
    -m 512 \
    -smp 2 \
    -drive "file=$RAW_IMAGE,format=raw,if=ide" \
    -nographic \
    -serial "file:$SERIAL_OUT" \
    -netdev "user,id=n0,hostfwd=tcp::2222-:22" \
    -device e1000,netdev=n0 \
    -rtc base=utc \
    "$@"
