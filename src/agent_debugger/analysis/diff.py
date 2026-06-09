"""Trace comparison — diff two AgentTrace runs."""

from __future__ import annotations

from dataclasses import dataclass, field

from agent_debugger.analysis.analyzer import TraceAnalyzer
from agent_debugger.core.schema import AgentTrace


@dataclass
class TraceDiff:
    trace_a_name: str
    trace_b_name: str
    iterations_delta: int  # b - a
    tokens_delta: int  # b - a
    cost_delta: float  # b - a
    efficiency_delta: float  # b - a
    tools_only_in_a: list[str] = field(default_factory=list)
    tools_only_in_b: list[str] = field(default_factory=list)
    tool_count_changes: dict[str, tuple[int, int]] = field(default_factory=dict)
    summary: str = ""


def compare_traces(trace_a: AgentTrace, trace_b: AgentTrace) -> TraceDiff:
    """Compare two traces and produce a diff report."""
    analyzer_a = TraceAnalyzer(trace_a)
    analyzer_b = TraceAnalyzer(trace_b)

    iterations_a = analyzer_a.total_iterations
    iterations_b = analyzer_b.total_iterations
    iterations_delta = iterations_b - iterations_a

    tokens_a = analyzer_a.total_tokens
    tokens_b = analyzer_b.total_tokens
    tokens_delta = tokens_b - tokens_a

    cost_a = analyzer_a.cost_estimate()
    cost_b = analyzer_b.cost_estimate()
    cost_delta = cost_b["total_cost"] - cost_a["total_cost"]

    efficiency_a = analyzer_a.token_efficiency()
    efficiency_b = analyzer_b.token_efficiency()
    efficiency_delta = efficiency_b - efficiency_a

    tools_a = analyzer_a.tool_call_counts
    tools_b = analyzer_b.tool_call_counts

    all_tools = set(tools_a.keys()) | set(tools_b.keys())
    tools_only_in_a = sorted(set(tools_a.keys()) - set(tools_b.keys()))
    tools_only_in_b = sorted(set(tools_b.keys()) - set(tools_a.keys()))

    tool_count_changes: dict[str, tuple[int, int]] = {}
    for tool in sorted(all_tools):
        count_a = tools_a.get(tool, 0)
        count_b = tools_b.get(tool, 0)
        tool_count_changes[tool] = (count_a, count_b)

    # Generate summary
    summary_parts: list[str] = []

    if tokens_delta != 0:
        pct = (tokens_delta / tokens_a * 100) if tokens_a > 0 else 0
        direction = "more" if tokens_delta > 0 else "fewer"
        summary_parts.append(
            f"Trace B uses {abs(pct):.1f}% {direction} tokens "
            f"({tokens_delta:+,})"
        )

    if efficiency_delta != 0:
        eff_a_pct = efficiency_a * 100
        eff_b_pct = efficiency_b * 100
        if efficiency_delta > 0:
            summary_parts.append(
                f"but achieves higher efficiency "
                f"({eff_b_pct:.1f}% vs {eff_a_pct:.1f}%)"
            )
        else:
            summary_parts.append(
                f"and has lower efficiency "
                f"({eff_b_pct:.1f}% vs {eff_a_pct:.1f}%)"
            )

    if tools_only_in_b:
        new_tools = ", ".join(f"'{t}'" for t in tools_only_in_b)
        summary_parts.append(f"New tool(s) {new_tools} introduced")

    if tools_only_in_a:
        removed_tools = ", ".join(f"'{t}'" for t in tools_only_in_a)
        summary_parts.append(f"Tool(s) {removed_tools} no longer used")

    if tokens_delta > 0 and efficiency_delta > 0:
        summary_parts.append(
            "Consider whether the extra token cost is justified by the efficiency gain"
        )
    elif tokens_delta > 0 and efficiency_delta <= 0:
        summary_parts.append(
            "The extra token cost does not appear to improve efficiency"
        )

    summary = ". ".join(summary_parts) + "." if summary_parts else "Traces are identical."

    return TraceDiff(
        trace_a_name=trace_a.agent_name,
        trace_b_name=trace_b.agent_name,
        iterations_delta=iterations_delta,
        tokens_delta=tokens_delta,
        cost_delta=cost_delta,
        efficiency_delta=efficiency_delta,
        tools_only_in_a=tools_only_in_a,
        tools_only_in_b=tools_only_in_b,
        tool_count_changes=tool_count_changes,
        summary=summary,
    )
