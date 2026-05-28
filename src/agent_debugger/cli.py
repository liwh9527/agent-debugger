"""CLI entry point for agent-debugger."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from agent_debugger import __version__
from agent_debugger.loader import load_trace

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

    console.print(f"\n[bold]Agent:[/bold] {trace.agent_name}")
    console.print(f"[bold]Model:[/bold] {trace.model}")
    console.print(f"[bold]Iterations:[/bold] {trace.total_iterations}")
    console.print(f"[bold]Total Tokens:[/bold] {trace.total_tokens:,}")
    if trace.has_errors:
        console.print("[bold red]Errors:[/bold red] Yes")

    tool_counts = trace.tool_call_counts
    if tool_counts:
        console.print()
        table = Table(title="Tool Calls")
        table.add_column("Tool", style="cyan")
        table.add_column("Count", justify="right", style="green")
        for name, count in sorted(tool_counts.items(), key=lambda x: -x[1]):
            table.add_row(name, str(count))
        console.print(table)

    console.print()
