# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- **P0-1** the documented `rtarch` commands now include the `analyze` subcommand;
  the Quick Start works verbatim on a fresh clone.
- **P0-2** the AI-output validator rejects invented and distorted numbers
  (token-boundary matching), hallucinated APIs (explicit allowlist over the
  explanation and the refactor plan), and scans the finding's evidence rather
  than only `observed`.
- **P0-3** both brake controllers shut down on SIGINT/SIGTERM: shared shutdown
  flag, `_NTO_CHF_UNBLOCK` channels, a pulse wake for workers blocked in
  `MsgReceive`, a bounded timed join, and `MsgError(rcvid, ENOTSUP)` for unknown
  message kinds. Verified on real QNX 8.0.
- **P0-4** the "exactly as captured" slog2 line in the docs is now a real captured
  line (the previous one existed in no log).
- **P0-5** `docs/verification.md`'s definition-of-done now matches the tool's
  actual output.
- QUEUE-WAIT findings are deduplicated per edge, not per node.
- Node "p95 processing" is pooled over all incoming samples (was
  max-of-incoming-edge-p95s).
- The A/B demo variants use identical service times, so only the thread split
  differs.
- Reports embed a provenance footer (source path, size, SHA-256) and a
  log-derived timestamp; two runs on one log are byte-identical.
- The parser rejects a truncated `msg_type`; scenario JSON is validated on load.
- Hygiene: ruff and mypy clean, pinned `requirements.lock`, the compiled QNX
  binaries removed from git (and from history), CI runs lint, types, tests and
  the verification harness.

### Added

- `verify/` — a six-layer verification harness (64 checks, exit 0/1/2) with
  mutation tests, wired into CI.
- `SECURITY.md`, `CHANGELOG.md`.

### Changed

- The evidence table now reports the pooled p95 values (10.19 ms / 0.35 ms).
