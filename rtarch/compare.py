"""Generate a side-by-side comparison report for two logs.

The comparison is the demo's money shot: the same tool, two architectures,
shown next to each other so the delta is visible at a glance. Every row is
derived from the deterministic metrics — nothing is hand-entered.
"""

import os
from typing import Dict, List

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .graph import build_graph
from .metrics import compute_edge_metrics, compute_node_metrics
from .models import EdgeMetrics, Finding, NodeMetrics
from .parser import parse_log
from .rules import run_rules

_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")


def analyze_log(log_path: str, scenario: Dict) -> Dict:
    """Run the full deterministic pipeline on one log."""
    events = parse_log(log_path)
    graph = build_graph(events)
    edges = compute_edge_metrics(events)
    nodes = compute_node_metrics(graph, edges, events, scenario)
    findings = run_rules(nodes, edges, scenario)

    return {
        "events": len(events),
        "graph": graph,
        "nodes": nodes,
        "edges": edges,
        "findings": findings,
        "critical": sum(1 for f in findings if f.severity == "critical"),
        "warning": sum(1 for f in findings if f.severity == "warning"),
        "info": sum(1 for f in findings if f.severity == "info"),
    }


def _finding_key(finding: Finding):
    return (finding.rule_id, finding.node)


def finding_diff(flawed: Dict, fixed: Dict) -> List[Dict]:
    """Which findings cleared, which are new, which remain."""
    before = {_finding_key(f): f for f in flawed["findings"]}
    after = {_finding_key(f): f for f in fixed["findings"]}

    rows: List[Dict] = []
    for key in sorted(set(before) | set(after)):
        old = before.get(key)
        new = after.get(key)
        if old and not new:
            change = "cleared"
        elif new and not old:
            change = "new"
        else:
            change = "still present"
        rows.append(
            {
                "rule_id": key[0],
                "node": key[1] or "-",
                "severity": (old or new).severity,
                "change": change,
            }
        )
    return rows


def node_metric_rows(flawed: Dict, fixed: Dict) -> List[Dict]:
    rows: List[Dict] = []
    for name in sorted(set(flawed["nodes"]) | set(fixed["nodes"])):
        before = flawed["nodes"].get(name)
        after = fixed["nodes"].get(name)
        rows.append(
            {
                "name": name,
                "before_p95_ms": _ms(before.p95_processing_ns if before else None),
                "after_p95_ms": _ms(after.p95_processing_ns if after else None),
                "before_in_degree": before.in_degree if before else None,
                "after_in_degree": after.in_degree if after else None,
            }
        )
    return rows


def edge_metric_rows(flawed: Dict, fixed: Dict) -> List[Dict]:
    rows: List[Dict] = []
    keys = sorted(set(flawed["edges"]) | set(fixed["edges"]))
    for key in keys:
        before: EdgeMetrics = flawed["edges"].get(key)
        after: EdgeMetrics = fixed["edges"].get(key)
        rows.append(
            {
                "edge": key,
                "before_qw_ms": _ms(before.p95_queue_wait_ns if before else None),
                "after_qw_ms": _ms(after.p95_queue_wait_ns if after else None),
                "before_proc_ms": _ms(before.p95_processing_ns if before else None),
                "after_proc_ms": _ms(after.p95_processing_ns if after else None),
            }
        )
    return rows


def _ms(value) -> str:
    return "-" if value is None else f"{value / 1e6:.3f}"


def _delta(before, after) -> str:
    if before is None or after is None:
        return "-"
    diff = after - before
    if abs(diff) < 1:                      # < 1 ns, treat as unchanged
        return "0"
    return f"{diff / 1e6:+.3f}"


def generate_comparison_report(
    flawed_log: str,
    fixed_log: str,
    scenario: Dict,
    output_path: str,
) -> str:
    """Render the side-by-side report and return the written path."""
    flawed = analyze_log(flawed_log, scenario)
    fixed = analyze_log(fixed_log, scenario)

    env = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "j2"]),
    )
    template = env.get_template("comparison_report.html.j2")

    html = template.render(
        scenario=scenario,
        flawed=flawed,
        fixed=fixed,
        finding_rows=finding_diff(flawed, fixed),
        node_rows=node_metric_rows(flawed, fixed),
        edge_rows=edge_metric_rows(flawed, fixed),
        delta=_delta,
    )

    absolute_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
    with open(absolute_path, "w", encoding="utf-8") as handle:
        handle.write(html)

    return absolute_path
