"""Generate the self-contained HTML analysis report.

The report is deterministic: it embeds a static SVG service-interaction graph,
the evidence-backed findings, and the full node/edge metric tables.  No
JavaScript is required to read it.
"""

import os
from datetime import datetime, timezone
from typing import Dict, List, Optional
from xml.sax.saxutils import escape

import networkx as nx
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import EdgeMetrics, Finding, NodeMetrics

_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

_SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def _severity_counts(findings: List[Finding]) -> Dict[str, int]:
    counts = {"critical": 0, "warning": 0, "info": 0}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    return counts


def _layers(graph) -> List[List[str]]:
    """Return graph nodes grouped into visual layers.

    Uses topological generations for DAGs (deterministic, left-to-right) and
    falls back to a single column for cyclic graphs.
    """
    try:
        return [sorted(generation) for generation in nx.topological_generations(graph)]
    except nx.NetworkXException:
        # Cyclic graph: fall back to a single deterministic column.
        return [sorted(graph.nodes())]


def _render_svg_graph(
    graph,
    node_metrics: Dict[str, NodeMetrics],
    findings: List[Finding],
) -> str:
    """Render the service interaction graph as a static, dependency-free SVG."""
    if graph is None or graph.number_of_nodes() == 0:
        return ""

    layers = _layers(graph)
    finding_nodes = {f.node for f in findings if f.node}
    critical_nodes = {n for n, m in node_metrics.items() if m.on_critical_path}

    node_w, node_h = 168, 46
    x_gap, y_gap = 240, 92
    margin = 48

    max_rows = max(len(layer) for layer in layers)
    plot_h = max_rows * y_gap
    width = margin * 2 + len(layers) * x_gap + node_w
    height = margin * 2 + plot_h + node_h

    coordinates = {}
    for layer_idx, layer in enumerate(layers):
        layer_h = len(layer) * y_gap
        y_start = margin + (plot_h - layer_h) / 2
        for row_idx, node in enumerate(layer):
            coordinates[node] = (
                margin + layer_idx * x_gap,
                y_start + row_idx * y_gap,
            )

    parts: List[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} '
        f'{height:.0f}" width="100%" role="img" aria-label="Service interaction graph">'
    )
    parts.append(
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="#718096"/></marker></defs>'
    )
    parts.append(
        f'<rect x="0" y="0" width="{width:.0f}" height="{height:.0f}" fill="#0d1117"/>'
    )

    for src, dst, data in graph.edges(data=True):
        if src not in coordinates or dst not in coordinates:
            continue
        x1, y1 = coordinates[src]
        x2, y2 = coordinates[dst]
        sx, sy = x1 + node_w, y1 + node_h / 2
        tx, ty = x2, y2 + node_h / 2

        parts.append(
            f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{tx:.1f}" y2="{ty:.1f}" '
            'stroke="#718096" stroke-width="1.5" marker-end="url(#arrow)"/>'
        )

        label = data.get("msg_type", "")
        if label:
            mx, my = (sx + tx) / 2, (sy + ty) / 2
            parts.append(
                f'<text x="{mx:.1f}" y="{my - 5:.1f}" text-anchor="middle" '
                f'class="edge-label">{escape(label)}</text>'
            )

    for node, (x, y) in coordinates.items():
        classes = "node"
        if node in critical_nodes:
            classes += " critical"
        if node in finding_nodes:
            classes += " has-finding"

        parts.append(f'<g class="{classes}" transform="translate({x:.1f},{y:.1f})">')
        parts.append(f'<rect width="{node_w}" height="{node_h}" rx="9" ry="9"/>')
        parts.append(
            f'<text x="{node_w / 2}" y="{node_h / 2}" text-anchor="middle" '
            f'dominant-baseline="central">{escape(node)}</text>'
        )
        parts.append("</g>")

    parts.append("</svg>")
    return "".join(parts)


def generate_report(
    findings: List[Finding],
    node_metrics: Dict[str, NodeMetrics],
    edge_metrics: Dict[str, EdgeMetrics],
    scenario: Dict,
    output_path: str,
    graph=None,
) -> str:
    """Render the HTML report to ``output_path`` and return the written path."""
    env = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "j2"]),
    )
    template = env.get_template("report.html.j2")

    svg_graph = _render_svg_graph(graph, node_metrics, findings)

    html = template.render(
        scenario=scenario,
        findings=findings,
        node_metrics=node_metrics,
        edge_metrics=edge_metrics,
        severity_counts=_severity_counts(findings),
        svg_graph=svg_graph,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    )

    absolute_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
    with open(absolute_path, "w", encoding="utf-8") as handle:
        handle.write(html)

    return absolute_path
