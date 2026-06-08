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
        trend: list[float] = []
        for it in self.trace.iterations:
            prompt = it.token_usage.prompt_tokens
            if prompt > 0:
                trend.append(prompt / max_context)
            else:
                # For zero-token iterations, carry forward the previous value
                trend.append(trend[-1] if trend else 0.0)
        return trend

    def context_growth_rate(self) -> list[float]:
        rates: list[float] = []
        iterations = self.trace.iterations
        if len(iterations) <= 1:
            return []
        prev_prompt = 0
        for it in iterations:
            curr_prompt = it.token_usage.prompt_tokens
            if curr_prompt > 0:
                rates.append(curr_prompt - prev_prompt)
                prev_prompt = curr_prompt
            else:
                rates.append(0)
        # Remove the first element since there's no "previous" for iteration 0
        return rates[1:] if len(rates) > 1 else rates

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

    def detect_anomalies(self) -> list[dict]:
        """Detect anomalous iterations using IQR-based outlier detection."""
        anomalies: list[dict] = []

        # Token spike detection using IQR
        tokens = [
            it.token_usage.total_tokens
            for it in self.trace.iterations
            if it.token_usage.total_tokens > 0
        ]
        if len(tokens) >= 4:
            sorted_tokens = sorted(tokens)
            q1 = sorted_tokens[len(sorted_tokens) // 4]
            q3 = sorted_tokens[3 * len(sorted_tokens) // 4]
            iqr = q3 - q1
            upper_threshold = q3 + 1.5 * iqr

            for it in self.trace.iterations:
                if it.token_usage.total_tokens > upper_threshold:
                    anomalies.append({
                        "iteration": it.index,
                        "type": "token_spike",
                        "value": it.token_usage.total_tokens,
                        "threshold": upper_threshold,
                    })

        # Error detection
        for it in self.trace.iterations:
            if it.error:
                anomalies.append({
                    "iteration": it.index,
                    "type": "error",
                    "message": it.error,
                })

        return anomalies
