"""RTArchitect command-line interface (Typer + Rich)."""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .graph import build_graph
from .metrics import compute_edge_metrics, compute_node_metrics
from .parser import parse_log_with_stats
from .report import generate_report
from .rules import run_rules
from .scenario import load_scenario

app = typer.Typer(
    help="RTArchitect — deterministic-first QNX IPC architectural analysis.",
    add_completion=False,
)
console = Console()


@app.callback()
def _main() -> None:
    """RTArchitect — deterministic-first QNX IPC architectural analysis.

    Commands:
      analyze   analyse one log and write an HTML report
      compare   put two logs side by side (flawed vs fixed)
    """


@app.command()
def analyze(
    log_file: str = typer.Argument(..., help="Path to a raw slog2 log file."),
    scenario_file: str = typer.Option(
        "scenarios/brake_demo.json",
        "--scenario",
        "-s",
        help="Scenario config JSON (thresholds, deadline, critical path).",
    ),
    output: str = typer.Option(
        "report.html",
        "--output",
        "-o",
        help="Output HTML report path.",
    ),
    ai: bool = typer.Option(
        False,
        "--ai",
        help=(
            "Add optional AI explanations. Requires API_BASE_URL and API_KEY. "
            "Falls back to deterministic templates on any failure."
        ),
    ),
) -> None:
    """Analyze a QNX IPC log and generate a deterministic HTML report."""
    console.print(
        Panel.fit(
            "[bold orange1]RTArchitect[/bold orange1] — deterministic-first QNX IPC analysis",
            border_style="orange1",
        )
    )

    try:
        scenario = load_scenario(scenario_file)
    except (OSError, ValueError) as exc:
        console.print(f"[red]Failed to load scenario:[/red] {exc}")
        raise typer.Exit(code=1)

    console.print(f"Scenario: [cyan]{scenario['scenario']}[/cyan]")
    console.print(f"Log file: [cyan]{log_file}[/cyan]")

    try:
        events, skipped = parse_log_with_stats(log_file)
    except OSError as exc:
        console.print(f"[red]Failed to read log file:[/red] {exc}")
        raise typer.Exit(code=1)

    console.print(
        f"Parsed [bold]{len(events)}[/bold] RTARCH events "
        f"([dim]{skipped} malformed skipped[/dim])"
    )

    if not events:
        console.print("[yellow]No RTARCH events found — nothing to analyze.[/yellow]")
        raise typer.Exit(code=0)

    graph = build_graph(events)
    console.print(
        f"Graph: [bold]{graph.number_of_nodes()}[/bold] services, "
        f"[bold]{graph.number_of_edges()}[/bold] IPC edges"
    )

    edge_metrics = compute_edge_metrics(events)
    node_metrics = compute_node_metrics(graph, edge_metrics, events, scenario)

    findings = run_rules(node_metrics, edge_metrics, scenario)

    counts = {"critical": 0, "warning": 0, "info": 0}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1

    console.print(
        f"Findings: [red]{counts['critical']} critical[/red], "
        f"[yellow]{counts['warning']} warning[/yellow], "
        f"[blue]{counts['info']} info[/blue]"
    )

    if findings:
        table = Table(show_header=True, header_style="bold", box=None)
        table.add_column("ID", style="dim")
        table.add_column("Severity")
        table.add_column("Rule")
        table.add_column("Node")
        table.add_column("Title")
        for finding in findings:
            table.add_row(
                finding.finding_id,
                finding.severity,
                finding.rule_id,
                finding.node or "-",
                finding.title,
            )
        console.print(table)
    else:
        console.print("[green]No deterministic findings — architecture is clean.[/green]")

    if ai:
        from .ai import explain_findings

        with console.status("[bold]Requesting AI explanations (5 s bound)...[/bold]"):
            findings = explain_findings(findings, scenario, enabled=True)
        console.print("[green]AI explanations added (deterministic fallback on failure).[/green]")
    else:
        console.print("[dim]AI disabled — deterministic findings only.[/dim]")

    written = generate_report(
        findings, node_metrics, edge_metrics, scenario, output, graph=graph
    )
    console.print(f"[bold green]Report written to:[/bold green] {written}")


@app.command()
def compare(
    flawed_log: str = typer.Argument(..., help="Log from the flawed architecture."),
    fixed_log: str = typer.Argument(..., help="Log from the fixed architecture."),
    scenario_file: str = typer.Option(
        "scenarios/brake_demo.json",
        "--scenario",
        "-s",
        help="Scenario config JSON (thresholds, deadline, critical path).",
    ),
    output: str = typer.Option(
        "comparison.html",
        "--output",
        "-o",
        help="Output HTML comparison path.",
    ),
) -> None:
    """Compare two logs side by side: flawed architecture vs fixed."""
    console.print(
        Panel.fit(
            "[bold orange1]RTArchitect[/bold orange1] — architecture comparison",
            border_style="orange1",
        )
    )

    try:
        scenario = load_scenario(scenario_file)
    except (OSError, ValueError) as exc:
        console.print(f"[red]Failed to load scenario:[/red] {exc}")
        raise typer.Exit(code=1)

    console.print(f"Scenario: [cyan]{scenario['scenario']}[/cyan]")
    console.print(f"Flawed:   [red]{flawed_log}[/red]")
    console.print(f"Fixed:    [green]{fixed_log}[/green]")

    try:
        from .compare import analyze_log, generate_comparison_report

        flawed = analyze_log(flawed_log, scenario)
        fixed = analyze_log(fixed_log, scenario)
    except OSError as exc:
        console.print(f"[red]Failed to read a log file:[/red] {exc}")
        raise typer.Exit(code=1)

    console.print(
        f"Findings: [red]{len(flawed['findings'])} before[/red] "
        f"({flawed['critical']} critical) -> "
        f"[green]{len(fixed['findings'])} after[/green] "
        f"({fixed['critical']} critical)"
    )

    cleared = len(flawed["findings"]) - len(fixed["findings"])
    if cleared > 0:
        console.print(f"[green]{cleared} finding(s) cleared by the fix.[/green]")

    written = generate_comparison_report(flawed_log, fixed_log, scenario, output)
    console.print(f"[bold green]Comparison written to:[/bold green] {written}")


if __name__ == "__main__":
    app()
