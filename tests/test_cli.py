"""End-to-end CLI tests via Typer's CliRunner."""

import os

from typer.testing import CliRunner

from rtarch.cli import app

ROOT = os.path.dirname(os.path.dirname(__file__))
GOLDEN_DIR = os.path.join(ROOT, "tests", "golden")
FLAWED_LOG = os.path.join(GOLDEN_DIR, "synthetic_flawed.log")
FIXED_LOG = os.path.join(GOLDEN_DIR, "synthetic_fixed.log")
FLAWED_SCENARIO = os.path.join(ROOT, "scenarios", "brake_demo.json")
FIXED_SCENARIO = os.path.join(ROOT, "scenarios", "brake_demo_fixed.json")

runner = CliRunner()


def test_cli_generates_flawed_report(tmp_path):
    out = tmp_path / "report.html"
    result = runner.invoke(
        app,
        ["analyze", FLAWED_LOG, "--scenario", FLAWED_SCENARIO, "--output", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert out.exists()
    html = out.read_text(encoding="utf-8")
    assert "BOTTLENECK-001" in html
    assert "CRITICAL-PATH-001" in html


def test_cli_generates_clean_fixed_report(tmp_path):
    out = tmp_path / "fixed.html"
    result = runner.invoke(
        app,
        ["analyze", FIXED_LOG, "--scenario", FIXED_SCENARIO, "--output", str(out)],
    )
    assert result.exit_code == 0, result.output
    html = out.read_text(encoding="utf-8")
    assert "No deterministic findings" in html


def test_cli_compare_produces_comparison_report(tmp_path):
    out = tmp_path / "comparison.html"
    result = runner.invoke(
        app,
        [
            "compare",
            FLAWED_LOG,
            FIXED_LOG,
            "--scenario",
            FLAWED_SCENARIO,
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    html = out.read_text(encoding="utf-8")
    assert "Architecture Comparison" in html
    assert "BOTTLENECK-001" in html
    assert "cleared" in html


def test_cli_reports_malformed_lines(tmp_path):
    noisy = tmp_path / "noisy.log"
    noisy.write_text(
        "noise line\n"
        "RTARCH v=1 ts_ns=100 phase=SEND trace_id=1 msg_id=1 "
        "src_pid=1 src_name=a dst_pid=2 dst_name=b msg_type=X prio=10\n"
    )
    out = tmp_path / "report.html"
    result = runner.invoke(
        app,
        ["analyze", str(noisy), "--scenario", FLAWED_SCENARIO, "--output", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert "1" in result.output
