"""Rule-engine tests: all five rules fire on the flawed log, none on the fixed log."""

import os

from rtarch.graph import build_graph
from rtarch.metrics import compute_edge_metrics, compute_node_metrics
from rtarch.parser import parse_log
from rtarch.rules import run_rules
from rtarch.scenario import load_scenario

ROOT = os.path.dirname(os.path.dirname(__file__))
GOLDEN_DIR = os.path.join(ROOT, "tests", "golden")
FLAWED_LOG = os.path.join(GOLDEN_DIR, "synthetic_flawed.log")
FIXED_LOG = os.path.join(GOLDEN_DIR, "synthetic_fixed.log")
PUMP_LOG = os.path.join(GOLDEN_DIR, "synthetic_pump.log")
ROBOT_LOG = os.path.join(GOLDEN_DIR, "synthetic_robot.log")
FLAWED_SCENARIO = os.path.join(ROOT, "scenarios", "brake_demo.json")
FIXED_SCENARIO = os.path.join(ROOT, "scenarios", "brake_demo_fixed.json")
PUMP_SCENARIO = os.path.join(ROOT, "scenarios", "medical_pump.json")
ROBOT_SCENARIO = os.path.join(ROOT, "scenarios", "industrial_robot.json")

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def _run(log_path, scenario_path):
    events = parse_log(log_path)
    scenario = load_scenario(scenario_path)
    graph = build_graph(events)
    edges = compute_edge_metrics(events)
    nodes = compute_node_metrics(graph, edges, events, scenario)
    return run_rules(nodes, edges, scenario), nodes, edges


def test_flawed_log_triggers_all_five_rules():
    findings, _, _ = _run(FLAWED_LOG, FLAWED_SCENARIO)
    assert {f.rule_id for f in findings} == {
        "CRITICAL-PATH-001",
        "BOTTLENECK-001",
        "HEAD-OF-LINE-001",
        "QUEUE-WAIT-001",
        "SPOF-001",
    }


def test_flawed_findings_are_numbered_sequentially_in_display_order():
    findings, _, _ = _run(FLAWED_LOG, FLAWED_SCENARIO)
    assert [f.finding_id for f in findings] == [
        f"F-{index:03d}" for index in range(1, len(findings) + 1)
    ]


def test_findings_are_ordered_by_severity_then_node():
    findings, _, _ = _run(FLAWED_LOG, FLAWED_SCENARIO)
    severities = [f.severity for f in findings]
    assert severities == sorted(severities, key=lambda s: SEVERITY_ORDER[s])

    for severity in set(severities):
        nodes = [f.node for f in findings if f.severity == severity]
        assert nodes == sorted(nodes)


def test_findings_are_deduplicated_by_rule_and_node():
    findings, _, _ = _run(FLAWED_LOG, FLAWED_SCENARIO)
    keys = [(f.rule_id, f.node) for f in findings]
    assert len(keys) == len(set(keys))


def test_every_finding_is_evidence_backed_and_deterministic():
    findings, _, _ = _run(FLAWED_LOG, FLAWED_SCENARIO)
    for finding in findings:
        assert finding.deterministic is True
        assert finding.evidence
        assert finding.recommendation
        assert finding.observed
        assert finding.thresholds


def test_fixed_log_produces_no_findings():
    findings, _, _ = _run(FIXED_LOG, FIXED_SCENARIO)
    assert findings == []


def test_critical_finding_targets_brake_controller():
    findings, _, _ = _run(FLAWED_LOG, FLAWED_SCENARIO)
    critical = [f for f in findings if f.severity == "critical"]
    assert all(f.node == "brake_controller" for f in critical)
    assert {f.rule_id for f in critical} == {"CRITICAL-PATH-001", "BOTTLENECK-001"}


# --- second scenario: medical_pump -------------------------------------


def test_medical_pump_fires_all_five_rules():
    findings, _, _ = _run(PUMP_LOG, PUMP_SCENARIO)
    assert {f.rule_id for f in findings} == {
        "CRITICAL-PATH-001",
        "BOTTLENECK-001",
        "HEAD-OF-LINE-001",
        "QUEUE-WAIT-001",
        "SPOF-001",
    }


def test_medical_pump_flags_pump_controller_not_brake():
    """The engine is driven by the scenario, not by hardcoded service names."""
    findings, _, _ = _run(PUMP_LOG, PUMP_SCENARIO)
    assert findings
    assert all("brake" not in (f.node or "") for f in findings)
    assert any(f.node == "pump_controller" for f in findings)


def test_two_scenarios_produce_different_topologies():
    pump, _, _ = _run(PUMP_LOG, PUMP_SCENARIO)
    brake, _, _ = _run(FLAWED_LOG, FLAWED_SCENARIO)
    assert {f.node for f in pump} != {f.node for f in brake}
    assert "pump_controller" in {f.node for f in pump}
    assert "brake_controller" in {f.node for f in brake}


# --- third scenario: industrial_robot ----------------------------------


def test_industrial_robot_fires_all_five_rules():
    findings, _, _ = _run(ROBOT_LOG, ROBOT_SCENARIO)
    assert {f.rule_id for f in findings} == {
        "CRITICAL-PATH-001",
        "BOTTLENECK-001",
        "HEAD-OF-LINE-001",
        "QUEUE-WAIT-001",
        "SPOF-001",
    }


def test_industrial_robot_uses_a_tighter_deadline():
    """The same engine with a 1 ms deadline instead of 5 ms / 2 ms."""
    findings, _, _ = _run(ROBOT_LOG, ROBOT_SCENARIO)
    assert all(f.node == "motor_controller" for f in findings)
    assert any(f.rule_id == "CRITICAL-PATH-001" for f in findings)


def test_three_scenarios_share_no_hardcoded_service_names():
    brake, _, _ = _run(FLAWED_LOG, FLAWED_SCENARIO)
    pump, _, _ = _run(PUMP_LOG, PUMP_SCENARIO)
    robot, _, _ = _run(ROBOT_LOG, ROBOT_SCENARIO)
    brake_nodes = {f.node for f in brake}
    pump_nodes = {f.node for f in pump}
    robot_nodes = {f.node for f in robot}
    assert brake_nodes.isdisjoint(pump_nodes)
    assert pump_nodes.isdisjoint(robot_nodes)
    assert brake_nodes.isdisjoint(robot_nodes)
