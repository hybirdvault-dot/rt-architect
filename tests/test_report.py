"""Report generation tests."""

import os
from html import escape

from rtarch.graph import build_graph
from rtarch.metrics import compute_edge_metrics, compute_node_metrics
from rtarch.parser import parse_log
from rtarch.report import generate_report
from rtarch.rules import run_rules
from rtarch.scenario import load_scenario

ROOT = os.path.dirname(os.path.dirname(__file__))
GOLDEN_DIR = os.path.join(ROOT, "tests", "golden")
FLAWED_LOG = os.path.join(GOLDEN_DIR, "synthetic_flawed.log")
FIXED_LOG = os.path.join(GOLDEN_DIR, "synthetic_fixed.log")
FLAWED_SCENARIO = os.path.join(ROOT, "scenarios", "brake_demo.json")
FIXED_SCENARIO = os.path.join(ROOT, "scenarios", "brake_demo_fixed.json")


def _build(log_path, scenario_path):
    events = parse_log(log_path)
    scenario = load_scenario(scenario_path)
    graph = build_graph(events)
    edges = compute_edge_metrics(events)
    nodes = compute_node_metrics(graph, edges, events, scenario)
    findings = run_rules(nodes, edges, scenario)
    return findings, nodes, edges, scenario, graph


def test_report_contains_findings_graph_and_metrics(tmp_path):
    findings, nodes, edges, scenario, graph = _build(FLAWED_LOG, FLAWED_SCENARIO)
    out = tmp_path / "report.html"
    generate_report(findings, nodes, edges, scenario, str(out), graph=graph)

    html = out.read_text(encoding="utf-8")
    assert "RTArchitect" in html
    assert "<svg" in html
    for finding in findings:
        assert escape(finding.title) in html
        assert finding.rule_id in html
    assert "brake_controller" in html
    assert "BOTTLENECK-001" in html
    assert "perception_service" in html
    # SVG nodes use a distinct class so they never inherit the card styles.
    assert "has-finding" in html
    assert 'class="node finding"' not in html
    assert 'class="node critical has-finding"' in html


def test_report_states_when_architecture_is_clean(tmp_path):
    findings, nodes, edges, scenario, graph = _build(FIXED_LOG, FIXED_SCENARIO)
    out = tmp_path / "fixed.html"
    generate_report(findings, nodes, edges, scenario, str(out), graph=graph)

    html = out.read_text(encoding="utf-8")
    assert "No deterministic findings" in html
    assert "brake_controller_fast" in html


def test_report_creates_missing_output_directories(tmp_path):
    findings, nodes, edges, scenario, graph = _build(FIXED_LOG, FIXED_SCENARIO)
    out = tmp_path / "nested" / "deep" / "report.html"
    generate_report(findings, nodes, edges, scenario, str(out), graph=graph)
    assert out.exists()
