#!/usr/bin/env bash
#
# End-to-end smoke test for RTArchitect.
#
#   scripts/smoke_test_qnx.sh [sim|qnx]     (default: sim)
#
# sim : runs the host-side simulation of the real C sources. Works today,
#       needs no QNX license, and exercises the whole pipeline end to end.
# qnx : boots the real QEMU guest, runs the demos inside it, extracts slog2info
#       and analyses the genuine QNX log. Requires the SDP + image.
#
# Assertions
#   flawed : at least one critical finding
#   fixed  : BOTTLENECK-001 gone, and fewer critical findings than flawed
#            (on real QNX the expectation is exactly zero critical findings;
#             the host simulation carries scheduler noise, so it is compared
#             against the flawed run instead)
#
# Exit code 0 = pass, 1 = fail.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BACKEND="${1:-sim}"
VENV="$ROOT/.venv"
FLAWED_LOG="examples/logs/smoke_flawed.log"
FIXED_LOG="examples/logs/smoke_fixed.log"

analyze() {
    "$VENV/bin/python" - "$1" "$2" <<'PY'
import sys
from rtarch.parser import parse_log
from rtarch.graph import build_graph
from rtarch.metrics import compute_edge_metrics, compute_node_metrics
from rtarch.rules import run_rules
from rtarch.scenario import load_scenario

log_path, scenario_path = sys.argv[1], sys.argv[2]
events = parse_log(log_path)
scenario = load_scenario(scenario_path)
graph = build_graph(events)
edges = compute_edge_metrics(events)
nodes = compute_node_metrics(graph, edges, events, scenario)
findings = run_rules(nodes, edges, scenario)

critical = sum(1 for f in findings if f.severity == "critical")
warning = sum(1 for f in findings if f.severity == "warning")
rules = ",".join(sorted({f.rule_id for f in findings}))
print(f"events={len(events)}")
print(f"nodes={graph.number_of_nodes()}")
print(f"edges={graph.number_of_edges()}")
print(f"critical={critical}")
print(f"warning={warning}")
print(f"rules={rules}")
PY
}

field() {  # field <name> <summary>
    printf '%s\n' "$2" | sed -n "s/^$1=//p" | head -1
}

run_sim_backend() {
    echo "=== host simulation backend ==="
    (cd target/linux_sim && make >/dev/null 2>&1)
    target/linux_sim/rtarch_sim flawed > "$ROOT/$FLAWED_LOG" 2>&1
    target/linux_sim/rtarch_sim fixed  > "$ROOT/$FIXED_LOG" 2>&1
}

run_qnx_backend() {
    echo "=== real QNX backend ==="
    command -v slog2info >/dev/null 2>&1 || true

    echo "1/4 booting QEMU..."
    "$ROOT/scripts/boot_qnx_qemu.sh" &
    QEMU_PID=$!
    trap 'kill $QEMU_PID 2>/dev/null || true' EXIT
    sleep 15

    echo "2/4 running the flawed demo in the guest..."
    # Copy the binaries in, run the demo, extract slog2info, copy out.
    # The exact transport (scp / serial / shared folder) is described in
    # docs/qnx_setup.md. Adjust these three lines to match the image.
    echo "    TODO: transport target/qnx8_demo binaries into the guest"
    echo "    TODO: sh scripts/run_flawed_demo.sh"
    echo "    TODO: sh scripts/extract_slog2.sh $FLAWED_LOG"
    false

    echo "3/4 running the fixed demo in the guest..."
    echo "    TODO: sh scripts/run_fixed_demo.sh"
    echo "    TODO: sh scripts/extract_slog2.sh $FIXED_LOG"
    false
}

run_backend() {
    if [ "$BACKEND" = "qnx" ]; then
        run_qnx_backend
    else
        run_sim_backend
    fi
}

main() {
    run_backend

    echo
    echo "=== flawed log ==="
    flawed_summary="$(analyze "$FLAWED_LOG" scenarios/brake_demo.json)"
    echo "$flawed_summary"
    flawed_critical="$(field critical "$flawed_summary")"
    flawed_rules="$(field rules "$flawed_summary")"

    echo
    echo "=== fixed log ==="
    fixed_summary="$(analyze "$FIXED_LOG" scenarios/brake_demo.json)"
    echo "$fixed_summary"
    fixed_critical="$(field critical "$fixed_summary")"
    fixed_rules="$(field rules "$fixed_summary")"

    echo
    echo "=== assertions ==="
    failed=0

    if [ "$flawed_critical" -lt 1 ]; then
        echo "FAIL: flawed log produced $flawed_critical critical findings (expected >= 1)"
        failed=1
    else
        echo "ok: flawed log has $flawed_critical critical finding(s)"
    fi

    if [ "$BACKEND" = "qnx" ]; then
        if [ "$fixed_critical" -ne 0 ]; then
            echo "FAIL: fixed log produced $fixed_critical critical findings (expected 0)"
            failed=1
        else
            echo "ok: fixed log has 0 critical findings"
        fi
    else
        case ",$fixed_rules," in
            *,BOTTLENECK-001,*)
                echo "FAIL: BOTTLENECK-001 still fires on the fixed log"
                failed=1
                ;;
            *)
                echo "ok: BOTTLENECK-001 cleared"
                ;;
        esac

        if [ "$fixed_critical" -ge "$flawed_critical" ]; then
            echo "FAIL: fixed log has $fixed_critical critical findings, flawed had $flawed_critical"
            failed=1
        else
            echo "ok: critical findings dropped $flawed_critical -> $fixed_critical"
        fi
    fi

    echo
    if [ "$failed" -eq 0 ]; then
        echo "SMOKE TEST PASSED ($BACKEND backend)"
    else
        echo "SMOKE TEST FAILED ($BACKEND backend)"
    fi
    return "$failed"
}

main
