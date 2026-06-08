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
from agent_debugger.core.loader import load_trace
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
def timeline(
    trace_file: str,
    verbose: bool,
    output_format: str,
    head: int | None,
    tail: int | None,
    filter_tool: str | None,
    output: str | None,
) -> None:
    """Display iteration-by-iteration timeline of a trace."""
    trace = load_trace(trace_file)
    analyzer = TraceAnalyzer(trace)

    if output_format == "json":
        if verbose:
            data = []
            for it in trace.iterations:
                data.append({
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
                })
        else:
            data = analyzer.timeline_summary()

        if filter_tool:
            data = [
                item
                for item in data
                if filter_tool in (item.get("tool_names") or [])  # type: ignore[operator]
            ]
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
def analyze(trace_file: str, max_context: int, output_format: str, output: str | None) -> None:
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
    for i, util in enumerate(utilization):
        bar_width = int(util * 40)
        bar_str = "█" * bar_width + "░" * (40 - bar_width)
        table.add_row(str(i), bar_str, f"{util * 100:.1f}%")
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

    console.print()


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
    start_server(trace, port=port, open_browser=not no_open)
