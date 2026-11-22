#!/usr/bin/env python3
"""RTArchitect verification harness.

Usage:
    python verify/run_verify.py              # run all six layers
    python verify/run_verify.py --layer 2    # run one layer
    python verify/run_verify.py --list       # list checks

Writes verify/scorecard.md and exits 0 (GREEN), 1 (YELLOW) or 2 (RED).
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verify.layers import LAYERS
from verify.models import Scorecard
from verify.scorecard import write


def main() -> int:
    parser = argparse.ArgumentParser(description="RTArchitect verification harness")
    parser.add_argument("--layer", type=int, choices=sorted(LAYERS), action="append",
                        help="run only this layer (repeatable)")
    parser.add_argument("--list", action="store_true", help="list layers and exit")
    args = parser.parse_args()

    if args.list:
        for number, fn in sorted(LAYERS.items()):
            print(f"layer {number}: {fn.__name__}")
        return 0

    selected = args.layer or sorted(LAYERS)
    scorecard = Scorecard()

    for number in selected:
        fn = LAYERS[number]
        print(f"=== layer {number} ({fn.__name__}) ===", flush=True)
        before = len(scorecard.results)
        try:
            fn(scorecard)
        except Exception as exc:               # noqa: BLE001 - a crashing layer is a failed check
            scorecard.add(__import__("verify.models", fromlist=["CheckResult"]).CheckResult(
                number, f"{fn.__name__} crashed", "FAIL", "P0", repr(exc)))
        for r in scorecard.results[before:]:
            print(f"  [{r.verdict}] {r.name}: {r.evidence[:120]}", flush=True)

    path = write(scorecard, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scorecard.md"))
    counts = scorecard.counts()
    code = scorecard.exit_code()
    print(f"\nscorecard: {path}")
    print(f"checks={len(scorecard.results)} PASS={counts.get('PASS', 0)} "
          f"FAIL={counts.get('FAIL', 0)} WARN={counts.get('WARN', 0)}")
    print(f"exit code: {code} ({'GREEN' if code == 0 else 'YELLOW' if code == 1 else 'RED'})")
    return code


if __name__ == "__main__":
    sys.exit(main())
