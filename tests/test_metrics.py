"""Metric computation tests against the golden flawed log."""

import os

import pytest

from rtarch.graph import build_graph
from rtarch.metrics import compute_edge_metrics, compute_node_metrics, percentile
from rtarch.parser import parse_log
from rtarch.scenario import load_scenario

GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")
FLAWED_LOG = os.path.join(GOLDEN_DIR, "synthetic_flawed.log")
SCENARIO = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "scenarios", "brake_demo.json"
)


def _flawed():
    events = parse_log(FLAWED_LOG)
    scenario = load_scenario(SCENARIO)
    graph = build_graph(events)
    edges = compute_edge_metrics(events)
    nodes = compute_node_metrics(graph, edges, events, scenario)
    return events, graph, edges, nodes, scenario


def test_percentile_is_deterministic():
    assert percentile([], 95) == 0
    assert percentile([1, 2, 3, 4], 50) == 3
    assert percentile([1, 2, 3, 4], 95) == 4


def test_edge_metrics_carry_real_message_type():
    _, _, edges, _, _ = _flawed()
    edge = edges["perception_service->brake_controller"]
    assert edge.msg_type == "BRAKE_CMD"


def test_edge_metrics_perception_to_brake():
    _, _, edges, _, _ = _flawed()
    edge = edges["perception_service->brake_controller"]
    assert edge.count == 1
    assert edge.p95_queue_wait_ns == 2_000_000
    assert edge.p95_processing_ns == 7_000_000
    assert edge.p95_total_ns == 9_000_000


def test_edge_metrics_telemetry_queue_wait_dominates():
    _, _, edges, _, _ = _flawed()
    edge = edges["telemetry_client->brake_controller"]
    assert edge.p95_queue_wait_ns == 3_000_000
    assert edge.p95_processing_ns == 1_000_000
    assert edge.p95_total_ns == 4_000_000


def test_node_metrics_brake_controller():
    _, _, _, nodes, _ = _flawed()
    brake = nodes["brake_controller"]
    assert brake.in_degree == 3
    assert brake.out_degree == 0
    assert brake.p95_processing_ns == 7_000_000
    assert brake.total_messages_received == 3
    assert brake.on_critical_path is True
    assert brake.high_priority_blocked_count == 1
    assert brake.low_priority_work_ratio == pytest.approx(2 / 3, abs=1e-3)


def test_node_metrics_leaf_service():
    _, _, _, nodes, _ = _flawed()
    sensor = nodes["sensor_service"]
    assert sensor.in_degree == 0
    assert sensor.out_degree == 1
    assert sensor.p95_processing_ns == 0
    assert sensor.high_priority_blocked_count == 0
    assert sensor.low_priority_work_ratio == 0.0


def test_graph_topology():
    _, graph, _, _, _ = _flawed()
    assert graph.number_of_nodes() == 5
    assert graph.number_of_edges() == 4
    assert graph.has_edge("sensor_service", "perception_service")
    assert graph.has_edge("perception_service", "brake_controller")
