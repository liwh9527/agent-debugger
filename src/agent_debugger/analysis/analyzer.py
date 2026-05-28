"""Trace analysis — statistics and insights from AgentTrace data."""

from __future__ import annotations

from agent_debugger.core.schema import AgentTrace


class TraceAnalyzer:
    def __init__(self, trace: AgentTrace) -> None:
        self.trace = trace

    @property
    def total_tokens(self) -> int:
        return sum(it.token_usage.total_tokens for it in self.trace.iterations)

    @property
    def total_iterations(self) -> int:
        return len(self.trace.iterations)

    @property
    def tool_call_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for it in self.trace.iterations:
            for tc in it.tool_calls:
                counts[tc.name] = counts.get(tc.name, 0) + 1
        return counts

    @property
    def has_errors(self) -> bool:
        return any(it.error is not None for it in self.trace.iterations)
