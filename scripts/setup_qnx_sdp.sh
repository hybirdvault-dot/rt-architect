#!/usr/bin/env bash
#
# Point the demo at an installed QNX SDP 8.0 and build the services with qcc.
#
# The SDP is normally installed by the QNX Software Center (see
# docs/qnx_setup.md section 3), which puts it in ~/qnx800 by default.  This
# script then sources the environment and builds.
#
# Usage:
#   scripts/setup_qnx_sdp.sh                     # use ~/qnx800
#   scripts/setup_qnx_sdp.sh --prefix /opt/qnx800
#   scripts/setup_qnx_sdp.sh --installer <x.run> # run an installer first
#
# The QNX Software Center installs to a location it chooses; pass --prefix
# if it is not ~/qnx800.

set -euo pipefail

PREFIX="${QNX_SDP:-$HOME/qnx800}"
INSTALLER=""

while [ $# -gt 0 ]; do
    case "$1" in
        --prefix)   PREFIX="$2"; shift 2 ;;
        --installer) INSTALLER="$2"; shift 2 ;;
        -*) echo "unknown option: $1" >&2; exit 2 ;;
        *)  echo "usage: $0 [--prefix <dir>] [--installer <file.run>]" >&2; exit 2 ;;
    esac
done

# --- optional: run a raw installer ------------------------------------
if [ -n "$INSTALLER" ]; then
    if [ ! -f "$INSTALLER" ]; then
        echo "ERROR: installer not found: $INSTALLER" >&2
        exit 1
    fi
    chmod +x "$INSTALLER"
    echo "Running $INSTALLER into $PREFIX ..."
    if ! "$INSTALLER" --mode silent --prefix "$PREFIX" --accept-licenses 2>/dev/null; then
        echo "Silent install failed; run it interactively:" >&2
        echo "    $INSTALLER -i console --prefix $PREFIX" >&2
        echo "then re-run this script with --prefix $PREFIX" >&2
        exit 1
    fi
fi

# --- locate the SDP environment ---------------------------------------
ENV_SH="$PREFIX/qnxsdp-env.sh"
if [ ! -f "$ENV_SH" ]; then
    cat >&2 <<EOF
ERROR: $ENV_SH not found.

The QNX SDP 8.0 is installed by the QNX Software Center, not by this script.
Steps (docs/qnx_setup.md):

  1. accept and deploy the licence in myQNX License Manager
  2. run ~/qnx/qnxsoftwarecenter/qnxsoftwarecenter and log in
  3. install "QNX SDP 8.0" for the Linux host
  4. install "QNX SDP 8.0 Quick Start Target Image for QEMU"
  5. re-run this script, adding --prefix if it installed somewhere else
EOF
    exit 1
fi

echo "Sourcing $ENV_SH"
# shellcheck disable=SC1090
source "$ENV_SH"

QCC_BIN="$(command -v qcc || true)"
if [ -z "$QCC_BIN" ]; then
    echo "ERROR: qcc not on PATH after sourcing $ENV_SH" >&2
    exit 1
fi
echo "qcc: $QCC_BIN"
qcc -V 2>&1 | head -1 || true

echo
echo "Building the demo services ..."
DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/target/qnx8_demo"
make -C "$DEMO_DIR" clean
make -C "$DEMO_DIR" all

echo
echo "Done. Binaries:"
ls -1 "$DEMO_DIR"/sensor_service \
      "$DEMO_DIR"/perception_service \
      "$DEMO_DIR"/brake_controller \
      "$DEMO_DIR"/brake_controller_fixed \
      "$DEMO_DIR"/telemetry_client \
      "$DEMO_DIR"/diagnostics_client

echo
echo "Next: bash scripts/run_qnx_demo.sh"
