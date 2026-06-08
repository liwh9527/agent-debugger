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

    def context_utilization_trend(self, max_context: int = 200000) -> list[float]:
        cumulative = 0
        trend: list[float] = []
        for it in self.trace.iterations:
            cumulative += it.token_usage.prompt_tokens
            trend.append(cumulative / max_context)
        return trend

    def context_growth_rate(self) -> list[float]:
        rates: list[float] = []
        iterations = self.trace.iterations
        for i in range(1, len(iterations)):
            prev = iterations[i - 1].token_usage.total_tokens
            curr = iterations[i].token_usage.total_tokens
            rates.append(curr - prev)
        return rates

    def token_efficiency(self) -> float:
        total_prompt = sum(it.token_usage.prompt_tokens for it in self.trace.iterations)
        total_completion = sum(
            it.token_usage.completion_tokens for it in self.trace.iterations
        )
        if total_prompt == 0:
            return 0.0
        return total_completion / total_prompt

    def timeline_summary(self) -> list[dict]:
        summaries: list[dict] = []
        for it in self.trace.iterations:
            thinking_preview = (it.think or "")[:80]
            tool_names = [tc.name for tc in it.tool_calls]
            summaries.append({
                "index": it.index,
                "thinking_preview": thinking_preview,
                "tool_names": tool_names,
                "tokens": it.token_usage.total_tokens,
                "duration_ms": it.duration_ms,
                "has_error": it.error is not None,
            })
        return summaries

    def cost_estimate(
        self, input_price: float = 3.0, output_price: float = 15.0
    ) -> dict:
        total_prompt = sum(it.token_usage.prompt_tokens for it in self.trace.iterations)
        total_completion = sum(
            it.token_usage.completion_tokens for it in self.trace.iterations
        )
        input_cost = (total_prompt / 1_000_000) * input_price
        output_cost = (total_completion / 1_000_000) * output_price
        return {
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": input_cost + output_cost,
        }
