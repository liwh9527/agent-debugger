from agent_debugger.analysis.analyzer import TraceAnalyzer
from agent_debugger.core.schema import AgentTrace, Iteration, TokenUsage, ToolCall


def test_total_tokens():
    trace = AgentTrace(
        iterations=[
            Iteration(index=0, token_usage=TokenUsage(total_tokens=100)),
            Iteration(index=1, token_usage=TokenUsage(total_tokens=200)),
        ],
    )
    analyzer = TraceAnalyzer(trace)
    assert analyzer.total_tokens == 300


def test_total_iterations():
    trace = AgentTrace(
        iterations=[Iteration(index=0), Iteration(index=1), Iteration(index=2)],
    )
    analyzer = TraceAnalyzer(trace)
    assert analyzer.total_iterations == 3


def test_tool_call_counts():
    trace = AgentTrace(
        iterations=[
            Iteration(
                index=0,
                tool_calls=[ToolCall(name="read_file"), ToolCall(name="edit_file")],
            ),
            Iteration(
                index=1,
                tool_calls=[ToolCall(name="read_file")],
            ),
        ],
    )
    analyzer = TraceAnalyzer(trace)
    assert analyzer.tool_call_counts == {"read_file": 2, "edit_file": 1}


def test_has_errors_false():
    trace = AgentTrace(iterations=[Iteration(index=0)])
    assert not TraceAnalyzer(trace).has_errors


def test_has_errors_true():
    trace = AgentTrace(
        iterations=[Iteration(index=0, error="Something went wrong")],
    )
    assert TraceAnalyzer(trace).has_errors


def test_empty_trace():
    trace = AgentTrace()
    analyzer = TraceAnalyzer(trace)
    assert analyzer.total_tokens == 0
    assert analyzer.total_iterations == 0
    assert analyzer.tool_call_counts == {}
    assert not analyzer.has_errors


def _make_trace():
    return AgentTrace(
        iterations=[
            Iteration(
                index=0,
                think="First iteration thinking about the problem at hand",
                token_usage=TokenUsage(
                    prompt_tokens=1000, completion_tokens=100, total_tokens=1100
                ),
                tool_calls=[ToolCall(name="read_file")],
                duration_ms=2000,
            ),
            Iteration(
                index=1,
                think="Second iteration applying the fix",
                token_usage=TokenUsage(
                    prompt_tokens=2000, completion_tokens=150, total_tokens=2150
                ),
                tool_calls=[ToolCall(name="edit_file"), ToolCall(name="read_file")],
                duration_ms=1500,
            ),
            Iteration(
                index=2,
                think="Third iteration verifying",
                token_usage=TokenUsage(
                    prompt_tokens=3000, completion_tokens=80, total_tokens=3080
                ),
                tool_calls=[ToolCall(name="read_file")],
                duration_ms=1200,
                error="Verification failed",
            ),
        ],
    )


def test_context_utilization_trend():
    analyzer = TraceAnalyzer(_make_trace())
    trend = analyzer.context_utilization_trend(max_context=100000)
    assert len(trend) == 3
    # Each value is per-iteration prompt_tokens / max_context (not cumulative)
    assert trend[0] == 1000 / 100000
    assert trend[1] == 2000 / 100000
    assert trend[2] == 3000 / 100000


def test_context_utilization_trend_default_max():
    analyzer = TraceAnalyzer(_make_trace())
    trend = analyzer.context_utilization_trend()
    assert trend[0] == 1000 / 200000


def test_context_utilization_trend_empty():
    analyzer = TraceAnalyzer(AgentTrace())
    assert analyzer.context_utilization_trend() == []


def test_context_utilization_trend_zero_tokens_carry_forward():
    trace = AgentTrace(
        iterations=[
            Iteration(
                index=0,
                token_usage=TokenUsage(
                    prompt_tokens=5000, completion_tokens=100, total_tokens=5100
                ),
            ),
            Iteration(
                index=1,
                token_usage=TokenUsage(
                    prompt_tokens=0, completion_tokens=0, total_tokens=0
                ),
            ),
            Iteration(
                index=2,
                token_usage=TokenUsage(
                    prompt_tokens=8000, completion_tokens=200, total_tokens=8200
                ),
            ),
        ],
    )
    analyzer = TraceAnalyzer(trace)
    trend = analyzer.context_utilization_trend(max_context=100000)
    assert len(trend) == 3
    assert trend[0] == 5000 / 100000
    # Zero-token iteration carries forward the previous value
    assert trend[1] == 5000 / 100000
    assert trend[2] == 8000 / 100000


def test_context_growth_rate():
    analyzer = TraceAnalyzer(_make_trace())
    rates = analyzer.context_growth_rate()
    # Growth rate uses prompt_tokens difference between iterations
    assert len(rates) == 2
    assert rates[0] == 2000 - 1000
    assert rates[1] == 3000 - 2000


def test_context_growth_rate_single_iteration():
    trace = AgentTrace(iterations=[Iteration(index=0)])
    assert TraceAnalyzer(trace).context_growth_rate() == []


def test_token_efficiency():
    analyzer = TraceAnalyzer(_make_trace())
    total_prompt = 1000 + 2000 + 3000
    total_completion = 100 + 150 + 80
    assert analyzer.token_efficiency() == total_completion / total_prompt


def test_token_efficiency_empty():
    assert TraceAnalyzer(AgentTrace()).token_efficiency() == 0.0


def test_timeline_summary():
    analyzer = TraceAnalyzer(_make_trace())
    summary = analyzer.timeline_summary()
    assert len(summary) == 3
    assert summary[0]["index"] == 0
    assert summary[0]["thinking_preview"] == "First iteration thinking about the problem at hand"
    assert summary[0]["tool_names"] == ["read_file"]
    assert summary[0]["tokens"] == 1100
    assert summary[0]["duration_ms"] == 2000
    assert summary[0]["has_error"] is False
    assert summary[2]["has_error"] is True
    assert summary[1]["tool_names"] == ["edit_file", "read_file"]


def test_timeline_summary_truncates_thinking():
    trace = AgentTrace(
        iterations=[
            Iteration(index=0, think="x" * 200),
        ],
    )
    summary = TraceAnalyzer(trace).timeline_summary()
    assert len(summary[0]["thinking_preview"]) == 80


def test_cost_estimate():
    analyzer = TraceAnalyzer(_make_trace())
    cost = analyzer.cost_estimate(input_price=3.0, output_price=15.0)
    total_prompt = 1000 + 2000 + 3000
    total_completion = 100 + 150 + 80
    assert cost["input_cost"] == (total_prompt / 1_000_000) * 3.0
    assert cost["output_cost"] == (total_completion / 1_000_000) * 15.0
    assert cost["total_cost"] == cost["input_cost"] + cost["output_cost"]


def test_cost_estimate_custom_prices():
    analyzer = TraceAnalyzer(_make_trace())
    cost = analyzer.cost_estimate(input_price=10.0, output_price=30.0)
    total_prompt = 6000
    total_completion = 330
    assert cost["input_cost"] == (total_prompt / 1_000_000) * 10.0
    assert cost["output_cost"] == (total_completion / 1_000_000) * 30.0


def test_detect_anomalies_no_anomalies():
    """Normal trace with similar token counts should have no token_spike anomalies."""
    trace = AgentTrace(
        iterations=[
            Iteration(index=0, token_usage=TokenUsage(total_tokens=100)),
            Iteration(index=1, token_usage=TokenUsage(total_tokens=110)),
            Iteration(index=2, token_usage=TokenUsage(total_tokens=105)),
            Iteration(index=3, token_usage=TokenUsage(total_tokens=95)),
        ],
    )
    analyzer = TraceAnalyzer(trace)
    anomalies = analyzer.detect_anomalies()
    assert anomalies == []


def test_detect_anomalies_token_spike():
    """One iteration with 10x tokens should be detected as a spike."""
    trace = AgentTrace(
        iterations=[
            Iteration(index=0, token_usage=TokenUsage(total_tokens=100)),
            Iteration(index=1, token_usage=TokenUsage(total_tokens=110)),
            Iteration(index=2, token_usage=TokenUsage(total_tokens=105)),
            Iteration(index=3, token_usage=TokenUsage(total_tokens=95)),
            Iteration(index=4, token_usage=TokenUsage(total_tokens=1000)),
        ],
    )
    analyzer = TraceAnalyzer(trace)
    anomalies = analyzer.detect_anomalies()
    spike_anomalies = [a for a in anomalies if a["type"] == "token_spike"]
    assert len(spike_anomalies) == 1
    assert spike_anomalies[0]["iteration"] == 4
    assert spike_anomalies[0]["value"] == 1000
    assert "threshold" in spike_anomalies[0]


def test_detect_anomalies_error():
    """Iterations with errors should be detected."""
    trace = AgentTrace(
        iterations=[
            Iteration(index=0, token_usage=TokenUsage(total_tokens=100)),
            Iteration(index=1, token_usage=TokenUsage(total_tokens=100), error="fail"),
        ],
    )
    analyzer = TraceAnalyzer(trace)
    anomalies = analyzer.detect_anomalies()
    error_anomalies = [a for a in anomalies if a["type"] == "error"]
    assert len(error_anomalies) == 1
    assert error_anomalies[0]["iteration"] == 1
    assert error_anomalies[0]["message"] == "fail"
