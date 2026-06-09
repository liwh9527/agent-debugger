"""CLI entry point for agent-debugger."""

from __future__ import annotations

import json

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from agent_debugger import __version__
from agent_debugger.analysis.analyzer import TraceAnalyzer
from agent_debugger.analysis.diagnostics import DiagnosticEngine
from agent_debugger.analysis.diff import compare_traces
from agent_debugger.core.loader import load_trace
from agent_debugger.core.scanner import scan_sessions, shorten_path
from agent_debugger.web.server import start_server

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="agent-debugger")
def main() -> None:
    """Interactive debugger for AI Agent loops."""


@main.command()
@click.argument("trace_file", type=click.Path(exists=True))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["rich", "json"]),
    default="rich",
    help="Output format.",
)
def info(trace_file: str, output_format: str) -> None:
    """Show summary info for a trace file."""
    trace = load_trace(trace_file)
    analyzer = TraceAnalyzer(trace)

    source = trace.metadata.get("source")
    source_label = {
        "claude_code": "Claude Code transcript",
        "langgraph": "LangGraph/LangSmith trace",
    }.get(str(source) if source else "", "native JSON")

    if output_format == "json":
        data = {
            "agent_name": trace.agent_name,
            "model": trace.model,
            "total_iterations": analyzer.total_iterations,
            "total_tokens": analyzer.total_tokens,
            "tool_call_counts": analyzer.tool_call_counts,
            "start_time": trace.start_time.isoformat() if trace.start_time else None,
            "end_time": trace.end_time.isoformat() if trace.end_time else None,
            "has_errors": analyzer.has_errors,
            "source": source_label,
        }
        click.echo(json.dumps(data, indent=2))
        return

    console.print(f"\n[bold]Source:[/bold] {source_label}")
    console.print(f"[bold]Agent:[/bold] {trace.agent_name}")
    console.print(f"[bold]Model:[/bold] {trace.model}")
    console.print(f"[bold]Iterations:[/bold] {analyzer.total_iterations}")
    console.print(f"[bold]Total Tokens:[/bold] {analyzer.total_tokens:,}")
    if trace.start_time:
        console.print(f"[bold]Start:[/bold] {trace.start_time:%Y-%m-%d %H:%M:%S}")
    if trace.end_time:
        console.print(f"[bold]End:[/bold] {trace.end_time:%Y-%m-%d %H:%M:%S}")
    if analyzer.has_errors:
        console.print("[bold red]Errors:[/bold red] Yes")

    tool_counts = analyzer.tool_call_counts
    if tool_counts:
        console.print()
        table = Table(title="Tool Calls")
        table.add_column("Tool", style="cyan")
        table.add_column("Count", justify="right", style="green")
        for name, count in sorted(tool_counts.items(), key=lambda x: -x[1]):
            table.add_row(name, str(count))
        console.print(table)

    console.print()


@main.command()
@click.argument("trace_file", type=click.Path(exists=True))
@click.option("--verbose", is_flag=True, help="Show full thinking and tool results.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["rich", "json"]),
    default="rich",
    help="Output format.",
)
@click.option("--head", type=int, default=None, help="Show only first N iterations.")
@click.option("--tail", type=int, default=None, help="Show only last N iterations.")
@click.option(
    "--filter",
    "filter_tool",
    type=str,
    default=None,
    help="Show only iterations that used this tool.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Write output to file instead of stdout.",
)
@click.option("--anomalies-only", is_flag=True, help="Show only anomalous iterations.")
def timeline(
    trace_file: str,
    verbose: bool,
    output_format: str,
    head: int | None,
    tail: int | None,
    filter_tool: str | None,
    output: str | None,
    anomalies_only: bool,
) -> None:
    """Display iteration-by-iteration timeline of a trace."""
    trace = load_trace(trace_file)
    analyzer = TraceAnalyzer(trace)

    # Determine anomaly indices if needed
    anomaly_indices: set[int] | None = None
    if anomalies_only:
        anomalies = analyzer.detect_anomalies()
        anomaly_indices = {a["iteration"] for a in anomalies}

    if output_format == "json":
        if verbose:
            data = []
            for it in trace.iterations:
                item: dict = {
                    "index": it.index,
                    "think": it.think,
                    "tool_calls": [
                        {
                            "name": tc.name,
                            "arguments": tc.arguments,
                            "result": tc.result,
                            "duration_ms": tc.duration_ms,
                        }
                        for tc in it.tool_calls
                    ],
                    "tokens": it.token_usage.total_tokens,
                    "duration_ms": it.duration_ms,
                    "error": it.error,
                }
                if anomaly_indices is not None:
                    item["is_anomaly"] = it.index in anomaly_indices
                data.append(item)
        else:
            data = analyzer.timeline_summary()
            if anomaly_indices is not None:
                for item in data:
                    item["is_anomaly"] = item["index"] in anomaly_indices

        if anomaly_indices is not None:
            data = [item for item in data if item.get("is_anomaly")]

        if filter_tool:
            def _has_tool(item: dict) -> bool:
                # Non-verbose format
                if "tool_names" in item:
                    return filter_tool in item["tool_names"]
                # Verbose format
                if "tool_calls" in item:
                    return filter_tool in [tc["name"] for tc in item["tool_calls"]]
                return False
            data = [item for item in data if _has_tool(item)]
        if head is not None:
            data = data[:head]
        elif tail is not None:
            data = data[-tail:]

        if output:
            with open(output, "w") as f:
                f.write(json.dumps(data, indent=2))
            click.echo(f"Written to {output}")
        else:
            click.echo(json.dumps(data, indent=2))
        return

    console.print(f"\n[bold]Timeline:[/bold] {trace.agent_name} ({trace.model})\n")

    iterations = list(trace.iterations)
    if anomaly_indices is not None:
        iterations = [it for it in iterations if it.index in anomaly_indices]
    if filter_tool:
        iterations = [
            it for it in iterations if filter_tool in [tc.name for tc in it.tool_calls]
        ]
    if head is not None:
        iterations = iterations[:head]
    elif tail is not None:
        iterations = iterations[-tail:]

    for it in iterations:
        border_style = "red" if it.error else "green"
        title = f"Iteration {it.index}"
        if it.duration_ms is not None:
            title += f" ({it.duration_ms}ms)"

        content_parts: list[str] = []

        if it.think:
            thinking_text = it.think if verbose else it.think[:80]
            if not verbose and len(it.think) > 80:
                thinking_text += "..."
            content_parts.append(f"[dim]Think:[/dim] {thinking_text}")

        if it.tool_calls:
            tool_lines: list[str] = []
            for tc in it.tool_calls:
                tool_line = f"  • {tc.name}"
                if verbose and tc.result:
                    result_str = (
                        tc.result
                        if isinstance(tc.result, str)
                        else json.dumps(tc.result)
                    )
                    tool_line += f" → {result_str}"
                tool_lines.append(tool_line)
            content_parts.append("[cyan]Tools:[/cyan]\n" + "\n".join(tool_lines))

        content_parts.append(
            f"[green]Tokens:[/green] {it.token_usage.total_tokens:,}"
        )

        if it.error:
            content_parts.append(f"[red]Error:[/red] {it.error}")

        panel = Panel(
            "\n".join(content_parts),
            title=title,
            border_style=border_style,
        )
        console.print(panel)

    console.print()


@main.command()
@click.argument("trace_file", type=click.Path(exists=True))
@click.option("--max-context", default=200000, help="Max context window size.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["rich", "json"]),
    default="rich",
    help="Output format.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Write output to file instead of stdout.",
)
@click.option(
    "--fail-if-cost-above",
    type=float,
    default=None,
    help="Exit with code 1 if estimated cost exceeds threshold.",
)
@click.option(
    "--fail-if-errors",
    is_flag=True,
    help="Exit with code 1 if any errors are detected.",
)
@click.option(
    "--fail-if-efficiency-below",
    type=float,
    default=None,
    help="Exit with code 1 if token efficiency is below threshold.",
)
def analyze(
    trace_file: str,
    max_context: int,
    output_format: str,
    output: str | None,
    fail_if_cost_above: float | None,
    fail_if_errors: bool,
    fail_if_efficiency_below: float | None,
) -> None:
    """Analyze context window usage, cost, and anomalies."""
    trace = load_trace(trace_file)
    analyzer = TraceAnalyzer(trace)

    utilization = analyzer.context_utilization_trend(max_context)
    growth = analyzer.context_growth_rate()
    efficiency = analyzer.token_efficiency()
    cost = analyzer.cost_estimate()

    anomalies = analyzer.detect_anomalies()

    if output_format == "json":
        data = {
            "context_utilization": utilization,
            "context_growth_rate": growth,
            "token_efficiency": efficiency,
            "cost_estimate": cost,
            "anomalies": anomalies,
        }
        if output:
            with open(output, "w") as f:
                f.write(json.dumps(data, indent=2))
            click.echo(f"Written to {output}")
        else:
            click.echo(json.dumps(data, indent=2))
        return

    console.print(f"\n[bold]Analysis:[/bold] {trace.agent_name} ({trace.model})\n")

    console.print("[bold]Context Utilization Trend:[/bold]")
    table = Table(show_header=True)
    table.add_column("Iter", justify="right", style="cyan", width=4)
    table.add_column("Utilization", width=50)
    table.add_column("%", justify="right", style="green", width=6)
    max_util_pct = max(utilization) * 100 if utilization else 100
    for i, util in enumerate(utilization):
        util_pct = util * 100
        bar_width = int((util_pct / max_util_pct) * 40) if max_util_pct > 0 else 0
        bar_str = "█" * bar_width + "░" * (40 - bar_width)
        table.add_row(str(i), bar_str, f"{util_pct:.1f}%")
    console.print(table)

    console.print(f"\n[bold]Token Efficiency:[/bold] {efficiency:.4f}")
    console.print(
        "  (completion_tokens / prompt_tokens = "
        "useful output per input token)\n"
    )

    console.print("[bold]Cost Estimate:[/bold]")
    console.print(f"  Input:  ${cost['input_cost']:.6f}")
    console.print(f"  Output: ${cost['output_cost']:.6f}")
    console.print(f"  Total:  ${cost['total_cost']:.6f}\n")

    if anomalies:
        console.print("[bold red]Anomalies Detected:[/bold red]")
        for anomaly in anomalies:
            if anomaly["type"] == "token_spike":
                val = anomaly["value"]
                thresh = anomaly["threshold"]
                console.print(
                    f"  ⚠ Iteration {anomaly['iteration']}: "
                    f"token spike ({val:.0f} tokens, threshold: {thresh:.0f})"
                )
            elif anomaly["type"] == "error":
                console.print(
                    f"  ✗ Iteration {anomaly['iteration']}: "
                    f"error — {anomaly['message']}"
                )
    else:
        console.print("[green]No anomalies detected.[/green]")

    # Summary line
    console.print()
    if anomalies:
        error_count = sum(1 for a in anomalies if a["type"] == "error")
        spike_count = sum(1 for a in anomalies if a["type"] == "token_spike")
        parts = []
        if spike_count:
            parts.append(f"{spike_count} token spikes")
        if error_count:
            parts.append(f"{error_count} errors")
        console.print(
            f"[bold yellow]Summary:[/bold yellow] {', '.join(parts)} detected "
            f"across {len(trace.iterations)} iterations."
        )
    else:
        max_util = max(utilization) * 100 if utilization else 0
        console.print(
            f"[bold green]Summary:[/bold green] Context healthy "
            f"(peak {max_util:.0f}%), no anomalies "
            f"across {len(trace.iterations)} iterations."
        )

    # Recommendations from DiagnosticEngine
    engine = DiagnosticEngine(trace, analyzer)
    report = engine.run()
    if report.recommendations:
        console.print("\n[bold]Recommendations:[/bold]")
        for i, rec in enumerate(report.recommendations, 1):
            savings = f" ({rec.estimated_savings})" if rec.estimated_savings else ""
            console.print(f"  {i}. {rec.message}{savings}")

    console.print()

    # CI threshold checks
    exit_code = 0
    if fail_if_cost_above is not None and cost["total_cost"] > fail_if_cost_above:
        console.print(
            f"[red]FAIL: Cost ${cost['total_cost']:.4f} exceeds "
            f"threshold ${fail_if_cost_above}[/red]"
        )
        exit_code = 1
    if fail_if_errors and analyzer.has_errors:
        console.print("[red]FAIL: Errors detected[/red]")
        exit_code = 1
    if fail_if_efficiency_below is not None and efficiency < fail_if_efficiency_below:
        console.print(
            f"[red]FAIL: Efficiency {efficiency:.4f} below "
            f"threshold {fail_if_efficiency_below}[/red]"
        )
        exit_code = 1
    if exit_code:
        raise SystemExit(exit_code)


@main.command()
@click.argument("trace_file", type=click.Path(exists=True))
@click.argument("iteration_index", type=int)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["rich", "json"]),
    default="rich",
    help="Output format.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Write output to file instead of stdout.",
)
def inspect(trace_file: str, iteration_index: int, output_format: str, output: str | None) -> None:
    """Inspect a single iteration in full detail."""
    trace = load_trace(trace_file)

    if not trace.iterations:
        click.echo("Error: Trace has no iterations.", err=True)
        raise SystemExit(1)

    matching = [it for it in trace.iterations if it.index == iteration_index]
    if not matching:
        console.print(
            f"[red]Error:[/red] Iteration {iteration_index} not found. "
            f"Valid range: 0-{len(trace.iterations) - 1}"
        )
        raise SystemExit(1)

    it = matching[0]

    if output_format == "json":
        data = {
            "index": it.index,
            "think": it.think,
            "tool_calls": [
                {
                    "name": tc.name,
                    "arguments": tc.arguments,
                    "result": tc.result,
                    "duration_ms": tc.duration_ms,
                }
                for tc in it.tool_calls
            ],
            "token_usage": {
                "prompt_tokens": it.token_usage.prompt_tokens,
                "completion_tokens": it.token_usage.completion_tokens,
                "total_tokens": it.token_usage.total_tokens,
            },
            "context_window": (
                {
                    "used_tokens": it.context_window.used_tokens,
                    "max_tokens": it.context_window.max_tokens,
                }
                if it.context_window
                else None
            ),
            "duration_ms": it.duration_ms,
            "error": it.error,
        }
        if output:
            with open(output, "w") as f:
                f.write(json.dumps(data, indent=2))
            click.echo(f"Written to {output}")
        else:
            click.echo(json.dumps(data, indent=2))
        return

    console.print(
        f"\n[bold]Iteration {it.index}[/bold] — {trace.agent_name} ({trace.model})\n"
    )

    if it.think:
        console.print(Panel(Markdown(it.think), title="Thinking", border_style="blue"))

    if it.tool_calls:
        for tc in it.tool_calls:
            args_json = json.dumps(tc.arguments, indent=2)
            args_syntax = Syntax(args_json, "json", theme="monokai")

            result_str = ""
            if tc.result is not None:
                result_str = (
                    tc.result if isinstance(tc.result, str) else json.dumps(tc.result)
                )

            tool_content = Text()
            tool_content.append("Arguments:\n", style="bold")
            console.print(
                Panel(args_syntax, title=f"Tool: {tc.name}", border_style="cyan")
            )
            if result_str:
                console.print(
                    Panel(result_str, title=f"Result: {tc.name}", border_style="dim")
                )
            if tc.duration_ms is not None:
                console.print(f"  [dim]Duration: {tc.duration_ms}ms[/dim]")

    console.print("\n[bold]Token Breakdown:[/bold]")
    console.print(f"  Prompt:     {it.token_usage.prompt_tokens:,}")
    console.print(f"  Completion: {it.token_usage.completion_tokens:,}")
    console.print(f"  Total:      {it.token_usage.total_tokens:,}")

    if it.context_window:
        console.print("\n[bold]Context Window:[/bold]")
        console.print(f"  Used:  {it.context_window.used_tokens:,}")
        if it.context_window.max_tokens:
            console.print(f"  Max:   {it.context_window.max_tokens:,}")

    if it.duration_ms is not None:
        console.print(f"\n[bold]Duration:[/bold] {it.duration_ms}ms")

    if it.error:
        console.print(f"\n[bold red]Error:[/bold red] {it.error}")

    console.print()


@main.command()
@click.argument("trace_file", type=click.Path(exists=True))
@click.option("--port", default=8080, help="Server port.")
@click.option("--no-open", is_flag=True, help="Don't open browser automatically.")
def serve(trace_file: str, port: int, no_open: bool) -> None:
    """Launch web UI to visualize a trace."""
    trace = load_trace(trace_file)
    console.print(f"\n[bold]Starting web UI[/bold] on http://localhost:{port}")
    console.print(f"[dim]Trace:[/dim] {trace.agent_name} ({trace.model})")
    console.print("[dim]Press Ctrl+C to stop.[/dim]\n")
    start_server(trace, port=port, open_browser=not no_open, trace_path=trace_file)


@main.command()
@click.argument("trace_file_a", type=click.Path(exists=True))
@click.argument("trace_file_b", type=click.Path(exists=True))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["rich", "json"]),
    default="rich",
    help="Output format.",
)
def diff(trace_file_a: str, trace_file_b: str, output_format: str) -> None:
    """Compare two trace files side by side."""
    trace_a = load_trace(trace_file_a)
    trace_b = load_trace(trace_file_b)
    result = compare_traces(trace_a, trace_b)

    analyzer_a = TraceAnalyzer(trace_a)
    analyzer_b = TraceAnalyzer(trace_b)

    if output_format == "json":
        from dataclasses import asdict

        click.echo(json.dumps(asdict(result), indent=2))
        return

    # Header
    console.print(
        f"\n[bold]Diff:[/bold] {result.trace_a_name} vs {result.trace_b_name}\n"
    )

    # Comparison table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Metric", style="cyan", width=20)
    table.add_column("Trace A", justify="right", width=16)
    table.add_column("Trace B", justify="right", width=16)
    table.add_column("Delta", justify="right", width=22)

    # Iterations
    table.add_row(
        "Iterations",
        str(analyzer_a.total_iterations),
        str(analyzer_b.total_iterations),
        _format_delta_int(result.iterations_delta),
    )

    # Total Tokens
    tokens_a = analyzer_a.total_tokens
    tokens_b = analyzer_b.total_tokens
    pct = (result.tokens_delta / tokens_a * 100) if tokens_a > 0 else 0
    delta_str = f"{result.tokens_delta:+,}"
    if pct != 0:
        delta_str += f" ({pct:+.1f}%)"
    color = "green" if result.tokens_delta <= 0 else "red"
    table.add_row(
        "Total Tokens",
        f"{tokens_a:,}",
        f"{tokens_b:,}",
        f"[{color}]{delta_str}[/{color}]",
    )

    # Cost
    cost_a = analyzer_a.cost_estimate()["total_cost"]
    cost_b = analyzer_b.cost_estimate()["total_cost"]
    cost_color = "green" if result.cost_delta <= 0 else "red"
    table.add_row(
        "Est. Cost",
        f"${cost_a:.4f}",
        f"${cost_b:.4f}",
        f"[{cost_color}]${result.cost_delta:+.4f}[/{cost_color}]",
    )

    # Efficiency
    eff_a = analyzer_a.token_efficiency()
    eff_b = analyzer_b.token_efficiency()
    eff_color = "green" if result.efficiency_delta >= 0 else "red"
    table.add_row(
        "Efficiency",
        f"{eff_a * 100:.1f}%",
        f"{eff_b * 100:.1f}%",
        f"[{eff_color}]{result.efficiency_delta * 100:+.1f}%[/{eff_color}]",
    )

    console.print(table)

    # Tool changes
    if result.tool_count_changes:
        console.print("\n[bold]Tool Changes:[/bold]")
        for tool, (count_a, count_b) in result.tool_count_changes.items():
            if count_a == 0:
                console.print(f"  {tool}: [green]— → {count_b} (new)[/green]")
            elif count_b == 0:
                console.print(f"  {tool}: [red]{count_a} → — (removed)[/red]")
            elif count_a == count_b:
                console.print(f"  {tool}: {count_a} → {count_b} (=)")
            else:
                delta = count_b - count_a
                console.print(f"  {tool}: {count_a} → {count_b} ({delta:+d})")

    # Summary
    console.print(f"\n[bold]Summary:[/bold] {result.summary}\n")


def _format_delta_int(delta: int) -> str:
    """Format an integer delta with color."""
    if delta == 0:
        return "0"
    return f"{delta:+d}"


@main.command()
@click.option(
    "--sort",
    type=click.Choice(["time", "tokens", "cost", "iterations"]),
    default="time",
    help="Sort sessions by.",
)
@click.option("--limit", "-n", type=int, default=10, help="Max sessions to show.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["rich", "json"]),
    default="rich",
)
def scan(sort: str, limit: int, output_format: str) -> None:
    """Scan for Claude Code sessions on this machine."""
    sessions = scan_sessions()

    # Sort
    sort_keys = {
        "time": lambda s: s.get("last_modified") or "",
        "tokens": lambda s: s.get("estimated_tokens", 0),
        "cost": lambda s: s.get("estimated_cost", 0.0),
        "iterations": lambda s: s.get("lines", 0),
    }
    sessions.sort(key=sort_keys[sort], reverse=True)

    # Limit
    sessions = sessions[:limit]

    if output_format == "json":
        click.echo(json.dumps(sessions, indent=2))
        return

    if not sessions:
        console.print("[yellow]No Claude Code sessions found.[/yellow]")
        return

    table = Table(title="Claude Code Sessions")
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("Path", style="cyan", max_width=40)
    table.add_column("Agent", style="blue")
    table.add_column("Model", style="magenta")
    table.add_column("Tokens", justify="right", style="green")
    table.add_column("Est. Cost", justify="right", style="yellow")
    table.add_column("Duration", justify="right")
    table.add_column("Last Modified", style="dim")

    for i, s in enumerate(sessions, 1):
        path_display = shorten_path(s["path"])
        tokens_display = f"{s['estimated_tokens']:,}"
        cost_display = f"${s['estimated_cost']:.4f}"

        # Duration
        duration_display = "—"
        if s.get("start_time") and s.get("end_time"):
            from datetime import datetime

            start = datetime.fromisoformat(s["start_time"])
            end = datetime.fromisoformat(s["end_time"])
            delta = end - start
            total_s = int(delta.total_seconds())
            if total_s >= 3600:
                duration_display = f"{total_s // 3600}h{(total_s % 3600) // 60}m"
            elif total_s >= 60:
                duration_display = f"{total_s // 60}m{total_s % 60}s"
            else:
                duration_display = f"{total_s}s"

        # Last modified
        mtime_display = "—"
        if s.get("last_modified"):
            from datetime import datetime

            mtime = datetime.fromisoformat(s["last_modified"])
            mtime_display = mtime.strftime("%Y-%m-%d %H:%M")

        table.add_row(
            str(i),
            path_display,
            s["agent_name"],
            s["model"],
            tokens_display,
            cost_display,
            duration_display,
            mtime_display,
        )

    console.print(table)
    console.print(f"\n[dim]Found {len(sessions)} session(s)[/dim]")


@main.command()
@click.argument("trace_file", type=click.Path(exists=True))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["rich", "json"]),
    default="rich",
)
def diagnose(trace_file: str, output_format: str) -> None:
    """Run diagnostic analysis and get actionable recommendations."""
    trace = load_trace(trace_file)
    analyzer = TraceAnalyzer(trace)
    engine = DiagnosticEngine(trace, analyzer)
    report = engine.run()

    if output_format == "json":
        from dataclasses import asdict

        data = {
            "findings": [asdict(f) for f in report.findings],
            "recommendations": [asdict(r) for r in report.recommendations],
            "summary": report.summary,
        }
        click.echo(json.dumps(data, indent=2))
        return

    console.print(f"\n[bold]Diagnostics:[/bold] {trace.agent_name} ({trace.model})\n")

    if not report.findings:
        console.print(
            Panel(
                "[green]No issues detected — session looks healthy.[/green]",
                title="Diagnostics",
                border_style="green",
            )
        )
    else:
        # Group findings by severity
        for severity, color in [("critical", "red"), ("warning", "yellow"), ("info", "blue")]:
            sev_findings = [f for f in report.findings if f.severity == severity]
            if not sev_findings:
                continue
            lines: list[str] = []
            for f in sev_findings:
                iter_label = f" (iter #{f.iteration})" if f.iteration is not None else ""
                lines.append(f"• [{color}]{f.message}[/{color}]{iter_label}")
            console.print(
                Panel(
                    "\n".join(lines),
                    title=f"{severity.upper()} ({len(sev_findings)})",
                    border_style=color,
                )
            )

    if report.recommendations:
        rec_lines: list[str] = []
        for i, rec in enumerate(report.recommendations, 1):
            savings = f" ({rec.estimated_savings})" if rec.estimated_savings else ""
            rec_lines.append(f"{i}. {rec.message}{savings}")
        console.print(
            Panel(
                "\n".join(rec_lines),
                title="Recommendations",
                border_style="green",
            )
        )

    console.print(f"\n[bold]Summary:[/bold] {report.summary}")
    console.print()
