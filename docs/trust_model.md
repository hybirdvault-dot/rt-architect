# Trust Model — Deterministic First

## The one rule that must never break

> **If AI is not working, ship without AI. Never ship without the rule engine.**

## Why deterministic first

Architectural findings are used to make changes to safety-relevant systems. A
finding must therefore be:

1. **Reproducible** — the same log and the same scenario always produce the
   same findings.
2. **Auditable** — every finding states the condition, the observed values and
   the thresholds that triggered it.
3. **Bounded** — the tool never crashes or hangs because an external service is
   unavailable.

A deterministic rule engine satisfies all three. A language model satisfies
none of them on its own.

## The role of AI

AI explanation is an *optional* layer on top of the deterministic core. It can
make a finding easier to understand, but it can never introduce a finding, and
it can never change a number.

The AI layer is guarded by three independent mechanisms:

| Guard | Purpose |
|---|---|
| `try/except` around the call | Any failure falls back to the deterministic template |
| 5 second timeout | A slow API cannot hang the analysis |
| Output validation | Unknown APIs and mismatched numbers are rejected |

If any guard trips, the deterministic template takes over and the report says
so.

## What this means in practice

- The rule engine is always present and always runs.
- AI is enabled by an explicit opt-in flag.
- The report is complete and correct with AI disabled.
- No network access is required for the core analysis.

## Threat mitigations

| Threat | Shield | Where |
|---|---|---|
| Hardcoded toy objection | Everything config-driven | `scenarios/*.json` |
| slog2 parsing fragility | `RTARCH` pre-filter + malformed-line skip | `rtarch/parser.py` |
| AI JSON crash | try/except + timeout + fallback | (Phase 2) `rtarch/ai.py` |
| QNX/QEMU unavailable | Golden synthetic logs | `tests/golden/` |
| Scope creep | Deterministic core first, AI later | Phase plan |
