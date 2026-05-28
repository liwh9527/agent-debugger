"""CLI entry point for agent-debugger."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from agent_debugger import __version__
from agent_debugger.analysis.analyzer import TraceAnalyzer
from agent_debugger.core.loader import load_trace

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="agent-debugger")
def main() -> None:
    """Interactive debugger for AI Agent loops."""


@main.command()
@click.argument("trace_file", type=click.Path(exists=True))
def info(trace_file: str) -> None:
    """Show summary info for a trace file."""
    trace = load_trace(trace_file)
    analyzer = TraceAnalyzer(trace)

    source = trace.metadata.get("source")
    source_label = {"claude_code": "Claude Code transcript"}.get(
        source, "native JSON"
    )

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
