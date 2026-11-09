#!/usr/bin/env bash
#
# Install the QNX SDP 8.0 from its installer and build the demo services.
#
#   scripts/setup_qnx_sdp.sh <installer.run> [install_prefix]
#
# Default install prefix: ~/qnx800
#
# What this does:
#   1. runs the QNX installer into a user-writable prefix (no root needed)
#   2. sources qnxsdp-env.sh
#   3. builds all six demo services with the real qcc
#   4. reports the qcc version and the binaries it produced
#
# If the installer needs a display, run it yourself with:
#   ./<installer>.run            (GUI)  or  ./<installer>.run -i console
# then re-run this script with --env-only to skip straight to the build.

set -euo pipefail

INSTALLER=""
PREFIX="${QNX_SDP_PREFIX:-$HOME/qnx800}"
ENV_ONLY=0

while [ $# -gt 0 ]; do
    case "$1" in
        --env-only) ENV_ONLY=1; shift ;;
        -*) echo "unknown option: $1" >&2; exit 2 ;;
        *) if [ -z "$INSTALLER" ]; then INSTALLER="$1"; else PREFIX="$1"; fi; shift ;;
    esac
done

if [ "$ENV_ONLY" -eq 0 ]; then
    if [ -z "$INSTALLER" ]; then
        echo "usage: $0 <qnx800-linux-x86_64-installer.run> [install_prefix]" >&2
        echo "   or: $0 --env-only            (skip the install, just build)" >&2
        exit 2
    fi
    if [ ! -f "$INSTALLER" ]; then
        echo "ERROR: installer not found: $INSTALLER" >&2
        exit 1
    fi

    chmod +x "$INSTALLER"
    echo "Installing QNX SDP 8.0 into $PREFIX ..."
    # The QNX installer is a InstallAnywhere/Qt installer.  Try the silent
    # forms first; fall back to the interactive console mode.
    if ! "$INSTALLER" --mode silent --prefix "$PREFIX" --accept-licenses 2>/dev/null; then
        if ! "$INSTALLER" -i console --prefix "$PREFIX" --accept-licenses 2>/dev/null; then
            echo
            echo "Silent install failed. Run the installer interactively:" >&2
            echo "    $INSTALLER -i console --prefix $PREFIX" >&2
            echo "then re-run: $0 --env-only" >&2
            exit 1
        fi
    fi
fi

ENV_SH="$PREFIX/qnxsdp-env.sh"
if [ ! -f "$ENV_SH" ]; then
    echo "ERROR: $ENV_SH not found — the SDP is not installed at $PREFIX" >&2
    exit 1
fi

echo
echo "Sourcing $ENV_SH"
# shellcheck disable=SC1090
source "$ENV_SH"

echo "qcc: $(command -v qcc)"
qcc -V 2>&1 | head -1 || true

echo
echo "Building the demo services ..."
make -C "$(dirname "${BASH_SOURCE[0]}")/../target/qnx8_demo" clean
make -C "$(dirname "${BASH_SOURCE[0]}")/../target/qnx8_demo" all

echo
echo "Done. Binaries:"
ls -1 "$(dirname "${BASH_SOURCE[0]}")/../target/qnx8_demo"/sensor_service \
      "$(dirname "${BASH_SOURCE[0]}")/../target/qnx8_demo"/perception_service \
      "$(dirname "${BASH_SOURCE[0]}")/../target/qnx8_demo"/brake_controller \
      "$(dirname "${BASH_SOURCE[0]}")/../target/qnx8_demo"/brake_controller_fixed \
      "$(dirname "${BASH_SOURCE[0]}")/../target/qnx8_demo"/telemetry_client \
      "$(dirname "${BASH_SOURCE[0]}")/../target/qnx8_demo"/diagnostics_client
