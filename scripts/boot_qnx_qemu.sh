#!/usr/bin/env bash
#
# Boot a QNX 8.0 QEMU image with a single command.
#
# Usage:
#   scripts/setup_qemu_local.sh              # one-off: install QEMU privately
#   scripts/boot_qnx_qemu.sh [image]         # boot the guest
#
# Environment:
#   QEMU_BIN   path to the qemu-system-x86_64 wrapper
#              (default: ~/rt-architect-tools/qemu/bin/qemu-system-x86_64)
#   QNX_IMAGE  path to the bootable QNX disk image
#              (default: ./qnx80-hdd.img)
#
# The guest serial console is captured to /tmp/qnx_serial.txt, which is how
# `slog2info` output is read back on the host (see docs/qnx_setup.md).

set -euo pipefail

QEMU_BIN="${QEMU_BIN:-$HOME/rt-architect-tools/qemu/bin/qemu-system-x86_64}"
QNX_IMAGE="${1:-${QNX_IMAGE:-qnx80-hdd.img}}"
SERIAL_OUT="${SERIAL_OUT:-/tmp/qnx_serial.txt}"
HOST_SSH_PORT="${HOST_SSH_PORT:-2222}"

if [ ! -x "$QEMU_BIN" ]; then
    echo "ERROR: QEMU not found at $QEMU_BIN" >&2
    echo "       Run: bash scripts/setup_qemu_local.sh" >&2
    exit 1
fi

if [ ! -f "$QNX_IMAGE" ]; then
    echo "ERROR: QNX disk image not found: $QNX_IMAGE" >&2
    echo "       Set QNX_IMAGE or pass it as the first argument." >&2
    exit 1
fi

echo "Booting QNX 8.0 from $QNX_IMAGE"
echo "  serial console -> $SERIAL_OUT"
echo "  hostfwd ssh    -> localhost:$HOST_SSH_PORT"
echo "  quit QEMU with: Ctrl-A then X"
echo

exec "$QEMU_BIN" \
    -m 512 \
    -smp 2 \
    -drive "file=$QNX_IMAGE,format=raw,if=ide" \
    -nographic \
    -serial "file:$SERIAL_OUT" \
    -netdev "user,id=n0,hostfwd=tcp::$HOST_SSH_PORT-:22" \
    -device e1000,netdev=n0 \
    -rtc base=utc \
    "$@"
