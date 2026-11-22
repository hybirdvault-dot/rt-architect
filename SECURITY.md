# Security Policy

## Supported Versions

The current `master` branch is the supported version. Fixes are made there and
released by tagging.

## Reporting a Vulnerability

Please do **not** open a public issue for security reports.

- Email: `security@rtarchitect.local` (replace with the maintainers' address)
- Include: the commit SHA, the affected component (`rtarch/` Python pipeline,
  `target/qnx8_demo/` C services, or `target/linux_sim/`), and a minimal
  reproduction.

Reports are acknowledged within 3 working days. A fix is developed in a private
fork and disclosed after the patched release is available.

## Scope notes

- The optional AI explainer (`--ai`) can send finding text to a configured
  OpenAI-compatible endpoint. Never point it at an endpoint you do not trust with
  your log contents, and never set `API_KEY` in a shared environment.
- The deterministic rule engine makes no network calls and reads only the log and
  scenario files it is given.
